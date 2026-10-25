# Lead Finder 2.0

Search a business type and a city. Get a ranked list of businesses with phone numbers, websites, emails and, where published, the name of the owner or manager. Built for a sales team: click-to-call cards, readiness score, Excel/CSV export, and saved leads with status and notes.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py               # run from this folder so the theme in .streamlit/ is used
```

Set `CONTACT_EMAIL` in `lead_finder/config.py` (already set to yours).

## What changed in 2.0

**Why you had no phones or websites.** OpenStreetMap volunteers rarely add them, and the old website reader failed on any redirect (`http` to `https`, `www`), only looked at `tel:` links, and ran only from a manual button. Now:

| Need | How it is found |
|---|---|
| Phone | Listing, then `tel:` links, structured data and visible numbers on contact/about/team pages (validated and formatted, fax skipped) |
| Website | Listing, then Google Places (optional), then a slow web-search lookup (marked **verify**) |
| Email | `mailto:` links, page text, `[at]`/`[dot]` forms, Cloudflare-protected emails |
| Decision-maker | JSON-LD people, "Name, Owner" / "Owner: Name" text, team cards, "founded by Name", and "Dr. Name" as a low-confidence fallback. Each is labelled **High / Medium / Low** with a link to the page it came from |

**Biggest improvement for phones:** paste a Google Places API key in the sidebar (or set `GOOGLE_PLACES_API_KEY`). One search returns phone and website for most businesses. Google has a free monthly allowance; check current pricing and its terms on storing results.

## Limits (be aware)

- Decision-makers are only found when a business publishes them. Many small sites don't. Every card has a "Look up owner" link for the rest.
- The web-search website lookup is capped (40 per search) and stops if the search engine pushes back.
- Medium and Low confidence names should be checked before use.
- Respect robots.txt (the app does), do-not-call lists and email-marketing law in your market. Keep the OpenStreetMap attribution.

## Saved leads

Stored in `data/leads.sqlite3`. An existing database from version 1 is upgraded automatically.
