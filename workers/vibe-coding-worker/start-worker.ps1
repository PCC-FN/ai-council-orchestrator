#Requires -Version 5.1
<#
.SYNOPSIS
  Startet den AI Orchestra Vibe-Coding-Worker (npm install, Token, Verbindung).

.EXAMPLE
  .\start-worker.ps1

.EXAMPLE
  .\start-worker.ps1 -Production
#>
param(
    [switch]$Production,
    [string]$ServerUrl,
    [string]$AdminToken
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$WorkerDir = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $WorkerDir "..\..")).Path
$EnvFile = Join-Path $WorkerDir ".env"
$EnvExample = Join-Path $WorkerDir ".env.example"

function Write-Step([string]$Message) {
    Write-Host "> $Message" -ForegroundColor Cyan
}

function Read-DotEnv([string]$Path) {
    $values = @{}
    if (-not (Test-Path $Path)) { return $values }
    Get-Content $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { return }
        $key = $line.Substring(0, $eq).Trim()
        $val = $line.Substring($eq + 1).Trim()
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        $values[$key] = $val
    }
    return $values
}

function Set-DotEnvValue([string]$Path, [string]$Key, [string]$Value) {
    $lines = @()
    $found = $false
    if (Test-Path $Path) {
        $lines = @(Get-Content $Path -Encoding UTF8)
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match "^\s*$([regex]::Escape($Key))\s*=") {
                $lines[$i] = "$Key=$Value"
                $found = $true
                break
            }
        }
    }
    if (-not $found) {
        if ($lines.Count -gt 0 -and $lines[-1].Trim() -ne "") { $lines += "" }
        $lines += "$Key=$Value"
    }
    Set-Content -Path $Path -Value $lines -Encoding UTF8
}

function Apply-DotEnv([hashtable]$Values) {
    foreach ($entry in $Values.GetEnumerator()) {
        if ($entry.Value) {
            Set-Item -Path "Env:$($entry.Key)" -Value $entry.Value
        }
    }
}

function Get-HttpBaseFromWorkerUrl([string]$WorkerWsUrl) {
    $uri = [Uri]$WorkerWsUrl
    $scheme = if ($uri.Scheme -eq "wss") { "https" } else { "http" }
    $port = if ($uri.IsDefaultPort) { "" } else { ":$($uri.Port)" }
    return "$scheme`://$($uri.Host)$port"
}

function Test-TokenPlaceholder([string]$Token) {
    return [string]::IsNullOrWhiteSpace($Token) -or $Token -eq "replace-me"
}

function Test-AdminTokenPlaceholder([string]$Token) {
    if ([string]::IsNullOrWhiteSpace($Token)) { return $false }
    $placeholders = @(
        "dein-admin-token",
        "your-admin-token",
        "DEIN-ADMIN-TOKEN",
        "replace-me",
        "EchterToken"
    )
    return $placeholders -contains $Token.Trim()
}

function Ensure-NodeTools {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        throw "Node.js nicht gefunden. Bitte von https://nodejs.org installieren."
    }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm nicht gefunden."
    }
}

function Ensure-Dependencies {
    $nodeModules = Join-Path $WorkerDir "node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Step "npm install ..."
        Push-Location $WorkerDir
        try {
            npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install fehlgeschlagen (Exit $LASTEXITCODE)" }
        }
        finally {
            Pop-Location
        }
    }
}

function Register-WorkerToken {
    param(
        [string]$ApiBase,
        [string]$WorkerName,
        [string]$AuthToken
    )

    $uri = "$ApiBase/api/vibe/workers/register-token?name=$([Uri]::EscapeDataString($WorkerName))"
    Write-Step "Worker-Token registrieren: $uri"

    $headers = @{}
    if ($AuthToken) {
        $headers["X-Orchestra-Token"] = $AuthToken
    }

    try {
        return Invoke-RestMethod -Method POST -Uri $uri -Headers $headers
    }
    catch {
        $detail = $_.Exception.Message
        if ($_.ErrorDetails.Message) { $detail = $_.ErrorDetails.Message }
        $hint = @"
Hinweise:
  - Echten Admin-Token verwenden (nicht den Platzhalter dein-admin-token)
  - Auf dem Server: docker exec ai-council-orchestrator-api-1 python -c "import sqlite3; c=sqlite3.connect('/data/council.db'); print(c.execute(\"select value from app_settings where key='bootstrap_admin_token'\").fetchone()[0])"
  - Oder ORCHESTRA_ADMIN_TOKEN in /opt/docker/ai-council-orchestrator/.env setzen und API neu starten (nur bei leerer User-Tabelle wirksam)
  - Server erreichbar? API: $ApiBase/docs
"@
        throw "Worker-Token konnte nicht erstellt werden.`n$detail`n`n$hint"
    }
}

function Resolve-CursorCli([string]$Current) {
    if ($Current) { return $Current }
    $candidate = Join-Path $env:LOCALAPPDATA "cursor-agent\agent.cmd"
    if (Test-Path $candidate) { return $candidate }
    return ""
}

