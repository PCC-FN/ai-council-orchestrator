# AI Orchestra Worker

Kleiner Dienst für dein Windows-Notebook. Verbindet sich per HTTPS mit AI Orchestra,
registriert sich, sendet Heartbeats und holt Implementierungs-Jobs ab.

**Keine Cursor-Automatisierung** — kein AutoHotkey, keine Tastatur/Maus-Steuerung.
Der Worker koordiniert Jobs, schreibt den Prompt lokal und meldet Status zurück.

## Start

```powershell
cd workers\ai-orchestra-worker
copy .env.example .env
# ORCHESTRA_URL anpassen
python main.py
```

## Protokoll

- `POST /api/workers/register`
- `POST /api/workers/{id}/heartbeat`
- `GET  /api/workers/{id}/jobs/poll`
- `POST /api/workers/{id}/jobs/{job_id}/start|progress|complete|fail`
