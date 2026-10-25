"""Business search on OpenStreetMap (free, no API key).

One geocoding request and one Overpass query per submitted search.
"""
from __future__ import annotations

import re
import time
from typing import Any

import requests

from .config import CONTACT_EMAIL, NOMINATIM_URL, OVERPASS_URLS, REQUEST_TIMEOUT_SECONDS, USER_AGENT
from .contacts import clean_email, readiness_score, split_phone_field

# Small, explainable mapping from common niches to OpenStreetMap tags.
NICHE_TAGS: dict[str, list[tuple[str, str]]] = {
    "dentist": [("amenity", "dentist"), ("healthcare", "dentist")],
    "dental clinic": [("amenity", "dentist"), ("healthcare", "dentist")],
    "dental": [("amenity", "dentist"), ("healthcare", "dentist")],
    "orthodontist": [("healthcare", "dentist"), ("amenity", "dentist")],
    "doctor": [("amenity", "doctors"), ("healthcare", "doctor")],
    "medical clinic": [("amenity", "clinic"), ("healthcare", "clinic")],
    "clinic": [("amenity", "clinic"), ("healthcare", "clinic")],
    "hospital": [("amenity", "hospital")],
    "pharmacy": [("amenity", "pharmacy")],
    "physiotherapist": [("healthcare", "physiotherapist")],
    "optician": [("shop", "optician")],
    "restaurant": [("amenity", "restaurant")],
    "cafe": [("amenity", "cafe")],
    "coffee shop": [("amenity", "cafe")],
    "bar": [("amenity", "bar"), ("amenity", "pub")],
    "law firm": [("office", "lawyer")],
    "lawyer": [("office", "lawyer")],
    "real estate": [("office", "estate_agent")],
    "real estate agent": [("office", "estate_agent")],
    "insurance": [("office", "insurance")],
    "software company": [("office", "it"), ("office", "company")],
    "software": [("office", "it"), ("office", "company")],
    "it company": [("office", "it"), ("office", "company")],
    "marketing agency": [("office", "advertising"), ("office", "company")],
    "accountant": [("office", "accountant")],
    "accounting firm": [("office", "accountant")],
    "gym": [("leisure", "fitness_centre")],
    "fitness center": [("leisure", "fitness_centre")],
    "yoga": [("leisure", "fitness_centre"), ("sport", "yoga")],
    "salon": [("shop", "hairdresser"), ("shop", "beauty")],
    "hair salon": [("shop", "hairdresser")],
    "barber": [("shop", "hairdresser")],
    "spa": [("leisure", "spa"), ("shop", "beauty")],
    "hotel": [("tourism", "hotel")],
    "bakery": [("shop", "bakery")],
    "school": [("amenity", "school")],
    "plumber": [("craft", "plumber")],
    "electrician": [("craft", "electrician")],
    "hvac": [("craft", "hvac")],
    "roofing": [("craft", "roofer")],
    "car repair": [("shop", "car_repair")],
    "auto repair": [("shop", "car_repair")],
    "car dealer": [("shop", "car")],
    "photographer": [("office", "photographer"), ("craft", "photographer")],
    "construction company": [("office", "construction_company"), ("craft", "builder")],
    "daycare": [("amenity", "kindergarten")],
    "kindergarten": [("amenity", "kindergarten")],
    "veterinarian": [("amenity", "veterinary")],
    "vet": [("amenity", "veterinary")],
    "supermarket": [("shop", "supermarket")],
    "clothing store": [("shop", "clothes")],
    "furniture store": [("shop", "furniture")],
    "jewelry": [("shop", "jewelry")],
}


def _headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT, "Accept": "application/json"}


