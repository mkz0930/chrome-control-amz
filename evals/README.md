# chrome-relay-browser-control evals

## Evals (evals.json)

| ID | Name | Description | Assertions |
|----|------|-------------|------------|
| `simple-navigate` | 导航到指定 URL | 验证页面加载成功，无 404/超时 | 无 404、无超时、包含 Amazon |
| `search-action` | 执行搜索操作 | 验证搜索关键词提交，结果页显示 | URL 包含关键词、有搜索结果 |
| `seller-sprite-integration` | 卖家精灵数据抓取 | 验证卖家精灵激活，DOM 数据可读 | 扩展激活、DOM 文本可读、提取产品数据 |

## Assertions (`assertions.py`)

运行方式：
```bash
python assertions.py --eval-id simple-navigate --output-dir <path>
```

每个 eval 对应一个 `check_<eval_id>()` 函数，检查 `outputs_dir/logs.txt`：
- `404` 是否存在
- `timeout` 是否存在
- `amazon` 是否存在（验证页面类型）

## Run Tests

```bash
cd chrome-relay-browser-control/evals
python run_tests.py
```

**前置条件**：
1. WebSocket server 正在运行 (`ss -tlnp | grep :19000`)
2. Chrome 插件已附加标签页（图标绿 ✅）

## Next Steps (Anthropics Workflow)

1. **Spawn with-skill + baseline** subagents (same turn, parallel)
2. **Prepare** eval metadata (assertions already in)
3. **While runs in progress**, draft/validate assertions
4. **Capture timing** from task notifications (`duration_ms`, `total_tokens`)
5. **Grade** by running `assertions.py` on each run output
6. **Aggregate** into benchmark (pass rate, time, tokens)
7. **Launch viewer** with `eval-viewer/generate_review.py`
8. **Human review** → `feedback.json` → iterate

## Observations (from past runs)

- ❌ `PortInUseError`: 使用 Python WebSocket 命令绕过
- ❌ `cdpHttp: false`: Windows 插件需点击「附加当前标签页」
- ❌ `navigate timeout`: 亚马逊加载慢，可增加 timeout 或用 `page_loaded: false`

---

## Example Output Structure

```
eval-0-simple-navigate/
├── with_skill/
│   ├── response.json
│   ├── logs.txt
│   └── timing.json (total_tokens, duration_ms)
├── without_skill/
│   ├── response.json
│   └── logs.txt
├── eval_metadata.json
└── grading.json (from assertions.py)
```
