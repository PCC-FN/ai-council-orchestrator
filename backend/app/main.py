from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth_routes import auth_router
from app.api.settings_routes import router as settings_router
from app.api.orchestra_routes import (
    agents_router,
    orchestra_router,
    tasks_router,
    workers_router,
)
from app.api.routes import router, session_router, set_ws, websocket_session
from app.api.vibe_routes import (
    set_vibe_ws,
    vibe_job_websocket,
    vibe_router,
    vibe_worker_websocket,
    vibe_workers_router,
)
from app.api.vibe_websocket import VibeWSManager
from app.api.websocket_manager import WSManager
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.plugins.bootstrap import register_builtin_plugins
from app.services.seed import seed_auth_users, seed_if_empty
from app.services.settings_service import SettingsService

ws = WSManager()
vibe_ws = VibeWSManager()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    register_builtin_plugins()
    await init_db()
    await seed_if_empty()
    await seed_auth_users()
    async with SessionLocal() as db:
        await SettingsService().sync_runtime_from_db(db)
    set_ws(ws)
    set_vibe_ws(vibe_ws)
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
app.include_router(auth_router)
app.include_router(session_router)
app.include_router(settings_router)
app.include_router(orchestra_router)
app.include_router(tasks_router)
app.include_router(workers_router)
app.include_router(agents_router)
app.include_router(vibe_router)
app.include_router(vibe_workers_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/sessions/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str):
    await websocket_session(websocket, session_id)


@app.websocket("/ws/vibe/jobs/{job_id}")
async def vibe_job_ws(websocket: WebSocket, job_id: str):
    await vibe_job_websocket(websocket, job_id)


@app.websocket("/ws/worker")
async def vibe_worker_ws(websocket: WebSocket):
    async with SessionLocal() as db:
        await vibe_worker_websocket(websocket, db)
