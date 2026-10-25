"""Read a business's own public website for phone, email, socials and a decision-maker.

Polite by design: it observes robots.txt, only visits public HTTP(S) hosts, stays on
the business's own domain, never logs in and never touches social-network pages.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .config import (
    ENRICH_WORKERS,
    MAX_REDIRECTS,
    MAX_WEBSITE_PAGES,
    USER_AGENT,
    WEBSITE_TIMEOUT_SECONDS,
)
from .contacts import (
    EMAIL_RE,
    clean_email,
    clean_person_name,
    decode_cfemail,
    deobfuscate,
    format_phone,
    phones_in_text,
    role_of,
)

SOCIAL_DOMAINS = {
    "linkedin": ("linkedin.com",),
    "instagram": ("instagram.com",),
    "facebook": ("facebook.com", "fb.com"),
    "youtube": ("youtube.com",),
    "x": ("twitter.com", "x.com"),
    "tiktok": ("tiktok.com",),
}
# Link text / URL fragments that suggest a page lists contact details or people.
PAGE_HINTS = re.compile(
    r"contact|about|team|staff|people|leadership|management|our-story|who-we-are|meet|doctor|dentist|"
    r"physician|attorney|lawyer|founder|owner|principal|provider|practitioner|company|why-us",
    re.I,
)
FALLBACK_PATHS = ["contact", "contact-us", "about", "about-us", "team", "our-team", "meet-the-team"]
BLOCK_TAGS = ["p", "div", "li", "ul", "ol", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "td", "th",
              "section", "article", "header", "footer", "figure", "figcaption", "dd", "dt", "address", "blockquote"]
SEPARATORS = r"\s*[,|–—•·:/\-]\s*|\s+\(\s*|\s+–\s+|\s+-\s+"
NAME = r"((?:Dr\.?\s+)?[A-Z][A-Za-z'’\-]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z'’\-]+){1,2})"
BY_RE = re.compile(
    r"\b(?:founded|owned|started|established|created|run|operated|led|headed)(?:\s+and\s+\w+)?\s+by\s+" + NAME
)
DR_RE = re.compile(r"\bDr\.?\s+([A-Z][a-z'’\-]+(?:\s+[A-Z]\.)?(?:\s+[A-Z][a-z'’\-]+)+)")


# ----------------------------------------------------------------------------- safety


def _is_public_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        host = parsed.hostname.lower()
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            pass
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        return bool(infos) and all(ipaddress.ip_address(i[4][0]).is_global for i in infos)
    except (ValueError, OSError):
        return False


def _site_key(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


class _Fetcher:
    """One session per website: follows a few redirects, re-checking every hop."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
            "Accept-Language": "en;q=0.9",
        })
        self.robots: dict[str, RobotFileParser | bool] = {}

    def get(self, url: str, allowed_site: str | None = None) -> requests.Response | None:
        for _ in range(MAX_REDIRECTS + 1):
            if not _is_public_http_url(url):
                return None
            if allowed_site and _site_key(url) != allowed_site:
                return None
            try:
                response = self.session.get(url, timeout=WEBSITE_TIMEOUT_SECONDS, allow_redirects=False, stream=True)
            except requests.RequestException:
                return None
            if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                response.close()
                if not location:
                    return None
                url = urljoin(url, location)
                continue
            response.url = url
            return response
        return None

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self.robots:
            parser: RobotFileParser | bool = True
            response = self.get(origin + "/robots.txt", allowed_site=_site_key(url))
            if response is None:
                parser = True  # unreachable robots.txt: be tolerant, pages themselves are still fetched politely
            elif response.status_code in (401, 403) or response.status_code >= 500:
                parser = False
            elif response.status_code == 200:
                rp = RobotFileParser()
                rp.parse(response.text[:200_000].splitlines())
                parser = rp
            if response is not None:
                response.close()
            self.robots[origin] = parser
        rules = self.robots[origin]
        return rules if isinstance(rules, bool) else rules.can_fetch(USER_AGENT, url)

    def page(self, url: str, site: str) -> tuple[str, BeautifulSoup] | None:
        if not self.allowed(url):
            return None
        response = self.get(url, allowed_site=site)
        if response is None:
            return None
        try:
            if response.status_code >= 400 or "html" not in response.headers.get("Content-Type", "").lower():
                return None
            raw = response.raw.read(1_500_000, decode_content=True)
            encoding = response.encoding or "utf-8"
            return response.url, BeautifulSoup(raw.decode(encoding, errors="replace"), "lxml")
        except Exception:
            return None
        finally:
            response.close()


