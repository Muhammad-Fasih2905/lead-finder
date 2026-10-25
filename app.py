from __future__ import annotations

import utils.clients
import utils.http_session
import utils.transport
import utils.session
import pandas as pd
import streamlit as st

from lead_finder.config import APP_NAME, APP_VERSION, DEFAULT_RADIUS_KM, GOOGLE_PLACES_API_KEY, MAX_RADIUS_KM
from lead_finder.contacts import readiness_score
from lead_finder.export import to_csv_bytes, to_excel_bytes
from lead_finder.osm_client import geocode_location, search_businesses
from lead_finder.places_google import merge_sources, search_google_places
from lead_finder.storage import STATUSES, delete_all_leads, load_leads, save_leads, update_team_fields
from lead_finder.ui_cards import ICONS, card_grid, kpi_strip, lead_card
from lead_finder.ui_style import CSS
from lead_finder.website_enrichment import enrich_leads
from lead_finder.website_finder import find_websites

st.set_page_config(page_title=APP_NAME, page_icon="📞", layout="wide", initial_sidebar_state="expanded")
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

PAGE_SIZE = 24
RADIUS_OPTIONS = [r for r in (2, 5, 10, 15, 25) if r <= MAX_RADIUS_KM]
EXAMPLES = [("Dentist", "Los Angeles, California, USA"), ("Restaurant", "Austin, Texas, USA"),
            ("Law firm", "London, UK"), ("Gym", "Dubai, UAE")]

st.session_state.setdefault("niche", "Dentist")
st.session_state.setdefault("location", "Los Angeles, California, USA")
st.session_state.setdefault("shown", PAGE_SIZE)


@st.cache_data(ttl=60 * 60, show_spinner=False)
def cached_osm_search(niche: str, location: str, radius_km: int, max_results: int):
    """Cache repeated searches for an hour to go easy on the free public services."""
    return search_businesses(niche, location, radius_km, max_results)


def use_example(niche: str, location: str) -> None:
    st.session_state["niche"], st.session_state["location"] = niche, location


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-mark"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0D2B2E" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg></div>'
        f'<div><div class="brand-name">{APP_NAME}</div><div class="brand-sub">Local business prospecting</div></div></div>',
        unsafe_allow_html=True,
    )
    with st.expander("Get more phone numbers", expanded=not GOOGLE_PLACES_API_KEY):
        st.caption(
            "OpenStreetMap often has no phone or website. Add a Google Places API key to fill them in "
            "for most businesses. Google includes a free monthly allowance; check current pricing."
        )
        google_key = st.text_input("Google Places API key", value=GOOGLE_PLACES_API_KEY, type="password",
                                   placeholder="Optional", label_visibility="collapsed")
        st.caption("Stays in this browser session. Not saved to disk.")
    st.markdown("**Sources**")
    st.markdown("- [OpenStreetMap](https://www.openstreetmap.org/copyright)\n- Business websites (public pages)\n- Google Places (only with a key)")
    st.caption(f"Version {APP_VERSION}")

# ------------------------------------------------------------------ header
st.markdown(
    '<div class="page-head"><div><h1>Find businesses worth calling</h1>'
    '<p>Search a niche and a city. You get phone numbers, websites, emails and, where it is published, the name of the owner or manager.</p></div></div>',
    unsafe_allow_html=True,
)

search_tab, saved_tab, help_tab = st.tabs(["Find leads", "Saved leads", "How it works"])

