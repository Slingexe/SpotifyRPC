import os
import time
from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

# Get your environment variables set as needed
load_dotenv()
SPOTIFY_CLIENT_ID      = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET  = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI   = os.getenv("SPOTIFY_REDIRECT_URI")

# Authorize
sp = Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope="playlist-read-private"
), retries=0)  # disables spotipy's internal retry handler

# Use your own playlist ID here!
PLAYLIST_ID = "7GcD8GUGHwC6H5vfufXzSq"

def fetch_playlist_loop():
    while True:
        try:
            print("Fetching playlist...")
            playlist = sp.playlist(PLAYLIST_ID)
            print("Got playlist:", playlist["name"])
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 5))
                print(f"⚠️ Rate limit hit! Sleeping for {retry_after} seconds.")
                time.sleep(retry_after)
            else:
                print("Spotify error:", e)
                time.sleep(2)
        except Exception as e:
            print("Other error:", e)
            time.sleep(2)
        time.sleep(3)

if __name__ == "__main__":
    fetch_playlist_loop()
