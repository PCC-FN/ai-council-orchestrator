# AI Orchestra

**AI Orchestra ist kein Chatbot** — es ist ein Betriebssystem für KI-Agenten und Coding-Worker.

Der Benutzer beschreibt ein gewünschtes Feature. AI Orchestra übernimmt vollständig die Orchestrierung: Agenten diskutieren im Hintergrund, der Coordinator steuert 12 Phasen, Worker setzen um.

> Ausführliche Architektur: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Plattform-Erweiterung

- **Coordinator** — Workflow-Manager ohne eigene KI (`app/coordinator/`)
- **Knowledge Layer** — dauerhaftes Projektwissen (`app/knowledge/`)
- **Konfigurierbare Agenten** — `GET/POST /agents`
- **Worker-System** — Registrierung, Heartbeat, Job-Polling (`/workers/*`)
- **Job-System** — Implementierungs-Jobs mit Projektwissen
- **Event-System** — persistenter Audit-Log (`GET /orchestra/events`)
- **12-Phasen-Workflow** — jede Phase einzeln gespeichert
- **Plugin-Registry** — erweiterbar ohne Kern-Änderungen
- **Windows Worker** — `workers/ai-orchestra-worker/` (keine Cursor-Automatisierung)

## Features

- **FastAPI + SQLite (async)**, modulare **Provider** (OpenAI, Anthropic, Compose2-Placeholder, Mock)
- **Strukturierte Runden**: Normalisierung → Initial Assessment → Cross Review → Konsens → Freigabe → Prompt Engineering → Prompt Review → (Compose2-Handoff) → Implementation → Code Review
- **React + Vite + TypeScript + Tailwind** UI mit Dashboard, Projektverwaltung, Session-Detail, Live-Status (WebSocket), Dark Mode
- **Mock-Modus**: vollständig nutzbar ohne API-Keys — die Agenten liefern realistische Beispielantworten
- **Compose2 manuell**: Prompt kopieren/exportieren, Status „umgesetzt“ setzen; optionaler `api`-Modus vorbereitet
- Sichere Projektdatei-Helfer (Pfad-Sandbox, Größenlimit, Ausschluss sensibler Muster)
- **Markdown-Export** der kompletten Session

## Architekturüberblick

```
┌────────────┐      /api (REST)        ┌─────────────────────┐
│  Frontend  │ ───────────────────────▶│  FastAPI Backend    │
│ React/Vite │      /ws (WebSocket)    │  Orchestrator       │
│  (nginx)   │ ◀───────────────────────│  Provider-Registry  │
└────────────┘     Live-Events         │  SQLite (async)     │
                                        └─────────────────────┘
```

- `backend/app/services/orchestrator.py` — Ablauf, Runden und Persistenz
- `backend/app/services/providers/*` — austauschbare KI-Provider
- `backend/app/api/routes.py` — REST-Endpunkte
- `frontend/src/pages/*` — Dashboard, Projekte, Neue Session, Session-Detail
- `frontend/src/components/*` — Layout-, Projekt-, Session- und UI-Komponenten

## Schnellstart mit Docker Compose (empfohlen)

```bash
cp .env.example .env          # Windows: copy .env.example .env
# Für eine reine Demo nichts weiter ändern (USE_MOCK_PROVIDERS=true ist Standard).
docker compose up --build
```

- **Frontend (UI):** http://localhost:8080
- **API / Swagger-Docs:** http://localhost:8000/docs

nginx im Frontend-Container leitet `/api` und `/ws` automatisch ans Backend weiter — es ist kein zusätzlicher Proxy nötig.

## Start ohne Docker (lokale Entwicklung)

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env     # Windows: copy ..\.env.example ..\.env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://localhost:5173 — der Vite-Dev-Server proxyt `/api` und `/ws` auf Port 8000.

## Mock-Modus (ohne API-Keys)

Das Tool funktioniert vollständig ohne externe Keys:

- `USE_MOCK_PROVIDERS=true` in der `.env` **oder** einfach keine Keys setzen — fehlende Provider fallen automatisch auf den `MockProvider` zurück.
- Der Mock liefert realistische, strukturierte Beispielantworten (Bewertungen, Bedenken, Konsens, finaler Prompt), sodass sich der komplette Ablauf durchspielen lässt.
- In der UI erscheint links der Hinweis **„Mock-Modus aktiv“**.

## API-Key-Konfiguration (echte Modelle)

In der Backend-`.env` (Keys verbleiben **immer** serverseitig, nie im Frontend):

