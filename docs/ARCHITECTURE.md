# AI Orchestra

**AI Orchestra ist kein Chatbot.** Es ist ein Betriebssystem für mehrere KI-Agenten und Coding-Worker.

Der Benutzer beschreibt ein Feature — AI Orchestra übernimmt die komplette Orchestrierung im Hintergrund.

## Vier Ebenen

```
┌─────────────────────────────────────────────────────────────┐
│  Dashboard (React) — Features, Agenten, Worker, Events    │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  1. COORDINATOR — Workflow-Manager (keine eigene KI)        │
│     12 Phasen · Jobs · Entscheidungen · Phase-Audit         │
└───────┬───────────────────────────────┬─────────────────────┘
        │                               │
┌───────▼──────────┐           ┌────────▼────────────────────┐
│ 2. KNOWLEDGE     │           │ 3. AI AGENTS (beliebig viele)│
│ Projektwissen    │           │ ChatGPT, Claude, Gemini, …   │
│ ADR, Standards   │           │ konfigurierbar · Plugin      │
└──────────────────┘           └─────────────────────────────┘
                                        │
                               ┌────────▼────────────────────┐
                               │ 4. WORKERS (keine KI)       │
                               │ Cursor, Claude Code, …      │
                               │ Job-Polling · Live-Status   │
                               └─────────────────────────────┘
```

## 12-Phasen-Workflow

| # | Phase | Beschreibung |
|---|-------|--------------|
| 1 | Problem verstehen | Aufgabe normalisieren |
| 2 | Architektur entwickeln | Initial Assessment |
| 3 | Agenten-Diskussion | Cross Review |
| 4 | Konsens finden | Moderator + Freigabe |
| 5 | Prompt Engineering | Finaler Coding-Prompt |
| 6 | Prompt Review | Agenten-Freigabe |
| 7 | Worker-Übergabe | Job erstellen |
| 8 | Implementierung | Worker führt aus |
| 9 | Code Review | Agenten prüfen Code |
| 10 | Verbesserungsrunden | Auto-Retry (max. konfigurierbar) |
| 11 | Git Commit | Worker-Job |
| 12 | Pull Request | Abschluss |

Jede Phase wird als `PhaseExecution` gespeichert — vollständig nachvollziehbar.

## API (neu)

| Bereich | Endpunkte |
|---------|-----------|
| Dashboard | `GET /orchestra/dashboard` |
| Phasen | `GET /orchestra/phases` |
| Events | `GET /orchestra/events` |
| Jobs | `GET /orchestra/jobs` |
| Tasks | `POST /tasks`, `/tasks/{id}/orchestrate`, `/tasks/{id}/advance-phase` |
| Agenten | `GET/POST /agents` |
| Worker | `POST /workers/register`, `/heartbeat`, `/jobs/poll`, `/jobs/{id}/complete` |
| Knowledge | `GET/PUT /orchestra/projects/{id}/knowledge` |

Legacy-Endpunkte (`/sessions`, `/projects`) bleiben kompatibel.

## Windows Worker

Skeleton unter `workers/ai-orchestra-worker/`:

- Registrierung + Heartbeat
- Job-Polling
- **Keine Cursor-Automatisierung** — Prompt wird lokal geschrieben, Mensch implementiert

```powershell
cd workers\ai-orchestra-worker
set ORCHESTRA_URL=http://192.168.111.43:8080/api
python main.py
```

## Plugin-System

Neue Agenten, Worker, Provider, Exporter über `app/plugins/registry.py` registrieren — ohne Kern-Änderungen.

## Roadmap (vorbereitet)

- MCP Server · GitHub/GitLab/Azure DevOps · Jira/Linear
- Docker Swarm / Kubernetes · Remote Linux Cluster
- Lokale LLMs · Multi-Worker-Lastverteilung

## Schnellstart

Siehe [README.md](README.md) — Docker Compose, Mock-Modus, Frontend auf Port 8080.
