#!/usr/bin/env python3
"""
Test runner for chrome-relay-browser-control evals
Run: python run_tests.py
"""

import asyncio
import json
import websockets
import os
from pathlib import Path
from datetime import datetime


def load_evals():
    with open(Path(__file__).parent / "evals.json") as f:
        return json.load(f)


async def cmd(action, **kwargs):
    """Send command to Chrome relay WebSocket server"""
    ws_url = "ws://localhost:19000"
    try:
        async with websockets.connect(ws_url) as ws:
            # Send handshake
            await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
            await ws.recv()  # Echo response
            
            # Send command
            rid = str(asyncio.get_event_loop().time())
            await ws.send(json.dumps({
                'action': action,
                'request_id': rid,
                **kwargs
            }))
            return json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
    except Exception as e:
        return {"error": str(e), "ws_url": ws_url}


async def run_nav_test():
    """Test: navigate to amazon with search"""
    print("🔍 Running eval: simple-navigate")
    result = await cmd('navigate', url='https://www.amazon.com/s?k=led')
    
    # Save output
    output_dir = Path(__file__).parent / "outputs" / "eval-0-simple-navigate"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "response.json"
    output_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    
    log_file = output_dir / "logs.txt"
    log_file.write_text(f"Timestamp: {datetime.now().isoformat()}\nResponse: {json.dumps(result, ensure_ascii=False)}")
    
    print(f"✅ Test saved to {output_dir}")
    return result


async def main():
    evals = load_evals()
    print(f"📋 Found {len(evals['evals'])} evals")
    
    # Run all tests
    for eval_item in evals['evals']:
        eval_id = eval_item['id']
        eval_name = eval_item['name']
        print(f"\n🔄 Running: {eval_id} - {eval_name}")
        
        if eval_id == 'simple-navigate':
            result = await run_nav_test()
            print(f"   Result: {result}")
        
        # Add other test runners here
        # if eval_id == 'search-action': ...


if __name__ == "__main__":
    asyncio.run(main())
