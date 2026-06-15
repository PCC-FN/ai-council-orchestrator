from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.api.orchestra_routes import (
    agents_router,
    orchestra_router,
    tasks_router,
    workers_router,
)
from app.api.routes import router, session_router, set_ws, websocket_session
from app.api.websocket_manager import WSManager
from app.config import get_settings
from app.database import init_db
from app.plugins.bootstrap import register_builtin_plugins
from app.services.seed import seed_if_empty

ws = WSManager()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    register_builtin_plugins()
    await init_db()
    await seed_if_empty()
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
app.include_router(orchestra_router)
app.include_router(tasks_router)
app.include_router(workers_router)
app.include_router(agents_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/settings")
async def runtime_settings():
    """Non-secret runtime info the frontend needs (never expose API keys)."""
    s = get_settings()
    using_mock = s.use_mock_providers or not (
        s.openai_api_key.strip() and s.anthropic_api_key.strip()
    )
    return {
        "product": "AI Orchestra",
        "compose2_mode": s.compose2_mode,
        "use_mock_providers": s.use_mock_providers,
        "mock_active": using_mock,
        "openai_configured": bool(s.openai_api_key.strip()),
        "anthropic_configured": bool(s.anthropic_api_key.strip()),
        "compose2_configured": bool(s.compose2_api_key.strip()),
    }


@app.websocket("/ws/sessions/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str):
    await websocket_session(websocket, session_id)
