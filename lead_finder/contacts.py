"""Helpers for cleaning phone numbers, emails and person names, and for scoring leads."""
from __future__ import annotations

import re
from typing import Iterable

import phonenumbers
from phonenumbers import Leniency, PhoneNumberFormat, PhoneNumberMatcher

# ----------------------------------------------------------------------------- phones


def format_phone(raw: str, region: str | None = None, strict: bool = True) -> str:
    """Return an international-format number, or '' if it does not parse.

    With strict=False a possible-but-unverifiable number is accepted (used for
    numbers typed into OpenStreetMap, which are usually right but oddly formatted).
    """
    try:
        number = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return ""
    ok = phonenumbers.is_valid_number(number) or (not strict and phonenumbers.is_possible_number(number))
    return phonenumbers.format_number(number, PhoneNumberFormat.INTERNATIONAL) if ok else ""


def split_phone_field(raw: str, region: str | None = None) -> list[str]:
    """OSM allows several numbers separated by ';' or ','. Return cleaned numbers."""
    out: list[str] = []
    for part in re.split(r"[;,/]|\bor\b", raw or ""):
        part = part.strip()
        if not part:
            continue
        formatted = format_phone(part, region, strict=False)
        if formatted and formatted not in out:
            out.append(formatted)
    return out


def phones_in_text(text: str, region: str | None) -> list[str]:
    out: list[str] = []
    try:
        for match in PhoneNumberMatcher(text, region, leniency=Leniency.VALID, max_tries=200):
            before = text[max(0, match.start - 14):match.start].lower()
            if "fax" in before:  # fax numbers are not useful for sales calls
                continue
            formatted = phonenumbers.format_number(match.number, PhoneNumberFormat.INTERNATIONAL)
            if formatted not in out:
                out.append(formatted)
    except Exception:
        pass
    return out


# ----------------------------------------------------------------------------- emails

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
JUNK_EMAIL_PARTS = ("example.", "sentry", "wixpress", "domain.com", "email.com", "yourname", "your@", "@2x", "u003e")
JUNK_EMAIL_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")


def clean_email(value: str) -> str:
    value = (value or "").strip().strip(".,;:<>()[]\"'").lower()
    if not EMAIL_RE.fullmatch(value):
        return ""
    if any(part in value for part in JUNK_EMAIL_PARTS) or value.endswith(JUNK_EMAIL_SUFFIXES):
        return ""
    return value


def decode_cfemail(encoded: str) -> str:
    """Decode Cloudflare's 'email protection' hex string."""
    try:
        data = bytes.fromhex(encoded)
        key = data[0]
        return bytes(b ^ key for b in data[1:]).decode("utf-8")
    except (ValueError, IndexError, UnicodeDecodeError):
        return ""


def deobfuscate(text: str) -> str:
    """Turn 'name [at] site [dot] com' into 'name@site.com'."""
    text = re.sub(r"\s*[\[\(\{]\s*at\s*[\]\)\}]\s*", "@", text, flags=re.I)
    text = re.sub(r"\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*", ".", text, flags=re.I)
    return text


# ----------------------------------------------------------------------------- people

