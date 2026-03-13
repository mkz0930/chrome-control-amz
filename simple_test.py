#!/usr/bin/env python3
"""
OpenClaw Browser Relay - 简单测试
"""
import asyncio
import websockets
import json

WS_URL = 'ws://172.25.0.1:19000'

async def test():
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        
        # 创建 tab
        await ws.send(json.dumps({
            'action': 'new_tab',
            'request_id': '1',
            'url': 'https://www.amazon.com/s?k=light',
            'active': True
        }))
        result = await asyncio.wait_for(ws.recv(), timeout=15)
        print('New tab:', json.loads(result))
        
        # 等待加载
        await asyncio.sleep(5)
        
        # get_url
        await ws.send(json.dumps({'action': 'get_url', 'request_id': '2'}))
        result = await asyncio.wait_for(ws.recv(), timeout=15)
        print('URL:', json.loads(result))
        
        # 切到 tab
        tab_id = json.loads(result).get('tab_id')
        if tab_id:
            await ws.send(json.dumps({
                'action': 'switch_tab',
                'request_id': '3',
                'tabId': tab_id
            }))
            result = await asyncio.wait_for(ws.recv(), timeout=15)
            print('Switch tab:', json.loads(result))

asyncio.run(test())
