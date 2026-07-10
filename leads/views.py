# leads/views.py

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from freelanceleads.quota_guard import check, increment, get_remaining_quota
from services.serp import search_businesses
from services.scoring import calculate_score
from leads.tasks import audit_leads_batch
from .models import Lead, SavedLead, SearchCache
from .serializers import (
    LeadSerializer,
    LeadSearchSerializer,
    SavedLeadSerializer,
    SaveLeadSerializer,
)


# ═══════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════

REDIS_CACHE_TTL = 60 * 60 * 24 * 3  # 3 days
SERP_PAGE_SIZE = 20

User = get_user_model()


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════


def _make_cache_key(niche: str, city: str, country: str) -> str:
    parts = filter(None, [niche, city, country])
    return "leads:" + ":".join(parts).replace(" ", "_")


def _get_search_cache(cache_key: str) -> SearchCache | None:
    return SearchCache.objects.filter(cache_key=cache_key).only("id", "next_start", "is_exhausted", "total_results").first()


def _leads_by_ids(lead_ids: list[int]) -> list[Lead]:
    if not lead_ids:
        return []
    # Use .only() to skip unused heavy fields and avoid loading full model
    return list(
        Lead.objects.filter(id__in=lead_ids).order_by("-opportunity_score")
    )


def _get_saved_lead_ids(user, lead_ids: list[int]) -> set[int]:
    if not lead_ids:
        return set()
    return set(
        SavedLead.objects.filter(user=user, lead_id__in=lead_ids).values_list(
            "lead_id", flat=True
        )
    )


def _serializer_context(request, leads: list[Lead]) -> dict:
    lead_ids = [lead.id for lead in leads]
    return {
        "request": request,
        "saved_lead_ids": _get_saved_lead_ids(request.user, lead_ids),
    }


def _query_leads_from_db(niche: str, city: str, country: str):
    """
    Cache lookup — exact city match only.
    State-level matching is intentionally excluded here to prevent
    cross-city cache pollution and unnecessary API calls.
    """
    qs = Lead.objects.filter(niche=niche, city__iexact=city)
    if country:
        qs = qs.filter(country__iexact=country)
    return qs.order_by("-opportunity_score")


def _query_leads_with_region(niche: str, city: str, country: str):
    """
    User-facing query — includes state-level matches for geographic hierarchy.
    Example: Albany leads appear in New York search results.
    Used only when returning final results to user, NOT for cache decisions.
    """
    qs = Lead.objects.filter(niche=niche).filter(
        Q(city__iexact=city) | Q(state__iexact=city)
    )
    if country:
        qs = qs.filter(country__iexact=country)
    return qs.order_by("-opportunity_score")


def _save_businesses_as_leads(
    businesses: list[dict],
    niche: str,
    city: str,
    country: str,
    refresh: bool = False,
) -> list:
    """
    Bulk-save businesses as Lead records.
    Uses bulk operations to minimize DB round-trips:
    - Single query to find existing leads by place_id
    - Bulk create for new leads
    - Bulk update for refresh
    """
    if not businesses:
        return []

    # Filter out businesses without place_id
    valid_businesses = [b for b in businesses if b.get("place_id")]
    if not valid_businesses:
        return []

    # Single query: fetch all existing leads by place_id
    place_ids = [b["place_id"] for b in valid_businesses]
    existing_leads = {
        lead.place_id: lead
        for lead in Lead.objects.filter(place_id__in=place_ids)
    }

    new_leads_to_create = []
    leads_to_update = []
    result_leads = []

    for biz in valid_businesses:
        pid = biz["place_id"]
        defaults = {
            "name": biz.get("name", ""),
            "niche": niche,
            "city": biz.get("city", city),
            "state": biz.get("state", ""),
            "country": biz.get("country", country),
            "address": biz.get("address", ""),
            "phone": biz.get("phone", ""),
            "website": biz.get("website", ""),
            "rating": biz.get("rating"),
            "review_count": biz.get("review_count", 0),
            "gbp_status": biz.get("gbp_status", ""),
            "has_website": biz.get("has_website", False),
            "latitude": biz.get("latitude"),
            "longitude": biz.get("longitude"),
            "opportunity_score": calculate_score(
                has_website=biz.get("has_website", False),
                has_ssl=False,
                pagespeed_score=None,
                rating=biz.get("rating"),
                review_count=biz.get("review_count", 0),
                has_meta_title=False,
                has_meta_desc=False,
                has_schema=False,
                has_social=False,
            ),
        }

        if pid in existing_leads:
            lead = existing_leads[pid]
            if refresh:
                # Update existing lead — collect for bulk_update
                defaults.update({
                    "audit_done": False,
                    "has_ssl": False,
                    "has_meta_title": False,
                    "has_meta_desc": False,
                    "has_schema": False,
                    "has_social": False,
                })
                for key, val in defaults.items():
                    setattr(lead, key, val)
                leads_to_update.append(lead)
            result_leads.append(lead)
        else:
            # Build new Lead object for bulk_create
            new_lead = Lead(place_id=pid, **defaults)
            new_leads_to_create.append(new_lead)

    # Bulk update all refreshed leads in one query
    if leads_to_update:
        update_fields = list(defaults.keys())
        Lead.objects.bulk_update(leads_to_update, update_fields)

    # Bulk create all new leads in one query
    if new_leads_to_create:
        created_leads = Lead.objects.bulk_create(
            new_leads_to_create,
            ignore_conflicts=True,
        )
        # bulk_create with ignore_conflicts doesn't set IDs on all DBs,
        # so re-fetch the created leads to get their IDs
        new_place_ids = [l.place_id for l in new_leads_to_create]
        created_with_ids = Lead.objects.filter(place_id__in=new_place_ids)
        result_leads.extend(list(created_with_ids))

    return result_leads