```env
USE_MOCK_PROVIDERS=false
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_OPENAI_MODEL=gpt-4o-mini
DEFAULT_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

Danach neu starten (`docker compose up -d --build` bzw. uvicorn neu starten). Ist nur ein Key gesetzt, nutzt nur der entsprechende Agent das echte Modell, die übrigen bleiben im Mock.

## Compose2 — manueller Modus

`COMPOSE2_MODE=manual` (Standard):

1. Sobald der finale Prompt freigegeben ist, erscheint der Hinweis **„Compose2 läuft im manuellen Modus“**.
2. **Prompt kopieren** und in Compose2 ausführen.
3. Im Bereich **Implementation Review** geänderte Dateien + Zusammenfassung eintragen und **„Als umgesetzt markieren“**.
4. **Review starten** lässt ChatGPT + Claude die Umsetzung prüfen; bei offenen Punkten lässt sich ein **Verbesserungs-Prompt** erzeugen.

`COMPOSE2_MODE=api` mit `COMPOSE2_BASE_URL` ist als Platzhalter-Contract vorbereitet (`Compose2Provider`).

## Ablauf einer Council-Session

1. **Projekt anlegen** (Name, Beschreibung, Repository-Pfad, Coding-/Security-Regeln, Tech-Stack, ausgeschlossene Pfade).
2. **Neue Council-Session**: Projekt wählen, Titel, Aufgabe sowie optional betroffene Dateien, gewünschtes Ergebnis und Einschränkungen angeben → **Council starten**.
3. **Runden** laufen Schritt für Schritt (Button „Nächste Runde“) oder automatisch („Automatisch bis Prompt“):
   - **Initial Assessment** — jeder Agent bewertet die Aufgabe.
   - **Cross Review** — die Agenten kommentieren die Einschätzungen der anderen.
   - **Consensus** — der Orchestrator konsolidiert alles zu einem Konsens.
   - **Approval** — die Agenten geben den Konsens frei (oder manuelle Freigabe).
   - **Prompt Engineering** — der finale Coding-Prompt wird erzeugt.
   - **Prompt Review** — die Agenten prüfen den Prompt; alle drei Freigaben → Prompt bereit.
4. **Finaler Prompt**: anzeigen, kopieren, als Markdown exportieren, erneut optimieren, manuell freigeben, **an Compose2 übergeben**.
5. **Implementation Review**: Ergebnis eintragen, Review starten, optional Verbesserungs-Prompt.

Die UI zeigt jederzeit, **welche Runde läuft**, **welcher Agent gerade arbeitet**, **was entschieden wurde** und **was als Nächstes passiert**.

## Wichtige API-Endpunkte

Projects: `GET/POST /api/projects`, `GET/PUT/DELETE /api/projects/:id`
Sessions: `GET/POST /api/sessions`, `GET /api/sessions/:id`,
`POST /api/sessions/:id/start`, `/run-next-round`, `/approve`, `/export-markdown`
Konsens: `GET /api/sessions/:id/consensus`, `POST /api/sessions/:id/generate-consensus`
Prompt: `GET /api/sessions/:id/final-prompt`, `POST .../generate-final-prompt`, `/review-final-prompt`, `/approve-final-prompt`
Compose2: `POST /api/sessions/:id/submit-to-compose2`, `/mark-implemented`, `/review-implementation`
Live: `WS /ws/sessions/:id` (Events: `session_started`, `round_started`, `agent_started`, `agent_finished`, `agent_failed`, `consensus_created`, `final_prompt_created`, `prompt_approved`, `submitted_to_compose2`, `implementation_reviewed`)

Vollständige, interaktive Referenz: http://localhost:8000/docs

## Seed-Daten

Beim ersten Start (leere DB) wird automatisch angelegt:

- **Projekt:** „Beispiel React App“
- **Session:** „Login-Formular mit Validierung ergänzen“

## Tests

```bash
cd backend
pip install -r requirements.txt
# PowerShell:  $env:USE_MOCK_PROVIDERS="true"
USE_MOCK_PROVIDERS=true python -m pytest tests/ -v
```

Frontend-Typecheck/Build:

```bash
cd frontend
npm run lint      # tsc --noEmit
npm run build
```

## Beispiele

- `examples/sample-project` — Mini-Repo für `repository_path`
- `examples/sample_session.md` — Ablauf per HTTP

## Sicherheit

- **Keine API-Keys im Frontend** — ausschließlich serverseitig in der `.env`.
- Projektdatei-Zugriff ist sandboxed (Pfadprüfung, Größenlimit, Ausschluss von `.env`, Keys, `node_modules` etc.).

## Nächste Schritte

- Echte Compose2-API, sobald verfügbar (Contract in `Compose2Provider` anpassen)
- MCP-Server, der die REST-/DB-Operationen wrappt
- Git-Diff-Review, automatische Tests gegen das Ziel-Repo

## Lizenz

MIT (anpassen nach Bedarf).
