# Setup: Chrome Relay Browser Control

## Prerequisites

- OpenClaw Browser Relay extension installed in Windows Chrome
- Linux WSL2 environment (OpenClaw agent)
- Python venv with `websockets`: `/home/claw/.openclaw/workspace/.venv`

## Step 1: Start Relay Server (Linux)

```bash
cd /home/claw/.openclaw/extensions/openclaw-browser-relay/server
PYTHONUNBUFFERED=1 nohup /home/claw/.openclaw/workspace/.venv/bin/python3 -u server.py \
  > /tmp/relay-server.log 2>&1 &
echo "PID: $!"
sleep 2 && cat /tmp/relay-server.log
```

Expected output:
```
🚀 OpenClaw Browser Relay Server
📡 Listening on: ws://localhost:19000
Waiting for connections...
```

## Step 2: Connect Chrome Extension (Windows)

1. Open Windows Chrome
2. Click **OpenClaw Browser Relay** extension icon in toolbar
3. Badge turns **green** ✅ = connected
4. Tell AI: "已变绿"

## Step 3: Verify Connection

```bash
cat /tmp/relay-server.log | grep "Extension connected"
# Expected: [HH:MM:SS] 🔌 Extension connected! Total: 1
```

## Notes

- The Chrome extension connects to `ws://172.25.4.135:19000` (WSL IP)
- `background.js` WS_URL was patched from `localhost:19000` → `172.25.4.135:19000`
- If WSL IP changes after reboot, update `background.js` and reload extension
- Check WSL IP: `ip addr show eth0 | grep "inet "`
