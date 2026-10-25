"""Application defaults. Change CONTACT_EMAIL before using public OpenStreetMap services."""
import os
from pathlib import Path

APP_NAME = "Lead Finder"
APP_VERSION = "2.0.1"
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "leads.sqlite3"

# Public OpenStreetMap services ask for an identifiable User-Agent/contact.
CONTACT_EMAIL = "avyronixofficial@gmail.com"
USER_AGENT = f"LeadFinder/{APP_VERSION} (contact: {CONTACT_EMAIL})"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Tried in order; the first one that answers is used.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
REQUEST_TIMEOUT_SECONDS = 25
DEFAULT_RADIUS_KM = 5
MAX_RADIUS_KM = 25
DEFAULT_MAX_RESULTS = 50
MAX_RESULTS_LIMIT = 100

# Website reading
WEBSITE_TIMEOUT_SECONDS = 8
MAX_WEBSITE_PAGES = 6          # pages read per business website
MAX_REDIRECTS = 4
ENRICH_WORKERS = 8             # websites read in parallel (each site is still read politely)

# Website discovery for businesses that list no website (web search fallback)
MAX_WEBSITE_LOOKUPS = 40       # per search, to stay polite to the search engine
LOOKUP_DELAY_SECONDS = 1.2

# Optional: Google Places API key. Gives far more phone numbers and websites than OSM.
# Set the GOOGLE_PLACES_API_KEY environment variable, or paste the key in the app sidebar.
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")

DATA_DIR.mkdir(parents=True, exist_ok=True)