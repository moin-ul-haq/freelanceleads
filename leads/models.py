# leads/models.py

from django.db import models
from django.conf import settings


class Lead(models.Model):
    """
    Represents a single business discovered via search.
    place_id is the unique identifier from Google Places / SerpAPI.
    """

    STATUS_CHOICES = [
        ("new", "New"),
        ("saved", "Saved"),
        ("contacted", "Contacted"),
        ("closed", "Closed"),
    ]

    # ── Identity ──────────────────────────────────────────────
    place_id = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    niche = models.CharField(max_length=100)  # e.g. "plumber"
    city = models.CharField(max_length=100)  # e.g. "albany"
    state = models.CharField(max_length=100, blank=True)  # e.g. "new york"
    country = models.CharField(max_length=50, default="US")

    # ── Location ──────────────────────────────────────────────
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    # SMTP-level deliverability: unchecked/deliverable/risky/undeliverable/unknown
    email_status = models.CharField(max_length=15, default="unchecked", blank=True)
    email_checked_at = models.DateTimeField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # ── Google Data ───────────────────────────────────────────
    rating = models.FloatField(null=True, blank=True)
    review_count = models.IntegerField(default=0)
    gbp_status = models.CharField(max_length=50, blank=True)  # OPERATIONAL etc

    # ── Audit Results ─────────────────────────────────────────
    has_website = models.BooleanField(default=False)
    has_ssl = models.BooleanField(default=False)
    pagespeed_score = models.IntegerField(null=True, blank=True)  # 0-100
    has_meta_title = models.BooleanField(default=False)
    has_meta_desc = models.BooleanField(default=False)
    has_schema = models.BooleanField(default=False)
    has_social = models.BooleanField(default=False)

    # ── Opportunity Score ─────────────────────────────────────
    opportunity_score = models.IntegerField(default=0, db_index=True)  # 0-100

    # ── Status ────────────────────────────────────────────────
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    audit_done = models.BooleanField(
        default=False
    )  # True when Celery audit task completes

    # ── Timestamps ────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-opportunity_score"]
        indexes = [
            models.Index(
                fields=["niche", "city", "state", "country"]
            ),  # supports both city and state level search
            # Individual field indexes for iexact filter paths
            models.Index(fields=["niche", "city", "country"]),
            models.Index(fields=["city"]),
            models.Index(fields=["niche"]),
            models.Index(fields=["audit_done", "has_website", "email"]),  # audit backfill query
        ]

    def __str__(self):
        return f"{self.name} — {self.city} — Score: {self.opportunity_score}"


class SavedLead(models.Model):
    """
    Junction table — user saves a lead for later action.
    Same lead can be saved by multiple users.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_leads"
    )
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="saved_by")
    notes = models.TextField(blank=True)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "lead")  # user can save a lead only once

    def __str__(self):
        return f"{self.user.email} saved {self.lead.name}"


class SearchCache(models.Model):
    """
    Tracks which niche+city combinations have been fetched.
    Used as Layer 2 cache — if Redis expires, check here before hitting API.
    """

    cache_key = models.CharField(
        max_length=255, unique=True, db_index=True
    )  # leads:plumber:albany:new_york:US
    niche = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=50, default="US")
    total_results = models.IntegerField(default=0)  # how many leads are stored
    next_start = models.IntegerField(default=0)  # will handle pagination
    is_exhausted = models.BooleanField(default=False)  # no more pages available
    last_fetched = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["niche", "city", "state", "country"]),
        ]

    def __str__(self):
        return f"{self.cache_key} — {self.total_results} results"
