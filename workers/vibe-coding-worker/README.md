# Vibe Coding Worker

Windows-Worker für AI Orchestra Vibe Coding. Baut eine **ausgehende** WebSocket-Verbindung zum Server auf — keine eingehenden Ports nötig.

## Schnellstart

```powershell
cd workers/vibe-coding-worker
npm install

# Token im Backend erzeugen: POST /api/vibe/workers/register-token
$env:ORCHESTRA_SERVER_URL = "ws://127.0.0.1:8000/ws/worker"
$env:ORCHESTRA_WORKER_TOKEN = "ihr-token"
$env:PROJECT_ROOTS = "F:\ai-council-orchestrator"
$env:ADAPTER_TYPE = "mock"

npm run dev
```

## Adapter

| ADAPTER_TYPE | Beschreibung |
|---|---|
| `mock` | Vollständige Simulation (Standard für Tests) |
| `cursor` | Echte Cursor Headless CLI (`agent -p --force --output-format stream-json`) |

### Cursor CLI einrichten (Windows)

```powershell
irm 'https://cursor.com/install?win32=true' | iex
$env:CURSOR_API_KEY = "ihr-api-key"
$env:ADAPTER_TYPE = "cursor"
$env:CURSOR_CLI_EXECUTABLE = "$env:LOCALAPPDATA\cursor-agent\agent.cmd"
npm run dev
```

Ohne CLI: Mock-Adapter verwenden (`ADAPTER_TYPE=mock`).

## Konfiguration

Siehe `.env.example`.
