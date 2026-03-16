"""
full_flow.py - 亚马逊卖家精灵数据导出
v9: 后台tab模式 + 反爬 + 每步实时截图发飞书群
"""
import asyncio, websockets, json, time, os, sys, base64, requests

sys.path.insert(0, os.path.dirname(__file__))
from anti_detect import AntiDetect

WS_URL = 'ws://172.25.0.1:19000'
APP_ID = "cli_a90368220db89cd1"
APP_SECRET = "R184ONuIpFTCaAIUHsyyxb2eahXZ8ugh"
CHAT_ID = "oc_e0c619610b0f4b16593fd16dd9b2d186"

def get_token():
    r = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET}
    )
    return r.json()["tenant_access_token"]

def send_text(token, text):
    requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": CHAT_ID, "msg_type": "text", "content": json.dumps({"text": text})}
    )

def send_image(token, png_bytes):
    r = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/images",
        headers={"Authorization": f"Bearer {token}"},
        data={"image_type": "message"},
        files={"image": ("screenshot.png", png_bytes, "image/png")}
    ).json()
    if r.get("code") != 0:
        print(f"⚠️ 图片上传失败: {r}")
        return
    image_key = r["data"]["image_key"]
    requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": CHAT_ID, "msg_type": "image", "content": json.dumps({"image_key": image_key})}
    )

def send_file(token, file_path):
    filename = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        r = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"file_type": "xlsx", "file_name": filename},
            files={"file": (filename, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        ).json()
    if r.get("code") != 0:
        print(f"⚠️ 文件上传失败: {r}")
        return
    file_key = r["data"]["file_key"]
    requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": CHAT_ID, "msg_type": "file", "content": json.dumps({"file_key": file_key})}
    )

async def ws_cmd(action, **kwargs):
    timeout = 60 if action == 'screenshot' else 30
    async with websockets.connect(WS_URL, max_size=10*1024*1024) as ws:
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        await ws.recv()
        rid = str(asyncio.get_event_loop().time())
        await ws.send(json.dumps({'action': action, 'request_id': rid, **kwargs}))
        return json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))

async def screenshot_and_send(tc, token, step_name):
    r = await tc('screenshot', format='png')
    png = base64.b64decode(r['data'].split(',')[1])
    send_image(token, png)
    print(f"📸 {step_name} 截图已发送")

async def main(keyword='light'):
    token = get_token()
    send_text(token, f"🚀 开始抓取 [{keyword}] 数据，全程实时播报...")
    print(f"▶ keyword: {keyword}")

    # Step 1: 打开新 tab
    send_text(token, "📌 Step 1/5：打开亚马逊搜索页...")
    r = await ws_cmd('new_tab', url=f'https://www.amazon.com/s?k={keyword}')
    tab_id = r.get('tab_id') or r.get('id')
    if not tab_id:
        send_text(token, f"❌ 无法获取 tabId: {r}")
        return

    async def tc(action, **kwargs):
        return await ws_cmd(action, tabId=tab_id, **kwargs)

    ad = AntiDetect(tc)
    await asyncio.sleep(3)
    await ad.after_page_load()
    await screenshot_and_send(tc, token, "Step 1")
    send_text(token, f"✅ Step 1 完成：页面已打开，tab_id={tab_id}")

    # Step 2: 点击卖家精灵
    send_text(token, "📌 Step 2/5：点击卖家精灵，等待数据注入...")
    await ad.before_click()
    r = await tc('click_text', text='卖家精灵')
    if r.get('ok'):
        send_text(token, "✅ 卖家精灵已点击，等待数据加载（约 18~25 秒）...")
    else:
        send_text(token, f"⚠️ 卖家精灵点击失败: {r}")

    await ad.long_delay(18, 25)
    await ad.random_scroll(times=2)
    await ad.human_delay(1, 3)
    await screenshot_and_send(tc, token, "Step 2")
    send_text(token, "✅ Step 2 完成：卖家精灵数据已注入")

    # Step 3: 全选产品
    send_text(token, "📌 Step 3/5：全选产品...")
    selected = False
    for attempt in range(6):
        await ad.before_click()
        r = await tc('click_text', text='全选')
        if r.get('ok'):
            selected = True
            break
        send_text(token, f"  ⏳ 全选未找到，等待重试 ({attempt+1}/6)...")
        await asyncio.sleep(5)

    await screenshot_and_send(tc, token, "Step 3")
    send_text(token, "✅ Step 3 完成：产品已全选" if selected else "⚠️ Step 3：全选未找到，继续导出")
    await ad.human_delay(1.5, 3)

    # Step 4: 导出
    send_text(token, "📌 Step 4/5：点击导出...")
    await ad.before_click()
    r = await tc('click_text', text='导出')
    await screenshot_and_send(tc, token, "Step 4")
    send_text(token, "✅ Step 4 完成：导出已触发，等待文件下载..." if r.get('ok') else f"⚠️ 导出失败: {r}")

    # Step 5: 等待下载完成
    send_text(token, "📌 Step 5/5：等待文件下载完成...")
    download_dir = '/mnt/d/download/'
    files_before = set(os.listdir(download_dir))
    final_file = None
    for i in range(90):
        files_after = set(os.listdir(download_dir))
        new_files = files_after - files_before
        done = [f for f in new_files if not f.endswith('.crdownload') and not f.endswith('.tmp')]
        if done:
            final_file = done[0]
            path = os.path.join(download_dir, final_file)
            size = os.path.getsize(path)
            send_text(token, f"✅ 下载完成：{final_file}（{size:,} bytes）")
            print(f"✅ {final_file} ({size} bytes)")
            break
        if new_files:
            print(f"  下载中... {new_files} ({i}s)")
        time.sleep(1)

    if not final_file:
        send_text(token, "❌ 下载超时，未检测到新文件")
        return

    send_text(token, "📤 正在发送文件到群...")
    send_file(token, os.path.join(download_dir, final_file))
    send_text(token, f"🎉 全部完成！[{final_file}] 已发送到群")

if __name__ == '__main__':
    kw = sys.argv[1] if len(sys.argv) > 1 else 'light'
    asyncio.run(main(kw))
