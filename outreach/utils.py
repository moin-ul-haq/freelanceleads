import os
import smtplib
import uuid
import base64
from email.message import EmailMessage

from cryptography.fernet import Fernet

def get_fernet():
    key = os.environ.get('FERNET_ENCRYPTION_KEY')
    if not key:
        raise ValueError("FERNET_ENCRYPTION_KEY is not set in environment.")
    return Fernet(key.encode('utf-8'))

def encrypt_value(value: str) -> bytes:
    if not value:
        return b""
    f = get_fernet()
    return f.encrypt(value.encode('utf-8'))

def decrypt_value(token: bytes) -> str:
    if not token:
        return ""
    f = get_fernet()
    # Convert memoryview to bytes (PostgreSQL BinaryField returns memoryview)
    if isinstance(token, memoryview):
        token = bytes(token)
    return f.decrypt(token).decode('utf-8')


def send_email_via_account(account, to_email: str, subject: str, body: str) -> str:
    """
    Sends one plain-text email through the user's connected account
    (Gmail OAuth or custom SMTP). Returns the Message-ID.
    Raises on failure — callers decide how to surface the error.
    """
    from outreach.tasks import refresh_google_token, generate_oauth2_string

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = account.email_address
    msg["To"] = to_email
    unique_id = f"<{uuid.uuid4()}@{account.email_address.split('@')[-1]}>"
    msg["Message-ID"] = unique_id
    msg.set_content(body)

    if account.provider == "google":
        refresh_google_token(account)
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        auth_str = base64.b64encode(
            generate_oauth2_string(account.email_address, account.access_token)
        ).decode("ascii")
        server.docmd("AUTH", "XOAUTH2 " + auth_str)
    else:
        server = smtplib.SMTP(account.smtp_host, account.smtp_port, timeout=30)
        server.starttls()
        server.login(account.smtp_username, account.smtp_password)

    try:
        server.send_message(msg)
    finally:
        server.quit()

    return unique_id.strip("<>")