# ----------------------------------------------------------------------------- extraction


def _walk_jsonld(value, relation: bool = False):
    """Yield (name, title, phone, email) hints from JSON-LD blocks."""
    if isinstance(value, list):
        for child in value:
            yield from _walk_jsonld(child, relation)
        return
    if not isinstance(value, dict):
        return
    raw_type = value.get("@type", "")
    types = {raw_type} if isinstance(raw_type, str) else set(raw_type or [])
    if "Person" in types:
        name = value.get("name")
        job = value.get("jobTitle", "")
        if isinstance(job, dict):
            job = job.get("name", "")
        job = job if isinstance(job, str) else ""
        if name and isinstance(name, str) and (relation or role_of(job)[0]):
            yield "person", name, job or ("Founder" if relation else "")
    for key in ("telephone", "email"):
        if isinstance(value.get(key), str):
            yield key, value[key], ""
    for key, child in value.items():
        yield from _walk_jsonld(child, relation or key.lower() in {"founder", "founders", "owner", "employee", "member", "author", "leader"})


def _jsonld_blocks(soup: BeautifulSoup):
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            yield json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue


def _lines(soup: BeautifulSoup) -> list[str]:
    """Visible text split into lines at block boundaries (so 'Dr. <b>Jane</b> Smith' stays together)."""
    for tag in soup(["script", "style", "noscript", "svg", "template", "iframe"]):
        tag.decompose()
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    text = soup.get_text(" ")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.split("\n")]
    return [ln for ln in lines if ln]


def _candidate(name: str, title: str, confidence: str, url: str, bonus: int = 0) -> dict | None:
    cleaned = clean_person_name(name)
    if not cleaned:
        return None
    priority, label = role_of(title)
    if not priority and not cleaned.startswith("Dr."):
        return None
    shown_title = title.strip(" ,-–—|:") if title else ""
    if not shown_title or len(shown_title) > 70:
        shown_title = label or "Practitioner (listed as Dr.)"
    weight = {"High": 300, "Medium": 200, "Low": 100}[confidence] + (priority or 40) + bonus
    return {"name": cleaned, "title": shown_title, "confidence": confidence, "url": url, "weight": weight}


def find_people(lines: list[str], url: str) -> list[dict]:
    """Find 'Name + decision-making title' pairs in page text."""
    found: list[dict] = []

    def add(c: dict | None) -> None:
        if c:
            found.append(c)

    for i, line in enumerate(lines):
        if len(line) > 200:
            # Long prose: only look for 'founded by <Name>' sentences.
            for m in BY_RE.finditer(line):
                add(_candidate(m.group(1), "Founder", "Medium", url))
            continue
        for m in BY_RE.finditer(line):
            add(_candidate(m.group(1), "Founder", "Medium", url))
        priority, _ = role_of(line)
        if priority:
            # "Jane Smith, Owner" / "Owner: Jane Smith" / "Jane Smith - CEO"
            parts = [p for p in re.split(SEPARATORS, line) if p]
            person = [p for p in parts if clean_person_name(p)]
            roles = [p for p in parts if role_of(p)[0]]
            for p in person:
                for r in roles:
                    if p is not r:
                        add(_candidate(p, r, "Medium", url, bonus=10))
            m = re.match(NAME + r"\s*(?:is|,)?\s*(?:the|our|a)?\s*([A-Za-z \-&]{3,50})$", line)
            if m and role_of(m.group(2))[0]:
                add(_candidate(m.group(1), m.group(2), "Medium", url, bonus=5))
            # Title alone on a line -> the name is the line before (most common) or after.
            if not person and len(line) <= 60:
                for j, bonus in ((i - 1, 8), (i + 1, 0)):
                    if 0 <= j < len(lines):
                        add(_candidate(lines[j], line, "Medium", url, bonus=bonus))
    return found


