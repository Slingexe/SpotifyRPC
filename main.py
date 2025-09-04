from __future__ import annotations

import os
import time
import typing as t
import requests
from dataclasses import dataclass
from spotipy import Spotify, SpotifyOAuth, SpotifyException
from dotenv import load_dotenv
from RPC import DiscordRPC


# =========================
# Env & Utilities
# =========================

def env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, str(default)).strip().lower()
    return val in {"1", "true", "t", "yes", "y", "on"}

def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default

def secrets_if(mask: bool, value: t.Any) -> str:
    return str(value) if mask else "***"


@dataclass(frozen=True)
class Config:
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str
    discord_client_id: str
    discord_asset_name: str | None
    use_spotify_asset: bool
    timeout: int
    song_status_icon: bool
    song_status_icon_play: str | None
    song_status_icon_pause: str | None
    server_fetch: bool
    server_url: str
    enable_custom_button: bool
    custom_button_text: str
    custom_button_url: str
    debug: bool
    print_secrets: bool

    @staticmethod
    def from_env() -> "Config":
        load_dotenv()

        return Config(
            spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID", ""),
            spotify_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", ""),
            spotify_redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", ""),
            discord_client_id=os.getenv("DISCORD_CLIENT_ID", ""),
            discord_asset_name=os.getenv("DISCORD_ASSET_NAME") or None,
            use_spotify_asset=env_bool("USE_SPOTIFY_ASSET", False),
            timeout=max(1, env_int("TIMEOUT", 5)),
            song_status_icon=env_bool("SONG_STATUS_ICON", False),
            song_status_icon_play=os.getenv("SONG_STATUS_ICON_PLAY"),
            song_status_icon_pause=os.getenv("SONG_STATUS_ICON_PAUSE"),
            server_fetch=env_bool("SERVER_FETCH", False),
            server_url=os.getenv("SERVER_URL", "http://localhost:62011"),
            enable_custom_button=env_bool("CUSTOM_BUTTON", False),
            custom_button_text=os.getenv("CUSTOM_BUTTON_TEXT", "Now Playing"),
            custom_button_url=os.getenv("CUSTOM_BUTTON_URL", "http://example.com"),
            debug=env_bool("DEBUG", False),
            print_secrets=env_bool("PRINT_SECRETS", False),
        )


# =========================
# Presence Updater
# =========================

