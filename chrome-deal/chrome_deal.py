"""
chrome_deal.py — Chrome 浏览器操作工具库
通过 WebSocket Relay Server 控制 Windows Chrome
"""
import asyncio
import json
import time
import base64
import random
import websockets

WS_URI = "ws://127.0.0.1:19000"


class ChromeDeal:
    """Chrome 浏览器操作封装"""

    def __init__(self, ws_uri=WS_URI):
        self.ws_uri = ws_uri
        self.tab_id = None

    async def cmd(self, action, timeout=None, **kwargs):
        """发送命令到 Chrome 插件"""
        if timeout is None:
            timeout = 60 if action in ("screenshot", "navigate") else 30

        async with websockets.connect(self.ws_uri, max_size=10 * 1024 * 1024) as ws:
            await ws.send(json.dumps({"type": "agent", "version": "1.0.0"}))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if not resp.get("extension_online"):
                return {"ok": False, "error": "Chrome 插件未连接 relay server"}

            rid = f"{action}-{int(time.time() * 1000)}"
            payload = {"action": action, "request_id": rid, "timeout": timeout, **kwargs}
            if self.tab_id and "tabId" not in kwargs:
                payload["tabId"] = self.tab_id

            await ws.send(json.dumps(payload))
            result = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout + 5))

            # 自动记录 tab_id
            if result.get("ok") and result.get("tab_id"):
                self.tab_id = result["tab_id"]

            return result

    # ── 导航 ──

    async def open(self, url):
        """打开网页"""
        return await self.cmd("navigate", url=url)

    async def get_url(self):
        """获取当前 URL"""
        return await self.cmd("get_url")

    async def new_tab(self, url="about:blank"):
        """新建标签页"""
        return await self.cmd("new_tab", url=url)

    async def list_tabs(self):
        """列出所有标签页"""
        return await self.cmd("list_tabs")

    async def switch_tab(self, tab_id):
        """切换标签页"""
        return await self.cmd("switch_tab", tabId=tab_id)

    async def close_tab(self, tab_id=None):
        """关闭标签页"""
        return await self.cmd("close_tab", tabId=tab_id or self.tab_id)

    # ── 交互 ──

    async def click(self, selector):
        """CSS 选择器点击"""
        return await self.cmd("click", selector=selector)

    async def click_text(self, text):
        """按文字点击"""
        return await self.cmd("click_text", text=text)

    async def click_xy(self, x, y):
        """坐标点击"""
        return await self.cmd("click_xy", x=x, y=y)

    async def type_text(self, selector, text):
        """输入文字"""
        return await self.cmd("type", selector=selector, text=text)

    async def scroll(self, y=500):
        """滚动页面"""
        return await self.cmd("scroll", y=y)

    async def wait_for(self, selector, timeout=10000):
        """等待元素出现"""
        return await self.cmd("wait", selector=selector, timeout=timeout)

    # ── 数据获取 ──

    async def screenshot(self, fmt="png"):
        """截图，返回 base64"""
        r = await self.cmd("screenshot", format=fmt)
        if r.get("ok"):
            raw = r.get("data", "")
            r["base64"] = raw.split(",")[1] if "," in raw else raw
        return r

    async def screenshot_bytes(self):
        """截图，返回 PNG bytes"""
        r = await self.screenshot("png")
        if r.get("ok"):
            return base64.b64decode(r["base64"])
        return None

    async def get_text(self):
        """获取页面文本"""
        return await self.cmd("get_text")

    async def get_html(self, selector=None):
        """获取 HTML"""
        kwargs = {}
        if selector:
            kwargs["selector"] = selector
        return await self.cmd("get_html", **kwargs)

    async def eval_js(self, code):
        """执行 JavaScript"""
        return await self.cmd("eval", code=code)

    # ── Cookie ──

    async def get_cookies(self, url=None):
        """获取 Cookie"""
        kwargs = {}
        if url:
            kwargs["url"] = url
        return await self.cmd("get_cookies", **kwargs)

    async def set_cookies(self, cookies):
        """设置 Cookie"""
        return await self.cmd("set_cookies", cookies=cookies)

    # ── 下载 ──

    async def download(self, url):
        """下载文件"""
        return await self.cmd("download", url=url)

    # ── 状态 ──

    async def status(self):
        """检查连接状态"""
        return await self.cmd("status")

    # ── 高级操作 ──

    async def human_scroll(self, pages=3, min_delay=1.0, max_delay=3.0):
        """模拟人类滚动"""
        for _ in range(pages):
            distance = random.randint(300, 800)
            await self.scroll(distance)
            await asyncio.sleep(random.uniform(min_delay, max_delay))

    async def human_delay(self, min_s=1.0, max_s=3.0):
        """随机延迟"""
        t = random.betavariate(2, 5) * (max_s - min_s) + min_s
        await asyncio.sleep(t)

    async def login(self, url, fields, submit_selector=None):
        """
        通用登录
        fields: [{"selector": "#email", "text": "user@example.com"}, ...]
        """
        r = await self.open(url)
        if not r.get("ok"):
            return r

        await asyncio.sleep(2)

        for field in fields:
            await self.type_text(field["selector"], field["text"])
            await self.human_delay(0.5, 1.5)

        if submit_selector:
            await self.click(submit_selector)
        else:
            # 尝试常见提交按钮
            for sel in ['[type="submit"]', 'button[type="submit"]', '#signInSubmit', '.submit-btn']:
                r = await self.click(sel)
                if r.get("ok"):
                    break

        await asyncio.sleep(3)
        return await self.get_url()

    async def wait_and_click(self, selector=None, text=None, timeout=30, interval=2):
        """等待元素出现后点击"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if text:
                r = await self.click_text(text)
            else:
                r = await self.click(selector)
            if r.get("ok"):
                return r
            await asyncio.sleep(interval)
        return {"ok": False, "error": f"等待超时 {timeout}s"}


# ── 快捷函数 ──

async def open_url(url):
    """快速打开网页"""
    c = ChromeDeal()
    return await c.open(url)


async def screenshot_to_file(path="screenshot.png"):
    """截图保存到文件"""
    c = ChromeDeal()
    data = await c.screenshot_bytes()
    if data:
        with open(path, "wb") as f:
            f.write(data)
        return {"ok": True, "path": path, "size": len(data)}
    return {"ok": False, "error": "截图失败"}


# ── CLI 测试 ──

if __name__ == "__main__":
    import sys

    async def main():
        c = ChromeDeal()
        
        # 检查状态
        r = await c.status()
        print(f"状态: {json.dumps(r, ensure_ascii=False)}")
        
        if len(sys.argv) > 1:
            url = sys.argv[1]
            print(f"打开: {url}")
            r = await c.open(url)
            print(f"结果: {json.dumps(r, ensure_ascii=False)}")

    asyncio.run(main())
