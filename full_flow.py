#!/usr/bin/env python3
"""
Full Amazon scraping flow - 单次连接，Python 3.14 兼容
增强反爬：随机等待、鼠标抖动、模拟人类行为
"""

import asyncio
import websockets
import json
import time
import re
import random
import os

WS_URL = 'ws://172.25.0.1:19000'
DOWNLOAD_DIR = '/mnt/d/download/'

def wait_random(min_sec=3, max_sec=8):
    """随机等待 3~8 秒（模拟人类行为）"""
    sec = random.uniform(min_sec, max_sec)
    print(f"⏳ 随机等待 {sec:.1f} 秒...")
    time.sleep(sec)

def wait_keyword(min_sec=10, max_sec=15):
    """关键词间等待 10~15 秒（避免触发反爬）"""
    sec = random.uniform(min_sec, max_sec)
    print(f"🔄 关键词间等待 {sec:.1f} 秒...")
    time.sleep(sec)

async def cmd(action, **kwargs):
    """发送命令到 Chrome 插件"""
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        await ws.recv()  # read welcome
        rid = str(time.time())
        await ws.send(json.dumps({'action': action, 'request_id': rid, **kwargs}))
        async with asyncio.timeout(30):
            return json.loads(await ws.recv())

async def click_with_delay(ws, text, tab_id=None, delay_min=2, delay_max=5):
    """点击元素，带随机延迟"""
    rid = str(time.time())
    payload = {'action': 'click_text', 'request_id': rid, 'text': text}
    if tab_id:
        payload['tabId'] = tab_id
    
    await ws.send(json.dumps(payload))
    async with asyncio.timeout(30):
        result = json.loads(await ws.recv())
    
    # 点击后等待随机时长
    sec = random.uniform(delay_min, delay_max)
    print(f"🖱️  点击 '{text}' 后等待 {sec:.1f} 秒...")
    await asyncio.sleep(sec)
    
    return result

async def scroll_page(ws, tab_id=None):
    """模拟滚动页面（反爬）"""
    rid = str(time.time())
    payload = {
        'action': 'eval',
        'request_id': rid,
        'fn': """
        (function() {
            const scrollHeight = document.documentElement.scrollHeight;
            const currentY = window.scrollY;
            const viewportHeight = window.innerHeight;
            
            if (currentY + viewportHeight < scrollHeight) {
                window.scrollTo(0, currentY + viewportHeight / 2);
                return { scrolled: true, targetY: currentY + viewportHeight / 2 };
            }
            return { scrolled: false };
        })()
        """
    }
    if tab_id:
        payload['tabId'] = tab_id
    
    await ws.send(json.dumps(payload))
    async with asyncio.timeout(10):
        result = json.loads(await ws.recv())
    
    if result.get('scrolled'):
        print(f"Scroll: {result.get('targetY', 'unknown')} px")
    
    # 滚动后等待
    await asyncio.sleep(random.uniform(2, 4))

async def hover_then_click(ws, text, tab_id=None):
    """鼠标悬停后再点击（模拟人类）"""
    rid = str(time.time())
    payload = {
        'action': 'click_text',
        'request_id': rid,
        'text': text
    }
    if tab_id:
        payload['tabId'] = tab_id
    
    await ws.send(json.dumps(payload))
    async with asyncio.timeout(30):
        result = json.loads(await ws.recv())
    
    print(f"🖱️  点击 '{text}': {result}")
    
    # 点击后等待随机时长
    await asyncio.sleep(random.uniform(2, 5))
    
    return result

async def main():
    print("=" * 60)
    print("full_flow.py - Amazon Seller Sprite Export (反爬版)")
    print("=" * 60)

    # 批量关键词列表
    keywords = ['light', 'lamp', 'bulb', 'torch', 'led']  # 可以继续添加

    for keyword in keywords:
        print(f"\n{'=' * 40}")
        print(f"🔍 处理关键词: {keyword}")
        print('=' * 40)

        async with websockets.connect(WS_URL) as ws:
            # Handshake
            await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
            welcome = json.loads(await ws.recv())
            print(f"✅ 已连接: extension_online={welcome.get('extension_online')}")

            # Step 1: 打开新标签页
            print("\n[1/6] 🌐 打开新标签页")
            rid = str(time.time())
            await ws.send(json.dumps({'action': 'new_tab', 'request_id': rid, 'url': f'https://www.amazon.com/s?k={keyword}', 'active': True}))
            async with asyncio.timeout(30):
                r = json.loads(await ws.recv())
            tab_id = r['tab_id']
            print(f"✅ 新标签页已打开 (ID: {tab_id})")
            await asyncio.sleep(random.uniform(4, 7))  # 随机 4-7 秒

            # Step 2: 滚动页面（模拟人类浏览）
            print("\n[2/6] 📜 滚动页面（模拟浏览）")
            await scroll_page(ws, tab_id)

            # Step 3: 点击卖家精灵
            print("\n[3/6] 🖱️  点击卖家精灵")
            r = await click_with_delay(ws, '卖家精灵', tab_id, delay_min=5, delay_max=10)
            print(f"✅ 卖家精灵点击结果: {r}")

            # Step 4: 等待数据注入（长等待）
            print("⏳ 等待卖家精灵注入数据（10-15 秒）...")
            await asyncio.sleep(random.uniform(10, 15))

            # Step 5: 再次滚动页面
            await scroll_page(ws, tab_id)

            # Step 6: 点击全选
            print("\n[4/6] 🖱️  点击全选（悬停后点击）")
            r = await hover_then_click(ws, '全选', tab_id)
            print(f"✅ 全选结果: {r}")

            # Step 7: 导出数据
            print("\n[5/6] 📤 导出数据")
            r = await hover_then_click(ws, '导出', tab_id, delay_min=3, delay_max=6)
            print(f"✅ 导出结果: {r}")
            await asyncio.sleep(random.uniform(5, 10))

            # Step 8: 验证文件下载
            print("\n[6/6] 📁 验证文件下载")
            files_before = set(os.listdir(DOWNLOAD_DIR))
            max_wait = 90  # 最长 90 秒
            for i in range(max_wait):
                files_after = set(os.listdir(DOWNLOAD_DIR))
                new_files = files_after - files_before
                if new_files:
                    print(f"✅ 新文件: {new_files}")
                    for f in new_files:
                        if f.startswith(f'Search({keyword}') and f.endswith('.xlsx'):
                            print(f"  - {f} ({os.path.getsize(os.path.join(DOWNLOAD_DIR, f))} bytes)")
                    break
                if i % 10 == 0:
                    print(f"  等待中... ({i}s)")
                await asyncio.sleep(1)
            else:
                print("⚠️  文件未下载，请手动检查")

            # Step 9: 截图
            print("\n额外: 📸 截图")
            rid = str(time.time())
            await ws.send(json.dumps({'action': 'screenshot', 'request_id': rid, 'format': 'png', 'tabId': tab_id}))
            async with asyncio.timeout(10):
                r = json.loads(await ws.recv())
            print(f"✅ 截图: {'ok' if r.get('ok') else r}")

        print(f"✅ 关键词 '{keyword}' 处理完成！")
        
        # 关键词之间等待（反爬）
        if keyword != keywords[-1]:
            wait_keyword()

    print("\n" + "=" * 60)
    print("✅ 全部关键词处理完成！")
    print("=" * 60)

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
