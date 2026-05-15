# Browser Farm

A distributed browser automation platform for developers. Manage multiple browser contexts across multiple servers with live monitoring, manual control, and custom scripts.

## Features

- 🖥️ **Multi-Server Management** - Connect and manage multiple automation servers
- 🌐 **Proxy Management** - Global proxy pool with per-site blacklisting
- 👤 **Account Vault** - Centralized credential management for automation
- 🤖 **Custom Scripts** - Write Python scripts using Playwright
- 📺 **Live Screen Viewing** - Real-time browser screen streaming
- 🎮 **Manual Control** - Take over any browser context with mouse/keyboard
- 📸 **Screenshots & Videos** - Automatic capture and gallery viewing
- 📊 **Resource Monitoring** - Memory, CPU, and network metrics per context
- 🔄 **Auto-Restart** - Memory threshold monitoring with custom restart scripts

## Architecture
```
Desktop App (Electron + React)
    ↓ HTTP/WebSocket
Server (Python + FastAPI + Playwright)
    ↓ Xvfb (Virtual Display)
Chromium Browser
    ↓ Multiple Contexts
Your Custom Scripts
```

## Installation

### Server Setup

1. **Install system dependencies:**
```bash
sudo apt update
sudo apt install -y python3.11 python3-pip xvfb chromium-browser
```

2. **Install Browser Farm server:**
```bash
cd server
pip install -r requirements.txt
playwright install chromium
```

3. **Start the server:**
```bash
python -m browser_farm.server --host 0.0.0.0 --port 8080
```

Output:
```
✓ Xvfb started on :99
✓ Chromium launched
✓ Server running on http://192.168.1.100:8080
✓ API Key: bf_abc123xyz789
```

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

5. **Create a profile:**
   - Go to Profiles tab
   - Click "New Profile"
   - Select server, proxy, and configure browser
   - Attach your Python script
   - Set memory threshold
   - Click "Save & Start"

6. **Monitor:**
   - Go to Home to see live screens
   - Click any screen to view details
   - Click "Take Control" for manual operation

## Writing Scripts

Scripts are standard Python using Playwright. Reference accounts by ID.

Example:
```python
from browser_farm import get_account
import asyncio

async def main(context):
    # Get account credentials
    account = get_account("acc_001")

    page = await context.new_page()
    await page.goto("https://instagram.com/accounts/login/")

    # Login
    await page.fill('input[name="username"]', account['username'])
    await page.fill('input[name="password"]', account['password'])
    await page.click('button[type="submit"]')

    # Wait for success
    await page.wait_for_url("https://instagram.com/")

    # Your automation logic here
    while True:
        # Do something
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
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

## License

MIT License - see [LICENSE](./LICENSE)

## Support

- GitHub Issues: [Issues](https://github.com/yourusername/browser-farm/issues)
- Discord: [Join Server](https://discord.gg/browserfarm)

## Roadmap

- [ ] Docker support
- [ ] Kubernetes orchestration
- [ ] Plugin system for custom integrations
- [ ] Cloud proxy integration
- [ ] Mobile app (iOS/Android)
