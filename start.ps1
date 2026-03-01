# ── Trading System Launcher (Windows PowerShell) ──
# Starts both the backend API server and frontend dev server.
# Press Ctrl+C to stop everything.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# ── Check prerequisites ──
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Error: 'uv' is not installed. See SETUP.md for installation instructions." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "Error: 'npm' is not installed. See SETUP.md for installation instructions." -ForegroundColor Red
    exit 1
}

# ── Install dependencies if needed ──
if (-not (Test-Path ".venv")) {
    Write-Host "First run detected - installing Python dependencies..."
    uv sync --extra dev
}

if (-not (Test-Path "dashboard\node_modules")) {
    Write-Host "First run detected - installing frontend dependencies..."
    Push-Location dashboard
    npm install
    Pop-Location
}

# ── Start backend ──
Write-Host "Starting backend server (port 9000)..."
$backend = Start-Process -FilePath "uv" -ArgumentList "run", "trading-server" `
    -PassThru -NoNewWindow

# Give the backend a moment to start
Start-Sleep -Seconds 2

# ── Start frontend ──
Write-Host "Starting frontend dev server (port 5173)..."
$frontend = Start-Process -FilePath "npm" -ArgumentList "run", "dev" `
    -WorkingDirectory "$ScriptDir\dashboard" -PassThru -NoNewWindow

Write-Host ""
Write-Host "========================================="
Write-Host "  Backend:   http://localhost:9000"
Write-Host "  Dashboard: http://localhost:5173"
Write-Host "========================================="
Write-Host "  Press Ctrl+C to stop all servers"
Write-Host "========================================="
Write-Host ""

# ── Wait and clean up on exit ──
try {
    # Wait for either process to exit
    while (-not $backend.HasExited -and -not $frontend.HasExited) {
        Start-Sleep -Milliseconds 500
    }
}
finally {
    Write-Host ""
    Write-Host "Shutting down..."

    if (-not $frontend.HasExited) {
        Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
        # Also stop any child node processes spawned by npm
        Get-Process -Name "node" -ErrorAction SilentlyContinue |
            Where-Object { $_.StartTime -ge $frontend.StartTime } |
            Stop-Process -Force -ErrorAction SilentlyContinue
    }

    if (-not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
        # Also stop any child python/uvicorn processes
        Get-Process -Name "python", "uvicorn" -ErrorAction SilentlyContinue |
            Where-Object { $_.StartTime -ge $backend.StartTime } |
            Stop-Process -Force -ErrorAction SilentlyContinue
    }

    Write-Host "All servers stopped."
}
