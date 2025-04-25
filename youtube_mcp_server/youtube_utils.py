import httpx
import os

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

BASE_URL = "https://www.googleapis.com/youtube/v3"

def youtube_get(endpoint: str, params: dict):
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY não definida no ambiente.")
    params["key"] = YOUTUBE_API_KEY
    response = httpx.get(f"{BASE_URL}/{endpoint}", params=params)
    response.raise_for_status()
    return response.json()
