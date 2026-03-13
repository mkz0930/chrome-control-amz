# Amazon Seller Sprite Chrome Relay

[![License](https://img.shields.io/github/license/mkz0930/amazon-seller-sprite-chrome-relay)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Chrome](https://img.shields.io/badge/Chrome-Extension-green.svg)](https://chrome.google.com/webstore)

OpenClaw Chrome Extension for Amazon Seller Sprite - Click seller sprite button & extract data via Python WebSocket.

---

## 📋 Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Commands](#commands)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## ✨ Features

- ✅ **Click Seller Sprite** - Click the "卖家精灵" button on Amazon product pages
- ✅ **Extract Data** - Extract ASIN, price, BSR from DOM
- ✅ **WebSocket Control** - Python-based automation via `ws://172.25.0.1:19000`
- ✅ **Cross-Platform** - Linux (WSL2) + Windows Chrome
- ✅ **One-Click Install** - Auto-detect & install dependencies

---

## 📋 Requirements

| Component | Requirement |
|-----------|-------------|
| **Windows** | Windows 10/11 |
| **Chrome** | Latest version |
| **WSL2** | Ubuntu 20.04+ |
| **Python** | 3.10+ |
| **Amazon Account** | Seller Sprite installed |

---

## 🚀 Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/mkz0930/amazon-seller-sprite-chrome-relay.git
cd amazon-seller-sprite-chrome-relay
```

### Step 2: Run Installation Script

```bash
chmod +x install.sh
./install.sh
```

This will:
- ✅ Install Python dependencies (websockets)
- ✅ Start WebSocket server on port 19000
- ✅ Generate config file
- ✅ Create快捷 commands (`.alias.sh`)

### Step 3: Load Chrome Extension

1. Open Chrome → `chrome://extensions/`
2. Enable **Developer mode** (top-right)
3. Click **Load unpacked**
4. Select `extension/` directory

### Step 4: Attach Amazon Tab

1. Open any Amazon page (e.g., `https://www.amazon.com/s?k=light`)
2. Click extension icon → **Attach current tab**
3. Confirm icon turns **green ✅**

---

## 💡 Usage

### Quick Test

```bash
source .alias.sh
relay-test
```

Expected output:
```json
{
  "type": "welcome",
  "message": "Connected to OpenClaw Browser Relay",
  "extension_online": true
}
```

### Full Automation

```python
import asyncio
import websockets
import json

WS_URL = 'ws://172.25.0.1:19000'

async def cmd(action, **kwargs):
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        await ws.recv()
        rid = str(asyncio.get_event_loop().time())
        await ws.send(json.dumps({'action': action, 'request_id': rid, **kwargs}))
        return json.loads(await asyncio.wait_for(ws.recv(), timeout=15))

async def main():
    # 1. Open Amazon
    r = await cmd('navigate', url='https://www.amazon.com/s?k=camping')
    print('Opened:', r)
    
    # 2. Wait
    await asyncio.sleep(5)
    
    # 3. Click Seller Sprite
    r = await cmd('click_text', text='卖家精灵')
    print('Clicked:', r)
    
    # 4. Wait for data
    await asyncio.sleep(3)
    
    # 5. Extract HTML
    r = await cmd('get_html', selector='div.s-main-slot')
    html = r.get('html', '')
    print('HTML length:', len(html))

asyncio.run(main())
```

---

## 📖 Commands

| Command | Parameters | Example |
|---------|------------|---------|
| `navigate` | `url` | `cmd('navigate', url='https://...')` |
| `click` | `selector` | `cmd('click', selector='.btn')` |
| `click_text` | `text, exact=False` | `cmd('click_text', text='卖家精灵')` |
| `click_xy` | `x, y` | `cmd('click_xy', x=100, y=200)` |
| `get_html` | `selector` | `cmd('get_html', selector='div.s-main-slot')` |
| `get_text` | `selector` | `cmd('get_text', selector='body')` |
| `get_url` | - | `cmd('get_url')` |
| `type` | `selector, text` | `cmd('type', selector='input', text='hello')` |
| `screenshot` | `format='png'` | `cmd('screenshot', format='png')` |

---

## ⚠️ Troubleshooting

### ❌ "No extension connected"

**Cause:** Chrome extension not attached to tab

**Solution:**
1. Check extension icon → should be **green ✅**
2. Click icon → **Attach current tab**
3. Verify弹窗 shows "Connected to 172.25.0.1:19000"

---

### ❌ "Connection timeout"

**Cause:** Wrong IP address

**Solution:**
- Use `ws://172.25.0.1:19000` (WSL2 IP)
- NOT `localhost` or `127.0.0.1`

---

### ❌ "text not found"

**Cause:** Seller Sprite text doesn't match

**Solution:**
1. Open DevTools (`F12`) on Amazon page
2. Find seller sprite button text/selector
3. Use exact text or `click` with selector

---

## 📊 Quick Commands Reference

```bash
# Check server status
relay-status

# View server logs
relay-log

# Stop server
relay-stop

# Quick test
relay-test
```

---

## 🌐 GitHub

- **Repository**: https://github.com/mkz0930/amazon-seller-sprite-chrome-relay
- **Issues**: https://github.com/mkz0930/amazon-seller-sprite-chrome-relay/issues
- **License**: MIT

---

## 📝 Author

- **Author**: 马振坤 (mkz0930@gmail.com)
- **Date**: 2026-03-13
- **Version**: 1.0.0

---

## 🙏 Acknowledgments

- Inspired by OpenClaw Browser Relay
- Built for Amazon seller automation
