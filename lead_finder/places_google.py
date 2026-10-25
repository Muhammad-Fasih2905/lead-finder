"""Optional Google Places (New) source. Needs your own API key.

Google's data has far better phone and website coverage than OpenStreetMap. A single
text search returns the phone number and website, so no extra lookups are needed.
Google offers a monthly free usage allowance on Places; check current pricing and
the Places terms (which limit how long results may be cached) before relying on it.
"""
from __future__ import annotations

import math
import re

import requests

from .config import REQUEST_TIMEOUT_SECONDS
from .contacts import format_phone
from .osm_client import blank_lead

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.location",
    "places.nationalPhoneNumber", "places.internationalPhoneNumber", "places.websiteUri",
    "places.googleMapsUri", "places.primaryTypeDisplayName", "places.rating", "places.userRatingCount",
    "places.businessStatus", "nextPageToken",
])


def search_google_places(api_key: str, niche: str, location: str, geo: dict, radius_km: int,
                         max_results: int, region: str | None = None) -> list[dict]:
    leads: list[dict] = []
    page_token = None
    for _ in range(math.ceil(min(max_results, 60) / 20)):
        body: dict = {
            "textQuery": f"{niche} in {location}",
            "pageSize": 20,
            "locationBias": {"circle": {
                "center": {"latitude": geo["lat"], "longitude": geo["lon"]},
                "radius": float(min(radius_km, 50) * 1000),
            }},
        }
        if page_token:
            body["pageToken"] = page_token
        response = requests.post(
            SEARCH_URL, json=body, timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELD_MASK, "Content-Type": "application/json"},
        )
        if response.status_code != 200:
            try:
                message = response.json().get("error", {}).get("message", response.text[:200])
            except ValueError:
                message = response.text[:200]
            raise RuntimeError(f"Google Places said: {message}")
        data = response.json()
        for place in data.get("places", []):
            if place.get("businessStatus") in {"CLOSED_PERMANENTLY"}:
                continue
            lead = blank_lead()
            phone_raw = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber") or ""
            phone = format_phone(phone_raw, region, strict=False) if phone_raw else ""
            loc = place.get("location") or {}
            site = place.get("websiteUri", "")
            lead.update({
                "lead_id": f"google/{place.get('id')}",
                "business_name": (place.get("displayName") or {}).get("text", ""),
                "category": (place.get("primaryTypeDisplayName") or {}).get("text", ""),
                "business_phone": phone,
                "phone_source": "Google Places" if phone else "",
                "website": site,
                "website_source": "Google Places" if site else "",
                "address": place.get("formattedAddress", ""),
                "map_url": place.get("googleMapsUri", ""),
                "source_url": place.get("googleMapsUri", ""),
                "latitude": loc.get("latitude", ""),
                "longitude": loc.get("longitude", ""),
                "rating": f"{place['rating']} ({place.get('userRatingCount', 0)})" if place.get("rating") else "",
            })
            if lead["business_name"]:
                leads.append(lead)
        page_token = data.get("nextPageToken")
        if not page_token or len(leads) >= max_results:
            break
    return leads[:max_results]


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _km(a: dict, b: dict) -> float:
    try:
        la1, lo1, la2, lo2 = (float(x) for x in (a["latitude"], a["longitude"], b["latitude"], b["longitude"]))
    except (TypeError, ValueError):
        return 9999.0
    dx = (lo2 - lo1) * math.cos(math.radians((la1 + la2) / 2)) * 111.32
    dy = (la2 - la1) * 110.57
    return math.hypot(dx, dy)


def merge_sources(primary: list[dict], secondary: list[dict]) -> list[dict]:
    """Add OSM leads to Google leads; where they are the same business, fill gaps in the Google lead."""
    merged = [dict(p) for p in primary]
    for other in secondary:
        match = next((m for m in merged if _norm(m["business_name"]) == _norm(other["business_name"])
                      and _km(m, other) < 0.3), None)
        if match is None:
            merged.append(dict(other))
            continue
        for key, value in other.items():
            if value and not match.get(key):
                match[key] = value
    return merged
