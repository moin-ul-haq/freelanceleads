# leads/management/commands/reaudit_leads.py
#
# Re-runs the website audit for existing leads — used after audit-logic fixes
# so stale flags/scores get corrected. Demo leads (place_id demo_*) are
# skipped: their audit data is synthetic on purpose.

from django.core.management.base import BaseCommand

from leads.models import Lead
from leads.tasks import dispatch_audits


class Command(BaseCommand):
    help = "Reset audit flags and re-queue audits for existing leads."

    def add_arguments(self, parser):
        parser.add_argument("--niche", help="Only re-audit this niche")
        parser.add_argument(
            "--sync", action="store_true",
            help="Run audits in-process and wait (default queues to Celery)",
        )

    def handle(self, *args, **options):
        qs = Lead.objects.exclude(place_id__startswith="demo_")
        if options["niche"]:
            qs = qs.filter(niche=options["niche"].strip().lower())

        lead_ids = list(qs.values_list("id", flat=True))
        if not lead_ids:
            self.stdout.write("No leads to re-audit.")
            return

        qs.update(audit_done=False)

        if options["sync"]:
            from concurrent.futures import ThreadPoolExecutor
            from leads.tasks import _audit_lead_safe
            with ThreadPoolExecutor(max_workers=10) as ex:
                list(ex.map(_audit_lead_safe, lead_ids))
            done = Lead.objects.filter(id__in=lead_ids, audit_done=True).count()
            self.stdout.write(self.style.SUCCESS(
                f"Re-audited {done}/{len(lead_ids)} leads synchronously."
            ))
        else:
            dispatch_audits(lead_ids)
            self.stdout.write(self.style.SUCCESS(
                f"Queued re-audit for {len(lead_ids)} leads."
            ))
