# services/email_finder.py
"""
Extract business contact emails from websites.
"""

from __future__ import annotations

import html as html_module
import json
import logging
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

EMAIL_BLOCKLIST = (
    "example.com",
    "email.com",
    "domain.com",
    "sentry.io",
    "wixpress.com",
    "schema.org",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "linkedin.com",
    "google.com",
    "youtube.com",
    "w3.org",
    "wordpress.org",
    "gravatar.com",
)

EMAIL_LOCAL_BLOCKLIST = (
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "mailer-daemon",
    "postmaster",
    "sentry",
)

CONTACT_PATHS = (
    "/contact",
    "/contact-us",
    "/contactus",
    "/contact.html",
    "/contact.php",
    "/about/contact",
    "/about-us/contact",
    "/get-in-touch",
    "/reach-us",
)

CONTACT_LINK_RE = re.compile(
    r"contact|get-in-touch|reach-us|email-us|request-quote|free-quote",
    re.I,
)

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Large builder sites often put email in footer after 200KB+ of assets/markup.
MAX_PAGE_BYTES = 1_500_000
HEAD_SCAN_BYTES = 250_000
TAIL_SCAN_BYTES = 250_000


def _website_hostname(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.netloc or parsed.path.split("/")[0]).lower()
    return host.removeprefix("www.")


def _normalize_website_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def _same_site(url: str, hostname: str) -> bool:
    if not hostname:
        return True
    host = _website_hostname(url)
    return host == hostname or host.endswith(f".{hostname}")


def _url_variants(url: str) -> list[str]:
    """Try https/http and www variants when fetch fails."""
    normalized = _normalize_website_url(url)
    if not normalized:
        return []

    parsed = urlparse(normalized)
    host = parsed.netloc
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""

    hosts = {host}
    if host.startswith("www."):
        hosts.add(host[4:])
    else:
        hosts.add(f"www.{host}")

    variants = []
    seen = set()
    for h in hosts:
        for scheme in ("https", "http"):
            candidate = f"{scheme}://{h}{path}{query}"
            if candidate not in seen:
                seen.add(candidate)
                variants.append(candidate)
    return variants


def _is_plausible_email(email: str) -> bool:
    email = email.lower().strip().strip(".")
    if not email or "@" not in email:
        return False
    if any(ext in email for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")):
        return False

    local, _, domain = email.partition("@")
    if not local or not domain or len(local) > 64:
        return False
    if any(blocked in domain for blocked in EMAIL_BLOCKLIST):
        return False
    if any(blocked in local for blocked in EMAIL_LOCAL_BLOCKLIST):
        return False
    if domain.count(".") < 1:
        return False
    tld = domain.rsplit(".", 1)[-1]
    if len(tld) < 2 or not tld.isalpha():
        return False
    return True


def _pick_best_email(candidates: list[str], website_hostname: str) -> str:
    seen: set[str] = set()
    unique: list[str] = []
    for raw in candidates:
        email = raw.lower().strip().strip(".")
        if not _is_plausible_email(email) or email in seen:
            continue
        seen.add(email)
        unique.append(email)

    if not unique:
        return ""

    preferred_locals = ("info", "contact", "hello", "office", "sales", "service", "support")
    domain_matches = [
        e
        for e in unique
        if website_hostname
        and (
            e.split("@", 1)[1] == website_hostname
            or e.split("@", 1)[1].endswith(f".{website_hostname}")
        )
    ]
    if domain_matches:
        for prefix in preferred_locals:
            for email in domain_matches:
                if email.split("@", 1)[0] == prefix:
                    return email
        return domain_matches[0]

    for prefix in preferred_locals:
        for email in unique:
            if email.split("@", 1)[0] == prefix:
                return email

    return unique[0]


def _deobfuscate_text(text: str) -> str:
    if not text:
        return text
    text = html_module.unescape(text)
    text = re.sub(r"\s*\[\s*at\s*\]\s*", "@", text, flags=re.I)
    text = re.sub(r"\s*\(\s*at\s*\)\s*", "@", text, flags=re.I)
    text = re.sub(r"\s*\[\s*dot\s*\]\s*", ".", text, flags=re.I)
    text = re.sub(r"\s*\(\s*dot\s*\)\s*", ".", text, flags=re.I)
    text = re.sub(r"\s+at\s+", "@", text, flags=re.I)
    text = re.sub(r"\s+dot\s+", ".", text, flags=re.I)
    return text


def _decode_cfemail(encoded: str) -> str:
    try:
        key = int(encoded[:2], 16)
        return "".join(
            chr(int(encoded[i : i + 2], 16) ^ key) for i in range(2, len(encoded), 2)
        )
    except (ValueError, IndexError):
        return ""


def _emails_from_json_ld(soup: BeautifulSoup) -> list[str]:
    found: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key.lower() == "email" and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        walk(data)

    return found


def _collect_candidates_from_html(content: bytes, website_url: str) -> list[str]:
    if not content:
        return []

    hostname = _website_hostname(website_url)
    candidates: list[str] = []

    # Scan head + tail — footer emails survive truncation on huge pages.
    if len(content) > HEAD_SCAN_BYTES + TAIL_SCAN_BYTES:
        scan_blob = content[:HEAD_SCAN_BYTES] + content[-TAIL_SCAN_BYTES:]
    else:
        scan_blob = content

    raw_html = _deobfuscate_text(scan_blob.decode("utf-8", errors="ignore"))
    candidates.extend(EMAIL_RE.findall(raw_html))

    try:
        soup = BeautifulSoup(scan_blob, "html.parser")

        for tag in soup.find_all(attrs={"data-cfemail": True}):
            decoded = _decode_cfemail(tag["data-cfemail"])
            if decoded:
                candidates.append(decoded)

        for tag in soup.find_all(class_=re.compile(r"__cf_email__")):
            encoded = tag.get("data-cfemail") or tag.get_text(strip=True)
            if encoded:
                decoded = _decode_cfemail(encoded)
                if decoded:
                    candidates.append(decoded)

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if href.lower().startswith("mailto:"):
                mailto = href[7:].split("?")[0].strip()
                for part in mailto.split(","):
                    part = part.strip()
                    if part:
                        candidates.append(part)

        for tag in soup.find_all(["span", "div", "p", "li"]):
            for attr in ("data-email", "data-mail", "data-e-mail"):
                if tag.get(attr):
                    candidates.append(tag[attr])

        candidates.extend(_emails_from_json_ld(soup))

        page_text = _deobfuscate_text(soup.get_text(" ", strip=True))
        candidates.extend(EMAIL_RE.findall(page_text))
    except Exception:
        pass

    return candidates


def _extract_email_from_html(content: bytes, website_url: str) -> str:
    candidates = _collect_candidates_from_html(content, website_url)
    return _pick_best_email(candidates, _website_hostname(website_url))


def _discover_contact_urls(soup: BeautifulSoup, base_url: str, hostname: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "tel:", "javascript:", "mailto:")):
            continue
        label = f"{href} {(anchor.get_text() or '')}"
        if not CONTACT_LINK_RE.search(label):
            continue
        full = urljoin(base_url, href)
        if not _same_site(full, hostname) or full in seen:
            continue
        seen.add(full)
        found.append(full)

    return found[:6]


