import os
import time
import requests
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from dotenv import load_dotenv
from RPC import DiscordRPC
from server import NowPlayingServer, TrackInfo

# ==== Load and Parse Env Variables ====
load_dotenv()
SPOTIFY_CLIENT_ID      = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET  = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI   = os.getenv("SPOTIFY_REDIRECT_URI")
DISCORD_CLIENT_ID      = os.getenv("DISCORD_CLIENT_ID")
DISCORD_ASSET_NAME     = os.getenv("DISCORD_ASSET_NAME")
USE_SPOTIFY_ASSET      = os.getenv("USE_SPOTIFY_ASSET")
TIMEOUT                = int(os.getenv("TIMEOUT", 5))
SONG_STATUS_ICON       = os.getenv("SONG_STATUS_ICON", "false").lower() in ("1", "true", "yes")
SONG_STATUS_ICON_PLAY  = os.getenv("SONG_STATUS_ICON_PLAY")
SONG_STATUS_ICON_PAUSE = os.getenv("SONG_STATUS_ICON_PAUSE")
ENABLE_SERVER          = os.getenv("ENABLE_SERVER", "false").lower() in ("1", "true", "yes")
ENABLE_CUSTOM_BUTTON   = os.getenv("CUSTOM_BUTTON", "false").lower() in ("1", "true", "yes")
CUSTOM_BUTTON_TEXT     = os.getenv("CUSTOM_BUTTON_TEXT", "Now Playing")
CUSTOM_BUTTON_URL      = os.getenv("CUSTOM_BUTTON_URL", "http://example.com")
DEBUG                  = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
PRINT_SECRETS          = os.getenv("PRINT_SECRETS", "false").lower() in ("1", "true", "yes")

C_BUTTON = (
    {"label": CUSTOM_BUTTON_TEXT, "url": CUSTOM_BUTTON_URL}
    if ENABLE_CUSTOM_BUTTON else None
)

# ==== Logging Helpers ====
def log(*args, **kwargs):
    if DEBUG:
        print("[DEBUG]", *args, **kwargs)

def log_env_vars():
    log("✅ Loaded environment variables:")
    secrets = lambda v: v if PRINT_SECRETS else "***"
    log(f"  SPOTIFY_CLIENT_ID:      {secrets(SPOTIFY_CLIENT_ID)}")
    log(f"  SPOTIFY_CLIENT_SECRET:  {secrets(SPOTIFY_CLIENT_SECRET)}")
    log(f"  SPOTIFY_REDIRECT_URI:   {secrets(SPOTIFY_REDIRECT_URI)}")
    log(f"  DISCORD_CLIENT_ID:      {secrets(DISCORD_CLIENT_ID)}")
    log(f"  DISCORD_ASSET_NAME:     {DISCORD_ASSET_NAME}")
    log(f"  USE_SPOTIFY_ASSET:      {USE_SPOTIFY_ASSET}")
    log(f"  TIMEOUT:                {TIMEOUT}")
    log(f"  SONG_STATUS_ICON:       {SONG_STATUS_ICON}")
    log(f"  ENABLE_SERVER:          {ENABLE_SERVER}")
    log(f"  ENABLE_CUSTOM_BUTTON:   {ENABLE_CUSTOM_BUTTON}")
    log(f"  CUSTOM_BUTTON_TEXT:     {CUSTOM_BUTTON_TEXT if ENABLE_CUSTOM_BUTTON else 'N/A'}")
    log(f"  CUSTOM_BUTTON_URL:      {CUSTOM_BUTTON_URL if ENABLE_CUSTOM_BUTTON else 'N/A'}")
    log(f"  DEBUG:                  {DEBUG}")