def _fetch_leads_for_city(
    niche: str,
    city: str,
    country: str,
    refresh: bool,
    load_more: bool,
) -> tuple[list, str | None, SearchCache | None, list]:
    cache_key = _make_cache_key(niche, city, country)
    search_cache = None
    next_start = 0

    if refresh:
        cache.delete(cache_key)
        search_cache = _get_search_cache(cache_key)
        next_start = 0

    elif load_more:
        search_cache = _get_search_cache(cache_key)
        if not search_cache:
            return None, None, None, []
        if search_cache.is_exhausted:
            return [], "exhausted", search_cache, []
        next_start = search_cache.next_start

    else:
        # Layer 1 — Redis (fast path: no DB query at all)
        cached_lead_ids = cache.get(cache_key)
        if cached_lead_ids:
            return _leads_by_ids(cached_lead_ids), "redis_cache", None, []

        # Layer 2 — DB (exact city match only)
        # Use a single query: get IDs directly. If IDs exist, cache them.
        lead_ids = list(
            Lead.objects.filter(niche=niche, city__iexact=city)
            .filter(**({'country__iexact': country} if country else {}))
            .order_by("-opportunity_score")
            .values_list("id", flat=True)
        )

        if lead_ids:
            cache.set(cache_key, lead_ids, timeout=REDIS_CACHE_TTL)
            # Return region-aware results to user (includes state matches)
            region_leads = list(_query_leads_with_region(niche, city, country))
            search_cache = _get_search_cache(cache_key)
            return region_leads, "db_cache", search_cache, []

        search_cache = _get_search_cache(cache_key)

    # Layer 3 — SerpAPI
    try:
        businesses = search_businesses(niche, city, country, start=next_start)
    except RuntimeError:
        return [], "api_error", search_cache, []

    if not businesses:
        if load_more and search_cache:
            SearchCache.objects.filter(cache_key=cache_key).update(is_exhausted=True)
        return [], "google_api", search_cache, []

    new_leads = _save_businesses_as_leads(
        businesses, niche, city, country, refresh=refresh
    )
    previous_total = search_cache.total_results if (search_cache and load_more) else 0

    search_cache, _ = SearchCache.objects.update_or_create(
        cache_key=cache_key,
        defaults={
            "niche": niche,
            "city": city,
            "country": country,
            "total_results": previous_total + len(new_leads),
            "next_start": next_start + SERP_PAGE_SIZE,
            "is_exhausted": len(businesses) < SERP_PAGE_SIZE,
        },
    )

    if load_more:
        existing_ids = cache.get(cache_key) or []
        all_ids = existing_ids + [lead.id for lead in new_leads]
        cache.set(cache_key, all_ids, timeout=REDIS_CACHE_TTL)
        leads = _leads_by_ids(all_ids)
    else:
        new_ids = [lead.id for lead in new_leads]
        cache.set(cache_key, new_ids, timeout=REDIS_CACHE_TTL)
        leads = new_leads

    if new_leads:
        audit_leads_batch.delay([lead.id for lead in new_leads])

    return list(leads), "google_api", search_cache, new_leads


def _deduplicate_leads(leads: list) -> list:
    seen = set()
    unique = []
    for lead in leads:
        if lead.id not in seen:
            seen.add(lead.id)
            unique.append(lead)
    unique.sort(key=lambda lead: lead.opportunity_score, reverse=True)
    return unique


