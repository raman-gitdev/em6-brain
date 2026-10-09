# run-local.ps1 - start EM6 Brain on this PC WITHOUT Docker.
#
# Uses: local PostgreSQL (database "brain"), Ollama on this PC, Python and Node.
# Opens three windows: clock-tool, orchestrator, frontend. Close them to stop.
#
# Run from the Brain folder:
#   powershell -ExecutionPolicy Bypass -File .\run-local.ps1

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

# ---- 1. Read settings from .env --------------------------------------------
if (-not (Test-Path "$root\.env")) {
    throw ".env not found. Copy .env.example to .env and set POSTGRES_PASSWORD."
}
foreach ($line in Get-Content "$root\.env") {
    $l = $line.Trim()
    if ($l -eq '' -or $l.StartsWith('#') -or -not $l.Contains('=')) { continue }
    $parts = $l.Split('=', 2)
    Set-Item -Path ("env:" + $parts[0].Trim()) -Value $parts[1].Trim()
}
if (-not $env:POSTGRES_PASSWORD) { throw "POSTGRES_PASSWORD is empty in .env." }

# ---- 2. Local addresses (Docker would use container names instead) ----------
# The password is URL-encoded, so characters like @ or : are safe.
$pw = [uri]::EscapeDataString($env:POSTGRES_PASSWORD)
$env:DATABASE_URL = "postgresql://brain:$pw@localhost:5432/brain"
if (-not $env:BRAIN_URL -or $env:BRAIN_URL -like '*host.docker.internal*') {
    $env:BRAIN_URL = 'http://127.0.0.1:11434'   # 127.0.0.1, not localhost: Ollama listens on IPv4 only
}
$env:TOOL_SERVICES = 'http://localhost:8101'
$env:NG_CLI_ANALYTICS = 'false'   # stop Angular asking questions on first run

# ---- 3. Python environment (created once, in .venv) -------------------------
$py = "$root\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Creating Python environment (first run only)..." -ForegroundColor Cyan
    python -m venv "$root\.venv"
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python environment." }
}
Write-Host "Checking Python packages..." -ForegroundColor Cyan
& $py -m pip install --quiet --disable-pip-version-check `
    -r "$root\orchestrator\requirements.txt" -r "$root\tools\clock-tool\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }

# ---- 4. Front-end packages (installed once) ---------------------------------
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "Installing front-end packages (first run only, a few minutes)..." -ForegroundColor Cyan
    Push-Location "$root\frontend"
    npm install
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { throw "npm install failed." }
}

# ---- 5. Start each service in its own window --------------------------------
function Open-BrainWindow($title, $folder, $command) {
    Start-Process powershell -WorkingDirectory $folder -ArgumentList @(
        '-NoExit', '-Command', "`$host.UI.RawUI.WindowTitle = '$title'; $command")
}

Open-BrainWindow 'Brain - clock-tool' "$root\tools\clock-tool" `
    "& '$py' -m uvicorn app.main:app --host 127.0.0.1 --port 8101"
Open-BrainWindow 'Brain - orchestrator' "$root\orchestrator" `
    "& '$py' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
Open-BrainWindow 'Brain - frontend' "$root\frontend" "npm start"

Write-Host ""
Write-Host "Starting. In about 20 seconds open:  http://localhost:4200" -ForegroundColor Green
Write-Host "API docs:                            http://localhost:8000/docs"
Write-Host "To stop: close the three 'Brain - ...' windows."
