from discord_rpc import DiscordRPC
import time, os

client_id = os.getenv("DISCORD_CLIENT_ID")
rpc = DiscordRPC(client_id)

playing_activity = {
    "name": "Spotify",
    "type": 0,
    "details": "Never Gonna Give You Up",
    "state": "Rick Astley",
    "timestamps": {"start": int(time.time())},
    "assets": {
        "large_image": "spotify_logo",
        "large_text": "Listening on Spotify"
    }
}

rpc.start(playing_activity)

try:
    while True:
        time.sleep(30)

        # pretend the song paused – push an update
        paused_activity = playing_activity | {"state": "Paused"}
        rpc.update(paused_activity)

        # 30 s later, simulate new track
        time.sleep(30)
        next_track = playing_activity | {
            "details": "Bohemian Rhapsody",
            "state": "Queen"
        }
        rpc.update(next_track)

except KeyboardInterrupt:
    rpc.stop()