# ==== Rate-Limited Spotify API Call Wrapper ====
def spotify_api_call(func, *args, **kwargs):
    """Run a Spotify API call and handle 429 retries globally."""
    while True:
        try:
            return func(*args, **kwargs)
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 30))
                log(f"⚠️ Spotify rate limit hit — sleeping for {retry_after} seconds.")
                if ENABLE_SERVER and server:
                    try:
                        clear_server_data()
                        server_data.is_offline = False
                        server_data.ratelimit = True
                        server_data.rl_time = retry_after
                        server.update(TrackInfo=server_data)
                        log("Updated Now Playing server with rate limit info.")
                    except Exception as ex:
                        log("Failed to update Now Playing server:", ex)
                ratelimit_presence()
                time.sleep(retry_after)
                clear_server_data()
            else:
                raise

# ==== Spotify Auth Helper ====
def wait_for_spotify_auth():
    """Attempt to authenticate Spotify, retrying on failure (e.g., network down or rate limit)."""
    while True:
        try:
            auth = SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope="user-read-playback-state"
            )
            sp = Spotify(auth_manager=auth, retries=0)
            # Test connection using the global rate limit handler
            spotify_api_call(sp.current_playback)
            print("✅ Spotify authenticated and reachable.")
            return sp
        except (SpotifyException, requests.exceptions.RequestException) as e:
            print("⛔ Spotify not reachable — waiting for internet...")
            log("Failed to connect to Spotify:", e)
            time.sleep(5)

# ==== Main State ====
sp = wait_for_spotify_auth()
rpc = DiscordRPC(DISCORD_CLIENT_ID)
rpc.start({})

server = None
if ENABLE_SERVER:
    server = NowPlayingServer()
    server.start()

last_track_uri = None
last_is_playing = None
last_metadata = {}

server_data = TrackInfo(
    is_offline=True, is_playing=False,
    ratelimit=False, rl_time=0,
    title="", artist="", uri="", artURL="",
    duration=0, progress=0,
    context_type="", context_uri="", context_name=""
)

def clear_server_data():
    """Reset server data to offline state."""
    global server_data
    server_data.is_offline = True
    server_data.is_playing = False
    server_data.title = ""
    server_data.artist = ""
    server_data.uri = ""
    server_data.artURL = ""
    server_data.duration = 0
    server_data.progress = 0
    server_data.context_type = ""
    server_data.context_uri = ""
    server_data.context_name = ""
    if ENABLE_SERVER and server:
        try:
            server.update(TrackInfo=server_data)
            log("Updated Now Playing server to offline state.")
        except Exception as e:
            log("Failed to update Now Playing server:", e)

