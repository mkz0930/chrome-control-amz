#!/usr/bin/env python3
"""
OpenClaw Browser Relay - 点击卖家精灵按钮 + 导出数据
"""
import asyncio
import websockets
import json
import re

WS_URL = 'ws://172.25.0.1:19000'

async def cmd(action, **kwargs):
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        
        rid = str(asyncio.get_event_loop().time())
        msg = {'action': action, 'request_id': rid, **kwargs}
        await ws.send(json.dumps(msg))
        result = await asyncio.wait_for(ws.recv(), timeout=20)
        return json.loads(result)

async def main():
    print("🚀 打开亚马逊 + 点击卖家精灵 + 导出数据")
    
    # Step 1: 创建 tab + 打开 URL
    result = await cmd('new_tab', url='https://www.amazon.com/s?k=light', active=True)
    tab_id = result['tab_id']
    print(f"✅ 创建 tab: {tab_id}")
    
    # Step 2: 等待页面加载 + 卖家精灵注入
    print("⏳ 等待页面加载 (10秒)...")
    await asyncio.sleep(10)
    
    # Step 3: 获取 HTML，找卖家精灵按钮
    result = await cmd('get_html', selector='body')
    html = result['html']
    print(f"✅ 获取 HTML, 长度: {len(html)}")
    
    # Step 4: 查找卖家精灵相关代码
    print("\n🔍 查找卖家精灵...")
    
    # 卖家精灵常见标识
    patterns = {
        'seajin': r'seajin',
        '卖家精灵': r'卖家精灵',
        'icon': r'class=["\'][^"\']*icon[^"\']*["\']',
        'button': r'<button[^>]*>',
    }
    
    found = False
    for name, pattern in patterns.items():
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            print(f"  {name}: 找到 {len(matches)} 处匹配")
            found = True
    
    if not found:
        print("⚠️ 未找到卖家精灵代码，可能需要等待更久")
    
    # Step 5: 检查当前 URL
    result = await cmd('get_url')
    print(f"\n📊 当前页面: {result['url']}")
    
    # Step 6: 如果在搜索页，点击第一个商品进入详情页
    if 's?k=' in result['url']:
        print("\n网页在搜索页，点击第一个商品...")
        
        # 尝试点击第一个商品链接
        # 卖家精灵通常在详情页才有数据
        result = await cmd('click_text', text='Amazon.com', exact=False)
        print(f"点击结果: {json.dumps(result, ensure_ascii=False)}")
        
        await asyncio.sleep(8)
        
        # 获取详情页 URL
        result = await cmd('get_url')
        print(f"详情页 URL: {result['url']}")
        
        # 再次获取 HTML，找卖家精灵按钮
        result = await cmd('get_html', selector='body')
        html = result['html']
        
        # 尝试点击卖家精灵
        seajin_patterns = [
            '卖家精灵',
            'seajin',
            'icon-seajin',
            'seajin-button',
        ]
        
        for pattern in seajin_patterns:
            if pattern in html:
                print(f"🔍 找到卖家精灵标识: {pattern}")
                result = await cmd('click_text', text=pattern, exact=False)
                print(f"点击卖家精灵结果: {json.dumps(result, ensure_ascii=False)}")
                break
    
    # Step 7: 截图验证
    result = await cmd('screenshot', format='png')
    if result.get('ok'):
        print(f"\n📸 截图已获取 (base64, {len(result['data'])} 字符)")
        # 保存截图
        import base64
        with open('/home/claw/.openclaw/workspace/amazon_screenshot.png', 'wb') as f:
            f.write(base64.b64decode(result['data']))
        print("✅ 截图已保存到: /home/claw/.openclaw/workspace/amazon_screenshot.png")
    
    # Step 8: 获取完整 HTML 保存
    result = await cmd('get_html', selector='body')
    with open('/home/claw/.openclaw/workspace/amazon.html', 'w', encoding='utf-8') as f:
        f.write(result['html'])
    print("✅ HTML 已保存到: /home/claw/.openclaw/workspace/amazon.html")

asyncio.run(main())