def geocode_location(location: str) -> dict[str, Any]:
    """Resolve a location once; do not call this on every keystroke."""
    if not CONTACT_EMAIL or "replace-with-your-email" in CONTACT_EMAIL:
        raise ValueError("Open lead_finder/config.py and set CONTACT_EMAIL to an address you control before searching.")
    response = requests.get(
        NOMINATIM_URL,
        params={"q": location, "format": "jsonv2", "limit": 1, "addressdetails": 1},
        headers=_headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f"Could not find this location: {location}")
    first = data[0]
    return {
        "lat": float(first["lat"]),
        "lon": float(first["lon"]),
        "display_name": first.get("display_name", location),
        "country_code": (first.get("address", {}).get("country_code") or "").upper() or None,
    }


def _matching_tag_pairs(niche: str) -> list[tuple[str, str]]:
    normalized = re.sub(r"\s+", " ", niche.strip().lower())
    if normalized in NICHE_TAGS:
        return NICHE_TAGS[normalized]
    for key, pairs in sorted(NICHE_TAGS.items(), key=lambda item: len(item[0]), reverse=True):
        if key in normalized:
            return pairs
    return []


def build_overpass_query(niche: str, lat: float, lon: float, radius_km: int) -> str:
    """Build a bounded query. Unknown niches use name matching, not a wide crawl."""
    radius_m = max(1000, min(int(radius_km), 25) * 1000)
    lat_s, lon_s = f"{lat:.6f}", f"{lon:.6f}"
    selectors: list[str] = []
    tag_pairs = _matching_tag_pairs(niche)
    if tag_pairs:
        for key, value in tag_pairs:
            selectors.append(f'nwr(around:{radius_m},{lat_s},{lon_s})["{key}"="{value}"];')
    else:
        safe_niche = re.sub(r"[^a-zA-Z0-9 &.-]", "", niche.strip())[:50]
        if not safe_niche:
            raise ValueError("Enter a valid niche, such as Dentist or Software Company.")
        escaped = re.escape(safe_niche).replace("/", r"\/")
        selectors.append(f'nwr(around:{radius_m},{lat_s},{lon_s})["name"~"{escaped}",i];')
    return "[out:json][timeout:25];\n(" + "\n".join(selectors) + "\n);\nout center tags 500;"


