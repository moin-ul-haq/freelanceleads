from celery import shared_task
from django.db import close_old_connections
from django.conf import settings
from django.utils import timezone
import smtplib
import imaplib
import email
from email.message import EmailMessage
import uuid
import requests
import base64
import re
import logging
from datetime import timedelta
from outreach.models import EmailAccount, CampaignLead, OutreachMessage, EmailReply

logger = logging.getLogger(__name__)

def refresh_google_token(account: EmailAccount):
    import os
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    
    if not account.refresh_token:
        return False
        
    response = requests.post("https://oauth2.googleapis.com/token", data={
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': account.refresh_token,
        'grant_type': 'refresh_token'
    })
    
    if response.status_code == 200:
        data = response.json()
        account.access_token = data.get('access_token')
        account.save()
        return True
    return False

def generate_oauth2_string(username, access_token):
    auth_string = f"user={username}\1auth=Bearer {access_token}\1\1"
    return auth_string.encode('ascii')

@shared_task
def process_outreach_campaigns():
    close_old_connections()
    now = timezone.now()
    active_leads = CampaignLead.objects.filter(
        status='active',
        next_step_date__lte=now,
        campaign__status='active',
        campaign__email_account__isnull=False,
    ).exclude(lead__email='').select_related(
        'campaign', 'campaign__email_account', 'lead'
    ).prefetch_related('campaign__steps')
    
    for cl in active_leads:
        account = cl.campaign.email_account
        if not account or not cl.lead.email:
            continue

        step = cl.campaign.steps.filter(step_order=cl.current_step).first()
        if not step:
            cl.status = 'completed'
            cl.save(update_fields=['status'])
            continue

        # Enforce email_send quota — skip if exhausted
        from freelanceleads.quota_guard import check, increment
        try:
            check(cl.campaign.user, 'email_send')
        except Exception:
            logger.info("Email send quota exhausted for user %s, skipping.", cl.campaign.user.id)
            continue
            
        msg = EmailMessage()
        first_name = cl.lead.name.split()[0] if cl.lead.name else ""
        msg['Subject'] = step.subject_template.replace("{{first_name}}", first_name)
        msg['From'] = account.email_address
        msg['To'] = cl.lead.email
        
        unique_id = f"<{uuid.uuid4()}@{account.email_address.split('@')[-1]}>"
        msg['Message-ID'] = unique_id
        
        tracking_url = f"{settings.SITE_URL}/api/outreach/track/{unique_id.strip('<>')}.gif"
        html_body = step.body_template.replace("{{first_name}}", first_name)
        html_body += f'<img src="{tracking_url}" width="1" height="1" style="display:none;" />'
        
        msg.set_content(html_body, subtype='html')

        try:
            if account.provider == 'google':
                refresh_google_token(account)
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.ehlo()
                server.starttls()
                server.ehlo()
                auth_str = base64.b64encode(generate_oauth2_string(account.email_address, account.access_token)).decode('ascii')
                server.docmd('AUTH', 'XOAUTH2 ' + auth_str)
            else:
                server = smtplib.SMTP(account.smtp_host, account.smtp_port)
                server.starttls()
                server.login(account.smtp_username, account.smtp_password)

            server.send_message(msg)
            server.quit()
            
            OutreachMessage.objects.create(
                campaign_lead=cl,
                message_id=unique_id.strip('<>'),
                subject=msg['Subject'],
                body=html_body
            )

            # Increment email_send quota after successful send
            increment(cl.campaign.user, 'email_send')
            
            cl.current_step += 1
            next_step = cl.campaign.steps.filter(step_order=cl.current_step).first()
            if next_step:
                cl.next_step_date = now + timedelta(days=next_step.delay_days)
            else:
                cl.status = 'completed'
            cl.save()
            
        except Exception as e:
            logger.error("Failed to send email to %s: %s", cl.lead.email, e)

@shared_task
def poll_imap_replies():
    close_old_connections()
    # Only poll accounts that have active campaigns (not all accounts globally)
    accounts = EmailAccount.objects.filter(
        campaigns__status='active'
    ).distinct()
    
    for account in accounts:
        try:
            if account.provider == 'google':
                refresh_google_token(account)
                mail = imaplib.IMAP4_SSL('imap.gmail.com')
                auth_string = generate_oauth2_string(account.email_address, account.access_token)
                mail.authenticate('XOAUTH2', lambda x: auth_string)
            else:
                mail = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
                mail.login(account.imap_username, account.imap_password)
                
            mail.select('inbox')
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK':
                continue
                
            for num in messages[0].split():
                status, data = mail.fetch(num, '(RFC822)')
                if status != 'OK':
                    continue
                    
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                in_reply_to = str(msg.get('In-Reply-To', ''))
                references = str(msg.get('References', ''))
                
                potential_ids = re.findall(r'<([^>]+)>', in_reply_to + " " + references)
                
                for pid in potential_ids:
                    outreach_msg = OutreachMessage.objects.filter(message_id=pid).first()
                    if outreach_msg:
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == 'text/plain':
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body += payload.decode('utf-8', errors='ignore')
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body = payload.decode('utf-8', errors='ignore')
                            
                        EmailReply.objects.create(
                            outreach_message=outreach_msg,
                            from_email=msg.get('From'),
                            subject=msg.get('Subject'),
                            body=body,
                            received_at=timezone.now()
                        )
                        
                        outreach_msg.campaign_lead.status = 'replied'
                        outreach_msg.campaign_lead.save()
                        break
                        
        except Exception as e:
            logger.error("Error polling IMAP for %s: %s", account.email_address, e)
