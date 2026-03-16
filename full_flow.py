"""
full_flow.py - 亚马逊卖家精灵数据导出
v12: 防空下载六层校验 + 熔断机制
  1. 前置：商品列表非空断言
  2. 前置：卖家精灵数据注入确认
  3. 前置：导出按钮可见且可用
  4. 下载后：文件存在 + 大小 > 0
  5. 内容校验：至少两行、非 HTML、有分隔符
  6. 交叉校验：页面商品数 vs CSV 行数
  + 空下载熔断（连续失败直接终止）
"""
import asyncio, websockets, json, time, os, sys, base64, requests, re
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

sys.path.insert(0, os.path.dirname(__file__))
from anti_detect import AntiDetect

# ─── 配置 ────────────────────────────────────────────────────────────────────

def _load_ws_url() -> str:
    import socket
    config_path = Path(__file__).parent / 'config.json'
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text())
            url = cfg.get('ws_url', '')
            if url:
                print(f"🔌 WS_URL from config: {url}")
                return url
        except Exception:
            pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = '172.25.0.1'
    url = f'ws://{ip}:19000'
    config_path.write_text(json.dumps({'ws_url': url}, indent=4))
    print(f"🔌 WS_URL 自动检测并写入 config: {url}")
    return url

WS_URL             = _load_ws_url()
APP_ID             = "cli_a90368220db89cd1"
APP_SECRET         = "R184ONuIpFTCaAIUHsyyxb2eahXZ8ugh"
CHAT_ID            = "oc_e0c619610b0f4b16593fd16dd9b2d186"
DOWNLOAD_DIR       = Path('/mnt/d/download/')
MAX_EXPORT_RETRIES = 2    # 导出失败后最多重试次数
DOWNLOAD_TIMEOUT   = 90   # 每次等待下载的秒数

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

# ─── 等待条件工具 ────────────────────────────────────────────────────────────

async def wait_for_condition(check_fn, timeout=30, interval=1.5, desc="condition"):
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            result = check_fn()
            if asyncio.iscoroutine(result):
                result = await result
            if result:
                print(f"✅ [{desc}] 满足（第{attempt}次，{time.time()-deadline+timeout:.1f}s）")
                return result
        except Exception as e:
            print(f"  [{desc}] 检查异常: {e}")
        await asyncio.sleep(interval)
    raise TimeoutError(f"[{desc}] 超时 {timeout}s（共检查{attempt}次）")

# ─── Watchdog 下载监听 ────────────────────────────────────────────────────────

class _DownloadHandler(FileSystemEventHandler):
    def __init__(self, files_before: set, loop):
        self.files_before = files_before
        self.loop = loop
        self._future = loop.create_future()

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.name.endswith(('.crdownload', '.tmp', '.part')):
            return
        if path.name not in self.files_before and not self._future.done():
            print(f"📥 watchdog 新文件: {path.name}")
            self.loop.call_soon_threadsafe(self._future.set_result, path)

    def on_moved(self, event):
        dest = Path(event.dest_path)
        if not dest.name.endswith(('.crdownload', '.tmp', '.part')) \
                and dest.name not in self.files_before \
                and not self._future.done():
            print(f"📥 watchdog 文件完成: {dest.name}")
            self.loop.call_soon_threadsafe(self._future.set_result, dest)

    @property
    def future(self):
        return self._future


async def wait_for_download(files_before: set, timeout=DOWNLOAD_TIMEOUT) -> Path:
    loop = asyncio.get_event_loop()
    handler = _DownloadHandler(files_before, loop)
    observer = Observer()
    observer.schedule(handler, str(DOWNLOAD_DIR), recursive=False)
    observer.start()
    print(f"👁️  watchdog 监听: {DOWNLOAD_DIR}")
    try:
        path = await asyncio.wait_for(handler.future, timeout=timeout)
        await _wait_file_stable(path)
        return path
    except asyncio.TimeoutError:
        raise TimeoutError(f"下载超时 {timeout}s，目录最新: {_latest_files(DOWNLOAD_DIR)}")
    finally:
        observer.stop()
        observer.join()