HONORIFICS = {"dr", "dr.", "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "prof", "prof."}
CREDENTIAL_RE = re.compile(
    r",?\s+(?:DDS|DMD|MD|DO|DVM|PhD|Esq\.?|CPA|MBA|JD|RN|NP|PA-C|FACS|DC|OD|PT|DPT|BDS|MBBS|FRCS|MSc|BSc)\b\.?",
    re.I,
)
# Words that mean "this is not a person's name".
NOT_NAME_WORDS = {
    "contact", "about", "team", "our", "us", "services", "service", "privacy", "policy", "terms", "home",
    "office", "clinic", "dental", "dentistry", "dentists", "medical", "health", "care", "center", "centre",
    "group", "company", "inc", "llc", "ltd", "limited", "corp", "corporation", "associates", "partners",
    "law", "legal", "firm", "studio", "salon", "shop", "store", "restaurant", "cafe", "hotel", "school",
    "welcome", "meet", "book", "call", "now", "today", "free", "new", "patients", "patient", "client",
    "clients", "appointment", "appointments", "hours", "location", "locations", "directions", "reviews",
    "testimonials", "gallery", "blog", "news", "careers", "jobs", "faq", "menu", "login", "sign", "read",
    "more", "learn", "view", "all", "the", "and", "for", "with", "from", "get", "your", "family", "cosmetic",
    "emergency", "general", "implants", "orthodontics", "pediatric", "business", "management", "executive",
    "officer", "president", "founder", "owner", "director", "manager", "chief", "head", "staff", "doctor",
    "doctors", "dentist", "lawyer", "attorney", "attorneys", "agent", "agents", "estate", "real", "property",
    "properties", "solutions", "services", "systems", "technologies", "technology", "digital", "global",
    "international", "national", "local", "city", "county", "state", "united", "america", "american",
}
_NAME_TOKEN = re.compile(r"^[A-Z][A-Za-z'’\-]*[a-z][A-Za-z'’\-]*$|^[A-Z]\.?$")

ROLE_PRIORITY: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"\b(co-?)?founder\b", re.I), 100, "Founder"),
    (re.compile(r"\bowner\b|\bproprietor\b", re.I), 100, "Owner"),
    (re.compile(r"\b(ceo|chief executive officer)\b", re.I), 95, "CEO"),
    (re.compile(r"\bmanaging (director|partner|principal)\b", re.I), 92, "Managing Director"),
    (re.compile(r"\bpresident\b", re.I), 90, "President"),
    (re.compile(r"\bprincipal\b", re.I), 88, "Principal"),
    (re.compile(r"\b(lead|head|chief|medical|managing) (dentist|doctor|physician|surgeon|veterinarian|attorney|lawyer)\b", re.I), 85, "Lead practitioner"),
    (re.compile(r"\bgeneral manager\b", re.I), 75, "General Manager"),
    (re.compile(r"\bpartner\b", re.I), 72, "Partner"),
    (re.compile(r"\bdirector\b", re.I), 70, "Director"),
    (re.compile(r"\bchief [a-z]+ officer\b", re.I), 70, "C-level"),
    (re.compile(r"\b(practice|office|operations|clinic|store|branch) manager\b", re.I), 60, "Manager"),
]


def role_of(text: str) -> tuple[int, str]:
    """Return (priority, label) of the strongest decision-making role in text, or (0, '')."""
    best = (0, "")
    for pattern, score, label in ROLE_PRIORITY:
        if pattern.search(text) and score > best[0]:
            best = (score, label)
    return best


def clean_person_name(text: str) -> str:
    """Return a tidy person name if `text` looks like one, else ''."""
    text = re.sub(r"\s+", " ", (text or "")).strip(" ,;:-–—|•·()[]\"'")
    text = CREDENTIAL_RE.sub("", text).strip(" ,.")
    if not text or len(text) > 48 or re.search(r"\d|@|https?:|/", text):
        return ""
    tokens = text.split()
    honorific = ""
    if tokens and tokens[0].lower() in HONORIFICS:
        honorific = tokens.pop(0).rstrip(".") + "."
    if not 2 <= len(tokens) <= 4:
        return ""
    if text.isupper():
        tokens = [t.capitalize() for t in tokens]
    for token in tokens:
        if token.lower().strip(".") in NOT_NAME_WORDS or not _NAME_TOKEN.match(token):
            return ""
    # at least two tokens must be real words, not just initials
    if sum(1 for t in tokens if len(t.strip(".")) > 1) < 2:
        return ""
    return " ".join(([honorific] if honorific else []) + tokens)


# ----------------------------------------------------------------------------- scoring

def readiness_score(lead: dict) -> int:
    """0-100 score for how ready a lead is to be contacted."""
    def has(key: str) -> bool:
        return bool(str(lead.get(key) or "").strip()) and str(lead.get(key)).strip().lower() not in {"not found", "nan"}

    score = 0
    score += 35 if has("business_phone") else 0
    score += 20 if has("website") else 0
    score += 15 if has("email") else 0
    if has("decision_maker"):
        score += {"High": 20, "Medium": 16}.get(str(lead.get("decision_maker_confidence")), 10)
    score += 5 if has("address") else 0
    score += 5 if any(has(k) for k in ("linkedin", "facebook", "instagram", "other_social")) else 0
    return min(score, 100)


def first_of(values: Iterable[str]) -> str:
    return next((v for v in values if v), "")
