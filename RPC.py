import os
import struct
import json
import time
import threading
import socket
import sys

class DiscordRPC:
    def __init__(self, client_id):
        self.client_id = client_id
        self.sock = None
        self.running = False
        self.thread = None
        self.activity = None

    def _get_ipc_path(self):
        if sys.platform == "win32":
            return r"\\?\pipe\discord-ipc-0"
        uid = os.getuid()
        xdg = os.environ.get("XDG_RUNTIME_DIR")
        candidates = []
        if xdg:
            candidates += [os.path.join(xdg, f"discord-ipc-{i}") for i in range(3)]
            candidates.append(
                os.path.join(xdg, "app/com.discordapp.Discord/discord-ipc-0")
            )
        candidates += [
            f"/run/user/{uid}/discord-ipc-{i}" for i in range(3),
            f"/run/user/{uid}/app/com.discordapp.Discord/discord-ipc-0"
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "discord-ipc-0")


    def _send_data(self, op, payload):
        data = json.dumps(payload).encode("utf-8")
        header = struct.pack("<II", op, len(data))
        self.sock.sendall(header + data)

    def _handshake(self):
        self._send_data(0, {"v": 1, "client_id": self.client_id})
        self._read_data()  # Wait for READY

    def _read_data(self):
        header = self.sock.recv(8)
        if not header:
            raise RuntimeError("Disconnected")
        op, length = struct.unpack("<II", header)
        data = self.sock.recv(length)
        return op, json.loads(data.decode("utf-8"))

    def _set_activity(self):
        if not self.activity:
            return
        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {
                "pid": os.getpid(),
                "activity": self.activity
            },
            "nonce": str(time.time())
        }
        self._send_data(1, payload)
        self.sock.settimeout(1.0)
        try:
            op, resp = self._read_data()
            if resp.get("evt") == "ERROR" or resp.get("code"):
                print("[RPC] Rejected SET_ACTIVITY:", resp)
        except socket.timeout:
            pass
        finally:
            self.sock.settimeout(None)

    def _ipc_loop(self):
        while self.running:
            try:
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.connect(self._get_ipc_path())
                self._handshake()
                self._set_activity()

                while self.running:
                    time.sleep(15)
                    self._set_activity()

            except Exception as e:
                print(f"[RPC] Error: {e}")
                time.sleep(5)

    def start(self, activity):
        self.activity = activity
        if self.thread and self.thread.is_alive():
            print("[RPC] Already running")
            return
        self.running = True
        self.thread = threading.Thread(target=self._ipc_loop, daemon=True)
        self.thread.start()
        print("[RPC] Started")

    def update(self, activity):
        self.activity = activity
        try:
            # Check if socket is valid by sending empty payload
            self._set_activity()
            print("[RPC] Updated activity")
        except Exception as e:
            print(f"[RPC] Update failed, attempting reconnect: {e}")
            try:
                if self.sock:
                    self.sock.close()
            except:
                pass
            
            # Try full reconnect
            try:
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.connect(self._get_ipc_path())
                self._handshake()
                self._set_activity()
            except Exception as ex:
                print(f"[RPC] Reconnect failed: {ex}")


    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        if self.sock:
            self.sock.close()
        print("[RPC] Stopped")

