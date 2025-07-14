import os
import time
from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from pypresence import Presence

# Load environment variables from .env
load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")

# Setup Spotify API client
sp = Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope="user-read-playback-state"
))

# Setup Discord Rich Presence client
rpc = Presence(DISCORD_CLIENT_ID)
rpc.connect()

# Store the last known track ID and play state
last_track_id = None
last_is_playing = None

def update_presence():
    global last_track_id, last_is_playing

    try:
        playback = sp.current_playback()

        if not playback or playback.get("item") is None:
            if last_track_id is not None:
                rpc.clear()
                last_track_id = None
                last_is_playing = None
            return

        is_playing = playback.get("is_playing", False)
        track = playback["item"]
        track_id = track["id"]
        title = track["name"]
        artist = ', '.join(artist["name"] for artist in track["artists"])
        duration = track["duration_ms"] // 1000
        progress = playback["progress_ms"] // 1000

        # Only update Discord if track changed or play/pause state changed
        if track_id != last_track_id or is_playing != last_is_playing:
            if is_playing:
                rpc.update(
                    details=title,
                    state=f"by {artist}",
                    large_image="spotify",
                    start=time.time() - progress,
                    end=time.time() + (duration - progress)
                )
            else:
                rpc.update(
                    details=title,
                    state=f"Paused — by {artist}",
                    large_image="spotify"
                )

            last_track_id = track_id
            last_is_playing = is_playing

    except Exception as e:
        print(f"Error while updating presence: {e}")
        rpc.clear()
        last_track_id = None
        last_is_playing = None

# Main loop
if __name__ == "__main__":
    print("🎵 Spotify → Discord Rich Presence bridge running...")
    while True:
        update_presence()
        time.sleep(3)  # Slightly more frequent for faster pause/resume updates
