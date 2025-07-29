from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import uvicorn

class TrackInfo(BaseModel):
    title: str = None
    artist: str = None
    uri: str = None
    artURL: str = None
    duration_ms: float = 0
    progress_ms: float = 0
    context_type: str = None
    context_uri: str = None
    context_name: str = None

class NowPlayingServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 62011):
        self.host = host
        self.port = port
        self._data = TrackInfo()
        self.app = FastAPI()
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.app.get("/")(self.get_now_playing)

    def get_now_playing(self):
        return self._data

    def update(self, *, TrackInfo: TrackInfo):
        self._data = TrackInfo

    def start(self):
        thread = threading.Thread(
            target=uvicorn.run,
            kwargs={
                "app": self.app,
                "host": self.host,
                "port": self.port,
                "log_level": "info"
            },
            daemon=True
        )
        thread.start()
