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

# Map difficulty to TMDB page depth
DIFFICULTY_PAGES = {
    "easy": (1, 5),     
    "medium": (5, 10),  
    "hard": (11, 25)    
}

async def fetch_random_popular_movie(difficulty: str = "easy"):
    """Gets a random movie based on difficulty level."""
    min_page, max_page = DIFFICULTY_PAGES.get(difficulty.lower(), (1, 2))
    page = random.randint(min_page, max_page)
    
    url = f"{BASE_URL}/movie/popular?language=en-US&page={page}"
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return random.choice(data['results'])

async def get_movie_details(movie_id):
    """Fetches details and filters for textless backdrop images."""
    url = f"{BASE_URL}/movie/{movie_id}?append_to_response=credits,images&include_image_language=null,en"
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as resp:
            data = await resp.json()
            all_backdrops = data.get('images', {}).get('backdrops', [])
            clean_backdrops = [img for img in all_backdrops if img.get('iso_639_1') is None]
            data['clean_backdrops'] = clean_backdrops if clean_backdrops else all_backdrops
            return data