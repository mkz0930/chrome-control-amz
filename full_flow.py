"""
full_flow.py - 亚马逊卖家精灵数据导出
v11: wait_for_condition 替换 sleep 轮询 + watchdog 目录监听 + 反爬 v2
"""
import asyncio, websockets, json, time, os, sys, base64, requests, threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

sys.path.insert(0, os.path.dirname(__file__))
from anti_detect import AntiDetect

WS_URL          = 'ws://172.25.0.1:19000'
APP_ID          = "cli_a90368220db89cd1"
APP_SECRET      = "R184ONuIpFTCaAIUHsyyxb2eahXZ8ugh"
CHAT_ID         = "oc_e0c619610b0f4b16593fd16dd9b2d186"
DOWNLOAD_DIR    = Path('/mnt/d/download/')
MAX_EXPORT_RETRIES = 2
DOWNLOAD_TIMEOUT   = 90   # 秒

# ─── 飞书工具 ────────────────────────────────────────────────────────────────

def get_token():
    r = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=15
    )
    return r.json()["tenant_access_token"]

def send_text(token, text):
    requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": CHAT_ID, "msg_type": "text", "content": json.dumps({"text": text})},
        timeout=15
    )

def send_image(token, png_bytes):
    r = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/images",
        headers={"Authorization": f"Bearer {token}"},
        data={"image_type": "message"},
        files={"image": ("screenshot.png", png_bytes, "image/png")},
        timeout=30
    ).json()
    if r.get("code") != 0:
        print(f"⚠️ 图片上传失败: {r}")
        return
    image_key = r["data"]["image_key"]
    requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": CHAT_ID, "msg_type": "image", "content": json.dumps({"image_key": image_key})},
        timeout=15
    )

def send_file(token, file_path):
    filename = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        r = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"file_type": "xlsx", "file_name": filename},
            files={"file": (filename, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=60
        ).json()
    if r.get("code") != 0:
        print(f"⚠️ 文件上传失败: {r}")
        return
    file_key = r["data"]["file_key"]
    requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": CHAT_ID, "msg_type": "file", "content": json.dumps({"file_key": file_key})},
        timeout=15
    )

# ─── WebSocket 命令 ──────────────────────────────────────────────────────────

async def ws_cmd(action, **kwargs):
    timeout = 60 if action in ('screenshot', 'navigate') else 30
    async with websockets.connect(WS_URL, max_size=10*1024*1024) as ws:
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        await ws.recv()
        rid = str(time.time())
        payload = {'action': action, 'request_id': rid, 'timeout': timeout, **kwargs}
        await ws.send(json.dumps(payload))
        return json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout + 5))

# ─── 等待条件工具（替代 sleep 轮询）────────────────────────────────────────────

async def wait_for_condition(check_fn, timeout=30, interval=1.5, desc="condition"):
    """
    轮询 check_fn()，直到返回 truthy 或超时。
    check_fn 可以是 async 或 sync。
    """
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            result = check_fn()
            if asyncio.iscoroutine(result):
                result = await result
            if result:
                print(f"✅ wait_for_condition [{desc}] 满足（第{attempt}次，{time.time()-deadline+timeout:.1f}s）")
                return result
        except Exception as e:
            print(f"  wait_for_condition [{desc}] 检查异常: {e}")
        await asyncio.sleep(interval)
    raise TimeoutError(f"wait_for_condition [{desc}] 超时 {timeout}s（共检查{attempt}次）")

# ─── Watchdog 下载监听 ────────────────────────────────────────────────────────

class _DownloadHandler(FileSystemEventHandler):
    """监听下载目录，新文件完成时通知"""
    def __init__(self, files_before: set, loop: asyncio.AbstractEventLoop):
        self.files_before = files_before
        self.loop = loop
        self._future = loop.create_future()

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        name = path.name
        # 跳过临时文件
        if name.endswith(('.crdownload', '.tmp', '.part')):
            return
        if name not in self.files_before:
            print(f"📥 watchdog 检测到新文件: {name}")
            if not self._future.done():
                self.loop.call_soon_threadsafe(self._future.set_result, path)

    def on_moved(self, event):
        """crdownload → 真实文件名"""
        dest = Path(event.dest_path)
        if dest.name not in self.files_before and not dest.name.endswith(('.crdownload', '.tmp', '.part')):
            print(f"📥 watchdog 检测到文件完成: {dest.name}")
            if not self._future.done():
                loop = self.loop
                loop.call_soon_threadsafe(self._future.set_result, dest)

    @property
    def future(self):
        return self._future


async def wait_for_download(files_before: set, timeout=DOWNLOAD_TIMEOUT) -> Path:
    """
    用 watchdog 监听下载目录，返回新完成的文件路径。
    比轮询更快、更准确。
    """
    loop = asyncio.get_event_loop()
    handler = _DownloadHandler(files_before, loop)
    observer = Observer()
    observer.schedule(handler, str(DOWNLOAD_DIR), recursive=False)
    observer.start()
    print(f"👁️  watchdog 开始监听: {DOWNLOAD_DIR}")
    try:
        path = await asyncio.wait_for(handler.future, timeout=timeout)
        # 等文件写完（大小稳定）
        await _wait_file_stable(path)
        return path
    except asyncio.TimeoutError:
        raise TimeoutError(f"下载超时 {timeout}s，目录最新文件: {_latest_files(DOWNLOAD_DIR)}")
    finally:
        observer.stop()
        observer.join()


