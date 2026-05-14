# leads/views.py
from leads.tasks import audit_leads_batch
from django.core.cache import cache
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from freelanceleads.quota_guard import check, increment
from services.serp import search_businesses
from services.scoring import calculate_score
from .models import Lead, SavedLead, SearchCache
from .serializers import (
    LeadSerializer,
    LeadSearchSerializer,
    SavedLeadSerializer,
    SaveLeadSerializer,
)


def _make_cache_key(niche: str, city: str, country: str) -> str:
    """Generates normalized cache key."""
    parts = filter(None, [niche, city, country])
    return 'leads:' + ':'.join(parts).replace(' ', '_')


def _get_leads_from_db(niche: str, city: str, country: str):
    """
    Fetches leads from DB.
    Searches both city level and state level for geographic hierarchy.
    """
    qs = Lead.objects.filter(niche=niche)

    if country:
        qs = qs.filter(country__iexact=country)

    qs = qs.filter(
        Q(city__iexact=city) | Q(state__iexact=city)
    )

    return qs.order_by('-opportunity_score')


def _save_leads_to_db(businesses: list[dict], niche: str, city: str, country: str, refresh: bool = False) -> list:
    leads = []

    for b in businesses:
        if not b.get('place_id'):
            continue

        defaults = {
            'name'        : b.get('name', ''),
            'niche'       : niche,
            'city'        : b.get('city', city),
            'state'       : b.get('state', ''),
            'country'     : b.get('country', country),
            'address'     : b.get('address', ''),
            'phone'       : b.get('phone', ''),
            'website'     : b.get('website', ''),
            'rating'      : b.get('rating'),
            'review_count': b.get('review_count', 0),
            'gbp_status'  : b.get('gbp_status', ''),
            'has_website' : b.get('has_website', False),
            'latitude'    : b.get('latitude'),
            'longitude'   : b.get('longitude'),
            'opportunity_score': calculate_score(
                has_website     = b.get('has_website', False),
                has_ssl         = False,
                pagespeed_score = None,
                rating          = b.get('rating'),
                review_count    = b.get('review_count', 0),
                has_meta_title  = False,
                has_meta_desc   = False,
                has_schema      = False,
                has_social      = False,
            ),
        }

        if refresh:
            # Update existing record with fresh data
            lead, _ = Lead.objects.update_or_create(
                place_id = b['place_id'],
                defaults = defaults
            )
        else:
            # Only create if not already present
            lead, _ = Lead.objects.get_or_create(
                place_id = b['place_id'],
                defaults = defaults
            )

        leads.append(lead)

    return leads
# ─────────────────────────────────────────────────────────────
#  Lead Search View
# ─────────────────────────────────────────────────────────────

class LeadSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LeadSearchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        niche     = serializer.validated_data['niche']
        city      = serializer.validated_data['city']
        country   = serializer.validated_data['country']
        refresh   = serializer.validated_data.get('refresh', False)
        load_more = serializer.validated_data.get('load_more', False)

        # refresh and load_more are mutually exclusive — refresh takes priority
        if refresh and load_more:
            load_more = False

        # ── Step 1: Quota check ───────────────────────────────────────────────
        check(request.user, 'search')

        # Block free users from refresh or load_more — both cost API credits
        if (refresh or load_more) and request.user.subscription.plan.name == 'free':
            return Response(
                {'error': 'Refresh and Load More are Pro features. Please upgrade.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        cache_key    = _make_cache_key(niche, city, country)
        source       = None
        leads        = None                          # always initialised — prevents UnboundLocalError
        next_start   = 0                             # safe default
        search_cache = SearchCache.objects.filter(cache_key=cache_key).first()

        # ── Step 2: refresh — re-fetch page 0 and overwrite existing data ─────
        if refresh:
            next_start = 0
            # Clear Redis so the response isn't served from stale cache
            cache.delete(cache_key)

        # ── Step 3: load_more — fetch the next page of results ───────────────
        elif load_more:
            if not search_cache:
                return Response(
                    {'error': 'No previous search found. Please search first.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if search_cache.is_exhausted:
                return Response(
                    {'error': 'No more results available for this search.'},
                    status=status.HTTP_200_OK,
                )

            next_start = search_cache.next_start

        # ── Step 4: normal request — check cache layers before hitting the API ─
        else:
            # Layer 1: Redis (fastest)
            cached_ids = cache.get(cache_key)
            if cached_ids:
                source = 'redis_cache'
                leads  = Lead.objects.filter(id__in=cached_ids).order_by('-opportunity_score')

            else:
                # Layer 2: Database
                db_leads = _get_leads_from_db(niche, city, country)
                if db_leads.exists():
                    source = 'db_cache'
                    leads  = db_leads
                    # Warm Redis for subsequent requests
                    cache.set(
                        cache_key,
                        list(leads.values_list('id', flat=True)),
                        timeout=60 * 60 * 24 * 3,
                    )
                # else: source stays None → falls through to API call below

        # ── Step 5: API call — runs on refresh, load_more, or full cache miss ──
        if refresh or load_more or source is None:
            try:
                businesses = search_businesses(niche, city, country, start=next_start)
            except RuntimeError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

            if not businesses:
                if load_more:
                    # Mark as exhausted so future calls don't hit the API needlessly
                    SearchCache.objects.filter(cache_key=cache_key).update(is_exhausted=True)
                return Response(
                    {'results': [], 'source': 'api', 'count': 0},
                    status=status.HTTP_200_OK,
                )

            new_leads = _save_leads_to_db(businesses, niche, city, country, refresh=refresh)
            source    = 'google_api'

            # Accumulate total only for load_more; refresh and first search reset it
            previous_total = search_cache.total_results if (search_cache and load_more) else 0
            new_total      = previous_total + len(new_leads)

            # next_start advances by 20 after every successful API page
            # For refresh: next page after the refreshed data starts at 20
            search_cache, _ = SearchCache.objects.update_or_create(
                cache_key=cache_key,
                defaults={
                    'niche'        : niche,
                    'city'         : city,
                    'country'      : country,
                    'total_results': new_total,
                    'next_start'   : next_start + 20,
                    'is_exhausted' : len(businesses) < 20,
                },
            )

            # Update Redis:
            #   load_more → merge new IDs with existing ones
            #   refresh / first search → replace entirely
            if load_more:
                existing_ids = cache.get(cache_key) or []
                cache.set(cache_key, existing_ids + [l.id for l in new_leads], timeout=60 * 60 * 24 * 3)
                # Return the full cumulative set, not just the new page
                all_ids = cache.get(cache_key)
                leads   = Lead.objects.filter(id__in=all_ids).order_by('-opportunity_score')
            else:
                cache.set(cache_key, [l.id for l in new_leads], timeout=60 * 60 * 24 * 3)
                leads = new_leads

                # Fire async audit for new leads
                from leads.tasks import audit_leads_batch
                audit_leads_batch.delay([l.id for l in new_leads])

        # ── Step 6: Increment quota ───────────────────────────────────────────
        increment(request.user, 'search')

        # ── Step 7: Serialize and return ─────────────────────────────────────
        lead_serializer = LeadSerializer(leads, many=True, context={'request': request})
        return Response(
            {
                'results'      : lead_serializer.data,
                'source'       : source,
                'count'        : len(lead_serializer.data),
                'total_results': search_cache.total_results if search_cache else len(lead_serializer.data),
                'is_exhausted' : search_cache.is_exhausted  if search_cache else False,
                'next_start'   : search_cache.next_start    if search_cache else 20,
            },
            status=status.HTTP_200_OK,
        )

# ─────────────────────────────────────────────────────────────
#  Save / Unsave Lead
# ─────────────────────────────────────────────────────────────

class SaveLeadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, lead_id):
        """Save a lead."""
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({'error': 'Lead not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SaveLeadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        saved, created = SavedLead.objects.get_or_create(
            user = request.user,
            lead = lead,
            defaults = {'notes': serializer.validated_data['notes']}
        )

        if not created:
            return Response({'message': 'Lead already saved.'}, status=status.HTTP_200_OK)

        return Response({'message': 'Lead saved successfully.'}, status=status.HTTP_201_CREATED)

    def delete(self, request, lead_id):
        """Unsave a lead."""
        deleted, _ = SavedLead.objects.filter(
            user    = request.user,
            lead_id = lead_id,
        ).delete()

        if not deleted:
            return Response({'error': 'Saved lead not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'message': 'Lead removed from saved.'}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────
#  Saved Leads List
# ─────────────────────────────────────────────────────────────

class SavedLeadsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        saved = SavedLead.objects.filter(
            user = request.user
        ).select_related('lead').order_by('-saved_at')

        serializer = SavedLeadSerializer(saved, many=True, context={'request': request})
        return Response({
            'results': serializer.data,
            'count'  : saved.count(),
        }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────
#  Lead Detail
# ─────────────────────────────────────────────────────────────

class LeadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({'error': 'Lead not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = LeadSerializer(lead, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)