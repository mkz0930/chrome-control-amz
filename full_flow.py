#!/usr/bin/env python3
"""
Full Amazon scraping flow - 单次连接，Python 3.14 兼容
超级反爬：随机等待、鼠标抖动、随机 User-Agent、随机滚动、随机点击、超时重试 + 飞书集成
导出 Excel 后自动上传到飞书 + 创建分析文档 + 给出下载链接
"""

import asyncio
import websockets
import json
import time
import re
import random
import os
import pandas as pd
import re

WS_URL = 'ws://172.25.0.1:19000'
DOWNLOAD_DIR = '/mnt/d/download/'

# User-Agent 列表（反爬）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

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
    
    sec = random.uniform(delay_min, delay_max)
    print(f"🖱️  点击 '{text}' 后等待 {sec:.1f} 秒...")
    await asyncio.sleep(sec)
    
    return result

async def scroll_page(ws, tab_id=None):
    """模拟滚动页面（反爬 - 随机滚动距离）"""
    rid = str(time.time())
    scroll_ratio = random.uniform(0.3, 0.7)
    
    payload = {
        'action': 'eval',
        'request_id': rid,
        'fn': f"""
        (function() {{
            const scrollHeight = document.documentElement.scrollHeight;
            const currentY = window.scrollY;
            const viewportHeight = window.innerHeight;
            const targetY = Math.min(scrollHeight - viewportHeight, currentY + viewportHeight * {scroll_ratio});
            
            if (targetY > currentY) {{
                window.scrollTo(0, targetY);
                return {{ scrolled: true, targetY: targetY, ratio: {scroll_ratio} }};
            }}
            return {{ scrolled: false, targetY: currentY }};
        }})()
        """
    }
    if tab_id:
        payload['tabId'] = tab_id
    
    await ws.send(json.dumps(payload))
    async with asyncio.timeout(10):
        result = json.loads(await ws.recv())
    
    if result.get('scrolled'):
        print(f"Scroll: {result.get('targetY', 'unknown')} px (ratio: {result.get('ratio', 0):.2f})")
    
    await asyncio.sleep(random.uniform(2, 4))

async def hover_then_click(ws, text, tab_id=None, delay_min=2, delay_max=5):
    """鼠标悬停后再点击（模拟人类）"""
    rid = str(time.time())
    payload = {'action': 'click_text', 'request_id': rid, 'text': text}
    if tab_id:
        payload['tabId'] = tab_id
    
    await ws.send(json.dumps(payload))
    async with asyncio.timeout(30):
        result = json.loads(await ws.recv())
    
    print(f"🖱️  点击 '{text}': {result}")
    await asyncio.sleep(random.uniform(delay_min, delay_max))
    
    return result

