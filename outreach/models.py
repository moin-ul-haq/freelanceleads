from django.db import models
from django.conf import settings
from leads.models import Lead
from outreach.utils import encrypt_value, decrypt_value

class EmailAccount(models.Model):
    PROVIDER_CHOICES = [
        ('google', 'Google Workspace / Gmail'),
        ('outlook', 'Microsoft Outlook'),
        ('custom', 'Custom SMTP/IMAP'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_accounts')
    email_address = models.EmailField(unique=True)
    # Cold-email safety: max sends per rolling day from this account.
    # 30-50 is the accepted safe range for a warmed inbox.
    daily_send_limit = models.PositiveIntegerField(default=40)
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    
    # OAuth Tokens (Encrypted)
    access_token_encrypted = models.BinaryField(null=True, blank=True)
    refresh_token_encrypted = models.BinaryField(null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # SMTP Settings
    smtp_host = models.CharField(max_length=255, null=True, blank=True)
    smtp_port = models.IntegerField(default=587)
    smtp_username = models.CharField(max_length=255, null=True, blank=True)
    smtp_password_encrypted = models.BinaryField(null=True, blank=True)
    
    # IMAP Settings
    imap_host = models.CharField(max_length=255, null=True, blank=True)
    imap_port = models.IntegerField(default=993)
    imap_username = models.CharField(max_length=255, null=True, blank=True)
    imap_password_encrypted = models.BinaryField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    
    @property
    def access_token(self):
        return decrypt_value(self.access_token_encrypted)
    @access_token.setter
    def access_token(self, value):
        self.access_token_encrypted = encrypt_value(value)

    @property
    def refresh_token(self):
        return decrypt_value(self.refresh_token_encrypted)
    @refresh_token.setter
    def refresh_token(self, value):
        self.refresh_token_encrypted = encrypt_value(value)

    @property
    def smtp_password(self):
        return decrypt_value(self.smtp_password_encrypted)
    @smtp_password.setter
    def smtp_password(self, value):
        self.smtp_password_encrypted = encrypt_value(value)

    @property
    def imap_password(self):
        return decrypt_value(self.imap_password_encrypted)
    @imap_password.setter
    def imap_password(self, value):
        self.imap_password_encrypted = encrypt_value(value)

    def __str__(self):
        return self.email_address

class Campaign(models.Model):
    STATUS_CHOICES = [('draft', 'Draft'), ('active', 'Active'), ('paused', 'Paused'), ('completed', 'Completed')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='campaigns')
    email_account = models.ForeignKey(EmailAccount, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class CampaignStep(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='steps')
    step_order = models.PositiveIntegerField()
    delay_days = models.PositiveIntegerField(default=1) # wait N days after previous step
    subject_template = models.CharField(max_length=255)
    body_template = models.TextField()
    
    class Meta:
        ordering = ['step_order']

    def __str__(self):
        return f"{self.campaign.name} - Step {self.step_order}"

class CampaignLead(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('replied', 'Replied'), ('bounced', 'Bounced'), ('completed', 'Completed')]
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='campaign_leads')
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='campaign_enrollments')
    current_step = models.PositiveIntegerField(default=1)
    send_failures = models.PositiveIntegerField(default=0)
    next_step_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='active')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('campaign', 'lead')
        indexes = [
            models.Index(fields=['campaign', 'status']),  # analytics queries
            models.Index(fields=['status', 'next_step_date']),  # scheduled task
        ]

    def __str__(self):
        return f"{self.lead.name} in {self.campaign.name}"

class OutreachMessage(models.Model):
    # Nullable: one-off sends (AI pitch "Send email") have no campaign
    campaign_lead = models.ForeignKey(CampaignLead, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    # Stamped directly so daily caps / tracking / reply matching cover
    # one-off sends and survive campaign account reassignment
    email_account = models.ForeignKey(EmailAccount, on_delete=models.SET_NULL, related_name='sent_messages', null=True, blank=True)
    lead = models.ForeignKey('leads.Lead', on_delete=models.SET_NULL, related_name='outreach_messages', null=True, blank=True)
    message_id = models.CharField(max_length=255, unique=True, db_index=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['campaign_lead']),  # analytics aggregation
        ]

    def __str__(self):
        return f"Msg: {self.subject} to {self.campaign_lead.lead.name}"

class EmailReply(models.Model):
    outreach_message = models.ForeignKey(OutreachMessage, on_delete=models.CASCADE, related_name='replies')
    from_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    received_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reply from {self.from_email}"


class UnsubscribedEmail(models.Model):
    """Per-user suppression list — checked before every send and enroll."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='unsubscribes')
    email = models.EmailField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'email')

    def __str__(self):
        return f"{self.email} (user {self.user_id})"
