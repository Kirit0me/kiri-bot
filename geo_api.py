import os
import aiohttp
import logging
from dotenv import load_dotenv

load_dotenv()

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GeoAPI")

# Load Token safely
GEO_TOKEN = os.getenv("GEO_API_TOKEN", "").strip('"\'')
BASE_URL = "https://api.restcountries.com/countries/v5"

# Ensure Authorization header has the 'Bearer ' prefix
if GEO_TOKEN and not GEO_TOKEN.startswith("Bearer "):
    AUTH_HEADER = f"Bearer {GEO_TOKEN}"
else:
    AUTH_HEADER = GEO_TOKEN

HEADERS = {
    "Authorization": AUTH_HEADER,
    "Accept": "application/json"
}

FALLBACK_COUNTRIES = [
    {"name": "Canada", "capital": "Ottawa", "flag": "https://flags.restcountries.com/v5/w640/ca.png"},
    {"name": "United States", "capital": "Washington, D.C.", "flag": "https://flags.restcountries.com/v5/w640/us.png"},
    {"name": "Japan", "capital": "Tokyo", "flag": "https://flags.restcountries.com/v5/w640/jp.png"},
    {"name": "France", "capital": "Paris", "flag": "https://flags.restcountries.com/v5/w640/fr.png"},
    {"name": "Germany", "capital": "Berlin", "flag": "https://flags.restcountries.com/v5/w640/de.png"},
    {"name": "India", "capital": "New Delhi", "flag": "https://flags.restcountries.com/v5/w640/in.png"},
    {"name": "United Kingdom", "capital": "London", "flag": "https://flags.restcountries.com/v5/w640/gb.png"},
    {"name": "Australia", "capital": "Canberra", "flag": "https://flags.restcountries.com/v5/w640/au.png"},
    {"name": "Brazil", "capital": "Brasília", "flag": "https://flags.restcountries.com/v5/w640/br.png"},
    {"name": "Italy", "capital": "Rome", "flag": "https://flags.restcountries.com/v5/w640/it.png"}
]

async def fetch_all_countries():
    """Loops through all pages of REST Countries v5 to return all ~250 countries."""
    logger.info("📡 [GeoAPI] Fetching full country list across pages...")
    
    if not GEO_TOKEN:
        logger.error("❌ [GeoAPI] GEO_API_TOKEN not found in .env! Using fallback.")
        return FALLBACK_COUNTRIES

    all_raw_data = []
    page = 1

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15), headers=HEADERS) as session:
            while True:
                # Fixed variable name to BASE_URL
                url = f"{BASE_URL}?page={page}"
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.warning(f"⚠️ [GeoAPI] HTTP {resp.status} on page {page}. Stopping pagination.")
                        break

                    res_json = await resp.json()
                    
                    page_data = []
                    if isinstance(res_json, dict):
                        page_data = res_json.get("data", {}).get("objects", []) or res_json.get("data", [])
                    elif isinstance(res_json, list):
                        page_data = res_json

                    if not page_data or not isinstance(page_data, list):
                        break

                    all_raw_data.extend(page_data)
                    logger.info(f"📥 [GeoAPI] Page {page} loaded ({len(page_data)} countries). Total: {len(all_raw_data)}")
                    page += 1

                # Safety check to avoid infinite loop
                if page > 15:
                    break

        # Map raw data to our game structure
        valid_countries = []
        for country in all_raw_data:
            if not isinstance(country, dict):
                continue

            names_obj = country.get("names", {})
            name = names_obj.get("common") if isinstance(names_obj, dict) else None

            capitals = country.get("capitals", [])
            capital = None
            if isinstance(capitals, list) and capitals and isinstance(capitals[0], dict):
                capital = capitals[0].get("name")
            elif isinstance(capitals, list) and capitals and isinstance(capitals[0], str):
                capital = capitals[0]

            flag_obj = country.get("flag", {})
            flag = flag_obj.get("url_png") if isinstance(flag_obj, dict) else None

            if name and capital and flag:
                valid_countries.append({"name": name, "capital": capital, "flag": flag})

        if len(valid_countries) > 10:
            logger.info(f"✅ [GeoAPI] Successfully parsed {len(valid_countries)} countries across {page - 1} page(s)!")
            return valid_countries
        else:
            logger.warning(f"⚠️ [GeoAPI] Parsed only {len(valid_countries)} countries. Using fallback.")
            return FALLBACK_COUNTRIES

    except Exception as e:
        logger.error(f"💥 [GeoAPI] Fetch failed: {e}. Using fallback dataset.")
        return FALLBACK_COUNTRIES