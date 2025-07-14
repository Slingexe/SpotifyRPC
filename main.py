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
DISCORD_ASSET_NAME = os.getenv("DISCORD_ASSET_NAME")
USE_SPOTIFY_ASSET = os.getenv("USE_SPOTIFY_ASSET")
TIMEOUT = int(os.getenv("TIMEOUT"))
DEBUG = os.getenv("DEBUG", False)

# Logger function
def log(*args, **kwargs):
    if DEBUG == "True":
        print("[DEBUG]", *args, **kwargs)

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
log("Connected to Discord RPC.")

# Store the last known track ID and play state
last_track_uri = None
last_is_playing = None
last_metadata = {}  # Stores title, artist, duration, progress

def update_presence():
    global last_track_uri, last_is_playing, last_metadata

    try:
        playback = sp.current_playback()
        # log("Fetched playback:", playback)
        log("Fetched playback (filtered):", {
            "is_playing": playback.get("is_playing"),
            "progress_ms": playback.get("progress_ms"),
            "item": {
                "name": playback.get("item", {}).get("name") if playback.get("item") else None,
                "artists": [a["name"] for a in playback.get("item", {}).get("artists", [])] if playback.get("item") else None,
                "uri": playback.get("item", {}).get("uri") if playback.get("item") else None,
            }
        })


        if not playback or playback.get("progress_ms") is None:
            if last_track_uri is not None:
                log("No valid track or progress — clearing presence.")
                rpc.clear()
                last_track_uri = None
                last_is_playing = None
                last_metadata = {}
            return

        is_playing = playback.get("is_playing", False)

        # When playing, extract and cache metadata
        if is_playing:
            track = playback["item"]
            if not track:
                return

            track_uri = track["uri"]
            title = track["name"]
            artist = ', '.join(artist["name"] for artist in track["artists"])
            duration = track["duration_ms"] // 1000
            progress = playback["progress_ms"] // 1000
            album_art_url = track["album"]["images"][0]["url"]

            if USE_SPOTIFY_ASSET == "True":
                art = album_art_url
            else:
                art = DISCORD_ASSET_NAME


            # Update presence only if something changed
            if track_uri != last_track_uri or not last_is_playing:
                log("Updating presence — playing:", title)
                rpc.update(
                    details=title,
                    state=f"by {artist}",
                    large_image=art,
                    start=time.time() - progress,
                    end=time.time() + (duration - progress)
                )

            # Update cache
            last_track_uri = track_uri
            last_is_playing = True
            last_metadata = {
                "title": title,
                "artist": artist,
                "duration": duration,
                "progress": progress
            }

        else:
            # Use last known metadata if available
            if last_metadata:
                title = last_metadata["title"]
                artist = last_metadata["artist"]

                if not last_is_playing:
                    log("Track still paused — no update.")
                    return

                log("Updating presence — paused:", title)
                rpc.update(
                    details="Paused",
                    state=f"{title} by {artist}",
                    large_image=art
                )

                last_is_playing = False
            else:
                log("Paused but no cached track — clearing.")
                rpc.clear()
                last_track_uri = None
                last_is_playing = None

    except Exception as e:
        print(f"[ERROR] Failed to update presence: {e}")
        try:
            rpc.clear()
        except Exception as clear_err:
            print(f"[ERROR] Failed to clear presence: {clear_err}")
        last_track_uri = None
        last_is_playing = None
        last_metadata = {}


# Main loop
if __name__ == "__main__":
    print("🎵 Spotify → Discord Rich Presence bridge running...")
    while True:
        update_presence()
        time.sleep(TIMEOUT)