class PresenceUpdater:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.sp: Spotify = self._wait_for_spotify_auth()
        self.rpc = DiscordRPC(self.cfg.discord_client_id)
        self.rpc.start({})

        self._last_track_uri: str | None = None
        self._last_is_playing: bool | None = None
        self._last_metadata: dict[str, t.Any] = {}

        self._http = requests.Session()

    # ---------- Logging ----------

    def log(self, *args: t.Any, **kwargs: t.Any) -> None:
        if self.cfg.debug:
            print("[DEBUG]", *args, **kwargs)

    def log_env(self) -> None:
        c = self.cfg
        mask = c.print_secrets
        self.log("✅ Loaded environment variables:")
        self.log(f"  SPOTIFY_CLIENT_ID:      {secrets_if(mask, c.spotify_client_id)}")
        self.log(f"  SPOTIFY_CLIENT_SECRET:  {secrets_if(mask, c.spotify_client_secret)}")
        self.log(f"  SPOTIFY_REDIRECT_URI:   {secrets_if(mask, c.spotify_redirect_uri)}")
        self.log(f"  DISCORD_CLIENT_ID:      {secrets_if(mask, c.discord_client_id)}")
        self.log(f"  DISCORD_ASSET_NAME:     {c.discord_asset_name or 'None'}")
        self.log(f"  USE_SPOTIFY_ASSET:      {c.use_spotify_asset}")
        self.log(f"  TIMEOUT:                {c.timeout}")
        self.log(f"  SONG_STATUS_ICON:       {c.song_status_icon}")
        self.log(f"  SERVER_FETCH:           {c.server_fetch}")
        self.log(f"  SERVER_URL:             {secrets_if(mask, c.server_url) if c.server_fetch else 'N/A'}")
        self.log(f"  ENABLE_CUSTOM_BUTTON:   {c.enable_custom_button}")
        self.log(f"  CUSTOM_BUTTON_TEXT:     {c.custom_button_text if c.enable_custom_button else 'N/A'}")
        self.log(f"  CUSTOM_BUTTON_URL:      {c.custom_button_url if c.enable_custom_button else 'N/A'}")
        self.log(f"  DEBUG:                  {c.debug}")
        self.log(f"  PRINT_SECRETS:          {c.print_secrets}")

    # ---------- Spotify ----------

    def _wait_for_spotify_auth(self) -> Spotify:
        """Loop until we can authenticate + make a basic call (covers network flaps)."""
        while True:
            try:
                auth = SpotifyOAuth(
                    client_id=self.cfg.spotify_client_id,
                    client_secret=self.cfg.spotify_client_secret,
                    redirect_uri=self.cfg.spotify_redirect_uri,
                    scope="user-read-playback-state",
                )
                sp = Spotify(auth_manager=auth, retries=0)
                # simple ping to ensure token/network is good
                self._spotify_api_call(sp.current_playback)
                print("✅ Spotify authenticated and reachable.")
                return sp
            except (SpotifyException, requests.exceptions.RequestException) as e:
                print("⛔ Spotify not reachable — waiting for internet...")
                self.log("Auth/connect error:", e)
                time.sleep(5)

    def _spotify_api_call(self, func: t.Callable, *args: t.Any, **kwargs: t.Any) -> t.Any:
        """Run a Spotify API call and handle 429 globally, returning the result."""
        while True:
            try:
                return func(*args, **kwargs)
            except SpotifyException as e:
                if e.http_status == 429:
                    retry_after = int(e.headers.get("Retry-After", 30))
                    self.log(f"⚠️ Spotify rate limit — sleeping {retry_after}s")
                    # show rate-limit presence without touching RPC elsewhere
                    self._ratelimit_presence(retry_after)
                    time.sleep(retry_after)
                    # clear presence once we resume trying
                    self.rpc.stop()
                else:
                    raise

    # ---------- Fetch Playback ----------

    def _fetch_playback(self) -> dict[str, t.Any] | None:
        """
        Returns a normalized playback dict or None if nothing playable.
        Normalized shape:
        {
          "is_playing": bool,
          "uri": str,
          "title": str,
          "artist": str,
          "duration": int (sec),
          "progress": int (sec),
          "album_name": str,
          "album_img": str | "spotify",
          "context_type": str,
          "context_uri": str,
          "context_name": str,
          "play_name": str | None
        }
        """
        if self.cfg.server_fetch:
            try:
                resp = self._http.get(self.cfg.server_url, timeout=5)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                self.log("Could not fetch from server:", e)
                return None

            # Server contract
            if data is None or data.get("is_offline") is True:
                return None

            return {
                "is_playing": bool(data["is_playing"]),
                "uri": data["uri"],
                "title": data["title"],
                "artist": data["artist"],
                "duration": int(data["duration"]),
                "progress": int(data["progress"]),
                "album_name": data.get("context_name", ""),
                "album_img": data.get("artURL", "spotify") or "spotify",
                "context_type": data.get("context_type", "") or "",
                "context_uri": data.get("context_uri", "") or "",
                "context_name": data.get("context_name", "") or "",
                "play_name": data.get("context_name", ""),
            }

        # Spotify API branch
        sp_playback = self._spotify_api_call(self.sp.current_playback)
        if not sp_playback:
            return None
        if not sp_playback.get("is_playing"):
            return None
        if sp_playback.get("progress_ms") is None:
            return None

        item = sp_playback.get("item")
        if not item:
            return None

        title = item.get("name", "Unknown")
        artists = ", ".join(a.get("name", "Unknown") for a in item.get("artists", []))
        duration = (item.get("duration_ms") or 0) // 1000
        progress = (sp_playback.get("progress_ms") or 0) // 1000
        album_name = (item.get("album", {}) or {}).get("name", "")
        album_img = (
            ((item.get("album", {}) or {}).get("images") or [{}])[0].get("url")
            if self.cfg.use_spotify_asset else "spotify"
        )

        context = sp_playback.get("context") or {}
        context_type = context.get("type") or ""
        context_uri = context.get("uri") or ""
        play_name = None
        context_name = ""

        try:
            if context_type == "playlist" and context_uri:
                playlist_id = context_uri.split(":")[-1]
                playlist = self._spotify_api_call(self.sp.playlist, playlist_id)
                play_name = f"playlist '{playlist['name']}'"
                context_name = playlist["name"]
            elif context_type == "album" and context_uri:
                album_id = context_uri.split(":")[-1]
                album = self._spotify_api_call(self.sp.album, album_id)
                play_name = f"album '{album['name']}'"
                context_name = album["name"]
            elif context_uri and ":collection" in context_uri:
                play_name = "Liked Songs"
                context_type = "user_collection"
                context_name = "Liked Songs"
        except Exception as e:
            self.log("Context lookup failed:", e)

        return {
            "is_playing": True,
            "uri": item.get("uri", ""),
            "title": title,
            "artist": artists,
            "duration": duration,
            "progress": progress,
            "album_name": album_name,
            "album_img": album_img or "spotify",
            "context_type": context_type,
            "context_uri": context_uri,
            "context_name": context_name,
            "play_name": play_name,
        }

    # ---------- Discord Activity ----------

    def _build_activity(
        self,
        *,
        title: str,
        artist: str,
        album_name: str,
        album_img: str | None,
        play_name: str | None,
        duration: int | None,
        progress: int | None,
        paused: bool = False,
    ) -> dict[str, t.Any]:
        # timestamps only when playing (avoid drift on pauses)
        now = int(time.time())
        timestamps: dict[str, int] | None = None
        if not paused and duration is not None and progress is not None:
            timestamps = {
                "start": now - max(progress, 0),
                "end": now + max(duration - progress, 0),
            }

        small_img = None
        small_txt = None
        if self.cfg.song_status_icon:
            small_img = (self.cfg.song_status_icon_pause if paused else self.cfg.song_status_icon_play) or ("pause" if paused else "play")
            small_txt = "Paused" if paused else "Playing"

        buttons = [{
            "label": "GitHub",
            "url": "https://github.com/Slingexe/SpotifyRPC",
        }]
        if self.cfg.enable_custom_button:
            buttons.insert(0, {"label": self.cfg.custom_button_text, "url": self.cfg.custom_button_url})

        assets = {
            "large_image": album_img or self.cfg.discord_asset_name or "spotify",
            "large_text": album_name or "Spotify",
        }
        if small_img:
            assets["small_image"] = small_img
        if small_txt:
            assets["small_text"] = small_txt

        activity = {
            "name": title if not paused else f"{title} - Paused",
            "type": 0,
            "details": f"by {artist}",
            "state": f"Listening to {play_name} on Spotify" if play_name else "Listening to Spotify",
            "assets": assets,
            "buttons": buttons,
        }
        if timestamps:
            activity["timestamps"] = timestamps
        return activity

    def _ratelimit_presence(self, time_to_wait: int | None) -> None:
        buttons = [{
            "label": "GitHub",
            "url": "https://github.com/Slingexe/SpotifyRPC",
        }]
        if self.cfg.enable_custom_button:
            buttons.insert(0, {"label": self.cfg.custom_button_text, "url": self.cfg.custom_button_url})

        activity = {
            "name": "Rate Limited",
            "type": 0,
            "details": "Spotify API Rate Limit Hit",
            "state": f"Retrying in {time_to_wait} seconds" if time_to_wait else "Retrying soon",
            "assets": {
                "large_image": self.cfg.discord_asset_name or "spotify",
                "large_text": "Rate Limited",
            },
            "buttons": buttons,
        }
        self.rpc.update(activity)

    # ---------- Public: one tick ----------

    def tick(self) -> None:
        """One update cycle: fetch playback, update presence, handle errors."""
        try:
            pb = self._fetch_playback()

            # nothing playable
            if not pb:
                if self._last_track_uri:
                    self.log("Clearing RPC presence (nothing playing).")
                    self.rpc.stop()
                    self._last_track_uri = None
                    self._last_is_playing = None
                    self._last_metadata = {}
                return

            is_playing = bool(pb["is_playing"])
            title = pb["title"]
            artist = pb["artist"]
            duration = int(pb["duration"])
            progress = int(pb["progress"])
            album_name = pb["album_name"]
            album_img = pb["album_img"]
            play_name = pb.get("play_name")
            track_uri = pb["uri"]

            self.log(f"Current track: {title} by {artist} ({'playing' if is_playing else 'paused'})")
            self.log(f"Track details: duration={duration}s, progress={progress}s, album={album_name}, image={album_img}")

            if is_playing:
                activity = self._build_activity(
                    title=title,
                    artist=artist,
                    album_name=album_name,
                    album_img=album_img,
                    play_name=play_name,
                    duration=duration,
                    progress=progress,
                    paused=False,
                )
                self.log("Updating RPC (playing):", title)
                self.rpc.update(activity)
                self._last_track_uri = track_uri
                self._last_is_playing = True
                self._last_metadata = {
                    "title": title, "artist": artist, "duration": duration,
                    "progress": progress, "album": album_name, "image": album_img
                }
            else:
                # only push a paused presence if we previously had playing metadata
                if self._last_is_playing and self._last_metadata:
                    activity = self._build_activity(
                        title=self._last_metadata["title"],
                        artist=self._last_metadata["artist"],
                        album_name=self._last_metadata["album"],
                        album_img=self._last_metadata["image"],
                        play_name=play_name,
                        duration=None,
                        progress=None,
                        paused=True,
                    )
                    self.log("Updating RPC (paused):", self._last_metadata["title"])
                    self.rpc.update(activity)
                    self._last_is_playing = False

        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 5))
                self.log(f"⚠️ Spotify rate limit — sleeping {retry_after}s.")
                self._ratelimit_presence(retry_after)
                time.sleep(retry_after)
            else:
                self.log("🔁 Spotify API error — re-authenticating:", e)
                self.sp = self._wait_for_spotify_auth()

        except requests.exceptions.RequestException as e:
            self.log("🔁 Network error — re-authenticating Spotify:", e)
            self.sp = self._wait_for_spotify_auth()

        except Exception as e:
            self.log("❌ Unhandled error during update:", e)

    # ---------- Clean shutdown ----------

    def shutdown(self) -> None:
        try:
            self.rpc.stop()
        except Exception:
            pass


# =========================
# Entrypoint
# =========================

if __name__ == "__main__":
    cfg = Config.from_env()
    updater = PresenceUpdater(cfg)
    updater.log_env()

    print("🎧 Spotify → Discord (with custom RPC) started.")
    try:
        while True:
            updater.tick()
            time.sleep(cfg.timeout)
    except KeyboardInterrupt:
        updater.log("Shutting down...")
        updater.shutdown()
