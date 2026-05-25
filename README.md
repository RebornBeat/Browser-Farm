# Browser Farm

A distributed browser automation platform for developers. Manage multiple browser contexts across multiple servers with live monitoring, manual control, and custom scripts.

## Features

- 🖥️ **Multi-Server Management** - Connect and manage multiple automation servers
- 🌐 **Proxy Management** - Global proxy pool with per-site blacklisting
- 👤 **Account Vault** - Centralized credential management for automation
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
- 📊 **Resource Monitoring** - Memory, CPU, and network metrics per context
- 🔄 **Auto-Dependency Install** - Scripts can define requirements installed at runtime

## Architecture

```
Desktop App (Electron + React)
    ↓ Management & Configuration
Server (Python + FastAPI + Playwright)
    ↓ Isolated Xvfb Display Per Profile
Chromium Browser (Stealth Injected)
    ↓ Script Chain Execution
Your Custom Scripts (Playwright + PyAutoGUI)
```

## Installation

### Server Setup

**1. Install system dependencies:**
```bash
sudo apt update
sudo apt install -y python3.10-venv python3-pip xvfb chromium-browser
```

**2. Create installation directory:**
```bash
sudo mkdir -p /opt/browser-farm
cd /opt/browser-farm
```

**3. Create Virtual Environment & Install Package:**
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install from PyPI
pip install browser-farm

# Install Playwright browsers
playwright install chromium
```

**4. Manual Run (Testing):**
```bash
python -m browser_farm.server --host 0.0.0.0 --port 8080
```

### Production Deployment (Systemd)

To run the server 24/7 with automatic restarts, use Systemd.

**1. Create Service File:**
```bash
sudo nano /etc/systemd/system/browser-farm.service
```

**2. Paste Configuration:**
```ini
[Unit]
Description=Browser Farm Server
After=network.target

[Service]
Type=simple
User=root
# Required for Xvfb and Headful browsers
Environment="DISPLAY=:99"
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

# View logs to find your generated API Key
sudo journalctl -u browser-farm -f
```
*Look for the line: `✓ API Key: bf_...`*

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
   - Enter API key: `bf_abc123xyz789`
   - Click "Connect"

3. **Add a proxy:**
   - Go to Proxies tab
   - Click "Add Proxy"
   - Enter proxy details
   - Save

4. **Add an account:**
   - Go to Accounts tab
   - Click "Add Account"
   - Enter credentials (stored locally, not encrypted)
   - Save

5. **Create scripts:**
   - Go to the new **Script Library** tab.
   - Create modular scripts (e.g., "Instagram Login", "Scraper", "Logout").
   - Define requirements (e.g., `pyautogui`, `bs4`).

6. **Create a profile:**
   - Go to Profiles tab
   - Click "New Profile"
   - **Select Mode:**
     - **Manual:** Opens a browser with proxy. No script. You control it via VNC/Stream.
     - **Automated:** Runs a chain of scripts.
     - **Command Center:** A special profile to orchestrate other profiles.
   - Select Server & Proxy.
   - **Attach Scripts:** Select one or more scripts from your Library to run in sequence.
   - Click "Save & Start"

7. **Monitor:**
   - Go to Home to see live screens
   - Click any screen to view details
   - Click "Take Control" for manual operation

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

**Script 1: Login (Instagram Login)**
*Requirements: none*
```python
import asyncio

async def main(context):
    account = get_account("acc_001") # Get credentials
    page = await context.new_page()
    await page.goto("https://instagram.com/accounts/login/")

    await page.fill('input[name="username"]', account['username'])
    await page.fill('input[name="password"]', account['password'])
    await page.click('button[type="submit"]')

    await page.wait_for_url("https://instagram.com/")

    # Signal to other profiles that we are logged in
    await set_state("insta_status", {"logged_in": True, "user": account['username']})
```

**Script 2: Scraper (Instagram Scraper)**
*Requirements: beautifulsoup4*
```python
import asyncio
from bs4 import BeautifulSoup # Injected, but can also be imported if installed

async def main(context):
    # Check if login script finished
    status = await get_state("insta_status")
    if not status.get("logged_in"):
        print("Not logged in!")
        return

    page = context.pages[0] # Reuse page from previous script
    await page.goto("https://instagram.com/explore/")

    # Parse content
    content = await page.content()
    soup = BeautifulSoup(content, 'html.parser')
    print(f"Found {len(soup.find_all('a'))} links")
```

### Example 2: Human-like Interaction with PyAutoGUI

*Requirements: pyautogui*
*Note: PyAutoGUI controls the mouse on the virtual display assigned to this profile. It does not interfere with other profiles.*

```python
import asyncio
import pyautogui # Available in namespace

async def main(context):
    page = await context.new_page()
    await page.goto("https://example.com")

    # Use Playwright to get element position
    button = await page.query_selector('button#submit')
    box = await button.bounding_box()

    if box:
        # Move mouse human-like using PyAutoGUI
        center_x = box['x'] + box['width'] / 2
        center_y = box['y'] + box['height'] / 2

        print(f"Moving mouse to {center_x}, {center_y}")
        pyautogui.moveTo(center_x, center_y, duration=1.0)
        pyautogui.click()

        print("Clicked using PyAutoGUI!")

    await asyncio.sleep(5)
```

### Example 3: Command Center Script

A "Command Center" profile runs a script that manages other profiles or global logic. It typically does not require a browser context.

```python
import asyncio

async def main(context):
    print("Command Center Active")

    while True:
        # Check global state
        farm_health = await get_state("farm_health_metrics")

        if farm_health and farm_health.get("cpu_avg") > 80:
            print("High CPU! Pausing non-essential profiles...")
            # Logic to call API to pause profiles would go here
            # Or send a signal via shared state
            await set_state("command", "throttle")

        await asyncio.sleep(60)
```

## API Documentation

See [API.md](./API.md) for full API reference.

## System Requirements

### Server
- Ubuntu 20.04+ or Debian 11+
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

Features like PyAutoGUI integration and browser fingerprint masking are intended for advanced testing scenarios and privacy preservation.

## License

MIT License - see [LICENSE](./LICENSE)

## Support

- GitHub Issues: [Issues](https://github.com/RebornBeat/browser-farm/issues)
- Discord: [Join Server](https://discord.gg/browserfarm)

## Roadmap

- [x] Script Library & Chaining
- [x] Inter-Profile Communication
- [x] PyAutoGUI Support
- [x] Command Center Mode
- [ ] Docker support
- [ ] Kubernetes orchestration
- [ ] LLM Orchestrator Integration
