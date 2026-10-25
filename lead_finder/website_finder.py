"""Find the official website of businesses that have none listed (free web-search fallback).

Uses DuckDuckGo's plain-HTML results page: one query per business, slowly, with a hard cap.
Matches are guesses based on name similarity, so they are labelled 'verify' in the app.
If the search engine starts refusing requests, the lookup stops cleanly instead of retrying.
"""
from __future__ import annotations

import re
import time
from typing import Callable
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .config import LOOKUP_DELAY_SECONDS, MAX_WEBSITE_LOOKUPS, USER_AGENT

SEARCH_URL = "https://html.duckduckgo.com/html/"
# Directories, maps and social sites are never a business's own website.
DIRECTORY_DOMAINS = (
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "tiktok.com", "youtube.com",
    "yelp.", "tripadvisor.", "yellowpages.", "mapquest.com", "google.", "bing.com", "maps.apple.com",
    "wikipedia.org", "foursquare.com", "bbb.org", "manta.com", "healthgrades.com", "zocdoc.com", "vitals.com",
    "opencare.com", "ratemds.com", "doctor.com", "webmd.com", "angi.com", "thumbtack.com", "houzz.com",
    "glassdoor.", "indeed.", "crunchbase.com", "zoominfo.com", "dnb.com", "cylex", "yell.com", "justdial.com",
    "pinterest.", "reddit.com", "ubereats.com", "doordash.com", "grubhub.com", "opentable.", "booking.com",
    "expedia.", "hotels.com", "agoda.com", "trustpilot.com", "nextdoor.com", "superpages.com", "chamberofcommerce.com",
)
STOP_TOKENS = {
    "the", "and", "of", "inc", "llc", "ltd", "co", "company", "group", "center", "centre", "clinic", "office",
    "offices", "dental", "dentistry", "dentist", "medical", "services", "service", "associates", "pllc", "pc",
    "family", "care", "health", "restaurant", "cafe", "salon", "studio", "shop", "store",
}


class SearchBlocked(RuntimeError):
    """The search engine refused further automated requests."""


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP_TOKENS and len(t) > 1]


def parse_results(html: str) -> list[tuple[str, str]]:
    """Return [(url, title)] from a DuckDuckGo HTML results page."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for a in soup.select("a.result__a"):
        href = a.get("href", "")
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
        elif href.startswith("//"):
            href = "https:" + href
        if href.startswith("http"):
            out.append((href, a.get_text(" ", strip=True)))
    return out


def pick_website(name: str, results: list[tuple[str, str]]) -> str:
    """Choose the result that looks like the business's own site, or ''."""
    wanted = _tokens(name)
    if not wanted:
        return ""
    best, best_score = "", 0.0
    for url, title in results[:8]:
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        if not host or any(d in host for d in DIRECTORY_DOMAINS):
            continue
        host_flat = re.sub(r"[^a-z0-9]", "", host.split(".")[0] if host.count(".") else host)
        in_host = sum(1 for t in wanted if t in host_flat) / len(wanted)
        title_tokens = set(_tokens(title))
        in_title = sum(1 for t in wanted if t in title_tokens) / len(wanted)
        score = in_host * 1.0 + in_title * 0.5
        if (in_host >= 0.5 or in_title >= 0.99) and score > best_score:
            best, best_score = f"{urlparse(url).scheme}://{urlparse(url).netloc}/", score
    return best


def find_websites(
    leads: list[dict],
    area_hint: str,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[list[dict], str]:
    """Fill in missing websites. Returns (leads, note) where note explains anything that stopped early."""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; " + USER_AGENT + ")", "Accept-Language": "en"})
    todo = [i for i, lead in enumerate(leads) if not lead.get("website")][:MAX_WEBSITE_LOOKUPS]
    out = [dict(l) for l in leads]
    note = ""
    for n, i in enumerate(todo, 1):
        lead = out[i]
        query = f'{lead["business_name"]} {area_hint}'.strip()
        try:
            response = session.post(SEARCH_URL, data={"q": query}, timeout=10)
        except requests.RequestException:
            note = "Web search could not be reached, so some websites were not looked up."
            break
        if response.status_code in (202, 403, 429) or "anomaly" in response.text[:5000].lower():
            note = "The free web search paused our lookups, so some websites were not found. Try again later or add a Google Places key."
            break
        site = pick_website(lead["business_name"], parse_results(response.text))
        if site:
            lead["website"] = site
            lead["website_source"] = "Web search (please verify)"
        if progress:
            progress(n, len(todo))
        time.sleep(LOOKUP_DELAY_SECONDS)
    skipped = sum(1 for l in leads if not l.get("website")) - len(todo)
    if not note and skipped > 0:
        note = f"Looked up {len(todo)} websites; {skipped} more were skipped to keep the web search polite."
    return out, note
