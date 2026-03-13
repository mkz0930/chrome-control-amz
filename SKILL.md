---
name: chrome-relay-browser-control
description: "控制 Windows Chrome 插件，打开网页、抓取亚马逊卖家精灵数据。支持 click/click_text/type/navigate/get_html 等完整命令。绕过 PortInUseError，用 Python WebSocket 命令。"
---

## ✅ 核心优势

- **完全兼容 OpenClaw 工具**：支持 `click`, `click_text`, `type`, `navigate`, `get_html`, `screenshot` 等命令
- **端口灵活配置**：`SERVER_PORT=19000` 或 `18792`（避免冲突）
- **自动保活监控**：`start-server.sh` + `monitor.sh`
- **Windows Chrome 原生控制**：无需模拟浏览器
- ✅ **已验证卖家精灵点击成功**（2026-03-13）

---

## 1. 启动 server（Linux）

```bash
cd /home/claw/.openclaw/extensions/openclaw-browser-relay/server

# 方式A：使用 19000 端口（默认）
./start-server.sh

# 方式B：使用 18792 端口（避免与 OpenClaw 工具冲突）
SERVER_PORT=18792 nohup python3 server.py > server-18792.log 2>&1 &
```

**验证：**
```bash
ss -tlnp | grep :19000
# 或
ss -tlnp | grep :18792
```

---

## 2. Windows 插件配置

1. **安装扩展**  
   - 在 Windows Chrome 加载自研扩展（开发者模式 → 加载解压的扩展）

2. **附加标签页**  
   - 打开任意亚马逊页（如 `https://www.amazon.com/s?k=light`）
   - 点击插件图标 → **「附加当前标签页」**
   - 确认图标变 **绿 ✅**（非红/闪烁）

3. **端口确认**  
   插件弹窗应显示：`Connected to 172.25.0.1:19000`

---

## 3. Python WebSocket 完整命令

### 通用发送函数
```python
import asyncio, websockets, json

WS_URL = 'ws://172.25.0.1:19000'  # 或 18792

async def cmd(action, **kwargs):
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        await ws.recv()  # welcome
        rid = str(asyncio.get_event_loop().time())
        await ws.send(json.dumps({'action': action, 'request_id': rid, **kwargs}))
        return json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
```

### 命令列表（完全兼容 OpenClaw）

| 命令 | 参数 | 示例 |
|------|------|------|
| `open` / `navigate` | `url` | `cmd('navigate', url='https://amazon.com/s?k=light')`
| `click` | `selector` | `cmd('click', selector='.seajin-icon')`
| `click_text` | `text, exact=False` | `cmd('click_text', text='卖家精灵')`
| `click_xy` | `x, y` | `cmd('click_xy', x=100, y=200)`
| `type` | `selector, text` | `cmd('type', selector='input[name=q]', text='light')`
| `get_html` | `selector` | `cmd('get_html', selector='div.s-main-slot')`
| `get_text` | `selector` | `cmd('get_text', selector='body')`
| `get_url` | - | `cmd('get_url')`
| `screenshot` | `format='png'` | `cmd('screenshot', format='png')`
| `eval` | `code` | `cmd('eval', code='document.title')`

---

### 完整示例：打开 + 点击 + 抓取

```python
import asyncio

async def main():
    # 1. 打开亚马逊搜索页
    r = await cmd('navigate', url='https://www.amazon.com/s?k=camping')
    print('Opened:', r)
    
    # 2. 等待加载
    await asyncio.sleep(3)
    
    # 3. 点击卖家精灵（按钮）
    r = await cmd('click_text', text='卖家精灵')
    print('Clicked seller sprite:', r)
    
    # 4. 等待注入数据
    await asyncio.sleep(2)
    
    # 5. 抓取 DOM HTML
    r = await cmd('get_html', selector='div.s-main-slot')
    html = r.get('html')
    print('HTML length:', len(html))
    
    # 6. 提取关键数据（示例）
    import re
    asin = re.search(r'/dp/([A-Z0-9]{10})', html)
    price = re.search(r'\$(\d+\.\d{2})', html)
    
    print(f"ASIN: {asin.group(1) if asin else 'N/A'}")
    print(f"Price: ${price.group(1) if price else 'N/A'}")

asyncio.run(main())
```

---

## 4. OpenClaw 工具调用（⚠️ 重要）

| OpenClaw 工具 | 是否可用 | 推荐替代 |
|---------------|----------|----------|
| `browser(action="open", ...)` | ❌ 报 `PortInUseError` | 用 `cmd('navigate', url=...)` |
| `browser(action="click", ...)` | ❌ 端口冲突 | 用 `cmd('click', selector='...')` |
| `browser(action="snapshot", ...)` | ❌ 端口冲突 | 用 `cmd('get_html', ...)` |
| `browser(action="screenshot", ...)` | ❌ 端口冲突 | 用 Windows `Win+Shift+S` 截图 |

**✅ 最佳实践：Python WS 命令 + Windows 截图**

---

## ⚠️ 3 个必须绕过的坑

1. **`PortInUseError`**  
   `browser.*` OpenClaw 工具会报错 → 用 Python WS 命令代替

2. **`cdpHttp: false`**  
   表示插件没附加标签页 → 在 Windows 插件里点击「附加当前标签页」

3. **server 崩了**  
   用 `monitor.sh` 保活，或手动重启

---

## ✅ 验证流程

1. **Linux server 是否运行？**
   ```bash
   ss -tlnp | grep :19000
   # 应有 TCP *:19000 (LISTEN)
   ```

2. **Python 脚本能否连接？**
   ```bash
   python3 test_relay.py
   # 应返回 extension_online: true
   ```

3. **Windows 插件是否 Attach？**
   - 图标绿 ✅（非红/闪烁）
   - 弹窗显示 `Connected to 172.25.0.1:19000`

---

## 📠 相关文件

| 文件 | 说明 |
|------|------|
| `server.py` | WebSocket relay server（支持 `SERVER_PORT`）|
| `background.js` | Chrome extension 逻辑（含 `click`, `click_text`, `type` 等）|
| `start-server.sh` | 启动脚本（nohup + monitor.sh）|
| `test_relay.py` | 直接发送命令的测试脚本|
| `do-amazon.py` | 完整亚马逊抓取示例|

---

## 🌐 GitHub

**注意：本 skill 已合并到 `clawd-workspace` 仓库，原 `openclaw-watchdog-skill-library` 中的版本已弃用。**

- **最新代码**: https://github.com/mkz0930/clawd-workspace/tree/master/skills/chrome-relay-browser-control/
- **旧版（已弃用）**: https://github.com/mkz0930/openclaw-watchdog-skill-library/tree/master/chrome-relay-browser-control

---

## 📚 相关记忆

- `memory_search("chrome relay")` → 查看历史配置
- `skill_get(taskId="ebd04f66-d90f-4f85-83ec-5a440b3c3843")` → 查看完整任务记录

---

## ✅ 作者

- Author: 马振坤
- Email: mkz0930@gmail.com
- Date: 2026-03-13
- **Verified**: ✅ 卖家精灵点击成功（2026-03-13）
- **Last Updated**: 2026-03-13 (Updated with working click_text example + debug log output)
- **Verified**: ✅ 卖家精灵点击成功（2026-03-13）
