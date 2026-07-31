# leads/management/commands/seed_demo_leads.py
#
# Seeds realistic demo leads so the app can be explored and the frontend
# developed without a SerpAPI key. Safe to run repeatedly (idempotent by
# place_id). Demo place_ids are prefixed "demo_" so they're easy to purge:
#   Lead.objects.filter(place_id__startswith="demo_").delete()

import random

from django.core.management.base import BaseCommand

from leads.models import Lead, SearchCache
from services.scoring import calculate_score

FIRST = ["Apex", "BlueBird", "Crown", "Delta", "Elite", "First Choice", "Golden",
         "Harbor", "Iron", "Junction", "Keystone", "Liberty", "Metro", "North Star",
         "Oakwood", "Prime", "Quick", "Reliable", "Summit", "TruePoint"]

SEARCHES = [
    ("plumber", "toronto", "canada"),
    ("dentist", "austin", "usa"),
    ("electrician", "lahore", "pakistan"),
]


class Command(BaseCommand):
    help = "Seed demo leads for local development (no external APIs needed)."

    def handle(self, *args, **options):
        rng = random.Random(42)  # deterministic — same demo data every run
        created = 0

        for niche, city, country in SEARCHES:
            for i, prefix in enumerate(FIRST):
                place_id = f"demo_{niche}_{city}_{i}"
                name = f"{prefix} {niche.title()} Co"

                has_website = rng.random() > 0.3
                has_ssl = has_website and rng.random() > 0.35
                has_meta_title = has_website and rng.random() > 0.3
                has_meta_desc = has_website and rng.random() > 0.5
                has_schema = has_website and rng.random() > 0.7
                has_social = rng.random() > 0.45
                pagespeed = rng.randint(18, 96) if has_website else None
                rating = round(rng.uniform(2.4, 5.0), 1)
                review_count = rng.randint(0, 220)

                score = calculate_score(
                    has_website=has_website,
                    has_ssl=has_ssl,
                    pagespeed_score=pagespeed,
                    rating=rating,
                    review_count=review_count,
                    has_meta_title=has_meta_title,
                    has_meta_desc=has_meta_desc,
                    has_schema=has_schema,
                    has_social=has_social,
                )

                domain = name.lower().replace(" ", "")
                _, was_created = Lead.objects.update_or_create(
                    place_id=place_id,
                    defaults={
                        "name": name,
                        "niche": niche,
                        "city": city,
                        "state": "",
                        "country": country,
                        "address": f"{100 + i * 7} Main Street, {city.title()}",
                        "phone": f"+1 555-01{i:02d}",
                        "website": f"https://{domain}.example.com" if has_website else "",
                        "email": f"info@{domain}.example.com" if rng.random() > 0.4 else "",
                        "rating": rating,
                        "review_count": review_count,
                        "gbp_status": niche.title(),
                        "has_website": has_website,
                        "has_ssl": has_ssl,
                        "pagespeed_score": pagespeed,
                        "has_meta_title": has_meta_title,
                        "has_meta_desc": has_meta_desc,
                        "has_schema": has_schema,
                        "has_social": has_social,
                        "opportunity_score": score,
                        "audit_done": True,
                    },
                )
                created += int(was_created)

            SearchCache.objects.update_or_create(
                cache_key=f"leads:{niche}:{city}:{country}",
                defaults={
                    "niche": niche,
                    "city": city,
                    "country": country,
                    "total_results": len(FIRST),
                    "next_start": len(FIRST),
                    "is_exhausted": True,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready — {created} new leads "
            f"(searches: plumber/toronto, dentist/austin, electrician/lahore)."
        ))
