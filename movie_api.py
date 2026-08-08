import os
import random
import aiohttp
import yt_dlp
from dotenv import load_dotenv

load_dotenv()

TMDB_READ_TOKEN = os.getenv("TMDB_READ_TOKEN")
BASE_URL = "https://api.themoviedb.org/3"

HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {TMDB_READ_TOKEN}"
}

# Curated difficulty rules based on vote counts and quality thresholds
DIFFICULTY_CONFIG = {
    "easy": {
        "vote_count_gte": 8000,       # Universally known global blockbusters (e.g., Inception, Titanic)
        "vote_average_gte": 7.0,
        "sort_by": "vote_count.desc",
        "max_page": 5
    },
    "medium": {
        "vote_count_gte": 2500,       # Famous cult classics & popular mid-tier hits
        "vote_count_lte": 7999,
        "vote_average_gte": 6.5,
        "sort_by": "vote_count.desc",
        "max_page": 5
    },
    "hard": {
        "vote_count_gte": 600,        # Niche masterpieces, older classics, & deep cinephile picks
        "vote_count_lte": 2499,
        "vote_average_gte": 6.0,
        "sort_by": "popularity.desc",
        "max_page": 5
    }
}


async def fetch_random_popular_movie(difficulty: str = "easy"):
    """Gets a random movie based on vote significance rather than daily trending popularity."""
    config = DIFFICULTY_CONFIG.get(difficulty.lower(), DIFFICULTY_CONFIG["easy"])
    
    # Select a random page from the top results of that difficulty bracket
    page = random.randint(1, config["max_page"])
    
    url = (
        f"{BASE_URL}/discover/movie?"
        f"include_adult=false&include_video=false&language=en-US&page={page}"
        f"&sort_by={config['sort_by']}"
        f"&vote_count.gte={config['vote_count_gte']}"
        f"&vote_average.gte={config['vote_average_gte']}"
    )
    
    # Add upper bound for vote count if present (Medium/Hard tiers)
    if "vote_count_lte" in config:
        url += f"&vote_count.lte={config['vote_count_lte']}"

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = data.get("results", [])
                if results:
                    return random.choice(results)
            
            # Fallback to page 1 if a higher page yields no results
            fallback_url = f"{BASE_URL}/discover/movie?include_adult=false&language=en-US&page=1&sort_by=vote_count.desc&vote_count.gte=5000"
            async with session.get(fallback_url) as fallback_resp:
                fallback_data = await fallback_resp.json()
                return random.choice(fallback_data["results"])


async def get_movie_details(movie_id):
    """Fetches details and filters for textless backdrop images."""
    url = f"{BASE_URL}/movie/{movie_id}?append_to_response=credits,images&include_image_language=null,en"
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as resp:
            data = await resp.json()
            all_backdrops = data.get('images', {}).get('backdrops', [])
            
            # Prefer clean backdrops with no text overlay (iso_639_1 is None)
            clean_backdrops = [img for img in all_backdrops if img.get('iso_639_1') is None]
            data['clean_backdrops'] = clean_backdrops if clean_backdrops else all_backdrops
            return data