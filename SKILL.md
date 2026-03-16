---
name: chrome-relay-browser-control
description: "控制 Windows Chrome 插件，打开网页、抓取亚马逊卖家精灵数据。支持 click/click_text/type/navigate/get_html 等完整命令。默认端口 19000，插件默认已连接（绿），可直接操作。"

---

## ✅ 核心优势

- ✅ **插件默认已连接**：图标常绿，无需等待，直接发命令
- ✅ **默认端口 19000**：`ws://172.25.0.1:19000`，固定不变
- ✅ **超级反爬机制**：随机 User-Agent、Referer、滚动比例、重试、随机跳过全选
- ✅ **批量关键词导出**：一次运行，处理多个关键词
- ✅ **格式清洗**：自动生成 `CLEAN-US-YYYYMMDD.xlsx`（含超链接、规范化列名）
- ✅ **Bitable CSV**：生成 `-BITABLE-US-YYYYMMDD.csv`（可直接导入飞书多维表格）
- ✅ **自动等待注入**：12 秒等待卖家精灵数据注入（避免提前导出）
- ✅ **Windows Chrome 原生控制**：无需模拟浏览器

---

## 1. 启动 server（Linux）

```bash
cd /home/claw/.openclaw/extensions/openclaw-browser-relay/server
SERVER_PORT=19000 nohup python3 server.py > server-19000.log 2>&1 &
```

**验证：**
```bash
ss -tlnp | grep :19000
# 应有 TCP *:19000 (LISTEN)
```

---

## 2. Windows 插件状态

✅ **插件默认已连接，图标常绿，无需任何操作，直接跑脚本即可。**

**首次安装步骤**（只需一次）：
1. Windows Chrome → `chrome://extensions` → 开发者模式
2. 「加载已解压的扩展程序」→ 选择 `extension/` 目录
3. 打开任意亚马逊页，插件自动附加，图标变绿 ✅

**反爬机制**：
- 随机 User-Agent：Chrome/Mac/Safari/Firefox 四种 UA 随机切换
- 随机 Referer：Amazon/Google/Bing 三种 Referer 随机切换
- 随机等待：3-8 秒（模拟人类行为）
- 随机滚动比例：30%-70%
- 超时重试：失败自动重试 3 次

---

## 3. Python WebSocket 完整命令

```python
import asyncio, websockets, json, time, random

WS_URL = 'ws://172.25.0.1:19000'

async def cmd(action, **kwargs):
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({'type': 'agent', 'version': '1.0.0'}))
        await ws.recv()  # welcome
        rid = str(time.time())
        await ws.send(json.dumps({'action': action, 'request_id': rid, **kwargs}))
        return json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
```

### 命令列表

| 命令 | 参数 | 示例 |
|------|------|------|
| `navigate` | `url` | `cmd('navigate', url='https://amazon.com/s?k=camping')` |
| `click` | `selector` | `cmd('click', selector='.seajin-icon')` |
| `click_text` | `text, exact=False` | `cmd('click_text', text='卖家精灵')` |
| `click_xy` | `x, y` | `cmd('click_xy', x=100, y=200)` |
| `type` | `selector, text` | `cmd('type', selector='input[name=q]', text='camping')` |
| `get_html` | `selector` | `cmd('get_html', selector='div.s-main-slot')` |
| `get_text` | `selector` | `cmd('get_text', selector='body')` |
| `get_url` | - | `cmd('get_url')` |
| `screenshot` | `format='png'` | `cmd('screenshot', format='png')` |
| `eval` | `code` | `cmd('eval', code='document.title')` |
| `status` | - | `cmd('status')` |

---

### 完整示例：打开 + 卖家精灵 + 抓取

```python
import asyncio, random

async def main():
    # 1. 打开亚马逊搜索页（插件默认已连接，直接操作）
    r = await cmd('navigate', url='https://www.amazon.com/s?k=camping')
    print('Opened:', r)
    
    # 2. 等待页面加载
    await asyncio.sleep(random.uniform(4, 7))
    
    # 3. 点击卖家精灵
    r = await cmd('click_text', text='卖家精灵')
    print('Clicked seller sprite:', r)
    
    # 4. 等待数据注入（12 秒）
    await asyncio.sleep(random.uniform(10, 15))
    
    # 5. 抓取 DOM HTML
    r = await cmd('get_html', selector='div.s-main-slot')
    html = r.get('html', '')
    print('HTML length:', len(html))

asyncio.run(main())
```

---

## 4. OpenClaw 工具说明

| OpenClaw 工具 | 是否可用 | 替代方案 |
|---------------|----------|----------|
| `browser(action="open", ...)` | ❌ 报 `PortInUseError` | `cmd('navigate', url=...)` |
| `browser(action="click", ...)` | ❌ 端口冲突 | `cmd('click', selector='...')` |
| `browser(action="snapshot", ...)` | ❌ 端口冲突 | `cmd('get_html', ...)` |

**✅ 统一用 Python WS 命令，不用 OpenClaw browser 工具。**

---

## ⚠️ 常见问题

1. **连接超时**  
   检查 server 是否在跑：`ss -tlnp | grep :19000`  
   重启：`SERVER_PORT=19000 nohup python3 server.py > server-19000.log 2>&1 &`

2. **插件图标不绿**  
   打开任意亚马逊页，插件会自动重连。

3. **导出了错误文件（KeywordHistory-...xlsx）**  
   卖家精灵未完全展开，增加等待时间到 15 秒。

---

## ✅ 完整亚马逊卖家精灵批量导出流程

**目标**：批量处理多个关键词，触发卖家精灵 → 全选 → 导出 Excel

```python
keywords = ['camping', 'light', 'lamp']  # 修改关键词列表

# 每个关键词流程：
# 1. navigate → 2. 等待 4-7s → 3. click_text('卖家精灵') → 
# 4. 等待 10-15s → 5. click_text('全选') → 6. click_text('导出') → 7. 等待 8s
```

完整脚本见：`full_flow.py`

**输出文件格式**：`Search(keyword)-[N]-US-YYYYMMDD.xlsx`

---

## 📠 相关文件

| 文件 | 说明 |
|------|------|
| `server.py` | WebSocket relay server |
| `background.js` | Chrome extension 逻辑 |
| `full_flow.py` | 批量版 + 反爬版（推荐） |
| `grab_amazon.py` | 单关键词抓取 |
| `simple_test.py` | 连接测试 |

---

## 📠 GitHub 仓库

**仓库**: https://github.com/mkz0930/chrome-control-amz

---

## ✅ 作者

- Author: 马振坤 (mkz0930@gmail.com)
- Last Updated: 2026-03-16
- Verified: ✅ 插件默认已连接，端口固定 19000