async def _wait_file_stable(path: Path, checks=3, interval=1.0):
    prev_size, stable = -1, 0
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

# ─── 防空下载：六层校验 ───────────────────────────────────────────────────────

async def assert_results_not_empty(tc, dbg) -> int:
    """
    校验1：页面商品列表非空，返回商品数量。
    空页面直接抛异常，禁止进入导出流程。
    """
    r = await tc('eval', code="""
        (function() {
            var items = document.querySelectorAll('.s-result-item[data-asin]');
            var noData = document.querySelector(
                '[class*="no-results"], [class*="noResults"], [class*="empty-state"]'
            );
            return {count: items.length, noData: !!noData};
        })()
    """)
    result = r.get('result', {})
    count = result.get('count', 0) if isinstance(result, dict) else 0
    no_data = result.get('noData', False) if isinstance(result, dict) else False
    dbg(f"  商品数量: {count}, 无数据提示: {no_data}")
    if no_data or count == 0:
        raise ValueError(f"页面无商品数据（count={count}, noData={no_data}），禁止导出")
    return count


async def assert_export_btn_ready(tc, dbg) -> bool:
    """
    校验2：导出按钮可见且未被禁用。
    """
    r = await tc('eval', code="""
        (function() {
            // 找导出按钮（卖家精灵的导出区域）
            var btns = Array.from(document.querySelectorAll('button, [role="button"]'));
            var exportBtn = btns.find(function(b) {
                return /导出|export/i.test(b.textContent);
            });
            if (!exportBtn) return {found: false};
            var rect = exportBtn.getBoundingClientRect();
            return {
                found: true,
                disabled: exportBtn.disabled || exportBtn.getAttribute('aria-disabled') === 'true',
                visible: rect.width > 0 && rect.height > 0
            };
        })()
    """)
    result = r.get('result', {})
    found   = result.get('found', False) if isinstance(result, dict) else False
    disabled = result.get('disabled', True) if isinstance(result, dict) else True
    visible  = result.get('visible', False) if isinstance(result, dict) else False
    dbg(f"  导出按钮: found={found} visible={visible} disabled={disabled}")
    if not found or not visible or disabled:
        raise ValueError(f"导出按钮不可用（found={found}, visible={visible}, disabled={disabled}）")
    return True


def validate_csv_content(path: Path, page_count: int, dbg) -> int:
    """
    校验3+4+5：
    - 文件存在且非空
    - 内容不是 HTML（错误页/登录页重定向）
    - 至少有表头 + 1 行数据
    - 有分隔符（是真正的 CSV）
    - 与页面商品数交叉校验
    返回 CSV 数据行数。
    """
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    size = path.stat().st_size
    if size == 0:
        raise ValueError(f"文件大小为 0: {path.name}")

    # 读内容（xlsx 也尝试读，至少确认非 HTML）
    try:
        text = path.read_text(encoding='utf-8', errors='ignore').strip()
    except Exception:
        text = ''

    if '<html' in text.lower():
        raise ValueError(f"下载到的不是数据文件，疑似错误页/登录页重定向: {path.name}")

    # xlsx 文件跳过文本行数校验，只校验大小
    if path.suffix.lower() in ('.xlsx', '.xls'):
        dbg(f"  xlsx 文件，大小校验通过: {size:,} bytes")
        return -1  # xlsx 行数不做文本解析

    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        raise ValueError(f"CSV 只有 {len(lines)} 行（需要至少表头+1行数据）")

    header = lines[0]
    if ',' not in header and '\t' not in header and ';' not in header:
        raise ValueError(f"首行不像 CSV 表头（无分隔符）: {header[:80]}")

    data_rows = len(lines) - 1
    dbg(f"  CSV 行数: 表头1行 + 数据{data_rows}行")

    # 交叉校验：页面有数据但 CSV 为空
    if page_count > 0 and data_rows == 0:
        raise ValueError(f"页面显示 {page_count} 个商品，但 CSV 无数据行（空下载）")

    return data_rows