async def _wait_file_stable(path: Path, checks=3, interval=1.0):
    """等待文件大小连续稳定，确认写入完成"""
    prev_size = -1
    stable = 0
    for _ in range(20):
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            await asyncio.sleep(interval)
            continue
        if size == prev_size and size > 0:
            stable += 1
            if stable >= checks:
                print(f"✅ 文件稳定: {path.name} ({size:,} bytes)")
                return
        else:
            stable = 0
        prev_size = size
        await asyncio.sleep(interval)


def _latest_files(directory: Path, n=5):
    try:
        files = sorted(directory.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
        return [f.name for f in files[:n]]
    except Exception:
        return []

# ─── 截图工具 ────────────────────────────────────────────────────────────────

async def screenshot_and_send(tc, token, step_name):
    try:
        r = await tc('screenshot', format='png')
        raw = r.get('data', '')
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
    返回 (file_path | None, debug_log_str)
    """
    debug = []
    def dbg(msg):
        print(msg)
        debug.append(msg)

    files_before = set(f.name for f in DOWNLOAD_DIR.iterdir())
    dbg(f"[attempt {attempt_no}] 下载目录现有文件数: {len(files_before)}")

    # 全选：用 wait_for_condition 替代固定 sleep
    dbg(f"[attempt {attempt_no}] 等待「全选」按钮出现...")
    selected = False
    try:
        async def check_select():
            await ad.before_click()
            r = await tc('click_text', text='全选')
            dbg(f"  全选检查: ok={r.get('ok')} tag={r.get('tag')} err={r.get('error','')}")
            return r.get('ok')

        await wait_for_condition(check_select, timeout=60, interval=3, desc="全选")
        selected = True
    except TimeoutError as e:
        dbg(f"[attempt {attempt_no}] ❌ {e}")

    await screenshot_and_send(tc, token, f"全选(attempt {attempt_no})")
    await ad.human_delay(1.5, 3)

    # 导出
    dbg(f"[attempt {attempt_no}] 点击导出...")
    await ad.before_click()
    r = await tc('click_text', text='导出')
    dbg(f"  导出结果: ok={r.get('ok')} tag={r.get('tag')} err={r.get('error','')}")
    if not r.get('ok'):
        dbg(f"[attempt {attempt_no}] ❌ 导出按钮未找到")
    await screenshot_and_send(tc, token, f"导出(attempt {attempt_no})")

    # 等待下载（watchdog）
    dbg(f"[attempt {attempt_no}] watchdog 等待下载（最多 {DOWNLOAD_TIMEOUT}s）...")
    try:
        path = await wait_for_download(files_before, timeout=DOWNLOAD_TIMEOUT)
        dbg(f"[attempt {attempt_no}] ✅ 文件已下载: {path.name} ({path.stat().st_size:,} bytes)")
        return str(path), '\n'.join(debug)
    except TimeoutError as e:
        dbg(f"[attempt {attempt_no}] ❌ {e}")
        return None, '\n'.join(debug)

# ─── 主流程 ──────────────────────────────────────────────────────────────────

async def main(keyword='light'):
    token = get_token()
    send_text(token, f"🚀 开始抓取 [{keyword}] 数据，全程实时播报...")
    print(f"▶ keyword: {keyword}")

    # Step 1: 打开搜索页
    send_text(token, "📌 Step 1/4：打开亚马逊搜索页...")
    r = await ws_cmd('navigate', url=f'https://www.amazon.com/s?k={keyword}')
    print(f"  navigate 结果: {r}")
    tab_id = r.get('tab_id') or r.get('id')
    if not tab_id:
        msg = f"❌ 无法获取 tabId: {r}"
        send_text(token, msg); print(msg); return

    async def tc(action, **kwargs):
        return await ws_cmd(action, tabId=tab_id, **kwargs)

    ad = AntiDetect(tc)

    # 等待页面真正加载完成（而不是固定 sleep）
    await wait_for_condition(
        lambda: tc('eval', code="document.readyState === 'complete'"),
        timeout=30, interval=1, desc="页面加载"
    )
    await ad.after_page_load()
    await screenshot_and_send(tc, token, "Step 1")
    send_text(token, f"✅ Step 1 完成：页面已打开，tab_id={tab_id}")

    # Step 2: 点击卖家精灵，等待数据注入
    send_text(token, "📌 Step 2/4：点击卖家精灵，等待数据注入...")
    await ad.before_click()
    r = await tc('click_text', text='卖家精灵')
    print(f"  卖家精灵点击: ok={r.get('ok')} tag={r.get('tag')}")
    if r.get('ok'):
        send_text(token, "✅ 卖家精灵已点击，等待数据加载...")
    else:
        send_text(token, f"⚠️ 卖家精灵点击失败: {r}")

    # 等待卖家精灵数据注入完成（等「全选」按钮出现，而不是固定 sleep）
    send_text(token, "⏳ 等待卖家精灵数据注入（最多 60s）...")
    try:
        await wait_for_condition(
            lambda: tc('eval', code="""
                !!document.querySelector('[class*="seajin"], [class*="seller-sprite"], .s-result-item [data-monthly-sales]')
            """),
            timeout=60, interval=3, desc="卖家精灵数据注入"
        )
        send_text(token, "✅ 卖家精灵数据已注入")
    except TimeoutError:
        send_text(token, "⚠️ 卖家精灵数据注入超时，继续尝试导出")

    await ad.random_scroll(times=2)
    await ad.human_delay(1, 3)
    await screenshot_and_send(tc, token, "Step 2")

    # Step 3+4: 全选 → 导出（失败时重试）
    final_file = None
    for attempt in range(1, MAX_EXPORT_RETRIES + 2):
        send_text(token, f"📌 Step 3/4：全选 + 导出（第 {attempt} 次尝试）...")
        final_file, debug_log = await try_export(tc, ad, token, keyword, attempt)

        if final_file:
            break

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
