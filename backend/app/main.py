from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.api.settings_routes import router as settings_router
from app.api.orchestra_routes import (
    agents_router,
    orchestra_router,
    tasks_router,
    workers_router,
)
from app.api.routes import router, session_router, set_ws, websocket_session
from app.api.websocket_manager import WSManager
from app.config import get_settings
from app.database import init_db, SessionLocal
from app.plugins.bootstrap import register_builtin_plugins
from app.services.seed import seed_if_empty
from app.services.settings_service import SettingsService

ws = WSManager()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    register_builtin_plugins()
    await init_db()
    await seed_if_empty()
    async with SessionLocal() as db:
        await SettingsService().sync_runtime_from_db(db)
    set_ws(ws)
    yield


app = FastAPI(title="AI Orchestra", description="Betriebssystem für KI-Agenten und Coding-Worker", lifespan=lifespan)

settings = get_settings()
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(session_router)
app.include_router(settings_router)
app.include_router(orchestra_router)
app.include_router(tasks_router)
app.include_router(workers_router)
app.include_router(agents_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/sessions/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str):
    await websocket_session(websocket, session_id)
