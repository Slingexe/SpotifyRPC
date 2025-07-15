import os
import time
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from discord_rpc import DiscordRPC

load_dotenv()
# Load environment variables from .env
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_ASSET_NAME = os.getenv("DISCORD_ASSET_NAME")
USE_SPOTIFY_ASSET = os.getenv("USE_SPOTIFY_ASSET")
TIMEOUT = int(os.getenv("TIMEOUT"))
SONG_STATUS_ICON = os.getenv("SONG_STATUS_ICON", "false").lower() in ("1", "true", "yes")
SONG_STATUS_ICON_PLAY = os.getenv("SONG_STATUS_ICON_PLAY")
SONG_STATUS_ICON_PAUSE = os.getenv("SONG_STATUS_ICON_PAUSE")

DEBUG = os.getenv("DEBUG", False)



# Logger function
def log(*args, **kwargs):
    if DEBUG == "True":
        print("[DEBUG]", *args, **kwargs)

def log_env_vars():
    log("✅ Environment variables   loaded:")
    log(f"  SPOTIFY_CLIENT_ID:       {SPOTIFY_CLIENT_ID}")
    log(f"  SPOTIFY_CLIENT_SECRET:   {SPOTIFY_CLIENT_SECRET}")
    log(f"  SPOTIFY_REDIRECT_URI:    {SPOTIFY_REDIRECT_URI}")
    log(f"  DISCORD_CLIENT_ID:       {DISCORD_CLIENT_ID}")
    log(f"  DISCORD_ASSET_NAME:      {DISCORD_ASSET_NAME}")
    log(f"  USE_SPOTIFY_ASSET:       {USE_SPOTIFY_ASSET}")
    log(f"  TIMEOUT:                 {TIMEOUT}")
    log(f"  SONG_STATUS_ICON:        {SONG_STATUS_ICON}")
    log(f"  SONG_STATUS_ICON_PLAY:   {SONG_STATUS_ICON_PLAY}")
    log(f"  SONG_STATUS_ICON_PAUSE:  {SONG_STATUS_ICON_PAUSE}")
    log(f"  DEBUG:                   {DEBUG}")

# Setup Spotify API client
sp = Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope="user-read-playback-state"
))

# Setup Discord Rich Presence client
rpc = DiscordRPC(DISCORD_CLIENT_ID)
rpc.start({})  # empty to initialize

# Store the last known track ID and play state
last_track_uri = None
last_is_playing = None
last_metadata = {}

def update_presence():
    global last_track_uri, last_is_playing, last_metadata

    playback = sp.current_playback()
    log("Fetched playback.")

    if not playback or playback.get("item") is None or playback.get("progress_ms") is None:
        if last_track_uri:
            log("Clearing RPC presence (nothing playing).")
            rpc.stop()
            last_track_uri = None
            last_is_playing = None
            last_metadata = {}
        return

    is_playing = playback["is_playing"]
    track = playback["item"]
    track_uri = track["uri"]
    title = track["name"]
    artist = ', '.join(a["name"] for a in track["artists"])
    duration = track["duration_ms"] // 1000
    progress = playback["progress_ms"] // 1000
    album_name = track["album"]["name"]
    album_image_url = track["album"]["images"][0]["url"] if USE_SPOTIFY_ASSET else "spotify"

    log(f"Current track: {title} by {artist} ({'playing' if is_playing else 'paused'})")
    log(f"Fetched data: duration={duration}s, progress={progress}s, album={album_name}, image={album_image_url}")

    # Always refresh metadata when playing
    if is_playing:
        activity = {
            "name": title,
            "type": 0,
            "details": f"by {artist}",
            "state": "RPC created by @Slingexe",
            "timestamps": {
                "start": int(time.time()) - progress,
                "end": int(time.time()) + (duration - progress)
            },
            "assets": {
                "large_image": album_image_url,
                "large_text": album_name
            }
        }

        if SONG_STATUS_ICON:
            activity["assets"]["small_image"] = "play"
            activity["assets"]["small_text"] = "Playing"

        log("Updating RPC (playing):", title)
        rpc.update(activity)

        last_track_uri = track_uri
        last_is_playing = True
        last_metadata = {
            "title": title,
            "artist": artist,
            "duration": duration,
            "progress": progress,
            "album": album_name,
            "image": album_image_url
        }

    elif last_is_playing and last_metadata:
        # Paused — reuse last song info
        activity = {
            "name": "{title} - Paused",
            "type": 0,
            "details": f"by {artist}",
            "state": "RPC created by @Slingexe",
            "assets": {
                "large_image": album_image_url,
                "large_text": album_name
            }
        }
        if SONG_STATUS_ICON:
            activity["name"] = title
            activity["assets"]["small_image"] = "pause"
            activity["assets"]["small_text"] = "Playing"

        log("Updating RPC (paused):", last_metadata["title"])
        rpc.update(activity)
        last_is_playing = False

if __name__ == "__main__":
    log_env_vars()
    
    print("🎧 Spotify → Discord (with custom RPC) started.")
    try:
        while True:
            update_presence()
            time.sleep(TIMEOUT)
    except KeyboardInterrupt:
        log("Shutting down...")
        rpc.stop()