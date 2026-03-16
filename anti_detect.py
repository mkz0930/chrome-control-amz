"""
anti_detect.py - 反爬行为模拟工具
用于 chrome-control-amz，模拟真实用户行为，降低被封风险。
"""
import asyncio
import random


class AntiDetect:
    def __init__(self, cmd_fn):
        self.cmd = cmd_fn

    async def human_delay(self, min_s=1.5, max_s=4.0):
        t = random.uniform(min_s, max_s)
        print(f"⏳ human_delay: {t:.1f}s")
        await asyncio.sleep(t)

    async def long_delay(self, min_s=8, max_s=20):
        t = random.uniform(min_s, max_s)
        print(f"⏳ long_delay: {t:.1f}s")
        await asyncio.sleep(t)

    async def random_scroll(self, times=None):
        n = times or random.randint(2, 4)
        print(f"🖱️  random_scroll: {n} 次")
        for i in range(n):
            direction = 1 if random.random() > 0.2 else -1
            distance = random.randint(200, 600) * direction
            await self.cmd('scroll', y=distance)
            await asyncio.sleep(random.uniform(0.8, 2.0))

    async def click_blank(self):
        x = random.randint(50, 300)
        y = random.randint(100, 400)
        print(f"🖱️  click_blank: ({x}, {y})")
        await self.cmd('click_xy', x=x, y=y)
        await asyncio.sleep(random.uniform(0.5, 1.5))

    async def simulate_mouse_move(self, steps=5):
        print(f"🖱️  simulate_mouse_move: {steps} 步")
        js = """
        (function() {
            let x = Math.floor(Math.random() * 800) + 100;
            let y = Math.floor(Math.random() * 400) + 100;
            for (let i = 0; i < %d; i++) {
                x += Math.floor(Math.random() * 60) - 30;
                y += Math.floor(Math.random() * 40) - 20;
                document.dispatchEvent(new MouseEvent('mousemove', {
                    clientX: Math.max(0, x), clientY: Math.max(0, y), bubbles: true
                }));
            }
            return {x, y};
        })()
        """ % steps
        await self.cmd('eval', code=js)
        await asyncio.sleep(random.uniform(0.3, 0.8))

    async def after_page_load(self):
        print("🛡️  after_page_load 反爬序列开始")
        await self.human_delay(2, 5)
        await self.random_scroll(random.randint(2, 3))
        await self.simulate_mouse_move(steps=random.randint(4, 8))
        await self.click_blank()
        await self.human_delay(1, 3)
        print("✅ after_page_load 完成")

    async def before_click(self):
        await self.simulate_mouse_move(steps=random.randint(3, 6))
        await self.human_delay(0.5, 1.5)

    async def spoof_navigator(self):
        js = """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        'ok'
        """
        await self.cmd('eval', code=js)
