import asyncio
import websockets
import json
import time
import threading
import os

class DiscordRPC:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.ws = None
        self.thread = None
        self.loop = None
        self.activity = None
        self.keep_running = False

    async def _connect(self):
        uri = f"ws://127.0.0.1:6463/?v=1&client_id={self.client_id}"
        return await websockets.connect(uri)

    async def _heartbeat_loop(self):
        try:
            while self.keep_running and self.ws:
                await self.ws.send(json.dumps({"op": 1, "d": None}))  # heartbeat
                await asyncio.sleep(15)
        except Exception as e:
            print(f"[RPC] Heartbeat error: {e}")

    async def _send_activity(self):
        if not self.ws or not self.activity:
            return

        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {
                "pid": os.getpid(),
                "activity": self.activity
            },
            "nonce": str(time.time())
        }

        try:
            await self.ws.send(json.dumps(payload))
            print("[RPC] Activity sent")
        except Exception as e:
            print(f"[RPC] Failed to send activity: {e}")

    async def _rpc_loop(self):
        while self.keep_running:
            try:
                print("[RPC] Connecting to Discord...")
                async with await self._connect() as ws:
                    self.ws = ws

                    # Wait for READY
                    while True:
                        message = await ws.recv()
                        data = json.loads(message)
                        if data.get("evt") == "READY":
                            print("[RPC] Ready received")
                            break

                    await self._send_activity()

                    heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                    while self.keep_running:
                        await asyncio.sleep(1)

                    heartbeat_task.cancel()

            except Exception as e:
                print(f"[RPC] Connection error: {e}")
                self.ws = None
                await asyncio.sleep(5)

    def _start_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._rpc_loop())

    def start(self, activity: dict):
        if self.thread and self.thread.is_alive():
            print("[RPC] Already running")
            self.update(activity)
            return

        self.activity = activity
        self.keep_running = True
        self.thread = threading.Thread(target=self._start_loop, daemon=True)
        self.thread.start()
        print("[RPC] Starting...")

    def update(self, activity: dict):
        self.activity = activity
        if self.loop and self.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._send_activity(), self.loop)
            try:
                future.result(timeout=2)
            except Exception as e:
                print(f"[RPC] Update failed: {e}")

    def stop(self):
        self.keep_running = False
        print("[RPC] Stopping...")
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        if self.loop:
            self.loop.stop()
            self.loop = None
