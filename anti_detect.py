"""
anti_detect.py - 反爬行为模拟工具 v2
增强：随机 UA 注入、随机 viewport resize、贝塞尔曲线鼠标轨迹、
      打字节奏模拟、页面可见性伪装、随机停顿节奏
"""
import asyncio
import random
import math


# 常见桌面 UA 池
_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]

# 常见 Referer 池
_REFERER_POOL = [
    "https://www.google.com/search?q=amazon+led+lights",
    "https://www.google.com/search?q=amazon+camping+gear",
    "https://www.bing.com/search?q=amazon+products",
    "https://www.amazon.com/",
    "",
]


def _bezier(p0, p1, p2, p3, t):
    """三次贝塞尔曲线插值"""
    return (
        (1 - t) ** 3 * p0
        + 3 * (1 - t) ** 2 * t * p1
        + 3 * (1 - t) * t ** 2 * p2
        + t ** 3 * p3
    )


class AntiDetect:
    def __init__(self, cmd_fn):
        self.cmd = cmd_fn

    # ── 基础延迟 ──────────────────────────────────────────────────────────────

    async def human_delay(self, min_s=1.5, max_s=4.0):
        # 非均匀分布：偏向较短停顿，偶尔长停顿
        t = random.betavariate(2, 5) * (max_s - min_s) + min_s
        print(f"⏳ human_delay: {t:.1f}s")
        await asyncio.sleep(t)

    async def long_delay(self, min_s=8, max_s=20):
        t = random.uniform(min_s, max_s)
        print(f"⏳ long_delay: {t:.1f}s")
        await asyncio.sleep(t)

    async def micro_pause(self):
        """极短停顿，模拟人眼扫描"""
        await asyncio.sleep(random.uniform(0.05, 0.25))

    # ── 鼠标模拟 ─────────────────────────────────────────────────────────────

    async def bezier_mouse_move(self, x0=None, y0=None, x1=None, y1=None, steps=None):
        """贝塞尔曲线鼠标轨迹，比直线更自然"""
        x0 = x0 or random.randint(100, 600)
        y0 = y0 or random.randint(100, 400)
        x1 = x1 or random.randint(100, 900)
        y1 = y1 or random.randint(100, 600)
        steps = steps or random.randint(8, 20)

        # 随机控制点
        cx1 = x0 + random.randint(-200, 200)
        cy1 = y0 + random.randint(-100, 100)
        cx2 = x1 + random.randint(-200, 200)
        cy2 = y1 + random.randint(-100, 100)

        points = []
        for i in range(steps + 1):
            t = i / steps
            px = int(_bezier(x0, cx1, cx2, x1, t))
            py = int(_bezier(y0, cy1, cy2, y1, t))
            points.append((px, py))

        js = """
        (function(pts) {
            pts.forEach(function(p) {
                document.dispatchEvent(new MouseEvent('mousemove', {
                    clientX: p[0], clientY: p[1], bubbles: true
                }));
            });
        })(%s)
        """ % str(points)

        await self.cmd('eval', code=js)
        print(f"🖱️  bezier_mouse: ({x0},{y0})→({x1},{y1}) {steps}步")
        await asyncio.sleep(random.uniform(0.2, 0.6))

    async def simulate_mouse_move(self, steps=5):
        """兼容旧接口，内部用贝塞尔"""
        await self.bezier_mouse_move(steps=steps)

    async def click_blank(self):
        x = random.randint(50, 300)
        y = random.randint(100, 400)
        print(f"🖱️  click_blank: ({x}, {y})")
        await self.bezier_mouse_move(x1=x, y1=y)
        await self.cmd('click_xy', x=x, y=y)
        await asyncio.sleep(random.uniform(0.5, 1.5))

    # ── 滚动模拟 ─────────────────────────────────────────────────────────────

    async def random_scroll(self, times=None):
        n = times or random.randint(2, 4)
        print(f"🖱️  random_scroll: {n} 次")
        for _ in range(n):
            direction = 1 if random.random() > 0.25 else -1
            # 非均匀滚动距离
            distance = int(random.betavariate(2, 3) * 600 + 100) * direction
            await self.cmd('scroll', y=distance)
            # 偶尔停顿更长，模拟阅读
            pause = random.uniform(0.5, 2.5) if random.random() > 0.3 else random.uniform(2.5, 5.0)
            await asyncio.sleep(pause)

    async def browse_scroll(self):
        """
        模拟真实用户浏览页面：
        - 分段缓慢向下滚动（每段 200~450px）
        - 偶尔停顿较长（模拟阅读商品）
        - 偶尔小幅回滚（模拟回看）
        - 偶尔悬停鼠标（模拟查看商品）
        - 总时长约 8~18s，让懒加载和卖家精灵数据充分注入
        """
        print("🖱️  browse_scroll: 模拟用户浏览页面")
        total_segments = random.randint(5, 9)
        for i in range(total_segments):
            if random.random() < 0.15 and i > 1:
                # 小幅回滚，模拟回看
                distance = -random.randint(80, 200)
                print(f"  ↑ 回滚 {abs(distance)}px")
            else:
                distance = random.randint(200, 450)
                print(f"  ↓ 滚动 {distance}px")

            await self.cmd('scroll', y=distance)

            # 停顿节奏：beta 分布偏短，偶尔长停顿模拟阅读
            if random.random() < 0.25:
                pause = random.uniform(2.0, 4.5)
                print(f"  ⏸  停顿 {pause:.1f}s（阅读中）")
            else:
                pause = random.betavariate(2, 4) * 2.0 + 0.5
                print(f"  ⏸  停顿 {pause:.1f}s")
            await asyncio.sleep(pause)

            # 偶尔移动鼠标，模拟悬停商品
            if random.random() < 0.4:
                await self.bezier_mouse_move(
                    x1=random.randint(200, 800),
                    y1=random.randint(200, 500),
                    steps=random.randint(6, 12)
                )

        print("✅ browse_scroll 完成")

    async def scroll_to_element_area(self, y_hint=400):
        """滚动到目标元素附近区域"""
        await self.cmd('scroll', y=y_hint)
        await asyncio.sleep(random.uniform(0.8, 1.5))

    # ── 浏览器指纹伪装 ────────────────────────────────────────────────────────

    async def spoof_navigator(self):
        """注入反检测 JS"""
        js = """
        (function() {
            // 隐藏 webdriver 标志
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            // 伪造插件列表
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const arr = [1,2,3,4,5];
                    arr.item = (i) => arr[i];
                    arr.namedItem = (n) => null;
                    arr.refresh = () => {};
                    return arr;
                }
            });
            // 伪造语言
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            // 伪造硬件并发数
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
            // 伪造设备内存
            Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
            // 页面可见性伪装（避免 visibilitychange 触发反爬）
            Object.defineProperty(document, 'hidden', {get: () => false});
            Object.defineProperty(document, 'visibilityState', {get: () => 'visible'});
            return 'spoofed';
        })()
        """
        r = await self.cmd('eval', code=js)
        print(f"🛡️  spoof_navigator: {r.get('result', '?')}")

    async def set_random_ua(self):
        """通过 eval 覆盖 userAgent（部分站点会读 JS 侧 UA）"""
        ua = random.choice(_UA_POOL)
        js = f"""
        Object.defineProperty(navigator, 'userAgent', {{get: () => '{ua}'}});
        navigator.userAgent
        """
        await self.cmd('eval', code=js)
        print(f"🛡️  UA 已设置: {ua[:60]}...")

    async def set_random_referer(self):
        """通过 eval 伪造 document.referrer"""
        ref = random.choice(_REFERER_POOL)
        if ref:
            js = f"""
            Object.defineProperty(document, 'referrer', {{get: () => '{ref}'}});
            document.referrer
            """
            await self.cmd('eval', code=js)
            print(f"🛡️  Referer 已设置: {ref}")

    # ── 打字模拟 ─────────────────────────────────────────────────────────────

    async def human_type(self, selector, text):
        """逐字符输入，带随机停顿，模拟真实打字节奏"""
        print(f"⌨️  human_type: '{text[:20]}...' ({len(text)} chars)")
        # 先点击输入框
        await self.bezier_mouse_move()
        await self.cmd('click', selector=selector)
        await asyncio.sleep(random.uniform(0.3, 0.8))

        for char in text:
            await self.cmd('type', selector=selector, text=char)
            # 打字间隔：正态分布，偶尔停顿（模拟思考）
            delay = random.gauss(0.08, 0.04)
            delay = max(0.03, min(delay, 0.3))
            if random.random() < 0.05:  # 5% 概率长停顿
                delay += random.uniform(0.3, 1.0)
            await asyncio.sleep(delay)

    # ── 组合序列 ─────────────────────────────────────────────────────────────

    async def after_page_load(self):
        """页面加载后的完整反爬序列"""
        print("🛡️  after_page_load 反爬序列开始")
        await self.spoof_navigator()
        await self.set_random_ua()
        await self.set_random_referer()
        await self.human_delay(2, 5)
        await self.random_scroll(random.randint(2, 3))
        await self.bezier_mouse_move()
        await self.click_blank()
        await self.human_delay(1, 3)
        print("✅ after_page_load 完成")

    async def before_click(self):
        """点击前的自然行为"""
        await self.bezier_mouse_move(steps=random.randint(6, 15))
        await self.micro_pause()
        await self.human_delay(0.4, 1.2)
