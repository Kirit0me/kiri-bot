import os
import aiohttp
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GeoAPI")

# Load Token safely from .env
GEO_TOKEN = os.getenv("GEO_API_TOKEN", "").strip('"\'')
BASE_URL = "https://api.restcountries.com/countries/v5"

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
    """Loops through all countries using limit & offset pagination in v5."""
    logger.info("📡 [GeoAPI] Fetching full country database from v5 API...")
    
    if not GEO_TOKEN:
        logger.error("❌ [GeoAPI] GEO_API_TOKEN not found in .env! Using fallback.")
        return FALLBACK_COUNTRIES

    all_raw_data = []
    limit = 50
    offset = 0

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15), headers=HEADERS) as session:
            while True:
                url = f"{BASE_URL}?limit={limit}&offset={offset}"
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.warning(f"⚠️ [GeoAPI] Status {resp.status} at offset {offset}. Stopping.")
                        break

                    res_json = await resp.json()
                    
                    page_data = []
                    if isinstance(res_json, dict):
                        page_data = res_json.get("data", {}).get("objects", []) or res_json.get("data", []) or res_json.get("results", [])
                    elif isinstance(res_json, list):
                        page_data = res_json

                    if not isinstance(page_data, list) or len(page_data) == 0:
                        break  # Reached the end of dataset

                    all_raw_data.extend(page_data)
                    logger.info(f"📥 [GeoAPI] Fetched offset {offset} ({len(page_data)} items)... Total: {len(all_raw_data)}")
                    
                    # Advance offset for next page
                    offset += limit

                # Safety guard
                if offset > 350:
                    break

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

        if len(valid_countries) > 50:
            logger.info(f"✅ [GeoAPI] Successfully loaded ALL {len(valid_countries)} countries into memory!")
            return valid_countries
        else:
            logger.warning(f"⚠️ [GeoAPI] Parsed only {len(valid_countries)} countries. Using fallback.")
            return FALLBACK_COUNTRIES

    except Exception as e:
        logger.error(f"💥 [GeoAPI] Fetch failed: {e}. Using fallback dataset.")
        return FALLBACK_COUNTRIES