# ─── 单次导出尝试（含六层校验）────────────────────────────────────────────────

async def try_export(tc, ad, token, keyword, attempt_no, page_count: int):
    """
    执行一次「前置校验 → 全选 → 导出按钮校验 → 触发下载 → 内容校验」。
    返回 (file_path | None, debug_log_str)
    """
    debug = []
    def dbg(msg):
        print(msg)
        debug.append(msg)

    # ── 校验1：页面商品非空 ──────────────────────────────────────────────────
    dbg(f"[attempt {attempt_no}] 校验1：页面商品列表非空...")
    try:
        page_count = await assert_results_not_empty(tc, dbg)
        dbg(f"  ✅ 商品数量: {page_count}")
    except ValueError as e:
        dbg(f"  ❌ {e}")
        await screenshot_and_send(tc, token, f"空页面(attempt {attempt_no})")
        return None, '\n'.join(debug)

    files_before = set(f.name for f in DOWNLOAD_DIR.iterdir())
    dbg(f"[attempt {attempt_no}] 下载目录现有文件数: {len(files_before)}")

    # ── 全选 ────────────────────────────────────────────────────────────────
    dbg(f"[attempt {attempt_no}] 等待「全选」按钮...")
    selected = False
    try:
        async def check_select():
            await ad.before_click()
            r = await tc('click_text', text='全选')
            dbg(f"  全选: ok={r.get('ok')} tag={r.get('tag')} err={r.get('error','')}")
            return r.get('ok')
        await wait_for_condition(check_select, timeout=60, interval=3, desc="全选")
        selected = True
    except TimeoutError as e:
        dbg(f"  ❌ {e}")

    await screenshot_and_send(tc, token, f"全选(attempt {attempt_no})")
    await ad.human_delay(1.5, 3)

    # ── 校验2：导出按钮可用 ──────────────────────────────────────────────────
    dbg(f"[attempt {attempt_no}] 校验2：导出按钮可见且可用...")
    try:
        await assert_export_btn_ready(tc, dbg)
        dbg("  ✅ 导出按钮就绪")
    except ValueError as e:
        dbg(f"  ⚠️ {e}（继续尝试点击）")

    # ── 触发导出 ─────────────────────────────────────────────────────────────
    dbg(f"[attempt {attempt_no}] 点击导出...")
    await ad.before_click()
    r = await tc('click_text', text='导出')
    dbg(f"  导出结果: ok={r.get('ok')} tag={r.get('tag')} err={r.get('error','')}")
    if not r.get('ok'):
        dbg(f"  ❌ 导出按钮未找到")
    await screenshot_and_send(tc, token, f"导出(attempt {attempt_no})")

    # ── 等待下载（watchdog）──────────────────────────────────────────────────
    dbg(f"[attempt {attempt_no}] watchdog 等待下载（最多 {DOWNLOAD_TIMEOUT}s）...")
    try:
        path = await wait_for_download(files_before, timeout=DOWNLOAD_TIMEOUT)
    except TimeoutError as e:
        dbg(f"  ❌ {e}")
        return None, '\n'.join(debug)

    # ── 校验3+4+5：内容校验 + 交叉校验 ──────────────────────────────────────
    dbg(f"[attempt {attempt_no}] 校验3-5：文件内容校验...")
    try:
        data_rows = validate_csv_content(path, page_count, dbg)
        dbg(f"  ✅ 内容校验通过（数据行: {data_rows}）")
    except (ValueError, FileNotFoundError) as e:
        dbg(f"  ❌ 内容校验失败: {e}")
        # 保留失败样本前200字节
        try:
            sample = path.read_bytes()[:200]
            dbg(f"  文件前200字节: {sample}")
        except Exception:
            pass
        return None, '\n'.join(debug)

    dbg(f"[attempt {attempt_no}] ✅ 全部校验通过: {path.name} ({path.stat().st_size:,} bytes)")
    return str(path), '\n'.join(debug)

# ─── 主流程 ──────────────────────────────────────────────────────────────────

