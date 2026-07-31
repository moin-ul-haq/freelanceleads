# services/email_verify.py
#
# Free SMTP-level email deliverability check (no external API):
#   1. syntax check
#   2. MX lookup for the domain
#   3. SMTP handshake: RCPT TO the address (no email is actually sent)
#   4. catch-all probe: RCPT TO a random address at the same domain —
#      if that is also accepted, the server accepts everything and the
#      result can't be trusted → "risky"
#
# Statuses:
#   deliverable    — mailbox confirmed by the receiving server
#   risky          — catch-all domain (accepts anything) or greylisted
#   undeliverable  — receiving server rejected the mailbox
#   unknown        — couldn't verify (blocked port, timeout, odd server)
#
# Note: many big providers rate-limit datacenter IPs; treat "unknown" as
# "send carefully", not as bad.

import re
import smtplib
import socket
import uuid

import dns.resolver
from django.conf import settings

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
SMTP_TIMEOUT = 12

STATUS_DELIVERABLE = "deliverable"
STATUS_RISKY = "risky"
STATUS_UNDELIVERABLE = "undeliverable"
STATUS_UNKNOWN = "unknown"


def _mx_hosts(domain: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=8)
        return [str(r.exchange).rstrip(".") for r in sorted(answers, key=lambda r: r.preference)]
    except Exception:
        # Fallback: RFC 5321 — no MX means try the A record host itself
        try:
            dns.resolver.resolve(domain, "A", lifetime=8)
            return [domain]
        except Exception:
            return []


def _rcpt_code(server: smtplib.SMTP, address: str) -> int:
    code, _ = server.rcpt(address)
    return code


def verify_email(email: str) -> str:
    """Returns one of the STATUS_* strings for a single address."""
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        return STATUS_UNDELIVERABLE

    domain = email.rsplit("@", 1)[1]
    hosts = _mx_hosts(domain)
    if not hosts:
        return STATUS_UNDELIVERABLE  # domain can't receive mail at all

    helo_domain = settings.SITE_URL.split("//")[-1].split("/")[0].split(":")[0] or "localhost"
    probe_from = f"verify@{helo_domain}"

    for host in hosts[:2]:
        try:
            with smtplib.SMTP(host, 25, timeout=SMTP_TIMEOUT) as server:
                server.ehlo_or_helo_if_needed()
                server.mail(probe_from)

                code = _rcpt_code(server, email)
                if code in (550, 551, 553):
                    return STATUS_UNDELIVERABLE
                if code not in (250, 251):
                    return STATUS_UNKNOWN  # greylist / policy answer

                # Accepted — but is the domain a catch-all?
                random_addr = f"zz-{uuid.uuid4().hex[:10]}@{domain}"
                random_code = _rcpt_code(server, random_addr)
                if random_code in (250, 251):
                    return STATUS_RISKY
                return STATUS_DELIVERABLE
        except (socket.timeout, TimeoutError, ConnectionRefusedError, OSError):
            continue
        except smtplib.SMTPServerDisconnected:
            continue
        except Exception:
            return STATUS_UNKNOWN

    return STATUS_UNKNOWN
