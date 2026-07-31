import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class GeneratedSite(models.Model):
    """
    AI-generated one-page demo website for a lead — used as a pitch asset
    ("here's what your site could look like"). Public at /sites/<slug>/.

    `content` holds the AI-written copy as structured JSON:
      headline, tagline, about, services [{name, description}],
      why_us [str], cta_headline, cta_text
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="generated_sites"
    )
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.CASCADE, related_name="generated_sites"
    )
    slug = models.SlugField(max_length=120, unique=True, db_index=True)

    business_name = models.CharField(max_length=255)
    niche = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    rating = models.FloatField(null=True, blank=True)
    review_count = models.IntegerField(default=0)

    content = models.JSONField(default=dict)

    # Customization — "ai" scheme picks a palette from the business name hash
    color_scheme = models.CharField(max_length=20, default="ai")
    custom_primary = models.CharField(max_length=9, blank=True)   # hex, when scheme=custom
    custom_secondary = models.CharField(max_length=9, blank=True)
    tone = models.CharField(max_length=20, default="auto")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "lead")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.business_name} ({self.slug})"

    @staticmethod
    def make_slug(name: str) -> str:
        base = slugify(name)[:100] or "site"
        slug = base
        while GeneratedSite.objects.filter(slug=slug).exists():
            slug = f"{base}-{uuid.uuid4().hex[:5]}"
        return slug


class SiteInquiry(models.Model):
    """A contact-form submission on a public demo site — proof for the pitch
    that the site is already capturing customers."""

    site = models.ForeignKey(GeneratedSite, on_delete=models.CASCADE, related_name="inquiries")
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Inquiry for {self.site.business_name} from {self.name}"
