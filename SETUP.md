# Local Setup Guide

Step-by-step instructions to get the trading system running on your machine. Works on macOS, Linux, and Windows.

---

## What You're Setting Up

This project has two parts:

1. **Python backend** — an API server that analyzes stocks and generates trade recommendations
2. **React frontend** — a web dashboard where you manage positions and view recommendations

By the end of this guide you'll have both running and connected.

---

## Prerequisites

You need three tools installed before starting. If you already have them, skip to [Step 1](#step-1-clone-the-repository).

### Install Git

Git is used to download the project code.

**macOS:**
```bash
# Open Terminal (search "Terminal" in Spotlight)
xcode-select --install
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update && sudo apt install git
```

**Linux (Fedora):**
```bash
sudo dnf install git
```

**Windows:**
Download and run the installer from https://git-scm.com/download/win — accept all defaults. Then open "Git Bash" for the remaining steps (or use PowerShell).

**Verify it works:**
```bash
git --version
```
You should see something like `git version 2.x.x`.

---

### Install uv (Python package manager)

`uv` manages Python and all the project's Python dependencies. You do **not** need to install Python separately — `uv` handles that.

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installing, **close and reopen your terminal** so the `uv` command is available.

**Verify it works:**
```bash
uv --version
```
You should see something like `uv 0.x.x`.

---

### Install Node.js (for the dashboard)

Node.js runs the React frontend. Install version 20 or newer.

**macOS:**
```bash
# If you have Homebrew:
brew install node

# If not, download from https://nodejs.org (LTS version)
```

**Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

**Linux (Fedora):**
```bash
sudo dnf install nodejs
```

**Windows:**
Download and run the installer from https://nodejs.org (choose the LTS version). Accept all defaults.

**Verify it works:**
```bash
node --version
npm --version
```
You should see version numbers for both (Node `v20.x.x` or higher, npm `10.x.x` or higher).

---

## Step 1: Clone the Repository

Open a terminal and run:

```bash
git clone https://github.com/dsayed/trading.git
cd trading
```

Replace the URL with the actual repository URL if it's different. You should now be inside the `trading/` folder.

---

## Step 2: Set Up the Python Backend

### Install Python dependencies

```bash
uv sync --extra dev
```

This command:
- Downloads Python 3.12 if you don't have it
- Creates a virtual environment (`.venv/` folder)
- Installs all Python packages the project needs

It takes 1-2 minutes on a fresh install.

### Create a config file

```bash
cp config.example.toml config.toml
```

This copies the example configuration. Open `config.toml` in any text editor and customize if you want:

```toml
[trading]
stake = 10000              # Total capital to deploy ($)
max_position_pct = 0.40    # Max 40% of stake in one position
stop_loss_pct = 0.05       # 5% stop-loss distance
watchlist = ["AAPL", "MSFT", "GOOG", "AMZN", "NVDA"]
```

The defaults are fine to start with.

### Verify the backend works

```bash
uv run pytest -k "not slow"
```

You should see all tests passing (200+ tests, 0 failures). If you see errors here, something went wrong with the install — check the error message.

### Start the API server

```bash
uv run trading-server
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:9000
INFO:     Started reloader process
```

**Leave this terminal running.** The server needs to stay running while you use the dashboard. Open a **new terminal window/tab** for the next steps.

---

## Step 3: Set Up the Dashboard (Frontend)

Open a **new terminal** (keep the server running in the first one), then:

```bash
cd trading/dashboard
npm install
```

This downloads all the JavaScript packages. Takes 1-2 minutes.

### Start the frontend dev server

```bash
npm run dev
```

You should see:

```
  VITE v7.x.x  ready in Xms

  ➜  Local:   http://localhost:5173/
```

### Open the dashboard

Open your web browser and go to:

```
http://localhost:5173
```

You should see the Trading dashboard with a sidebar showing: Scan, Watchlists, Positions, Plays, History, Settings.

---

## Step 4: Try It Out

Here's a quick walkthrough to confirm everything works:

### 1. Create a Watchlist
- Click **Watchlists** in the sidebar
- Click **New Watchlist**, name it "Test"
- Type stock symbols like `AAPL`, `MSFT`, `NVDA` and press Enter for each

### 2. Run a Scan
- Click **Scan** in the sidebar
- Select your "Test" watchlist from the dropdown
- Click **Run Scan**
- After 10-30 seconds, you'll see signal recommendations (or "No signals" if the market is flat)

### 3. Add a Position
- Click **Positions** in the sidebar
- Click **Add Position**
- Enter: Symbol = `MSFT`, Quantity = `100`, Cost basis = `420`, Purchase date = whenever you bought it
- Click **Create**

### 4. Get Play Recommendations
- Click **Plays** in the sidebar
- Select your MSFT position (click the button)
- Click **Get Plays**
- After 15-60 seconds, you'll see recommendations: stop-loss levels, whether to trim/hold/add, and option strategies (covered calls, protective puts) if applicable

---

## Using the CLI (Optional)

You can also run scans from the command line instead of the dashboard:

```bash
# Scan all symbols in your config.toml watchlist
uv run trading scan

# Get a detailed playbook for a specific stock
uv run trading scan --explain AAPL
```

---

## Stopping the Servers

To stop either server, press `Ctrl+C` in its terminal window.

---

## Running Again Later

After the initial setup, you only need two commands to start (in separate terminals):

**Terminal 1 — Backend:**
```bash
cd trading
uv run trading-server
```

**Terminal 2 — Frontend:**
```bash
cd trading/dashboard
npm run dev
```

Then open http://localhost:5173 in your browser.

---

## Production Mode (Single Server)

Instead of running two dev servers, you can build the dashboard and serve everything from the Python server:

```bash
# Build the frontend
cd dashboard
npm run build
cd ..

# Start the server (serves both API and dashboard)
uv run trading-server
```

Then open http://localhost:9000 in your browser. Everything runs from one server.

---

## Troubleshooting

### "command not found: uv"
Close your terminal and open a new one. If it still doesn't work, re-run the uv install command from [Prerequisites](#install-uv-python-package-manager).

### "command not found: npm" or "command not found: node"
Node.js isn't installed or isn't in your PATH. Re-install from https://nodejs.org and restart your terminal.

### Tests fail with import errors
Make sure you ran `uv sync --extra dev` (not just `uv sync`). The `--extra dev` flag installs test dependencies.

### "Address already in use" when starting the server
Another process is using port 9000 (or 5173). Either stop that process or:
- For the Python server, the port is set in `src/trading/api/server.py`
- For the frontend dev server, Vite will automatically try the next available port

### Dashboard shows "Request failed" or network errors
Make sure the Python backend is running in another terminal (`uv run trading-server`). The dashboard needs the API server at port 9000.

### Scans return no signals
This is normal — it means the momentum strategy doesn't see strong setups for the stocks in your watchlist right now. Try adding more symbols or checking back on a different day.

### Windows: "running scripts is disabled on this system"
Open PowerShell as Administrator and run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Windows: line ending issues with Git
If you see strange errors about files, configure Git to handle line endings:
```bash
git config --global core.autocrlf true
```
Then re-clone the repository.
