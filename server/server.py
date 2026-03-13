#!/usr/bin/env python3
"""
OpenClaw Browser Relay Server
WebSocket relay between OpenClaw agents and Chrome extension

Usage: python server.py
Server starts on ws://localhost:9999
"""
import asyncio
import json
import uuid
import websockets
from websockets.server import serve
from datetime import datetime

clients = {}  # type -> websocket
pending = {}  # request_id -> future
stats = {
    "started_at": datetime.now().isoformat(),
    "commands_processed": 0,
    "extensions_connected": 0,
    "agents_connected": 0
}

async def handler(ws):
    client_type = None
    client_id = None
    
    try:
        # First message: identify client type
        ident = await asyncio.wait_for(ws.recv(), timeout=10)
        data = json.loads(ident)
        client_type = data.get("type")
        client_id = f"{client_type}-{uuid.uuid4().hex[:8]}"
        clients[client_id] = {"ws": ws, "type": client_type, "version": data.get("version", "unknown")}
        
        if client_type == "extension":
            stats["extensions_connected"] += 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔌 Extension connected! Total: {stats['extensions_connected']}")
        elif client_type == "agent":
            stats["agents_connected"] += 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 Agent connected! Total: {stats['agents_connected']}")
            
        # Send welcome message to agent
        if client_type == "agent":
            await ws.send(json.dumps({
                "type": "welcome",
                "message": "Connected to OpenClaw Browser Relay",
                "extension_online": "extension" in [c["type"] for c in clients.values()],
                "stats": dict(stats)
            }))

        # Main message loop
        async for raw in ws:
            try:
                msg = json.loads(raw)
                
                if client_type == "extension" and "request_id" in msg:
                    # Extension response
                    rid = msg["request_id"]
                    if rid in pending:
                        pending[rid].set_result(msg)
                        stats["commands_processed"] += 1
                        
                elif client_type == "agent":
                    # Agent command - forward to extension
                    extension_clients = [cid for cid, c in clients.items() if c["type"] == "extension"]
                    
                    if not extension_clients:
                        await ws.send(json.dumps({
                            "error": "No extension connected",
                            "request_id": msg.get("request_id"),
                            "hint": "Please install and enable the OpenClaw Browser Relay Chrome extension"
                        }))
                        continue
                    
                    # Use first connected extension
                    target_client = extension_clients[0]
                    rid = msg.get("request_id", str(uuid.uuid4()))
                    msg["request_id"] = rid
                    
                    loop = asyncio.get_event_loop()
                    fut = loop.create_future()
                    pending[rid] = fut
                    
                    await clients[target_client]["ws"].send(json.dumps(msg))
                    
                    try:
                        result = await asyncio.wait_for(fut, timeout=msg.get("timeout", 30))
                        await ws.send(json.dumps(result))
                    except asyncio.TimeoutError:
                        await ws.send(json.dumps({
                            "error": "timeout",
                            "request_id": rid,
                            "message": f"Extension did not respond within {msg.get('timeout', 30)}s"
                        }))
                    finally:
                        pending.pop(rid, None)
                        
            except json.JSONDecodeError as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Invalid JSON: {e}")
                
    except asyncio.TimeoutError:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Connection timeout during handshake")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {client_type} disconnected ({client_id}): {e.code}")
    finally:
        if client_id and client_id in clients:
            del clients[client_id]
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 Active clients: {len(clients)}")

async def stats_reporter():
    """Print stats every 60 seconds"""
    while True:
        await asyncio.sleep(60)
        if stats["commands_processed"] > 0 or stats["extensions_connected"] > 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 Stats: {stats['commands_processed']} commands, "
                  f"{stats['extensions_connected']} extensions, {stats['agents_connected']} agents")

async def main():
    print("=" * 60)
    print("🚀 OpenClaw Browser Relay Server")
    print("=" * 60)
    print(f"📡 Listening on: ws://localhost:19000")
    print(f"🕐 Started at: {stats['started_at']}")
    print("=" * 60)
    print("Waiting for connections...")
    print()
    
    # Start stats reporter
    asyncio.create_task(stats_reporter())
    
    # Read port from env or default to 19000
    import os
    port = int(os.environ.get("SERVER_PORT", 19000))
    
    async with serve(handler, "0.0.0.0", port, ping_interval=30, ping_timeout=10):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user")
