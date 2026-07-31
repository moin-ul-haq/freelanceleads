import hashlib

from django.shortcuts import get_object_or_404, render
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from freelanceleads.quota_guard import check, increment
from leads.models import Lead

from .ai import generate_site_content
from .models import GeneratedSite
from .serializers import GeneratedSiteSerializer

# One accent palette per hue family — picked deterministically per business
ACCENTS = [
    ("#2563eb", "#1e40af"),  # blue
    ("#059669", "#065f46"),  # emerald
    ("#d97706", "#92400e"),  # amber
    ("#dc2626", "#991b1b"),  # red
    ("#7c3aed", "#5b21b6"),  # violet
    ("#0891b2", "#155e75"),  # cyan
]


def _accent_for(name: str):
    idx = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(ACCENTS)
    return ACCENTS[idx]


def public_site(request, slug):
    """Public one-page demo site — no auth, shareable with the prospect."""
    site = get_object_or_404(GeneratedSite, slug=slug)
    accent, accent_dark = _accent_for(site.business_name)
    return render(request, "demosites/site.html", {
        "site": site,
        "content": site.content,
        "accent": accent,
        "accent_dark": accent_dark,
    })


class GenerateSiteView(APIView):
    """POST /api/sites/generate/ {lead_id, regenerate?} → {slug, url}"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        lead_id = request.data.get("lead_id")
        regenerate = bool(request.data.get("regenerate"))
        if not lead_id:
            return Response({"error": "lead_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({"error": "Lead not found."}, status=status.HTTP_404_NOT_FOUND)

        existing = GeneratedSite.objects.filter(user=request.user, lead=lead).first()
        if existing and not regenerate:
            return Response(GeneratedSiteSerializer(existing, context={"request": request}).data)

        try:
            check(request.user, "ai_pitch")
        except PermissionDenied as e:
            return Response(e.detail, status=status.HTTP_403_FORBIDDEN)

        try:
            content = generate_site_content(lead)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if existing:
            site = existing
            site.content = content
        else:
            site = GeneratedSite(
                user=request.user,
                lead=lead,
                slug=GeneratedSite.make_slug(lead.name),
            )
            site.content = content

        site.business_name = lead.name
        site.niche = lead.niche
        site.city = lead.city
        site.phone = lead.phone or ""
        site.email = lead.email or ""
        site.address = lead.address or ""
        site.rating = lead.rating
        site.review_count = lead.review_count or 0
        site.save()

        increment(request.user, "ai_pitch")
        return Response(
            GeneratedSiteSerializer(site, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class SiteListView(APIView):
    """GET /api/sites/ — the current user's generated demo sites."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        sites = GeneratedSite.objects.filter(user=request.user).select_related("lead")
        return Response(GeneratedSiteSerializer(sites, many=True, context={"request": request}).data)


class SiteDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        deleted, _ = GeneratedSite.objects.filter(id=pk, user=request.user).delete()
        if not deleted:
            return Response({"error": "Site not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
