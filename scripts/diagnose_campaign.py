"""Diagnostic script: check why campaign 3 / lead 445 isn't sending."""
import os, sys, django
sys.path.insert(0, r"D:\python\django\Freelance Leads\freelanceleads")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freelanceleads.settings")
django.setup()

from django.utils import timezone
from outreach.models import Campaign, CampaignLead, CampaignStep

CAMPAIGN_ID = 3
LEAD_ID = 445

now = timezone.now()
print(f"Current time (UTC): {now}")
print()

# --- Campaign ---
try:
    c = Campaign.objects.get(id=CAMPAIGN_ID)
except Campaign.DoesNotExist:
    print(f"ERROR: Campaign {CAMPAIGN_ID} does NOT exist!")
    sys.exit()

print("=== CAMPAIGN ===")
print(f"  ID:            {c.id}")
print(f"  Name:          {c.name}")
print(f"  Status:        {c.status}  {'OK' if c.status == 'active' else 'PROBLEM: Must be active!'}")
print(f"  Email Account: {c.email_account}  {'OK' if c.email_account else 'PROBLEM: No email account linked!'}")
print()

# --- Steps ---
steps = CampaignStep.objects.filter(campaign=c).order_by("step_order")
print(f"=== CAMPAIGN STEPS ({steps.count()}) ===")
if steps.count() == 0:
    print("  PROBLEM: No steps found! The task needs at least one step.")
for s in steps:
    print(f"  Step {s.step_order}: delay={s.delay_days}d | subject='{s.subject_template}'")
print()

# --- Campaign Lead ---
cls = CampaignLead.objects.filter(campaign_id=CAMPAIGN_ID).select_related("lead")
print(f"=== CAMPAIGN LEADS ({cls.count()}) ===")

target_cl = None
for cl in cls:
    is_target = cl.lead_id == LEAD_ID
    marker = " <<< TARGET" if is_target else ""
    print(f"  Lead #{cl.lead.id} - {cl.lead.name}{marker}")
    print(f"    Email:          {cl.lead.email or 'PROBLEM: EMPTY'}")
    print(f"    Status:         {cl.status}  {'OK' if cl.status == 'active' else 'NOT ACTIVE'}")
    print(f"    Current Step:   {cl.current_step}")
    print(f"    Next Step Date: {cl.next_step_date}")
    if cl.next_step_date:
        is_due = cl.next_step_date <= now
        print(f"    Next Step <= Now: {is_due}  {'OK' if is_due else 'PROBLEM: Scheduled in the FUTURE'}")
    else:
        print(f"    Next Step <= Now: PROBLEM: next_step_date is NULL")

    # Check if matching step exists
    matching_step = steps.filter(step_order=cl.current_step).first()
    if matching_step:
        print(f"    Matching Step:  OK - Step {matching_step.step_order}")
    else:
        print(f"    Matching Step:  PROBLEM: No step for current_step={cl.current_step}")
    print()
    if is_target:
        target_cl = cl

if target_cl is None:
    print(f"PROBLEM: Lead {LEAD_ID} is NOT enrolled in campaign {CAMPAIGN_ID}!")

# --- Simulate the query ---
print("=== SIMULATING TASK QUERY ===")
active_leads = CampaignLead.objects.filter(
    status='active',
    next_step_date__lte=now,
    campaign__status='active',
    campaign__email_account__isnull=False,
).exclude(lead__email='').select_related('campaign', 'campaign__email_account', 'lead')

filtered_for_campaign = active_leads.filter(campaign_id=CAMPAIGN_ID)
print(f"  Total active leads across ALL campaigns: {active_leads.count()}")
print(f"  Active leads for campaign {CAMPAIGN_ID}: {filtered_for_campaign.count()}")

if filtered_for_campaign.count() == 0:
    print()
    print("  >>> NO LEADS MATCHED THE QUERY - this is why no email was sent!")
    print("  >>> Check the PROBLEM markers above to see which filter is excluding the lead.")
else:
    for cl in filtered_for_campaign:
        print(f"  OK: Would send to: {cl.lead.name} <{cl.lead.email}>")