def _dr_mentions(lines: list[str], url: str) -> list[dict]:
    names: dict[str, int] = {}
    for line in lines:
        if len(line) > 300:
            continue
        for m in DR_RE.finditer(line):
            names[m.group(1)] = names.get(m.group(1), 0) + 1
    out = []
    for name, count in sorted(names.items(), key=lambda kv: -kv[1])[:3]:
        c = _candidate("Dr. " + name, "", "Low", url, bonus=min(count, 5))
        if c:
            out.append(c)
    return out


def _socials(soup: BeautifulSoup) -> dict[str, str]:
    found: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        host = (urlparse(href).hostname or "").lower()
        if not host:
            continue
        host = host[4:] if host.startswith("www.") else host
        path = urlparse(href).path.strip("/")
        for key, domains in SOCIAL_DOMAINS.items():
            if any(host == d or host.endswith("." + d) for d in domains):
                # skip share/intent links
                if path and not re.match(r"(share|sharer|intent|dialog|plugins)", path, re.I):
                    found.setdefault(key, href)
    return found


def _discover_pages(soup: BeautifulSoup, base_url: str, site: str) -> list[str]:
    scored: list[tuple[int, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full, _ = urldefrag(urljoin(base_url, href))
        if _site_key(full) != site or not full.startswith(("http://", "https://")):
            continue
        path = urlparse(full).path.lower()
        if re.search(r"\.(pdf|jpg|jpeg|png|gif|zip|docx?)$", path):
            continue
        text = (a.get_text(" ", strip=True) or "")[:60]
        if PAGE_HINTS.search(path) or PAGE_HINTS.search(text):
            score = 3 if re.search(r"contact", path + text, re.I) else 2 if re.search(r"team|staff|doctor|people|leader", path + text, re.I) else 1
            scored.append((score, full))
    scored.sort(key=lambda s: -s[0])
    seen, out = set(), []
    for _, url in scored:
        key = url.rstrip("/")
        if key not in seen:
            seen.add(key)
            out.append(url)
    return out


# ----------------------------------------------------------------------------- main entry


def enrich_lead(lead: dict, region: str | None = None) -> dict:
    """Return a copy of `lead` filled in from the business's public website."""
    enriched = dict(lead)
    site_url = (lead.get("website") or "").strip()
    if not site_url:
        enriched["website_checked"] = "No website to check"
        return enriched
    if not re.match(r"^https?://", site_url, re.I):
        site_url = "https://" + site_url

    fetcher = _Fetcher()
    first = fetcher.page(site_url, site=_site_key(site_url))
    if first is None and site_url.startswith("https://"):
        site_url = "http://" + site_url[len("https://"):]
        first = fetcher.page(site_url, site=_site_key(site_url))
    if first is None:
        enriched["website_checked"] = "Website unreachable or blocked robots.txt"
        return enriched

    home_url, home_soup = first
    site = _site_key(home_url)
    to_visit = _discover_pages(home_soup, home_url, site)
    root = f"{urlparse(home_url).scheme}://{urlparse(home_url).netloc}/"
    to_visit += [urljoin(root, path) for path in FALLBACK_PATHS]

    pages: list[tuple[str, BeautifulSoup]] = [(home_url, home_soup)]
    visited = {home_url.rstrip("/")}
    for url in to_visit:
        if len(pages) >= MAX_WEBSITE_PAGES:
            break
        key = url.rstrip("/")
        if key in visited:
            continue
        visited.add(key)
        result = fetcher.page(url, site)
        if result:
            pages.append(result)

    tel_phones: list[str] = []
    ld_phones: list[str] = []
    text_phones: list[str] = []
    emails: list[str] = []
    socials: dict[str, str] = {}
    people: list[dict] = []
    all_lines: list[tuple[str, list[str]]] = []

    for url, soup in pages:
        # structured data first (before _lines() strips scripts)
        for block in _jsonld_blocks(soup):
            for kind, value, title in _walk_jsonld(block):
                if kind == "telephone":
                    p = format_phone(value, region)
                    if p and p not in ld_phones:
                        ld_phones.append(p)
                elif kind == "email":
                    e = clean_email(value)
                    if e:
                        emails.append(e)
                elif kind == "person":
                    c = _candidate(value, title, "High", url)
                    if c:
                        people.append(c)
        for a in soup.select('a[href^="tel:"]'):
            p = format_phone(a["href"].split(":", 1)[-1].split("?")[0].strip(), region)
            if p and p not in tel_phones:
                tel_phones.append(p)
        for a in soup.select('a[href^="mailto:"]'):
            e = clean_email(a["href"].split(":", 1)[-1].split("?", 1)[0])
            if e:
                emails.append(e)
        for tag in soup.select("[data-cfemail]"):
            e = clean_email(decode_cfemail(tag.get("data-cfemail", "")))
            if e:
                emails.append(e)
        for a in soup.select('a[href*="/cdn-cgi/l/email-protection#"]'):
            e = clean_email(decode_cfemail(a["href"].split("#", 1)[-1]))
            if e:
                emails.append(e)
        socials.update({k: v for k, v in _socials(soup).items() if k not in socials})

        lines = _lines(soup)
        page_text = deobfuscate(" \n ".join(lines))
        emails.extend(e for e in (clean_email(m.group(0)) for m in EMAIL_RE.finditer(page_text)) if e)
        for p in phones_in_text(" \n ".join(lines), region):
            if p not in text_phones:
                text_phones.append(p)
        people.extend(find_people(lines, url))
        all_lines.append((url, lines))

    # --- Phones: explicit tel: links are the most reliable, then structured data, then page text.
    phones: list[str] = []
    for p in tel_phones + ld_phones + text_phones:
        if p not in phones:
            phones.append(p)
    if not people:
        for url, lines in all_lines:
            people.extend(_dr_mentions(lines, url))

    # --- Emails: prefer addresses on the business's own domain.
    unique_emails = list(dict.fromkeys(emails))
    unique_emails.sort(key=lambda e: 0 if e.split("@")[-1].endswith(site) or site.endswith(e.split("@")[-1]) else 1)

    if phones and not enriched.get("business_phone"):
        enriched["business_phone"] = ", ".join(phones[:3])
        enriched["phone_source"] = "Business website"
    if unique_emails and not enriched.get("email"):
        enriched["email"] = ", ".join(unique_emails[:3])
        enriched["email_status"] = "Found on website; deliverability not verified"
    if people and not enriched.get("decision_maker"):
        best = max(people, key=lambda c: c["weight"])
        enriched["decision_maker"] = best["name"]
        enriched["decision_maker_title"] = best["title"]
        enriched["decision_maker_confidence"] = best["confidence"]
        enriched["decision_maker_source"] = best["url"]
    for key in ("linkedin", "instagram", "facebook"):
        if not enriched.get(key) and socials.get(key):
            enriched[key] = socials[key]
    others = [socials[k] for k in ("youtube", "x", "tiktok") if socials.get(k)]
    if not enriched.get("other_social") and others:
        enriched["other_social"] = ", ".join(others)
    enriched["website"] = home_url if not lead.get("website") else lead["website"]
    enriched["website_checked"] = f"Read {len(pages)} page{'s' if len(pages) != 1 else ''}"
    return enriched


def enrich_leads(
    leads: list[dict],
    region: str | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """Enrich many leads in parallel. `progress(done, total)` is called from the calling thread."""
    results: list[dict | None] = [None] * len(leads)
    total = len(leads)
    if not total:
        return []
    with ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as pool:
        futures = {pool.submit(enrich_lead, lead, region): i for i, lead in enumerate(leads)}
        done = 0
        for future in as_completed(futures):
            i = futures[future]
            try:
                results[i] = future.result()
            except Exception:
                results[i] = {**leads[i], "website_checked": "Could not read website"}
            done += 1
            if progress:
                progress(done, total)
    return [r for r in results if r is not None]
