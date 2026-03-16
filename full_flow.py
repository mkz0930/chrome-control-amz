"""
full_flow.py - 亚马逊卖家精灵数据导出
v10: 下载失败时重试2次 + 详细调试输出
"""
import asyncio, websockets, json, time, os, sys, base64, requests

sys.path.insert(0, os.path.dirname(__file__))
from anti_detect import AntiDetect

WS_URL = 'ws://172.25.0.1:19000'
APP_ID = "cli_a90368220db89cd1"
APP_SECRET = "R184ONuIpFTCaAIUHsyyxb2eahXZ8ugh"
CHAT_ID = "oc_e0c619610b0f4b16593fd16dd9b2d186"

MAX_EXPORT_RETRIES = 2   # 导出失败后最多重试次数
DOWNLOAD_TIMEOUT   = 90  # 每次等待下载的秒数

# ─── 飞书工具 ────────────────────────────────────────────────────────────────

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

# ─── WebSocket 命令 ──────────────────────────────────────────────────────────

async def ws_cmd(action, **kwargs):
    timeout = 60 if action == 'screenshot' else 30
    async with websockets.connect(WS_URL, max_size=10*1024*1024) as ws:
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        await ws.recv()
        rid = str(asyncio.get_event_loop().time())
        await ws.send(json.dumps({'action': action, 'request_id': rid, **kwargs}))
        return json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))

async def screenshot_and_send(tc, token, step_name):
    try:
        r = await tc('screenshot', format='png')
        raw = r.get('data', '')
        # data URI 或纯 base64 都兼容
        b64 = raw.split(',')[1] if ',' in raw else raw
        png = base64.b64decode(b64)
        send_image(token, png)
        print(f"📸 {step_name} 截图已发送")
    except Exception as e:
        print(f"⚠️ {step_name} 截图失败（跳过）: {e}")

# ─── 单次导出尝试 ─────────────────────────────────────────────────────────────

async def try_export(tc, ad, token, keyword, attempt_no):
    """
    执行一次「全选 → 导出 → 等待文件」流程。
    返回 (final_file_path | None, debug_info_str)
    """
    debug = []

    def dbg(msg):
        print(msg)
        debug.append(msg)

    download_dir = '/mnt/d/download/'
    files_before = set(os.listdir(download_dir))
    dbg(f"[attempt {attempt_no}] 下载目录现有文件数: {len(files_before)}")

    # 全选
    dbg(f"[attempt {attempt_no}] 点击全选...")
    selected = False
    for i in range(6):
        await ad.before_click()
        r = await tc('click_text', text='全选')
        dbg(f"  全选 try {i+1}: ok={r.get('ok')} tag={r.get('tag')} text={r.get('text')}")
        if r.get('ok'):
            selected = True
            break
        dbg(f"  全选未找到，等 5s 重试...")
        await asyncio.sleep(5)

    if not selected:
        dbg(f"[attempt {attempt_no}] ❌ 全选始终未找到")
    await screenshot_and_send(tc, token, f"全选(attempt {attempt_no})")
    await ad.human_delay(1.5, 3)

    # 导出
    dbg(f"[attempt {attempt_no}] 点击导出...")
    await ad.before_click()
    r = await tc('click_text', text='导出')
    dbg(f"  导出结果: ok={r.get('ok')} tag={r.get('tag')} text={r.get('text')}")
    if not r.get('ok'):
        dbg(f"[attempt {attempt_no}] ❌ 导出按钮未找到: {r}")
    await screenshot_and_send(tc, token, f"导出(attempt {attempt_no})")

    # 等待文件出现
    dbg(f"[attempt {attempt_no}] 等待下载（最多 {DOWNLOAD_TIMEOUT}s）...")
    for i in range(DOWNLOAD_TIMEOUT):
        files_after = set(os.listdir(download_dir))
        new_files = files_after - files_before
        done = [f for f in new_files if not f.endswith('.crdownload') and not f.endswith('.tmp')]
        if done:
            final_file = done[0]
            path = os.path.join(download_dir, final_file)
            size = os.path.getsize(path)
            dbg(f"[attempt {attempt_no}] ✅ 文件已下载: {final_file} ({size:,} bytes)")
            return path, '\n'.join(debug)
        if new_files:
            dbg(f"  下载中... {new_files} ({i}s)")
        time.sleep(1)

    dbg(f"[attempt {attempt_no}] ❌ 等待 {DOWNLOAD_TIMEOUT}s 后仍无新文件")
    dbg(f"  当前目录文件: {sorted(os.listdir(download_dir))[-5:]}")  # 最新5个
    return None, '\n'.join(debug)

# ─── 主流程 ──────────────────────────────────────────────────────────────────

async def main(keyword='light'):
    token = get_token()
    send_text(token, f"🚀 开始抓取 [{keyword}] 数据，全程实时播报...")
    print(f"▶ keyword: {keyword}")

    # Step 1: 打开新 tab
    send_text(token, "📌 Step 1/4：打开亚马逊搜索页...")
    r = await ws_cmd('new_tab', url=f'https://www.amazon.com/s?k={keyword}')
    print(f"  new_tab 结果: {r}")
    tab_id = r.get('tab_id') or r.get('id')
    if not tab_id:
        msg = f"❌ 无法获取 tabId: {r}"
        send_text(token, msg)
        print(msg)
        return

    async def tc(action, **kwargs):
        return await ws_cmd(action, tabId=tab_id, **kwargs)

    ad = AntiDetect(tc)
    await asyncio.sleep(3)
    await ad.after_page_load()
    await screenshot_and_send(tc, token, "Step 1")
    send_text(token, f"✅ Step 1 完成：页面已打开，tab_id={tab_id}")

    # Step 2: 点击卖家精灵
    send_text(token, "📌 Step 2/4：点击卖家精灵，等待数据注入...")
    await ad.before_click()
    r = await tc('click_text', text='卖家精灵')
    print(f"  卖家精灵点击: ok={r.get('ok')} tag={r.get('tag')}")
    if r.get('ok'):
        send_text(token, "✅ 卖家精灵已点击，等待数据加载（约 18~25 秒）...")
    else:
        send_text(token, f"⚠️ 卖家精灵点击失败: {r}")

    await ad.long_delay(18, 25)
    await ad.random_scroll(times=2)
    await ad.human_delay(1, 3)
    await screenshot_and_send(tc, token, "Step 2")
    send_text(token, "✅ Step 2 完成：卖家精灵数据已注入")

    # Step 3+4: 全选 → 导出（失败时重试）
    final_file = None
    for attempt in range(1, MAX_EXPORT_RETRIES + 2):  # 1次正常 + 2次重试
        send_text(token, f"📌 Step 3/4：全选 + 导出（第 {attempt} 次尝试）...")
        final_file, debug_log = await try_export(tc, ad, token, keyword, attempt)

        if final_file:
            break

        # 没拿到文件 → 发调试信息
        send_text(token, f"❌ 第 {attempt} 次导出未检测到文件，调试信息：\n```\n{debug_log}\n```")

        if attempt <= MAX_EXPORT_RETRIES:
            send_text(token, f"🔄 准备第 {attempt + 1} 次重试（等 5s）...")
            await asyncio.sleep(5)
        else:
            send_text(token, "❌ 已达最大重试次数，放弃。")
            return

    # Step 5: 发文件
    send_text(token, "📤 正在发送文件到群...")
    send_file(token, final_file)
    send_text(token, f"🎉 全部完成！[{os.path.basename(final_file)}] 已发送到群")

if __name__ == '__main__':
    kw = sys.argv[1] if len(sys.argv) > 1 else 'light'
    asyncio.run(main(kw))
