# AI Council Coding Orchestrator

Zentraler Orchestrator für mehrstufige Coding-Aufgaben: **ChatGPT (Architektur)**, **Claude (Review)**, **Compose2 (Umsetzbarkeit / Implementierung)** mit gespeicherter Begründung, Konsens, finalem Prompt, Freigaben und Markdown-Export.

## Features (MVP)

- FastAPI + SQLite (async), modularer **Provider** (OpenAI, Anthropic, Compose2-Placeholder, Mock)
- Strukturierte Runden: Initialbewertung → Cross-Review → Konsens → Freigaben → Prompt → Prompt-Review → (Compose2-Handoff) → Umsetzung → Code-Review → optional Verbesserungs-Prompt
- **Compose2 manuell**: Prompt kopieren/exportieren, Status „umgesetzt“ setzen; optionale `api`-Modus-URL (generischer Platzhalter)
- React + Vite UI, WebSocket für Live-Events
- Sichere Projektdatei-Helfer: Pfad-Sandbox, Größenlimit, Ausschluss sensibler Muster
- Vorbereitung **MCP**: `app/mcp/stubs.py` listet geplante Tool-Namen

## Schnellstart (lokal)

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
copy ..\.env.example ..\.env   # Windows: copy ..\.env.example ..\.env
# Für Demo ohne API-Keys:
# USE_MOCK_PROVIDERS=true in .env setzen
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: `http://localhost:5173` (Proxy `/api` und `/ws` → Port 8000)

## Docker

```bash
cp .env.example .env
docker compose up --build
```

API: `http://localhost:8000` — ohne Vite-Proxy Frontend separat starten oder einen eigenen Reverse-Proxy nutzen.

## Umgebungsvariablen

Siehe `.env.example`. **API-Keys nie ins Frontend legen** — nur Server-seitig in `.env`.

## Tests

```bash
cd backend
pip install -r requirements.txt
$env:USE_MOCK_PROVIDERS="true"   # PowerShell
python -m pytest tests/ -v
```

## Beispiele

- `examples/sample-project` — Mini-Repo für `repository_path`
- `examples/sample_session.md` — Ablauf per HTTP

## Architektur

- `app/services/orchestrator.py` — Ablauf und Speicherung
- `app/services/providers/*` — austauschbare KI-Provider
- `app/services/export_markdown.py` — Session-Export
- `app/services/project_context.py` — sichere Datei-Indexierung/-Reads

## Nächste Schritte (wie von dir skizziert)

- Echte Compose2-API sobald verfügbar (Contract in `Compose2Provider` anpassen)
- MCP-Server, der die REST-/DB-Operationen wrappt
- Git-Diff-Review, automatische Tests gegen das Ziel-Repo

## Lizenz

MIT (anpassen nach Bedarf).
