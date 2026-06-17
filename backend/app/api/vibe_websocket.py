from __future__ import annotations

from typing import Any

from fastapi import WebSocket


class VibeWSManager:
    """WebSocket connections for vibe coding (browser + workers)."""

    def __init__(self) -> None:
        self._browser_channels: dict[str, list[WebSocket]] = {}
        self._workers: dict[str, WebSocket] = {}
        self._worker_ids: dict[WebSocket, str] = {}

    async def connect_browser(self, channel: str, ws: WebSocket) -> None:
        await ws.accept()
        self._browser_channels.setdefault(channel, []).append(ws)

    def disconnect_browser(self, channel: str, ws: WebSocket) -> None:
        conns = self._browser_channels.get(channel, [])
        if ws in conns:
            conns.remove(ws)

    async def connect_worker(self, worker_id: str, ws: WebSocket) -> None:
        old = self._workers.get(worker_id)
        if old and old is not ws:
            try:
                await old.close()
            except Exception:
                pass
        self._workers[worker_id] = ws
        self._worker_ids[ws] = worker_id

    def disconnect_worker(self, ws: WebSocket) -> str | None:
        worker_id = self._worker_ids.pop(ws, None)
        if worker_id and self._workers.get(worker_id) is ws:
            del self._workers[worker_id]
        return worker_id

    def get_worker_socket(self, worker_id: str) -> WebSocket | None:
        return self._workers.get(worker_id)

    def is_worker_online(self, worker_id: str) -> bool:
        return worker_id in self._workers

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._browser_channels.get(channel, []):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_browser(channel, ws)

    async def send_to_worker(self, worker_id: str, message: dict[str, Any]) -> bool:
        ws = self._workers.get(worker_id)
        if not ws:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception:
            self.disconnect_worker(ws)
            return False
