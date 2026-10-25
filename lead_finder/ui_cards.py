"""HTML rendering for lead cards and the KPI strip. Every value is escaped before display."""
from __future__ import annotations

from html import escape
from urllib.parse import quote_plus, urlparse

from .contacts import readiness_score

ICONS = {
    "phone": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FFB400" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/></svg>',
    "user": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
    "mail": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>',
    "globe": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',
    "pin": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg>',
}


def _s(value) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"nan", "none", "not found"} else text


def safe_url(url: str) -> str:
    url = _s(url).split(",")[0].strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url if urlparse(url).scheme in {"http", "https"} and urlparse(url).netloc else ""


def _tel(phone: str) -> str:
    return "tel:" + "".join(ch for ch in phone if ch.isdigit() or ch == "+")


def _pretty_site(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc.removeprefix("www.") + parsed.path).rstrip("/")


def lead_card(lead: dict) -> str:
    name = _s(lead.get("business_name")) or "Unnamed business"
    score = readiness_score(lead)
    tone = "" if score >= 70 else "mid" if score >= 40 else "low"
    area = _s(lead.get("address"))

    # ---- phone strip
    phones = [p.strip() for p in _s(lead.get("business_phone")).split(",") if p.strip()]
    if phones:
        more = f'<span class="more">+{len(phones) - 1} more</span>' if len(phones) > 1 else ""
        call = f'<a class="call" href="{escape(_tel(phones[0]))}" aria-label="Call {escape(name)}">{ICONS["phone"]}<span>{escape(phones[0])}</span>{more}</a>'
        alts = ""
        if len(phones) > 1:
            links = "".join(f'<a href="{escape(_tel(p))}">{escape(p)}</a>' for p in phones[1:])
            alts = f'<div class="alt-phones">{links}</div>'
    else:
        maps = f"https://www.google.com/maps/search/?api=1&query={quote_plus(name + ' ' + area)}"
        call = f'<div class="call none">{ICONS["phone"].replace("#FFB400", "#9AAFAA")}<span>No phone found</span><a href="{escape(maps)}" target="_blank" rel="noopener">Check on Google Maps</a></div>'
        alts = ""

    rows = []
    # ---- decision maker
    person = _s(lead.get("decision_maker"))
    if person:
        title = _s(lead.get("decision_maker_title"))
        conf = _s(lead.get("decision_maker_confidence"))
        src = safe_url(lead.get("decision_maker_source"))
        who = f'<a href="{escape(src)}" target="_blank" rel="noopener" class="who">{escape(person)}</a>' if src else f'<span class="who">{escape(person)}</span>'
        badge = f'<span class="conf {escape(conf)}" title="How sure we are this is a decision-maker">{escape(conf)}</span>' if conf in {"High", "Medium", "Low"} else ""
        sub = f'<div class="sub">{escape(title)}</div>' if title else ""
        rows.append(f'<div class="row">{ICONS["user"]}<div class="val">{who}{badge}{sub}</div></div>')
    else:
        q = quote_plus(f'"{name}" owner OR founder OR director {area.split(",")[-3] if area.count(",") >= 3 else ""}'.strip())
        rows.append(f'<div class="row missing">{ICONS["user"]}<div class="val">No decision-maker found <a href="https://www.google.com/search?q={q}" target="_blank" rel="noopener">Look up owner</a></div></div>')

    # ---- email
    emails = [e.strip() for e in _s(lead.get("email")).split(",") if e.strip()]
    if emails:
        extra = f' <span class="sub">+{len(emails) - 1} more</span>' if len(emails) > 1 else ""
        rows.append(f'<div class="row">{ICONS["mail"]}<div class="val"><a href="mailto:{escape(emails[0])}">{escape(emails[0])}</a>{extra}</div></div>')
    else:
        rows.append(f'<div class="row missing">{ICONS["mail"]}<div class="val">No email found</div></div>')

    # ---- website
    site = safe_url(lead.get("website"))
    if site:
        verify = ""
        if "verify" in _s(lead.get("website_source")).lower():
            verify = ' <span class="conf Medium" title="Found by web search. Check it is the right business.">verify</span>'
        rows.append(f'<div class="row">{ICONS["globe"]}<div class="val"><a href="{escape(site)}" target="_blank" rel="noopener">{escape(_pretty_site(site))}</a>{verify}</div></div>')
    else:
        rows.append(f'<div class="row missing">{ICONS["globe"]}<div class="val">No website found</div></div>')

    if area:
        rows.append(f'<div class="row missing">{ICONS["pin"]}<div class="val">{escape(area)}</div></div>')

    # ---- footer
    chips = []
    for key, label in (("linkedin", "LinkedIn"), ("facebook", "Facebook"), ("instagram", "Instagram")):
        url = safe_url(lead.get(key))
        if url:
            chips.append(f'<a class="soc" href="{escape(url)}" target="_blank" rel="noopener">{label}</a>')
    sources = []
    if _s(lead.get("phone_source")):
        sources.append(f'phone: {_s(lead.get("phone_source"))}')
    rating = _s(lead.get("rating"))
    if rating:
        chips.append(f'<span class="soc" style="background:var(--amber-soft);color:#8A5D00">★ {escape(rating)}</span>')
    src_url = safe_url(lead.get("source_url"))
    source_link = f'<a href="{escape(src_url)}" target="_blank" rel="noopener">source</a>' if src_url else ""
    foot = f'<div class="lead-foot">{"".join(chips)}<span class="src">{escape(" · ".join(sources))}{" · " if sources and source_link else ""}{source_link}</span></div>'

    cat = f'<span class="cat">{escape(_s(lead.get("category")))}</span>' if _s(lead.get("category")) else ""
    return (
        f'<article class="lead"><div class="lead-top"><div class="lead-title"><h3>{escape(name)}</h3>{cat}</div>'
        f'<div class="ring {tone}" style="--p:{score}" title="Contact readiness: {score} out of 100"><b>{score}</b></div></div>'
        f'{call}{alts}<div class="rows">{"".join(rows)}</div>{foot}</article>'
    )


def card_grid(leads: list[dict]) -> str:
    return '<div class="grid">' + "".join(lead_card(l) for l in leads) + "</div>"


def kpi_strip(leads: list[dict]) -> str:
    total = max(len(leads), 1)

    def count(key: str) -> int:
        return sum(1 for l in leads if _s(l.get(key)))

    items = [
        ("Businesses", len(leads), None, True),
        ("With phone", count("business_phone"), count("business_phone") / total, False),
        ("With website", count("website"), count("website") / total, False),
        ("With email", count("email"), count("email") / total, False),
        ("With decision-maker", count("decision_maker"), count("decision_maker") / total, False),
    ]
    out = []
    for label, num, frac, accent in items:
        pct = f'<span class="kpi-pct">{round(frac * 100)}%</span>' if frac is not None else ""
        bar = f'<div class="kpi-bar"><i style="width:{round((frac if frac is not None else 1) * 100)}%"></i></div>'
        out.append(f'<div class="kpi{" accent" if accent else ""}"><div class="kpi-top"><span class="kpi-num">{num}</span>{pct}</div><div class="kpi-label">{label}</div>{bar}</div>')
    return '<div class="kpis">' + "".join(out) + "</div>"
