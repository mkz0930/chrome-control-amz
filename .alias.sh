# OpenClaw Browser Relay - 快捷命令
alias relay-status="ss -tlnp | grep :19000"
alias relay-log="tail -f /tmp/openclaw-relay-server.log"
alias relay-stop="pkill -f 'python3 server.py'"

# 测试命令
relay-test() {
    python3 -c '
import asyncio
import websockets
import json
async def test():
    async with websockets.connect("ws://172.25.0.1:19000") as ws:
        await ws.send(json.dumps({"type":"agent","version":"1.0.0"}))
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        print("Connected!")
        print(json.loads(msg))
asyncio.run(test())
'
}