def _determine_aggregate_source(sources: set) -> str:
    if len(sources) == 1:
        return next(iter(sources))
    elif sources:
        return "mixed"
    return "none"


# ═══════════════════════════════════════════════════════════════
#  VIEWS
# ═══════════════════════════════════════════════════════════════


class LeadSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LeadSearchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        niche = serializer.validated_data["niche"]
        cities = serializer.validated_data["cities"]
        country = serializer.validated_data["country"]
        refresh = serializer.validated_data.get("refresh", False)
        load_more = serializer.validated_data.get("load_more", False)

        if refresh and load_more:
            load_more = False

        # Single eager-loaded query for user + subscription + plan
        user = User.objects.select_related("subscription__plan").get(
            pk=request.user.pk
        )
        request.user = user

        subscription = getattr(user, "subscription", None)
        if not subscription:
            return Response(
                {"error": "No subscription found."},
                status=status.HTTP_403_FORBIDDEN,
            )

        is_free_user = subscription.plan.name == "free"

        if refresh and is_free_user:
            return Response(
                {"error": "Refresh is a Pro feature. Please upgrade."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if load_more and is_free_user:
            return Response(
                {"error": "Load More is a Pro feature. Please upgrade."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Use the centralized quota function (avoids duplicate _get_plan_limit + _get_counter calls)
        remaining_credits = get_remaining_quota(user, "search")

        if remaining_credits == 0:
            return Response(
                {
                    "error": "Quota limit reached.",
                    "upgrade_url": "/api/billing/checkout/",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        cities_to_search = cities[:remaining_credits]
        cities_skipped = list(cities[remaining_credits:])

        all_leads = []
        sources_seen = set()
        cities_searched = []
        api_calls_made = 0

        for city in cities_to_search:
            leads, source, _search_cache, _new_leads = _fetch_leads_for_city(
                niche,
                city,
                country,
                refresh,
                load_more,
            )

            if source is None:
                cities_skipped.insert(0, city)
                continue

            increment(user, "search")
            cities_searched.append(city)

            if source == "google_api":
                api_calls_made += 1
            if source:
                sources_seen.add(source)
            if leads:
                all_leads.extend(leads)

        unique_leads = _deduplicate_leads(all_leads)
        lead_serializer = LeadSerializer(
            unique_leads,
            many=True,
            context=_serializer_context(request, unique_leads),
        )

        response_data = {
            "results": lead_serializer.data,
            "count": len(lead_serializer.data),
            "source": _determine_aggregate_source(sources_seen),
            "cities_searched": cities_searched,
            "cities_skipped": cities_skipped,
            "api_calls_made": api_calls_made,
        }

        if cities_skipped:
            response_data["skipped_reason"] = "Insufficient search credits"

        return Response(response_data, status=status.HTTP_200_OK)


class LeadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response(
                {"error": "Lead not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = LeadSerializer(
            lead,
            context=_serializer_context(request, [lead]),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class SaveLeadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response(
                {"error": "Lead not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Eager load subscription + plan to avoid 2 lazy-load queries
        user = User.objects.select_related("subscription__plan").get(
            pk=request.user.pk
        )
        subscription = getattr(user, "subscription", None)
        if subscription:
            limit = subscription.plan.saved_leads_limit
            if limit != -1:
                current_count = SavedLead.objects.filter(user=request.user).count()
                if current_count >= limit:
                    return Response(
                        {
                            "error": "Saved leads limit reached.",
                            "upgrade_url": "/api/billing/checkout/",
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

        serializer = SaveLeadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        _saved, created = SavedLead.objects.get_or_create(
            user=request.user,
            lead=lead,
            defaults={"notes": serializer.validated_data["notes"]},
        )

        if not created:
            return Response(
                {"message": "Lead already saved."}, status=status.HTTP_200_OK
            )

        return Response(
            {"message": "Lead saved successfully."}, status=status.HTTP_201_CREATED
        )

    def delete(self, request, lead_id):
        deleted_count, _ = SavedLead.objects.filter(
            user=request.user,
            lead_id=lead_id,
        ).delete()

        if not deleted_count:
            return Response(
                {"error": "Saved lead not found."}, status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {"message": "Lead removed from saved."}, status=status.HTTP_200_OK
        )


class SavedLeadsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        saved_leads = list(
            SavedLead.objects.filter(user=request.user)
            .select_related("lead")
            .order_by("-saved_at")
        )

        serializer = SavedLeadSerializer(
            saved_leads, many=True, context={"request": request}
        )

        return Response(
            {"results": serializer.data, "count": len(saved_leads)},
            status=status.HTTP_200_OK,
        )
