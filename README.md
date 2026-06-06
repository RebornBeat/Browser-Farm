# Browser Farm

A distributed browser automation platform for developers. Manage multiple browser contexts across multiple servers with live monitoring, manual control, and custom scripts.

## Features

- 🖥️ **Multi-Server Management** - Connect and manage multiple automation servers
- 🗄️ **Persistent Storage** - PostgreSQL database backing for profiles, accounts, and proxies, ensuring state survives restarts
- 🌐 **Proxy Management** - Global proxy pool with per-site blacklisting
- 👤 **Account Vault** - Centralized credential management with Proxy Assignment support
- 🔗 **Proxy History Tracking** - Enforce "1 Account per Website per Proxy" compliance automatically
- 🤖 **Flexible Profile Modes** - Manual, Automated, or Command Center (Orchestrator) profiles
- 📚 **Script Library** - Centralized database for modular, reusable scripts
- 🔗 **Script Chaining** - Execute multiple scripts in sequence within a single profile
- 📺 **Live Screen Viewing** - Real-time browser screen streaming
- 🎮 **Manual Control** - Take over any browser context with mouse/keyboard
- 🧠 **Command Center** - Dedicated orchestrator profiles to coordinate your farm
- 🔗 **Inter-Profile Communication** - Shared state API for profile coordination
- 🖱️ **Human-like Automation** - Native PyAutoGUI support via isolated virtual displays
- 🕵️ **Anti-Detection** - Automatic injection of stealth scripts to hide automation flags
- 📸 **Screenshots & Videos** - Automatic capture and gallery viewing
- 📊 **Resource Monitoring** - Non-blocking memory, CPU, and network metrics per context
- 🔄 **Auto-Dependency Install** - Scripts can define requirements installed at runtime
- 🚑 **Crash Recovery** - Automatic detection and state reconciliation of ghost profiles on server restart

## Architecture

```
Desktop App (Electron + React)
    ↓ Management & Configuration
Server (Python + FastAPI + Playwright)
    ↓ State & Persistence
PostgreSQL Database
    ↓ Isolated Xvfb Display Per Profile
Chromium Browser (Stealth Injected)
    ↓ Script Chain Execution
Your Custom Scripts (Playwright + PyAutoGUI)
```

## Installation

### Prerequisites

1.  **PostgreSQL Database**: You need a running PostgreSQL instance.
2.  **System Dependencies**: Xvfb, Chromium, and Python build tools.

### Step 1: System Dependencies

```bash
sudo apt update
sudo apt install -y python3.10-venv python3-pip xvfb chromium-browser postgresql postgresql-contrib libpq-dev x11-utils
```

### Step 2: Database Setup

Create a dedicated database and user for Browser Farm.

```bash
# Switch to postgres user
sudo -u postgres psql

# In the SQL prompt:
CREATE USER browser_farm_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE browser_farm_db OWNER browser_farm_user;
GRANT ALL PRIVILEGES ON DATABASE browser_farm_db TO browser_farm_user;
\q
```

### Step 3: Server Installation

**1. Create installation directory:**
```bash
sudo mkdir -p /opt/browser-farm
cd /opt/browser-farm
```

**2. Create Virtual Environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install Package:**
```bash
# Install from PyPI
pip install browser-farm

# Install Playwright browsers
playwright install chromium
```

### Step 4: Configuration (Environment Variables)

The server requires the Database URL to start. You can set this in your environment or a `.env` file.

**Create `.env` file:**
```bash
nano /opt/browser-farm/.env
```

**Add the following content:**
```ini
# Database Connection String
DATABASE_URL="postgresql+asyncpg://browser_farm_user:your_secure_password@localhost/browser_farm_db"

# Optional: Override default port
# PORT=8080
# HOST=0.0.0.0
```

### Step 5: Production Deployment (Systemd)

To run the server 24/7 with automatic restarts, use Systemd.

**1. Create Service File:**
```bash
sudo nano /etc/systemd/system/browser-farm.service
```

**2. Paste Configuration:**
```ini
[Unit]
Description=Browser Farm Server
After=network.target postgresql.service

[Service]
Type=simple
User=root
# Required for Xvfb and Headful browsers
Environment="DISPLAY=:99"
# Load Environment Variables from .env file
EnvironmentFile=/opt/browser-farm/.env
WorkingDirectory=/opt/browser-farm
# Activate venv and run server
ExecStart=/opt/browser-farm/venv/bin/python -m browser_farm.server --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**3. Start and Enable Service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable browser-farm
sudo systemctl start browser-farm
```

**4. Verify Status & Get API Key:**
```bash
# Check if running
sudo systemctl status browser-farm

# View logs to find your generated API Key and confirm DB connection
sudo journalctl -u browser-farm -f
```
*Look for:*
*   `Database tables created/verified.`
*   `✓ API Key: bf_...`

## Updating the Server

When a new version is released:

```bash
# 1. Stop the service
sudo systemctl stop browser-farm

# 2. Activate venv
cd /opt/browser-farm
source venv/bin/activate

# 3. Upgrade package
pip install --upgrade browser-farm

# 4. Start the service
sudo systemctl start browser-farm
```

*Note: The server automatically handles database schema synchronization on startup for minor updates.*

