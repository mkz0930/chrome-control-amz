#!/usr/bin/env python3
"""
OpenClaw Browser Relay - 获取亚马逊 HTML + 调试卖家精灵
"""
import asyncio
import websockets
import json
import re

WS_URL = 'ws://172.25.0.1:19000'

async def test():
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        
        # 创建 tab + 打开 URL
        await ws.send(json.dumps({
            'action': 'new_tab',
            'request_id': '1',
            'url': 'https://www.amazon.com/s?k=light',
            'active': True
        }))
        result = await asyncio.wait_for(ws.recv(), timeout=15)
        print('New tab:', json.loads(result))
        
        await asyncio.sleep(5)
        
        # get_html
        await ws.send(json.dumps({
            'action': 'get_html',
            'request_id': '2',
            'selector': 'body'
        }))
        result = await asyncio.wait_for(ws.recv(), timeout=15)
        html = json.loads(result)
        
        if html.get('ok'):
            content = html['html']
            print(f"✅ Got HTML, length: {len(content)}")
            
            # 搜索卖家精灵相关代码
            patterns = [
                r'卖家精灵',
                r'seajin',
                r'seller.*精灵',
                r'\.seajin|\.seller',
                r'id=["\']seajin|id=["\']seller',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    print(f"🔍 找到卖家精灵相关 ({pattern}): {matches[:5]}")
            
            # 保存 HTML 到文件
            with open('/home/claw/.openclaw/workspace/amazon_search.html', 'w', encoding='utf-8') as f:
                f.write(content)
            print("📄 HTML saved to: /home/claw/.openclaw/workspace/amazon_search.html")
        else:
            print('❌ Error:', html.get('error'))

asyncio.run(test())