def _fetch_page(url: str) -> tuple[bytes, str]:
    """
    Fetch HTML for email extraction. Returns (content, final_url).
    Tries URL variants on SSL/connection errors.
    """
    last_error = None
    for candidate in _url_variants(url):
        try:
            response = requests.get(
                candidate,
                timeout=(4, 8),  # connect, read — dead hosts fail fast
                headers=FETCH_HEADERS,
                stream=True,
                allow_redirects=True,
            )
            final_url = response.url

            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and "text/html" not in content_type and "application/xhtml" not in content_type:
                continue

            if response.status_code >= 400 and not response.content:
                continue

            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                chunks.append(chunk)
                total += len(chunk)
                if total >= MAX_PAGE_BYTES:
                    break

            content = b"".join(chunks)
            if len(content) < 80:
                continue

            # Bot walls / captcha pages
            lowered = content[:2000].lower()
            if b"sgcaptcha" in lowered or b"captcha" in lowered and b"refresh" in lowered:
                continue

            return content, final_url
        except requests.RequestException as exc:
            last_error = exc
            continue

    if last_error:
        logger.debug("fetch failed for %s: %s", url, last_error)
    return b"", url


def find_business_email(
    website_url: str,
    try_contact_pages: bool = True,
    homepage_content: bytes | None = None,
    homepage_final_url: str | None = None,
) -> str:
    """Best-effort email discovery: homepage, discovered contact links, common paths."""
    base_url = _normalize_website_url(website_url)
    if not base_url:
        return ""

    hostname = _website_hostname(base_url)
    urls_to_try: list[str] = []
    seen_urls: set[str] = set()

    def add_url(u: str):
        u = u.split("#")[0].rstrip("/") or u
        if u and u not in seen_urls:
            seen_urls.add(u)
            urls_to_try.append(u)

    if homepage_content:
        content = homepage_content
        final_url = homepage_final_url or base_url
    else:
        content, final_url = _fetch_page(base_url)

    add_url(final_url)

    if content:
        email = _extract_email_from_html(content, final_url)
        if email:
            return email

        if try_contact_pages:
            soup = BeautifulSoup(content[:HEAD_SCAN_BYTES], "html.parser")
            for link in _discover_contact_urls(soup, final_url, hostname):
                add_url(link)

    if try_contact_pages:
        for path in CONTACT_PATHS:
            add_url(urljoin(final_url.rstrip("/") + "/", path.lstrip("/")))

    for url in urls_to_try[1:]:
        page_content, page_final = _fetch_page(url)
        if not page_content:
            continue
        email = _extract_email_from_html(page_content, page_final)
        if email:
            return email

    return ""