# ------------------------------------------------------------------ search
with search_tab:
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([2.2, 2.6, 1, 1, 1.3], vertical_alignment="bottom")
        niche = c1.text_input("Business type", key="niche", placeholder="Dentist, Software company, Restaurant")
        location = c2.text_input("City or area", key="location", placeholder="Austin, Texas, USA")
        radius = c3.selectbox("Radius (km)", RADIUS_OPTIONS, index=RADIUS_OPTIONS.index(DEFAULT_RADIUS_KM) if DEFAULT_RADIUS_KM in RADIUS_OPTIONS else 1)
        max_results = c4.selectbox("Leads", [10, 25, 50, 100], index=2)
        go = c5.button("Find leads", type="primary", use_container_width=True)
        t1, t2 = st.columns(2)
        read_sites = t1.toggle("Read business websites for phone, email and owner", value=True,
                               help="Opens each business's own website (contact, about and team pages) and reads public details. Respects robots.txt.")
        find_missing = t2.toggle("Look up websites that are not listed", value=True,
                                 help="Runs a web search for businesses with no website, so there is something to read. Matches are marked 'verify'.")

    if go:
        if not niche.strip() or not location.strip():
            st.error("Enter a business type and a city to search.")
        else:
            notes: list[str] = []
            try:
                with st.status("Finding leads…", expanded=True) as status:
                    st.write("Searching public listings")
                    try:
                        leads, geo = cached_osm_search(niche.strip(), location.strip(), radius, max_results)
                        leads = [dict(l) for l in leads]
                    except Exception as exc:
                        if not google_key.strip():
                            raise
                        # OpenStreetMap servers are down: carry on with Google Places only.
                        geo = geocode_location(location.strip())
                        leads = []
                        notes.append("OpenStreetMap was busy, so these results come from Google Places only.")
                    region = geo.get("country_code")
                    if google_key.strip():
                        st.write("Adding Google Places listings")
                        try:
                            g = search_google_places(google_key.strip(), niche.strip(), location.strip(), geo, radius, max_results, region)
                            leads = merge_sources(g, leads)
                        except Exception as exc:  # keep going with OpenStreetMap results
                            notes.append(f"Google Places was skipped. {exc}")
                    leads.sort(key=lambda r: (-readiness_score(r), r["business_name"].lower()))
                    leads = leads[:max_results]

                    if leads and find_missing and any(not l.get("website") for l in leads):
                        missing = sum(1 for l in leads if not l.get("website"))
                        st.write(f"Looking up websites for {missing} businesses without one")
                        bar = st.progress(0.0)
                        leads, note = find_websites(leads, geo["display_name"].split(",")[0], lambda d, t: bar.progress(d / max(t, 1)))
                        bar.empty()
                        if note:
                            notes.append(note)

                    if leads and read_sites and any(l.get("website") for l in leads):
                        n = sum(1 for l in leads if l.get("website"))
                        st.write(f"Reading {n} websites for phone, email and owner")
                        bar = st.progress(0.0)
                        leads = enrich_leads(leads, region, lambda d, t: bar.progress(d / max(t, 1), text=f"{d} of {t} websites"))
                        bar.empty()

                    leads.sort(key=lambda r: (-readiness_score(r), r["business_name"].lower()))
                    status.update(label=f"Found {len(leads)} businesses" if leads else "No businesses found", state="complete", expanded=False)

                st.session_state.update(leads=leads, meta={"niche": niche.strip(), "location": geo["display_name"], "notes": notes}, shown=PAGE_SIZE)
                if not leads:
                    st.warning("No matching businesses found. Try a broader business type, a nearby city or a larger radius.")
            except Exception as exc:
                st.error(f"The search did not finish. {exc}")
                st.caption("The free public map services get busy at times. Wait a minute and try again, or use a smaller radius.")

    leads: list[dict] = st.session_state.get("leads", [])
    meta = st.session_state.get("meta", {})

    if not leads:
        st.markdown(
            '<div class="empty"><div><h2>Start with a business type and a city</h2>'
            '<p>The finder searches public listings, then opens each business website to read its contact and team pages. '
            'Leads with a phone number and a named contact come first, so your team can start calling at the top of the list.</p>'
            '<p style="color:var(--muted);font-size:.9rem">Try one of these:</p></div>'
            f'<div class="sample">{lead_card({"business_name": "Harbor Family Dental", "category": "Dentist", "business_phone": "+1 310-555-0142", "decision_maker": "Dr. Maria Alvarez", "decision_maker_title": "Owner and Lead Dentist", "decision_maker_confidence": "Medium", "email": "hello@harbordental.example", "website": "https://harbordental.example", "address": "412 Pier Ave, Santa Monica", "phone_source": "Business website", "facebook": "https://facebook.com"})}</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="chip-row">', unsafe_allow_html=True)
        cols = st.columns(len(EXAMPLES))
        for col, (n, l) in zip(cols, EXAMPLES):
            col.button(f"{n} in {l.split(',')[0]}", key=f"ex_{n}", on_click=use_example, args=(n, l), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="sub" style="color:var(--muted);margin:.2rem 0 .1rem">Results for <b style="color:var(--ink)">{meta.get("niche", "")}</b> near {meta.get("location", "")}</div>'.replace("<b", "<b"), unsafe_allow_html=True)
        for note in meta.get("notes", []):
            st.markdown(f'<div class="notice">{note}</div>', unsafe_allow_html=True)
        st.markdown(kpi_strip(leads), unsafe_allow_html=True)

        f1, f2, f3, f4 = st.columns([2.2, 2.4, 1.6, 1.4], vertical_alignment="bottom")
        text_filter = f1.text_input("Filter", placeholder="Name, category, person, address", label_visibility="collapsed")
        must_have = f2.multiselect("Must have", ["Phone", "Website", "Email", "Decision-maker"], placeholder="Must have: phone, email…", label_visibility="collapsed")
        sort_by = f3.selectbox("Sort", ["Best contact details", "Name A–Z"], label_visibility="collapsed")
        view = f4.segmented_control("View", ["Cards", "Table"], default="Cards", label_visibility="collapsed") or "Cards"

        keymap = {"Phone": "business_phone", "Website": "website", "Email": "email", "Decision-maker": "decision_maker"}
        shown_leads = [
            l for l in leads
            if (not text_filter.strip() or text_filter.strip().lower() in " ".join(str(v) for v in l.values()).lower())
            and all(str(l.get(keymap[m]) or "").strip() for m in must_have)
        ]
        if sort_by == "Name A–Z":
            shown_leads.sort(key=lambda r: r["business_name"].lower())

        a1, a2, a3, a4 = st.columns([1.2, 1.2, 1.4, 3])
        a1.download_button("Download CSV", to_csv_bytes(shown_leads), "leads.csv", "text/csv", use_container_width=True)
        a2.download_button("Download Excel", to_excel_bytes(shown_leads), "leads.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        if a3.button("Save to my leads", use_container_width=True):
            count = save_leads(shown_leads, meta.get("niche", ""), meta.get("location", ""))
            st.toast(f"Saved {count} leads. Find them under Saved leads.")
        a4.markdown(f'<div style="text-align:right;color:var(--muted);padding-top:.5rem">{len(shown_leads)} of {len(leads)} leads</div>', unsafe_allow_html=True)

        if not shown_leads:
            st.info("No leads match these filters. Remove a filter to see more.")
        elif view == "Cards":
            visible = shown_leads[: st.session_state["shown"]]
            st.markdown(card_grid(visible), unsafe_allow_html=True)
            if len(visible) < len(shown_leads):
                _, mid, _ = st.columns([1, 1, 1])
                if mid.button(f"Show more ({len(shown_leads) - len(visible)} left)", use_container_width=True):
                    st.session_state["shown"] += PAGE_SIZE
                    st.rerun()
        else:
            df = pd.DataFrame(shown_leads)
            df.insert(0, "readiness", [readiness_score(r) for r in shown_leads])
            cols = [c for c in ["readiness", "business_name", "business_phone", "decision_maker", "decision_maker_title", "email",
                                "website", "category", "address", "linkedin", "facebook", "instagram", "map_url"] if c in df.columns]
            st.dataframe(df[cols], hide_index=True, use_container_width=True, height=620, column_config={
                "readiness": st.column_config.ProgressColumn("Ready", min_value=0, max_value=100, format="%d", width="small"),
                "business_name": "Business", "business_phone": "Phone", "decision_maker": "Decision-maker",
                "decision_maker_title": "Title", "email": "Email", "category": "Category", "address": "Address",
                "website": st.column_config.LinkColumn("Website", display_text=r"https?://(?:www\.)?([^/]+)"),
                "linkedin": st.column_config.LinkColumn("LinkedIn", display_text="Open"),
                "facebook": st.column_config.LinkColumn("Facebook", display_text="Open"),
                "instagram": st.column_config.LinkColumn("Instagram", display_text="Open"),
                "map_url": st.column_config.LinkColumn("Map", display_text="Open"),
            })

    st.markdown('<div class="foot">Map data © OpenStreetMap contributors. Details come from public sources and can be out of date. Confirm before outreach, and follow the calling and email-marketing rules in your market.</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ saved leads
with saved_tab:
    saved = load_leads()
    if saved.empty:
        st.markdown('<div class="empty" style="grid-template-columns:1fr"><div><h2>No saved leads yet</h2><p>Run a search and choose Save to my leads. Saved leads keep a status and notes, so your team can track who has been called.</p></div></div>', unsafe_allow_html=True)
    else:
        saved["readiness"] = [readiness_score(r) for r in saved.to_dict("records")]
        s1, s2 = st.columns([1, 3], vertical_alignment="bottom")
        status_filter = s1.multiselect("Status", STATUSES, placeholder="All statuses")
        s2.markdown(f'<div style="text-align:right;color:var(--muted)">{len(saved)} saved leads</div>', unsafe_allow_html=True)
        view_df = saved[saved["status"].isin(status_filter)] if status_filter else saved
        editor_cols = ["lead_id", "readiness", "business_name", "status", "notes", "business_phone", "decision_maker",
                       "decision_maker_title", "email", "website", "niche_searched", "location_searched"]
        edited = st.data_editor(
            view_df[editor_cols], hide_index=True, use_container_width=True, height=560, key="saved_editor",
            disabled=[c for c in editor_cols if c not in ("status", "notes")],
            column_config={
                "lead_id": None,
                "readiness": st.column_config.ProgressColumn("Ready", min_value=0, max_value=100, format="%d", width="small"),
                "status": st.column_config.SelectboxColumn("Status", options=STATUSES, required=True),
                "notes": st.column_config.TextColumn("Notes", width="medium"),
                "business_name": "Business", "business_phone": "Phone", "decision_maker": "Decision-maker",
                "decision_maker_title": "Title", "email": "Email", "website": st.column_config.LinkColumn("Website"),
                "niche_searched": "Searched for", "location_searched": "Searched in",
            },
        )
        b1, b2, b3 = st.columns([1.2, 1.2, 4])
        if b1.button("Save changes", type="primary", use_container_width=True):
            update_team_fields([(r.lead_id, r.status, r.notes or "") for r in edited.itertuples()])
            st.toast("Changes saved.")
            st.rerun()
        b2.download_button("Download CSV", to_csv_bytes(load_leads()), "saved_leads.csv", "text/csv", use_container_width=True)
        with st.expander("Delete all saved leads"):
            st.warning("This permanently removes every saved lead from this computer.")
            if st.button("Delete all", disabled=not st.checkbox("I understand this cannot be undone")):
                delete_all_leads()
                st.rerun()

# ------------------------------------------------------------------ help
with help_tab:
    st.markdown("### Where each detail comes from")
    st.markdown(
        "- **Businesses and addresses:** OpenStreetMap, and Google Places if you add a key.\n"
        "- **Phone numbers:** the listing, then `tel:` links, structured data and visible numbers on the business's own contact, about and team pages. Fax numbers are skipped.\n"
        "- **Websites:** the listing, then Google Places, then a slow web-search lookup. Searched websites are marked **verify**.\n"
        "- **Decision-maker:** a named person shown with an owner, founder, CEO, director, partner or manager title. "
        "**High** means the site's structured data says so, **Medium** means a name and title sit together on a page, and **Low** means only that a \"Dr. Name\" is mentioned. Check Medium and Low before you use the name."
    )
    st.markdown("### Why a lead can have no phone")
    st.markdown(
        "The business may not be in the map data with a phone, and its website may not exist, may block automated readers, or may show the number only as an image. "
        "Add a Google Places key in the sidebar for the biggest improvement. Every card also has a link to check Google Maps or look up the owner by hand."
    )
    st.markdown("### Be considerate")
    st.markdown(
        "The app reads only public pages, follows robots.txt, never signs in, and does not read social networks. "
        "Searches are cached for an hour. Honour do-not-call and opt-out requests, and follow the rules for cold calls and email in your market."
    )