"""
Management command: seed_plans
Usage: python manage.py seed_plans

Creates or updates the three subscription plans (Free, Pro, Max) with their
numeric limits and boolean feature flags based on your Plan and PlanFeature models.
"""

from django.core.management.base import BaseCommand
from billing.models import Plan, PlanFeature  # adjust app label if needed


# ---------------------------------------------------------------------------
# Plan definitions
# ---------------------------------------------------------------------------

PLANS = [
    {
        "name": "free",
        "price_usd": 0.00,
        "stripe_price_id": "",
        # Numeric limits (-1 = unlimited)
        "search_limit": 10,
        "backlink_search_limit": 5,
        "ai_pitch_limit": 5,
        "email_send_limit": 10,
        "saved_leads_limit": 20,
        "ai_chat_limit": 10,
        "bulk_search_limit": 0,
        "team_seat_limit": 1,
    },
    {
        "name": "pro",
        "price_usd": 49.00,
        "stripe_price_id": "price_1TVxVRHbrGvwr2y8qKVzCsjL",  # fill in your Stripe Price ID
        # Numeric limits (-1 = unlimited)
        "search_limit": 200,
        "backlink_search_limit": 100,
        "ai_pitch_limit": 100,
        "email_send_limit": 500,
        "saved_leads_limit": 500,
        "ai_chat_limit": 200,
        "bulk_search_limit": 50,
        "team_seat_limit": 3,
    },
    {
        "name": "max",
        "price_usd": 99.00,
        "stripe_price_id": "price_1TVxWiHbrGvwr2y8u0YYWZbo",  # fill in your Stripe Price ID
        # Numeric limits (-1 = unlimited)
        "search_limit": -1,
        "backlink_search_limit": -1,
        "ai_pitch_limit": -1,
        "email_send_limit": -1,
        "saved_leads_limit": -1,
        "ai_chat_limit": -1,
        "bulk_search_limit": -1,
        "team_seat_limit": 10,
    },
]


# ---------------------------------------------------------------------------
# Feature matrix  {feature_key: {plan_name: is_enabled}}
# ---------------------------------------------------------------------------

FEATURES = {
    "website_generation": {"free": False, "pro": True, "max": True},
    "pdf_audit_reports": {"free": False, "pro": True, "max": True},
    "ai_lead_scoring": {"free": False, "pro": True, "max": True},
    "pipeline_crm": {"free": False, "pro": True, "max": True},
    "follow_up_sequences": {"free": False, "pro": False, "max": True},
    "proposals_case_studies": {"free": False, "pro": False, "max": True},
    "competitor_comparison": {"free": False, "pro": True, "max": True},
    "niche_scanner": {"free": False, "pro": True, "max": True},
    "csv_export_import": {"free": False, "pro": True, "max": True},
    "bulk_pitch_generation": {"free": False, "pro": False, "max": True},
    "daily_email_automations": {"free": False, "pro": False, "max": True},
    "review_response_templates": {"free": False, "pro": True, "max": True},
    "priority_support": {"free": False, "pro": False, "max": True},
}


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = "Seed subscription plans (Free / Pro / Max) with limits and features."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing plans and recreate them from scratch.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = Plan.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"  Deleted {deleted} existing plan(s).")
            )

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding plans…\n"))

        for plan_data in PLANS:
            plan, created = Plan.objects.update_or_create(
                name=plan_data["name"],
                defaults={k: v for k, v in plan_data.items() if k != "name"},
            )

            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  {action} plan: {plan}"))

            # ---- Features ----
            feat_created = feat_updated = 0
            for feature_key, plan_map in FEATURES.items():
                is_enabled = plan_map.get(plan.name, False)
                _, f_created = PlanFeature.objects.update_or_create(
                    plan=plan,
                    feature=feature_key,
                    defaults={"is_enabled": is_enabled},
                )
                if f_created:
                    feat_created += 1
                else:
                    feat_updated += 1

            self.stdout.write(
                f"    Features — {feat_created} created, {feat_updated} updated"
            )

        self.stdout.write(self.style.SUCCESS("\n✅  Plan seeding complete."))