# ==== Presence Update Logic ====
def update_presence():
    """Checks playback state, updates Discord and (optionally) webserver."""
    global last_track_uri, last_is_playing, last_metadata, sp

    try:
        # -- Spotify Playback Fetch --
        playback = spotify_api_call(sp.current_playback)

        # -- Nothing Playing --
        if not playback or not playback.get("item") or playback.get("progress_ms") is None:
            if last_track_uri:
                log("Clearing RPC presence (nothing playing).")
                rpc.stop()
                last_track_uri = None
                last_is_playing = None
                last_metadata = {}
                clear_server_data()
            return

        # -- Gather Track Info --
        is_playing = playback["is_playing"]
        track      = playback["item"]
        track_uri  = track["uri"]
        title      = track["name"]
        artist     = ', '.join(a["name"] for a in track["artists"])
        duration   = track["duration_ms"] // 1000
        progress   = playback["progress_ms"] // 1000
        album_name = track["album"]["name"]
        album_img  = track["album"]["images"][0]["url"] if USE_SPOTIFY_ASSET else "spotify"
        context    = playback.get("context")

        play_name, context_type, context_uri, context_name = None, "", "", ""
        if context:
            context_type = context.get("type")
            context_uri = context.get("uri")
            if context_type == "playlist":
                playlist_id = context_uri.split(":")[-1]
                try:
                    playlist = spotify_api_call(sp.playlist, playlist_id)
                    play_name = f"playlist '{playlist['name']}'"
                    context_name = playlist['name']
                except Exception as e:
                    log("Could not fetch playlist name:", e)
            elif context_type == "album":
                album_id = context_uri.split(":")[-1]
                try:
                    album = spotify_api_call(sp.album, album_id)
                    play_name = f"album '{album['name']}'"
                    context_name = album['name']
                except Exception as e:
                    log("Could not fetch album name:", e)
            elif context_uri and ":collection" in context_uri:
                play_name, context_type, context_name = "Liked Songs", "user_collection", "Liked Songs"

        log(f"Current track: {title} by {artist} ({'playing' if is_playing else 'paused'})")
        log(f"Track details: duration={duration}s, progress={progress}s, album={album_name}, image={album_img}")

        # -- Update Server Data --
        if ENABLE_SERVER and server:
            server_data.is_offline   = False
            server_data.is_playing   = is_playing
            server_data.title        = title
            server_data.artist       = artist
            server_data.uri          = track_uri
            server_data.artURL       = album_img
            server_data.duration     = duration
            server_data.progress     = progress
            server_data.context_type = context_type
            server_data.context_uri  = context_uri
            server_data.context_name = context_name
            try:
                server.update(TrackInfo=server_data)
                log("Updated Now Playing server with current track info.")
            except Exception as e:
                log("Failed to update Now Playing server:", e)

        # -- Compose Discord Activity --
        def activity_base(paused=False):
            base = {
                "name": title if not paused else f"{title} - Paused",
                "type": 0,
                "details": f"by {artist}",
                "state": f"Listening to {play_name} on Spotify" if play_name else "Listening to Spotify",
                "assets": {
                    "large_image": album_img,
                    "large_text": album_name
                },
                "buttons": [{
                    "label": "GitHub",
                    "url": "https://github.com/Slingexe/SpotifyRPC"
                }]
            }
            if SONG_STATUS_ICON:
                base["assets"]["small_image"] = "play" if not paused else "pause"
                base["assets"]["small_text"]  = "Playing" if not paused else "Paused"
            if ENABLE_CUSTOM_BUTTON and C_BUTTON:
                base["buttons"].insert(0, C_BUTTON)
            return base

        # -- Update Discord RPC --
        if is_playing:
            activity = activity_base(paused=False)
            activity["timestamps"] = {
                "start": int(time.time()) - progress,
                "end": int(time.time()) + (duration - progress)
            }
            log("Updating RPC (playing):", title)
            rpc.update(activity)
            last_track_uri = track_uri
            last_is_playing = True
            last_metadata = {
                "title": title, "artist": artist, "duration": duration,
                "progress": progress, "album": album_name, "image": album_img
            }
        elif last_is_playing and last_metadata:
            activity = activity_base(paused=True)
            log("Updating RPC (paused):", last_metadata["title"])
            rpc.update(activity)
            last_is_playing = False

    # -- Error Handling --
    except SpotifyException as e:
        if e.http_status == 429:
            retry_after = int(e.headers.get("Retry-After", 5))
            log(f"⚠️ Spotify rate limit hit — sleeping for {retry_after} seconds.")
            time.sleep(retry_after)
        else:
            log("🔁 Spotify API error — re-authenticating:", e)
            sp = wait_for_spotify_auth()
            clear_server_data()

    except requests.exceptions.RequestException as e:
        log("🔁 Network error — re-authenticating Spotify:", e)
        sp = wait_for_spotify_auth()
        clear_server_data()

    except Exception as e:
        log("❌ Unhandled error during update:", e)

def ratelimit_presence():
    activity = {
        "name": "Rate Limited",
        "type": 0,
        "details": "Spotify API Rate Limit Hit",
        "state": f"Retrying in {server_data.rl_time} seconds" if server_data.rl_time else "Retrying soon",
        "assets": {
            "large_image": DISCORD_ASSET_NAME if DISCORD_ASSET_NAME else None,
            "large_text": "Rate Limited"
        },
        "buttons": [{
            "label": "GitHub",
            "url": "https://github.com/Slingexe/SpotifyRPC"
        }]
    }
    if ENABLE_CUSTOM_BUTTON and C_BUTTON:
        activity["buttons"].insert(0, C_BUTTON)
    rpc.update(activity)

# ==== Main Entrypoint ====
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
