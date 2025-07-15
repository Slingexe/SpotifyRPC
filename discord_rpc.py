import asyncio
import json
import time
import websockets
import os
import threading


class DiscordRPC:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.ws = None
        self.keep_running = False
        self.thread = None
        self.loop = None

    async def _send_activity(self, activity: dict):
        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {
                "pid": os.getpid(),
                "activity": activity
            },
            "nonce": str(time.time())
        }
        await self.ws.send(json.dumps(payload))
        print("[RPC] Sent activity")

    async def _run(self, activity: dict):
        try:
            uri = f"ws://127.0.0.1:6463/?v=1&client_id={self.client_id}"
            async with websockets.connect(uri) as websocket:
                self.ws = websocket
                self.loop = asyncio.get_event_loop()
                self.keep_running = True
                await self._send_activity(activity)

                while self.keep_running:
                    await asyncio.sleep(15)
        except Exception as e:
            print(f"[RPC] Error: {e}")

    def start(self, activity: dict):
        if self.thread and self.thread.is_alive():
            print("[RPC] Already running")
            return

        self.thread = threading.Thread(target=lambda: asyncio.run(self._run(activity)), daemon=True)
        self.thread.start()
        print("[RPC] Started")

    def update(self, activity: dict):
        if not self.ws or not self.loop:
            print("[RPC] Not connected, cannot update.")
            return
        
        asyncio.run_coroutine_threadsafe(
            self._send_activity(activity), 
            self.loop
        )

    def stop(self):
        self.keep_running = False
        print("[RPC] Stopping...")
