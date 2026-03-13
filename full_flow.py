#!/usr/bin/env python3
"""
Full Amazon scraping flow with seller sprite click + button click + export
"""

import asyncio
import websockets
import json
import time
import re

WS_URL = 'ws://172.25.0.1:19000'

async def cmd(action, **kwargs):
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        await ws.recv()
        rid = str(time.time())
        await ws.send(json.dumps({'action': action, 'request_id': rid, **kwargs}))
        return json.loads(await asyncio.wait_for(ws.recv(), timeout=30))

async def main():
    print("=" * 60)
    print("/full_flow.py - Amazon Seller Sprite Export")
    print("=" * 60)
    
    # Step 1: Open new Amazon page
    print("\n[1/6] 🌐 打开新标签页 + 访问亚马逊搜索页")
    r = await cmd('new_tab')
    tab_id = r['tab_id']
    print(f"✅ 新标签页已打开 (ID: {tab_id})")
    
    r = await cmd('navigate', url='https://www.amazon.com/s?k=light')
    print(f"✅ 页面已访问: {r.get('url', 'N/A')}")
    await asyncio.sleep(4)
    
    # Step 2: Click seller sprite button
    print("\n[2/6] 🖱️  点击卖家精灵按钮")
    r = await cmd('click_text', text='卖家精灵')
    print(f"✅ 卖家精灵点击结果: {r}")
    await asyncio.sleep(3)
    
    # Step 3: Click product selection button (产品全选)
    print("\n[3/6] 🖱️  点击产品全选按钮")
    r = await cmd('click_text', text='全选')
    print(f"✅ 全选按钮点击结果: {r}")
    await asyncio.sleep(2)
    
    # Step 4: Export seller sprite data
    print("\n[4/6] 📤 导出卖家精灵数据")
    r = await cmd('click_text', text='导出')
    print(f"✅ 导出操作结果: {r}")
    await asyncio.sleep(5)
    
    # Step 5: Get HTML and extract data
    print("\n[5/6] 📄 抓取页面数据")
    r = await cmd('get_html', selector='div.s-main-slot')
    html = r.get('html', '')
    print(f"✅ HTML 已抓取 (长度: {len(html)} 字符)")
    
    # Extract ASIN, price, title from HTML
    asin_pattern = r'/dp/([A-Z0-9]{10})'
    price_pattern = r'\$(\d+\.\d{2})'
    title_pattern = r'<h2.*?>(.*?)</h2>'
    
    asins = list(set(re.findall(asin_pattern, html)))[:10]
    prices = re.findall(price_pattern, html)[:10]
    titles = re.findall(title_pattern, html)[:10]
    
    print("\n📦 提取的数据:")
    for i, (asin, price, title) in enumerate(zip(asins[:5], prices[:5], titles[:5]), 1):
        print(f"  {i}. ASIN: {asin}, Price: ${price}, Title: {title[:50]}...")
    
    # Step 6: Screenshot (if supported)
    print("\n[6/6] 📸 截图保存")
    r = await cmd('screenshot', format='png')
    if 'data' in r:
        print("✅ 截图已生成 (base64)")
    else:
        print("ℹ️  截图返回: ", r)
    
    print("\n" + "=" * 60)
    print("✅ 全流程完成！")
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(main())