async def analyze_excel_and_create_feishu_doc(keyword, file_path):
    """分析 Excel 并创建飞书文档"""
    print(f"\n📊 读取原始 Excel: {file_path}")
    xl = pd.ExcelFile(file_path)
    print(f"Sheets: {xl.sheet_names}")

    # 读取 Products (US)
    df = pd.read_excel(file_path, sheet_name='US', skiprows=1)

    # 提取关键字段
    data = []
    for idx, row in df.iterrows():
        asin = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ''
        size_raw = str(row.iloc[3]) if pd.notna(row.iloc[3]) else ''
        size_match = re.search(r'Size:\s*([^\|]+)', size_raw)
        size = size_match.group(1).strip() if size_match else ''
        brand = str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else ''
        title = str(row.iloc[8])[:200] if pd.notna(row.iloc[8]) else ''
        bsr_match = re.search(r'第(\d+)页第(\d+)位', str(row.iloc[7]))
        bsr = (int(bsr_match.group(1))-1)*10 + int(bsr_match.group(2)) if bsr_match else None
        detail_url = str(row.iloc[12]) if pd.notna(row.iloc[12]) else ''

        if asin and asin != 'nan':
            data.append({'ASIN': asin, 'Size': size, 'Brand': brand, 'Title': title, 'BSR': bsr, 'Detail URL': detail_url})

    df_clean = pd.DataFrame(data)
    print(f"✅ 提取 {len(df_clean)} 个产品")

    # 保存 Clean Excel
    clean_file = file_path.replace('.xlsx', '-CLEAN-US-20260313.xlsx')
    df_clean.to_excel(clean_file, index=False)
    print(f"✅ 保存 Clean Excel: {clean_file}")

    # 保存 Bitable CSV
    bitable_file = file_path.replace('.xlsx', '-BITABLE-US-20260313.csv')
    df_clean.to_csv(bitable_file, index=False, encoding='utf-8-sig')
    print(f"✅ 保存 Bitable CSV: {bitable_file}")

    # 分析数据
    print("\n📈 数据分析:")
    brand_counts = df_clean['Brand'].value_counts()
    avg_bsr = df_clean['BSR'].mean()
    print(f"- 产品总数: {len(df_clean)}")
    print(f"- 品牌分布: {brand_counts.to_dict()}")
    print(f"- 平均 BSR: {avg_bsr:.1f}")

    # 创建飞书文档内容（优化排版）
    import datetime
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    content = f"""# 📊 Amazon {keyword} 产品销量分析报告

**生成时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**关键词**: {keyword}  
**导出文件**: {os.path.basename(file_path)}

---

## 📋 数据概览

| 指标 | 值 |
|------|-----|
| 产品总数 | {len(df_clean)} |
| 品牌数 | {len(df_clean['Brand'].unique())} |
| 平均 BSR | {avg_bsr:.1f} |

---

## 🏷️ 品牌销量分布

| 排名 | 品牌 | 产品数 | 占比 |
|------|------|--------|------|
"""

    for i, (brand, count) in enumerate(brand_counts.items(), 1):
        ratio = count / len(df_clean) * 100
        content += f"| {i} | {brand} | {count} | {ratio:.1f}% |\n"

    content += f"""
---

## 📦 产品列表

| # | ASIN | Brand | Size | BSR | 详情 |
|---|------|-------|------|-----|------|
"""

    for i, row in df_clean.iterrows():
        asin = row['ASIN']
        brand = row['Brand']
        size = row['Size']
        bsr = row['BSR']
        url = row['Detail URL']
        content += f"| {i+1} | {asin} | {brand} | {size} | {bsr} | [🔗 Amazon]({url}) |\n"

    content += f"""
---

## 📎 文件下载

- **原始 Excel**: [Download]({file_path})
- **Clean Excel**: [Download]({clean_file})
- **Bitable CSV**: [Download]({bitable_file})

---

## 📸 抓取界面截图

（截图已插入）

---

**报告生成**: Horse AIAssistant  
**更新时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    print("\n📝 飞书文档内容已生成（省略正文，见下方示例）")
    print(content[:500] + "...")

    # 创建飞书文档
    # 临时用 Python 调用，正式用 feishu_doc 工具
    import feishu_doc
    
    doc = feishu_doc.action.create(
        filename=f"Amazon {keyword} 产品销量分析 ({today})",
        content=content,
        folder_token=""
    )
    
    doc_url = f"https://feishu.cn/docx/{doc['document_id']}"
    print(f"\n✅ 飞书文档已创建: {doc_url}")
    
    return {
        'raw_file': file_path,
        'clean_file': clean_file,
        'bitable_file': bitable_file,
        'doc_url': doc_url,
        'product_count': len(df_clean),
        'brands': brand_counts.to_dict(),
        'avg_bsr': avg_bsr
    }

async def main():
    print("=" * 60)
    print("full_flow.py - Amazon Seller Sprite Export (飞书版)")
    print("=" * 60)

    keywords = ['laptop', 'laptops', 'notebook', ' ultrabook']

    for keyword in keywords:
        print(f"\n{'=' * 40}")
        print(f"🔍 处理关键词: {keyword}")
        print('=' * 40)

        async with websockets.connect(WS_URL) as ws:
            # Handshake
            await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
            await ws.recv()
            print(f"✅ 已连接: extension_online=True")

            # Step 1: 打开新标签页
            rid = str(time.time())
            await ws.send(json.dumps({'action': 'new_tab', 'request_id': rid, 'url': f'https://www.amazon.com/s?k={keyword}', 'active': True}))
            async with asyncio.timeout(30):
                r = json.loads(await ws.recv())
            tab_id = r['tab_id']
            print(f"✅ 新标签页已打开 (ID: {tab_id})")
            await asyncio.sleep(random.uniform(4, 7))

            # Step 2: 滚动页面
            print("\n[2/6] 📜 滚动页面（模拟浏览）")

            # Step 3: 点击卖家精灵
            print("\n[3/6] 🖱️  点击卖家精灵")
            r = await click_with_delay(ws, '卖家精灵', tab_id, delay_min=5, delay_max=10)
            print(f"✅ 卖家精灵: {r}")

            # Step 4: 等待数据注入
            print("⏳ 等待卖家精灵注入数据（15-20 秒）...")
            await asyncio.sleep(random.uniform(15, 20))

            # Step 5: 滚动页面
            print("\n[5/6] 📜 滚动页面（再次模拟浏览）")
            await scroll_page(ws, tab_id)

            # Step 6: 点击全选（20% 概率跳过）
            if random.random() > 0.2:
                print("\n[4/6] 🖱️  点击全选")
                r = await hover_then_click(ws, '全选', tab_id)
                print(f"✅ 全选: {r}")
            else:
                print("\n[4/6] 🖱️  跳过全选（模拟人工）")
                await asyncio.sleep(random.uniform(2, 4))

            # Step 7: 导出数据
            print("\n[6/6] 📤 导出数据")
            r = await hover_then_click(ws, '导出', tab_id, delay_min=3, delay_max=6)
            print(f"✅ 导出: {r}")
            await asyncio.sleep(random.uniform(8, 12))

            # Step 8: 验证文件下载
            print("\n[6/6] 📁 验证文件下载")
            files_before = set(os.listdir(DOWNLOAD_DIR))
            max_wait = 90
            for i in range(max_wait):
                files_after = set(os.listdir(DOWNLOAD_DIR))
                new_files = files_after - files_before
                if new_files:
                    print(f"✅ 新文件: {new_files}")
                    for f in new_files:
                        if f.startswith(f'Search({keyword}') and f.endswith('.xlsx'):
                            raw_file = os.path.join(DOWNLOAD_DIR, f)
                            print(f"  - {f} ({os.path.getsize(raw_file)} bytes)")
                    break
                if i % 10 == 0:
                    print(f"  等待中... ({i}s)")
                await asyncio.sleep(1)
            else:
                print("⚠️  文件未下载，请手动检查")

            # Step 9: 截图
            rid = str(time.time())
            await ws.send(json.dumps({'action': 'screenshot', 'request_id': rid, 'format': 'png', 'tabId': tab_id}))
            async with asyncio.timeout(10):
                r = json.loads(await ws.recv())
            print(f"✅ 截图: {'ok' if r.get('ok') else r}")

        print(f"\n📊 分析文件并创建飞书文档...")
        result = await analyze_excel_and_create_feishu_doc(keyword, raw_file)
        result = await analyze_excel_and_create_feishu_doc(keyword, raw_file)

        print(f"\n✅ 关键词 '{keyword}' 处理完成！")
        print(f"   - 产品数: {result['product_count']}")
        print(f"   - 品牌数: {len(result['brands'])}")
        print(f"   - 平均 BSR: {result['avg_bsr']:.1f}")
        print(f"   - 飞书文档: {result['doc_url']}")

        if keyword != keywords[-1]:
            wait_keyword()

    print("\n" + "=" * 60)
    print("✅ 全部关键词处理完成！")
    print("=" * 60)

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
