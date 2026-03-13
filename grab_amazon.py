#!/usr/bin/env python3
"""
OpenClaw Browser Relay - 快速抓取亚马逊数据（新版）
"""
import asyncio
import websockets
import json

WS_URL = 'ws://172.25.0.1:19000'

async def cmd(action, **kwargs):
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        
        rid = str(asyncio.get_event_loop().time())
        msg = {'action': action, 'request_id': rid, **kwargs}
        await ws.send(json.dumps(msg))
        result = await asyncio.wait_for(ws.recv(), timeout=15)
        return json.loads(result)

async def main():
    print("🚀 打开亚马逊页面 + 抓取卖家精灵数据")
    
    # Step 1: 新建 tab + 打开 URL (OpenClaw 不支持，手动跳转)
    result = await cmd('new_tab', url='about:blank', active=True)
    print('Created tab:', result)
    
    tab_id = result.get('tab_id')
    if not tab_id:
        print('❌ Failed to create tab')
        return
    
    # Step 2: navigate to Amazon
    result = await cmd('navigate', url='https://www.amazon.com/s?k=light', tabId=tab_id, waitForLoad=True)
    print('Navigate result:', json.dumps(result, ensure_ascii=False, indent=2))
    
    if not result.get('ok'):
        print('❌ Navigate failed:', result.get('error'))
        return
    
    # Step 3: wait for page loaded
    await asyncio.sleep(5)
    
    # Step 4: get URL
    result = await cmd('get_url')
    print('Current URL:', json.dumps(result, ensure_ascii=False, indent=2))
    
    # Step 5: get_html
    result = await cmd('get_html', selector='div.s-main-slot')
    if result.get('ok'):
        print('✅ Got HTML, length:', len(result['html']))
        # 抓取关键字段
        import re
        # ASIN from URL
        asin_match = re.search(r'/dp/([A-Z0-9]{10})', result['html'])
        asin = asin_match.group(1) if asin_match else 'N/A'
        print(f"ASIN: {asin}")
        
        # Price
        price_match = re.search(r'\$([0-9,.]+)', result['html'])
        price = price_match.group(0) if price_match else 'N/A'
        print(f"Price: {price}")
    else:
        print('❌ Error:', result.get('error'))

asyncio.run(main())
