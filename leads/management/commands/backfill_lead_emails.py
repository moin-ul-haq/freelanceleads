# leads/management/commands/backfill_lead_emails.py

from django.core.management.base import BaseCommand
from django.db.models import Q

from leads.models import Lead
from leads.tasks import audit_leads_batch


class Command(BaseCommand):
    help = "Queue email extraction for leads that have a website but no email."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Max leads to queue (default 100).",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run audit_lead synchronously (no Celery) for debugging.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        lead_ids = list(
            Lead.objects.filter(has_website=True)
            .filter(Q(email="") | Q(email__isnull=True))
            .order_by("-updated_at")
            .values_list("id", flat=True)[:limit]
        )

        if not lead_ids:
            self.stdout.write(self.style.SUCCESS("No leads need email backfill."))
            return

        if options["sync"]:
            from leads.tasks import audit_lead

            for lead_id in lead_ids:
                audit_lead(lead_id)
            self.stdout.write(
                self.style.SUCCESS(f"Processed {len(lead_ids)} leads synchronously.")
            )
            return

        audit_leads_batch.delay(lead_ids)
        self.stdout.write(
            self.style.SUCCESS(
                f"Queued {len(lead_ids)} leads for email extraction. "
                "Ensure Celery worker is running."
            )
        )