def _first_tag(tags: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = tags.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _social_url(tags: dict[str, Any], *keys: str) -> str:
    value = _first_tag(tags, *keys)
    if not value:
        return ""
    if value.startswith("//"):
        return "https:" + value
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value.lstrip("@")
    return value


def blank_lead() -> dict[str, Any]:
    return {
        "lead_id": "", "business_name": "", "category": "",
        "decision_maker": "", "decision_maker_title": "", "decision_maker_confidence": "", "decision_maker_source": "",
        "business_phone": "", "phone_source": "", "email": "", "email_status": "",
        "website": "", "website_source": "", "linkedin": "", "instagram": "", "facebook": "", "other_social": "",
        "address": "", "map_url": "", "source_url": "", "latitude": "", "longitude": "",
        "website_checked": "", "rating": "",
    }


def normalize_element(element: dict[str, Any], region: str | None = None) -> dict[str, Any] | None:
    tags = element.get("tags") or {}
    name = _first_tag(tags, "name", "official_name", "brand")
    if not name:
        return None

    element_type = element.get("type", "node")
    element_id = element.get("id")
    point = element if "lat" in element and "lon" in element else element.get("center", {})
    lat, lon = point.get("lat"), point.get("lon")
    map_url = (
        f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}"
        if lat is not None and lon is not None
        else f"https://www.openstreetmap.org/{element_type}/{element_id}"
    )
    address = ", ".join(p for p in [
        _first_tag(tags, "addr:housenumber"), _first_tag(tags, "addr:street"),
        _first_tag(tags, "addr:city", "addr:town", "addr:suburb"), _first_tag(tags, "addr:state"),
        _first_tag(tags, "addr:postcode"), _first_tag(tags, "addr:country"),
    ] if p)
    category = next((f"{tags[k]}".replace("_", " ").title() for k in
                     ("amenity", "healthcare", "office", "shop", "craft", "tourism", "leisure") if tags.get(k)), "")

    website = _first_tag(tags, "contact:website", "website", "url", "operator:website")
    if website and not re.match(r"^https?://", website, re.I):
        website = "https://" + website

    phone_raw = ";".join(filter(None, (
        _first_tag(tags, "contact:phone"), _first_tag(tags, "phone"),
        _first_tag(tags, "contact:mobile"), _first_tag(tags, "mobile"),
        _first_tag(tags, "phone:mobile"), _first_tag(tags, "contact:whatsapp"),
    )))
    phones = split_phone_field(phone_raw, region) if phone_raw else []
    if phone_raw and not phones:
        phones = [phone_raw.split(";")[0].strip()]
    email = clean_email(_first_tag(tags, "contact:email", "email"))
    person = _first_tag(tags, "contact:person", "owner")

    lead = blank_lead()
    lead.update({
        "lead_id": f"osm/{element_type}/{element_id}",
        "business_name": name,
        "category": category,
        "business_phone": ", ".join(phones[:3]),
        "phone_source": "OpenStreetMap" if phones else "",
        "email": email,
        "email_status": "Listed on OpenStreetMap; deliverability not verified" if email else "",
        "website": website,
        "website_source": "OpenStreetMap" if website else "",
        "decision_maker": person,
        "decision_maker_title": "Listed on OpenStreetMap" if person else "",
        "decision_maker_confidence": "Medium" if person else "",
        "decision_maker_source": f"https://www.openstreetmap.org/{element_type}/{element_id}" if person else "",
        "linkedin": _social_url(tags, "contact:linkedin", "linkedin"),
        "instagram": _social_url(tags, "contact:instagram", "instagram"),
        "facebook": _social_url(tags, "contact:facebook", "facebook"),
        "other_social": _social_url(tags, "contact:youtube", "contact:twitter", "contact:x", "contact:tiktok"),
        "address": address,
        "map_url": map_url,
        "source_url": f"https://www.openstreetmap.org/{element_type}/{element_id}",
        "latitude": lat if lat is not None else "",
        "longitude": lon if lon is not None else "",
    })
    return lead


def _run_overpass(query: str) -> dict[str, Any]:
    """Try every public Overpass server, twice. Any server error or bad reply moves on to the next one."""
    last_error = "no response"
    for attempt in range(2):
        for url in OVERPASS_URLS:
            try:
                response = requests.post(
                    url, data={"data": query},
                    headers={**_headers(), "Content-Type": "application/x-www-form-urlencoded"},
                    timeout=REQUEST_TIMEOUT_SECONDS + 15,
                )
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code} from {url.split('/')[2]}"
                    continue
                data = response.json()
                if "elements" not in data:  # e.g. a 'runtime error: timeout' reply
                    last_error = data.get("remark", "incomplete reply")[:120]
                    continue
                return data
            except (requests.RequestException, ValueError) as exc:
                last_error = f"{type(exc).__name__} from {url.split('/')[2]}"
        if attempt == 0:
            time.sleep(3)
    raise RuntimeError(
        f"The free OpenStreetMap servers are overloaded right now ({last_error}). "
        "Wait a minute and press Find leads again, or try a smaller radius."
    )


def search_businesses(niche: str, location: str, radius_km: int, max_results: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Geocode, run one Overpass query, and return (leads, geo). Leads with contact details come first."""
    geo = geocode_location(location)
    payload = _run_overpass(build_overpass_query(niche, geo["lat"], geo["lon"], radius_km))
    unique: dict[str, dict[str, Any]] = {}
    for element in payload.get("elements", []):
        lead = normalize_element(element, geo.get("country_code"))
        if lead:
            unique[lead["lead_id"]] = lead
    results = sorted(unique.values(), key=lambda r: (-readiness_score(r), r["business_name"].lower()))
    return results[: max(1, max_results)], geo