### Client Setup

**Option 1: Download Binary** (Recommended)
- Download from [Releases](https://github.com/RebornBeat/browser-farm/releases)
- Windows: `BrowserFarm-Setup.exe`
- macOS: `BrowserFarm.dmg`
- Linux: `BrowserFarm.AppImage`

**Option 2: Build from Source**
```bash
cd client
npm install
npm run build
npm run dist
```

## Quick Start

1. **Launch the desktop app**

2. **Add a server:**
   - Click "Add Server" in the Servers tab
   - Enter server URL: `http://192.168.1.100:8080`
   - Enter API key: (Found in server logs)
   - Click "Connect"

3. **Add a proxy:**
   - Go to Proxies tab -> "Add Proxy"
   - Enter details. (Optional: Can be skipped for Direct Connection).

4. **Create scripts:**
   - Go to the **Script Library** tab.
   - Create modular scripts (e.g., "Instagram Login").
   - Define requirements (e.g., `pyautogui`, `bs4`).

5. **Create a profile:**
   - Go to Profiles tab -> "New Profile"
   - **Select Mode:**
     - **Manual:** Opens a browser with proxy. No script.
     - **Automated:** Runs a chain of scripts.
     - **Command Center:** Orchestrates other profiles.
   - Select Server & Proxy (or "No Proxy").
   - **Attach Scripts:** Select scripts to run in sequence.
   - Click "Save & Start"

6. **Monitor:**
   - Go to Home to see live screens.
   - Click "Take Control" for manual operation.

## Writing Scripts

Scripts are standard Python using Playwright. The server injects powerful helpers into your script's namespace at runtime.

### Injected Namespace

You have access to these objects/functions without importing them:
- `context`: The Playwright BrowserContext.
- `page`: Helper to get the current active page.
- `accounts`: Dictionary of all accounts attached to this profile.
- `get_account(account_id)`: Retrieve credentials from your vault.
- `get_state(key)`: Retrieve shared state from the Orchestrator.
- `set_state(key, value)`: Set shared state for other profiles.
- `pyautogui`: The PyAutoGUI library (controls the mouse on the profile's dedicated virtual display).
- `BeautifulSoup`: For HTML parsing.

### Dependencies

If your script requires external libraries, list them in the **"Requirements"** field when creating the script in the Client. The server will automatically `pip install` them in the background before running.

### Example 1: Automation with Script Chaining & Shared State

**Script 1: Login**
```python
import asyncio

async def main(context):
    account = get_account("acc_001")
    page = await context.new_page()
    await page.goto("https://instagram.com/accounts/login/")

    await page.fill('input[name="username"]', account['username'])
    await page.fill('input[name="password"]', account['password'])
    await page.click('button[type="submit"]')

    # Signal to other profiles
    await set_state("insta_status", {"logged_in": True})
```

**Script 2: Scraper**
*Requirements: beautifulsoup4*
```python
import asyncio

async def main(context):
    # Check state from previous script
    status = await get_state("insta_status")
    if not status.get("logged_in"):
        print("Not logged in!")
        return

    page = context.pages[0]
    # ... scraping logic ...
```

### Example 2: Human-like Interaction with PyAutoGUI

*Requirements: pyautogui*

```python
import asyncio
import pyautogui

async def main(context):
    page = await context.new_page()
    await page.goto("https://example.com")

    # Use Playwright to get element position
    button = await page.query_selector('button#submit')
    box = await button.bounding_box()

    if box:
        center_x = box['x'] + box['width'] / 2
        center_y = box['y'] + box['height'] / 2

        # Move mouse human-like
        pyautogui.moveTo(center_x, center_y, duration=1.0)
        pyautogui.click()

    await asyncio.sleep(5)
```

## API Documentation

See [API.md](./API.md) for full API reference.

## System Requirements

### Server
- Ubuntu 20.04+ or Debian 11+
- PostgreSQL 12+
- 4GB RAM minimum (8GB recommended)
- 2 CPU cores minimum
- 10GB disk space

### Client
- Windows 10+, macOS 11+, or Linux
- 4GB RAM
- 500MB disk space

## Development

### Server
```bash
cd server
# Create local .env
echo "DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db" > .env

pip install -e .
python -m browser_farm.server --dev
```

### Client
```bash
cd client
npm install
npm run dev
```

## Disclaimer

**Browser Farm is intended for legitimate automation, testing, and research purposes only.**

This software is provided "as is", without warranty of any kind. The developers of Browser Farm do not encourage, endorse, or facilitate any activity that violates the Terms of Service of any website or platform.

Users are solely responsible for ensuring their usage of this software complies with all applicable laws and third-party agreements. Use of this tool to automate websites that explicitly forbid automation is done at the user's own risk.

## License

MIT License - see [LICENSE](./LICENSE)

## Support

- GitHub Issues: [Issues](https://github.com/RebornBeat/browser-farm/issues)

## Roadmap

- [x] Script Library & Chaining
- [x] Inter-Profile Communication
- [x] PyAutoGUI Support
- [x] PostgreSQL Persistence
- [x] Proxy History Tracking
- [ ] Docker support
- [ ] LLM Orchestrator Integration
