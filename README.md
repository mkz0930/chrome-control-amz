# Chrome Control - Amazon Edition

[EN](README.md) | [中文](README-zh.md)

Combined Chrome Extension Control Skill for Amazon - Merge of chrome-relay-browser-control & chrome-open-tab-skill.

## ✨ Features

- ✅ **Full Automation Mode** - No manual attach required. Python scripts click seller sprite & export data automatically.
- ✅ **Auto-Click Seller Sprite** - Automatic click on "卖家精灵" button on Amazon pages
- ✅ **Auto-Select All Products** - Automatic click on "全选" button after sprite injection
- ✅ **Auto-Export Data** - Automatic export of seller sprite table data
- ✅ Full Chrome extension relay control
- ✅ Python WebSocket automation
- ✅ Click seller sprite & extract data
- ✅ One-click install + auto-detection
- ✅ **Verified**: Seller sprite click + full export flow works end-to-end (2026-03-13 **latest: complete export flow**)

## 📋 Files

| File | Description |
|------|-------------|
| `extension/` | Chrome extension source (background.js, manifest.json) |
| `server/` | WebSocket relay server (Python 3.10+) |
| `click_seajin.py` | Click seller sprite button |
| `grab_amazon.py` | Full Amazon data extraction (with auto-click flow) |
| `simple_test.py` | Quick connection test |
| `full_flow.py` | Complete flow: open → search → click sprite → full → export → get_html |
| `install.sh` | One-click installation script (auto-starts server) |
| `.alias.sh` | Quick commands: `relay-test`, `relay-status`, `relay-log` |
| `README-zh.md` | 中文版本 |

## 🚀 Quick Start

```bash
./install.sh
source .alias.sh
relay-test
```

Then run `full_flow.py` or `grab_amazon.py` - **100% automated!**

## 📚 Documentation

- [SKILL.md](SKILL.md) - Complete skill documentation
- [GitHub](https://github.com/mkz0930/chrome-control-amz)

## 📝 Author

- Horse (mkz0930@gmail.com)
- Date: 2026-03-13
- **Last Updated**: 2026-03-13 16:42 (Added full export flow + Python script + Excel parsing)