# --- Bootstrap .env ---
if (-not (Test-Path $EnvFile)) {
    Write-Step ".env fehlt - erstelle aus .env.example"
    if (-not (Test-Path $EnvExample)) {
        throw ".env.example nicht gefunden in $WorkerDir"
    }
    Copy-Item $EnvExample $EnvFile
    Set-DotEnvValue $EnvFile "ORCHESTRA_SERVER_URL" "ws://192.168.111.41:8080/ws/worker"
    Set-DotEnvValue $EnvFile "PROJECT_ROOTS" $RepoRoot
    Set-DotEnvValue $EnvFile "WORKER_NAME" $env:COMPUTERNAME
    Write-Host "  Bitte ggf. ORCHESTRA_ADMIN_TOKEN in $EnvFile eintragen." -ForegroundColor Yellow
}

$config = Read-DotEnv $EnvFile

if ($ServerUrl) { $config["ORCHESTRA_SERVER_URL"] = $ServerUrl }
if ($AdminToken) { $config["ORCHESTRA_ADMIN_TOKEN"] = $AdminToken }

$serverWs = $config["ORCHESTRA_SERVER_URL"]
if ([string]::IsNullOrWhiteSpace($serverWs)) {
    $serverWs = "ws://192.168.111.41:8080/ws/worker"
    $config["ORCHESTRA_SERVER_URL"] = $serverWs
}

if ([string]::IsNullOrWhiteSpace($config["PROJECT_ROOTS"])) {
    $config["PROJECT_ROOTS"] = $RepoRoot
    Set-DotEnvValue $EnvFile "PROJECT_ROOTS" $RepoRoot
}

if ([string]::IsNullOrWhiteSpace($config["WORKER_NAME"])) {
    $config["WORKER_NAME"] = $env:COMPUTERNAME
}

if ($config["ADAPTER_TYPE"] -eq "cursor") {
    $existingCli = $config["CURSOR_CLI_EXECUTABLE"]
    $cursorCli = Resolve-CursorCli $existingCli
    if ($cursorCli) {
        $config["CURSOR_CLI_EXECUTABLE"] = $cursorCli
        if (-not $existingCli) {
            Set-DotEnvValue $EnvFile "CURSOR_CLI_EXECUTABLE" $cursorCli
        }
    }
    elseif (-not $existingCli) {
        Write-Host "Warnung: Cursor CLI nicht gefunden - ADAPTER_TYPE=mock verwenden oder CURSOR_CLI_EXECUTABLE setzen." -ForegroundColor Yellow
    }
}

Apply-DotEnv $config

Ensure-NodeTools
Ensure-Dependencies

# --- Worker-Token ---
$workerToken = $config["ORCHESTRA_WORKER_TOKEN"]
if (Test-TokenPlaceholder $workerToken) {
    $apiBase = Get-HttpBaseFromWorkerUrl $serverWs
    $adminToken = $config["ORCHESTRA_ADMIN_TOKEN"]
    if (-not $adminToken) { $adminToken = $env:ORCHESTRA_ADMIN_TOKEN }

    if ([string]::IsNullOrWhiteSpace($adminToken)) {
        throw @"
ORCHESTRA_ADMIN_TOKEN fehlt in .env (Server hat AUTH_REQUIRED=true).

Bootstrap-Token vom Server holen:
  ssh root@192.168.111.41 "docker exec ai-council-orchestrator-api-1 python -c \"import sqlite3; c=sqlite3.connect('/data/council.db'); print(c.execute('select value from app_settings where key=''bootstrap_admin_token''').fetchone()[0])\""

Dann in .env eintragen:
  ORCHESTRA_ADMIN_TOKEN=<token>
"@
    }

    if (Test-AdminTokenPlaceholder $adminToken) {
        throw @"
Ungueltiger Admin-Token (Platzhalter: $adminToken).
Bitte den echten Token in .env setzen: ORCHESTRA_ADMIN_TOKEN=...
"@
    }

    $result = Register-WorkerToken -ApiBase $apiBase -WorkerName $config["WORKER_NAME"] -AuthToken $adminToken
    $workerToken = $result.token
    if (-not $workerToken) { throw "Server lieferte keinen Worker-Token." }

    Set-DotEnvValue $EnvFile "ORCHESTRA_WORKER_TOKEN" $workerToken
    $env:ORCHESTRA_WORKER_TOKEN = $workerToken
    Write-Host "  Worker-Token gespeichert in .env (worker_id: $($result.worker_id))" -ForegroundColor Green
}

Write-Host ""
Write-Host "AI Orchestra Vibe Worker" -ForegroundColor Green
Write-Host "  Server:   $serverWs"
Write-Host "  Name:     $($config['WORKER_NAME'])"
Write-Host "  Adapter:  $($config['ADAPTER_TYPE'])"
Write-Host "  Projekte: $($config['PROJECT_ROOTS'])"
Write-Host ""

Push-Location $WorkerDir
try {
    if ($Production) {
        Write-Step "Production-Build ..."
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build fehlgeschlagen" }
        Write-Step "Worker starten (npm start) ..."
        npm start
    }
    else {
        Write-Step "Worker starten (npm run dev) - Strg+C zum Beenden"
        npm run dev
    }
}
finally {
    Pop-Location
}
