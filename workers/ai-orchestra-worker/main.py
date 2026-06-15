#!/usr/bin/env python3
"""
AI Orchestra Worker — Windows Notebook Dienst (Skeleton)

Verbindet sich per HTTPS mit AI Orchestra, registriert sich, sendet Heartbeats
und holt Implementierungs-Jobs ab. Keine Cursor-Automatisierung — der Mensch
oder ein lokales Tool führt die Implementierung aus; der Worker koordiniert
Git, Status-Meldungen und Job-Lifecycle.

Usage:
  set ORCHESTRA_URL=http://192.168.111.43:8080/api
  python main.py
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

ORCHESTRA_URL = os.environ.get("ORCHESTRA_URL", "http://127.0.0.1:8080/api").rstrip("/")
WORKER_NAME = os.environ.get("WORKER_NAME", platform.node())
WORKER_TYPE = os.environ.get("WORKER_TYPE", "cursor")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "10"))
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "30"))


def _http(method: str, path: str, body: dict | None = None) -> Any:
    url = f"{ORCHESTRA_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else None


def detect_capabilities() -> dict[str, Any]:
    def has(cmd: str) -> bool:
        return shutil.which(cmd) is not None

    caps = {
        "worker_type": WORKER_TYPE,
        "cursor_available": bool(shutil.which("cursor") or os.path.exists(
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe")
        )),
        "git_available": has("git"),
        "node_available": has("node"),
        "python_available": has("python") or has("py"),
        "docker_available": has("docker"),
        "powershell_available": has("powershell") or platform.system() == "Windows",
        "claude_code_available": has("claude"),
        "continue_available": False,
        "installed_versions": {},
        "extra": {"platform": platform.platform()},
    }
    if caps["node_available"]:
        try:
            caps["installed_versions"]["node"] = subprocess.check_output(
                ["node", "-v"], text=True
            ).strip()
        except subprocess.CalledProcessError:
            pass
    return caps


def register() -> str:
    resp = _http(
        "POST",
        "/workers/register",
        {
            "name": WORKER_NAME,
            "worker_type": WORKER_TYPE,
            "hostname": platform.node(),
            "capabilities": detect_capabilities(),
        },
    )
    worker_id = resp["id"]
    print(f"[worker] registered id={worker_id}")
    return worker_id


def heartbeat(worker_id: str, status: str = "idle") -> None:
    _http(
        "POST",
        f"/workers/{worker_id}/heartbeat",
        {"status": status, "capabilities": detect_capabilities()},
    )


def poll_job(worker_id: str) -> dict | None:
    resp = _http("GET", f"/workers/{worker_id}/jobs/poll")
    return resp.get("job")


def report(worker_id: str, job_id: str, endpoint: str, body: dict) -> None:
    _http("POST", f"/workers/{worker_id}/jobs/{job_id}/{endpoint}", body)


def execute_job(worker_id: str, job: dict) -> None:
    job_id = job["job_id"]
    print(f"[worker] job {job_id} — {job.get('description', '')}")
    report(worker_id, job_id, "start", {})
    report(worker_id, job_id, "progress", {"message": "Analysiere Repository…"})

    # Placeholder: echte Implementierung erfolgt manuell in Cursor/IDE.
    # Der Worker meldet Status und kann Git-Befehle ausführen.
    repo = job.get("project_knowledge", {}).get("project_name", "project")
    report(worker_id, job_id, "progress", {"message": f"Bereit für Implementierung in {repo}"})

    prompt_path = os.path.join(os.getcwd(), f"orchestra-job-{job_id[:8]}.md")
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(job.get("final_prompt", ""))
    print(f"[worker] Prompt geschrieben: {prompt_path}")
    print("[worker] Bitte Implementierung in Cursor durchführen, dann Enter drücken…")
    try:
        input()
    except EOFError:
        pass

    report(
        worker_id,
        job_id,
        "complete",
        {
            "summary": "Manuelle Implementierung abgeschlossen (Skeleton)",
            "changed_files": [],
            "prompt_file": prompt_path,
        },
    )


def main() -> int:
    print(f"[worker] AI Orchestra Worker → {ORCHESTRA_URL}")
    try:
        worker_id = register()
    except urllib.error.URLError as e:
        print(f"[worker] Registrierung fehlgeschlagen: {e}", file=sys.stderr)
        return 1

    last_hb = 0.0
    while True:
        now = time.time()
        if now - last_hb >= HEARTBEAT_INTERVAL:
            try:
                heartbeat(worker_id, "idle")
            except urllib.error.URLError:
                print("[worker] heartbeat failed")
            last_hb = now

        try:
            job = poll_job(worker_id)
            if job:
                heartbeat(worker_id, "busy")
                execute_job(worker_id, job)
                heartbeat(worker_id, "idle")
        except urllib.error.URLError as e:
            print(f"[worker] poll error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
