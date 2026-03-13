#!/usr/bin/env python3
"""
Full Amazon scraping flow - single WS connection, Python 3.14 compatible
"""

import asyncio
import websockets
import json
import time
import re

WS_URL = 'ws://172.25.0.1:19000'

async def main():
    print("=" * 60)
    print("full_flow.py - Amazon Seller Sprite Export")
    print("=" * 60)

    async with websockets.connect(WS_URL) as ws:
        # Handshake
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        welcome = json.loads(await ws.recv())
        print(f"✅ 已连接: extension_online={welcome.get('extension_online')}")

        async def cmd(action, **kwargs):
            rid = str(time.time())
            await ws.send(json.dumps({'action': action, 'request_id': rid, **kwargs}))
            async with asyncio.timeout(30):
                return json.loads(await ws.recv())

        # Step 1: Open new tab
        print("\n[1/6] 🌐 打开新标签页")
        r = await cmd('new_tab', url='https://www.amazon.com/s?k=light', active=True)
        tab_id = r['tab_id']
        print(f"✅ 新标签页已打开 (ID: {tab_id})")
        await asyncio.sleep(5)

        # Step 2: Click seller sprite
        print("\n[2/6] 🖱️  点击卖家精灵按钮")
        r = await cmd('click_text', text='卖家精灵', tabId=tab_id)
        print(f"✅ 卖家精灵点击结果: {r}")
        print("⏳ 等待 卖家精灵 注入数据...")
        await asyncio.sleep(5)  # 等待5秒让卖家精灵注入数据

        # Step 3: Click 全选
        print("\n[3/6] 🖱️  点击全选")
        r = await cmd('click_text', text='全选', tabId=tab_id)
        print(f"✅ 全选结果: {r}")
        await asyncio.sleep(2)

        # Step 4: Export
        print("\n[4/6] 📤 导出数据")
        r = await cmd('click_text', text='导出', tabId=tab_id)
        print(f"✅ 导出结果: {r}")
        await asyncio.sleep(5)

        # Step 5: Get HTML
        print("\n[5/6] 📄 抓取 HTML")
        r = await cmd('get_html', selector='div.s-main-slot', tabId=tab_id)
        html = r.get('html', '')
        print(f"✅ HTML 长度: {len(html)} 字符")

        asins = list(set(re.findall(r'/dp/([A-Z0-9]{10})', html)))[:10]
        prices = re.findall(r'\$(\d+\.\d{2})', html)[:10]
        print("\n📦 提取数据:")
        for i, (asin, price) in enumerate(zip(asins[:5], prices[:5]), 1):
            print(f"  {i}. ASIN: {asin}, Price: ${price}")

        # Step 6: Screenshot
        print("\n[6/6] 📸 截图")
        r = await cmd('screenshot', format='png', tabId=tab_id)
        print(f"✅ 截图: {'ok' if r.get('ok') else r}")

    print("\n" + "=" * 60)
    print("✅ 全流程完成！")
    print("=" * 60)

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
