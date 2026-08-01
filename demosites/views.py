import hashlib
import re

from django.shortcuts import get_object_or_404, render
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from freelanceleads.quota_guard import check, increment
from leads.models import Lead

from .ai import generate_site_content
from .models import GeneratedSite, SiteInquiry
from .serializers import GeneratedSiteSerializer

# Named palettes (primary, dark) — mirrors the picker in the frontend wizard
PALETTES = {
    "ocean_blue": ("#2563eb", "#1e40af"),
    "emerald": ("#059669", "#065f46"),
    "royal_purple": ("#7c3aed", "#5b21b6"),
    "sunset_orange": ("#ea580c", "#9a3412"),
    "rose_red": ("#dc2626", "#991b1b"),
    "slate": ("#475569", "#1e293b"),
    "teal": ("#0d9488", "#115e59"),
    "amber_gold": ("#d97706", "#92400e"),
    "indigo": ("#4f46e5", "#3730a3"),
    "forest_green": ("#16a34a", "#14532d"),
    "hot_pink": ("#db2777", "#9d174d"),
    "midnight": ("#334155", "#0f172a"),
}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _resolve_colors(site: GeneratedSite):
    if site.color_scheme == "custom" and HEX_RE.match(site.custom_primary or ""):
        secondary = site.custom_secondary if HEX_RE.match(site.custom_secondary or "") else site.custom_primary
        return site.custom_primary, secondary
    if site.color_scheme in PALETTES:
        return PALETTES[site.color_scheme]
    # "ai" — deterministic pick from the business name
    keys = sorted(PALETTES)
    idx = int(hashlib.md5(site.business_name.encode()).hexdigest(), 16) % len(keys)
    return PALETTES[keys[idx]]


def public_site(request, slug):
    """Public one-page demo site — no auth, shareable with the prospect.
    Also handles the contact-form POST and stores the inquiry."""
    site = get_object_or_404(GeneratedSite, slug=slug)

    form_sent = False
    form_error = ""
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()[:120]
        email = (request.POST.get("email") or "").strip()[:254]
        phone = (request.POST.get("phone") or "").strip()[:50]
        message = (request.POST.get("message") or "").strip()[:3000]
        if name and message:
            SiteInquiry.objects.create(
                site=site, name=name, email=email, phone=phone, message=message
            )
            form_sent = True
            from accounts.models import notify
            notify(
                site.user, "inquiry",
                f"New inquiry on {site.business_name} demo site 📬",
                f"{name}: {message[:150]}",
                link=f"/leads/{site.lead_id}",
            )
        else:
            form_error = "Please fill in your name and a short message."

    accent, accent_dark = _resolve_colors(site)
    return render(request, "demosites/site.html", {
        "site": site,
        "content": site.content,
        "accent": accent,
        "accent_dark": accent_dark,
        "form_sent": form_sent,
        "form_error": form_error,
    })


class GenerateSiteView(APIView):
    """
    POST /api/sites/generate/
    {
      lead_id,                 // required
      regenerate?,             // rebuild even if a site exists
      color_scheme?,           // palette key | "custom" | "ai" (default)
      custom_primary?, custom_secondary?,   // hex, when scheme=custom
      tone?,                   // auto|friendly|professional|bold|luxury|playful
      business_name?, phone?, email?, address?,   // overrides (default: lead data)
      services?,               // optional comma-separated list the AI must use
      extra_info?              // optional real facts to weave into the copy
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        lead_id = data.get("lead_id")
        regenerate = bool(data.get("regenerate"))
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

        tone = (data.get("tone") or "auto").strip().lower()
        try:
            content = generate_site_content(
                lead,
                tone=tone,
                services_hint=data.get("services") or "",
                extra_info=data.get("extra_info") or "",
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        site = existing or GeneratedSite(
            user=request.user, lead=lead, slug=GeneratedSite.make_slug(lead.name)
        )
        site.content = content
        site.tone = tone

        scheme = (data.get("color_scheme") or "ai").strip().lower()
        site.color_scheme = scheme if scheme in PALETTES or scheme in ("ai", "custom") else "ai"
        site.custom_primary = (data.get("custom_primary") or "").strip()
        site.custom_secondary = (data.get("custom_secondary") or "").strip()

        site.business_name = (data.get("business_name") or "").strip() or lead.name
        site.niche = lead.niche
        site.city = lead.city
        site.phone = (data.get("phone") or "").strip() or lead.phone or ""
        site.email = (data.get("email") or "").strip() or lead.email or ""
        site.address = (data.get("address") or "").strip() or lead.address or ""
        site.rating = lead.rating
        site.review_count = lead.review_count or 0
        site.save()

        increment(request.user, "ai_pitch")
        return Response(
            GeneratedSiteSerializer(site, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class SiteListView(APIView):
    """GET /api/sites/ — the current user's generated demo sites (with inquiries)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        sites = GeneratedSite.objects.filter(user=request.user).select_related("lead").prefetch_related("inquiries")
        return Response(GeneratedSiteSerializer(sites, many=True, context={"request": request}).data)


class SiteDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        deleted, _ = GeneratedSite.objects.filter(id=pk, user=request.user).delete()
        if not deleted:
            return Response({"error": "Site not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
