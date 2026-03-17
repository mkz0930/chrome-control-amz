---
name: chrome-deal
description: "通过 WebSocket Relay Server 控制 Windows Chrome 浏览器。支持打开网页、点击、输入、滚动、截图、登录、Cookie 管理、标签页管理等完整操作。基于自研 chrome-control-amz 插件。"
---

## 架构

```
Agent (Linux) → ws://127.0.0.1:19000 → Relay Server → ws://172.25.4.135:19000 → Chrome 插件 → Windows Chrome
```

- Relay Server: `/home/claw/.openclaw/extensions/openclaw-browser-relay/server/server.py`
- Chrome 插件: `E:\openclaw\extensions\openclaw-browser-relay\extension\`
- 源码: `/home/claw/git/chrome-control-amz/`

## 前置条件

1. Relay Server 运行中（端口 19000）
2. Chrome 插件已加载并连接（devtools 显示 `✅ connected`）

### 启动 Relay Server

```bash
cd /home/claw/.openclaw/extensions/openclaw-browser-relay/server
SERVER_PORT=19000 nohup python3 server.py > server.log 2>&1 &
echo $! > server.pid
```

### 验证连接

```bash
ss -tlnp | grep 19000
tail -5 server.log  # 应看到 🔌 Extension connected!
```

## 使用方法

### Python 调用

```python
import asyncio, json, websockets, time

async def ws_cmd(action, **kwargs):
    """发送命令到 Chrome 插件"""
    async with websockets.connect("ws://127.0.0.1:19000") as ws:
        await ws.send(json.dumps({"type": "agent", "version": "1.0.0"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
        if not resp.get("extension_online"):
            return {"ok": False, "error": "插件未连接"}
        
        rid = f"{action}-{int(time.time())}"
        timeout = 60 if action in ("screenshot", "navigate") else 30
        await ws.send(json.dumps({"action": action, "request_id": rid, "timeout": timeout, **kwargs}))
        return json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout + 5))
```

## 完整命令列表

### 1. navigate — 打开网页

```python
r = await ws_cmd("navigate", url="https://www.amazon.com/s?k=cup")
# 返回: {"ok": true, "url": "...", "tab_id": 337655143}
```

不传 tabId 时自动使用当前 active tab，没有则创建新 tab。

### 2. screenshot — 截图

```python
r = await ws_cmd("screenshot", format="png")
# 返回: {"ok": true, "data": "data:image/png;base64,..."}
```

### 3. click_text — 按文字点击

```python
r = await ws_cmd("click_text", text="全选", tabId=tab_id)
# 返回: {"ok": true, "tag": "BUTTON"}
```

### 4. click — CSS 选择器点击

```python
r = await ws_cmd("click", selector="#submit-btn", tabId=tab_id)
```

### 5. click_xy — 坐标点击

```python
r = await ws_cmd("click_xy", x=500, y=300, tabId=tab_id)
```

### 6. type — 输入文字

```python
r = await ws_cmd("type", selector="#search-input", text="cup", tabId=tab_id)
```

### 7. scroll — 滚动

```python
# 向下滚动 500px
r = await ws_cmd("scroll", y=500, tabId=tab_id)
# 向上滚动
r = await ws_cmd("scroll", y=-500, tabId=tab_id)
```

### 8. eval — 执行 JavaScript

```python
r = await ws_cmd("eval", code="document.title", tabId=tab_id)
# 返回: {"ok": true, "result": "Amazon.com: cup"}
```

### 9. get_text — 获取页面文本

```python
r = await ws_cmd("get_text", tabId=tab_id)
# 返回: {"ok": true, "text": "..."}
```

### 10. get_html — 获取 HTML

```python
r = await ws_cmd("get_html", selector=".s-result-item", tabId=tab_id)
```

### 11. get_url — 获取当前 URL

```python
r = await ws_cmd("get_url", tabId=tab_id)
# 返回: {"ok": true, "url": "...", "title": "..."}
```

### 12. wait — 等待元素

```python
r = await ws_cmd("wait", selector=".results-loaded", timeout=10000, tabId=tab_id)
```

### 13. get_cookies — 获取 Cookie

```python
r = await ws_cmd("get_cookies", url="https://www.amazon.com")
# 返回: {"ok": true, "cookies": [...]}
```

### 14. set_cookies — 设置 Cookie

```python
r = await ws_cmd("set_cookies", cookies=[{"name": "session", "value": "abc", "url": "https://www.amazon.com"}])
```

### 15. 标签页管理

```python
# 列出所有标签页
r = await ws_cmd("list_tabs")

# 新建标签页
r = await ws_cmd("new_tab", url="https://www.google.com")

# 切换标签页
r = await ws_cmd("switch_tab", tabId=123456)

# 关闭标签页
r = await ws_cmd("close_tab", tabId=123456)
```

### 16. download — 下载文件

```python
r = await ws_cmd("download", url="https://example.com/file.csv")
```

### 17. status — 检查状态

```python
r = await ws_cmd("status")
# 返回: {"ok": true, "connected": true, "url": "..."}
```

## 登录流程示例

```python
async def login_amazon(email, password):
    # 打开登录页
    r = await ws_cmd("navigate", url="https://www.amazon.com/ap/signin")
    tab_id = r["tab_id"]
    
    # 输入邮箱
    await ws_cmd("type", selector="#ap_email", text=email, tabId=tab_id)
    await ws_cmd("click", selector="#continue", tabId=tab_id)
    await asyncio.sleep(2)
    
    # 输入密码
    await ws_cmd("type", selector="#ap_password", text=password, tabId=tab_id)
    await ws_cmd("click", selector="#signInSubmit", tabId=tab_id)
    await asyncio.sleep(3)
    
    # 验证登录
    r = await ws_cmd("get_url", tabId=tab_id)
    return "signin" not in r.get("url", "")
```

## 反爬滚动示例

```python
import random

async def human_scroll(tab_id, pages=3):
    """模拟人类滚动浏览"""
    for i in range(pages):
        # 随机滚动距离
        distance = random.randint(300, 800)
        await ws_cmd("scroll", y=distance, tabId=tab_id)
        # 随机停顿
        await asyncio.sleep(random.uniform(1.0, 3.0))
```

## 关键配置

| 项目 | 值 |
|------|-----|
| Relay Server 端口 | 19000 |
| WSL IP | 172.25.4.135（可能变化，重启后检查） |
| 插件 WS_URL | `ws://172.25.4.135:19000` |
| Agent 连接 | `ws://127.0.0.1:19000` |
| 下载目录 | `/mnt/d/download/` |
| 插件路径 (Windows) | `E:\openclaw\extensions\openclaw-browser-relay\extension\` |
| 源码路径 (Linux) | `/home/claw/git/chrome-control-amz/` |

## 注意事项

- WSL IP 可能在重启后变化，需更新插件的 `WS_URL`（`background.js` 第 8 行）
- navigate 不传 tabId 时会用 active tab 或创建新 tab
- screenshot 截的是当前可见区域
- eval 在页面上下文执行，可访问 DOM
- 所有需要操作页面的命令都需要传 `tabId`（从 navigate 返回值获取）