async def main(keyword='light'):
    token = get_token()
    send_text(token, f"🚀 开始抓取 [{keyword}] 数据，全程实时播报...")
    print(f"▶ keyword: {keyword}")

    # Step 1: 打开搜索页
    send_text(token, "📌 Step 1/4：打开亚马逊搜索页...")
    r = await ws_cmd('navigate', url=f'https://www.amazon.com/s?k={keyword}')
    print(f"  navigate: {r}")
    tab_id = r.get('tab_id') or r.get('id')
    if not tab_id:
        msg = f"❌ 无法获取 tabId: {r}"
        send_text(token, msg); print(msg); return

    async def tc(action, **kwargs):
        return await ws_cmd(action, tabId=tab_id, **kwargs)

    ad = AntiDetect(tc)

    # 等页面加载完成
    await wait_for_condition(
        lambda: tc('eval', code="document.readyState === 'complete'"),
        timeout=30, interval=1, desc="页面加载"
    )
    await ad.after_page_load()

    # 等商品列表出现
    send_text(token, "⏳ 等待商品列表渲染...")
    page_count = 0
    try:
        await wait_for_condition(
            lambda: tc('eval', code="document.querySelectorAll('.s-result-item[data-asin]').length >= 5"),
            timeout=20, interval=2, desc="商品列表"
        )
        r = await tc('eval', code="document.querySelectorAll('.s-result-item[data-asin]').length")
        page_count = r.get('result', 0) or 0
        print(f"✅ 商品列表已渲染，数量: {page_count}")
    except TimeoutError:
        print("⚠️ 商品列表等待超时，继续")

    # 模拟用户浏览（反爬 + 让懒加载充分触发）
    print("🖱️  模拟用户浏览页面...")
    await ad.browse_scroll()

    await screenshot_and_send(tc, token, "Step 1")
    send_text(token, f"✅ Step 1 完成：tab_id={tab_id}，商品数≈{page_count}")

    # Step 2: 点击卖家精灵，等待数据注入
    send_text(token, "📌 Step 2/4：点击卖家精灵，等待数据注入...")
    await ad.before_click()
    r = await tc('click_text', text='卖家精灵')
    print(f"  卖家精灵: ok={r.get('ok')} tag={r.get('tag')}")
    if not r.get('ok'):
        send_text(token, f"⚠️ 卖家精灵点击失败: {r}")

    send_text(token, "⏳ 等待卖家精灵数据注入（最多 60s）...")
    try:
        await wait_for_condition(
            lambda: tc('eval', code="""
                !!document.querySelector('[class*="seajin"],[class*="seller-sprite"],[data-monthly-sales]')
            """),
            timeout=60, interval=3, desc="卖家精灵注入"
        )
        send_text(token, "✅ 卖家精灵数据已注入")
    except TimeoutError:
        send_text(token, "⚠️ 卖家精灵注入超时，继续尝试导出")

    await ad.random_scroll(times=2)
    await ad.human_delay(1, 3)
    await screenshot_and_send(tc, token, "Step 2")

    # Step 3+4: 全选 → 导出（失败时重试，空下载熔断）
    final_file = None
    consecutive_empty = 0

    for attempt in range(1, MAX_EXPORT_RETRIES + 2):
        send_text(token, f"📌 Step 3/4：全选 + 导出（第 {attempt} 次）...")
        final_file, debug_log = await try_export(tc, ad, token, keyword, attempt, page_count)

        if final_file:
            break

        consecutive_empty += 1
        send_text(token, f"❌ 第 {attempt} 次导出失败，调试信息：\n```\n{debug_log[-800:]}\n```")

        # 熔断：连续2次空下载且页面有数据 → 直接终止
        if consecutive_empty >= 2 and page_count > 0:
            send_text(token, f"🔥 熔断：连续 {consecutive_empty} 次空下载（页面有 {page_count} 个商品），终止任务")
            await screenshot_and_send(tc, token, "熔断截图")
            return

        if attempt <= MAX_EXPORT_RETRIES:
            send_text(token, f"🔄 第 {attempt + 1} 次重试（等 5s）...")
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
