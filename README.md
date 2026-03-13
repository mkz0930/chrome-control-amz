# Chrome Control - Amazon Edition

[EN](README.md) | [中文](README-zh.md)

Combined Chrome Extension Control Skill for Amazon - Merge of chrome-relay-browser-control & chrome-open-tab-skill.

## ✨ Features

- ✅ Full Chrome extension relay control
- ✅ Python WebSocket automation
- ✅ Click seller sprite & extract data
- ✅ One-click install + auto-detection

## 📋 Files

| File | Description |
|------|-------------|
| `extension/` | Chrome extension source (background.js, manifest.json) |
| `server/` | WebSocket relay server (Python 3.10+) |
| `click_seajin.py` | Click seller sprite button |
| `grab_amazon.py` | Full Amazon data extraction |
| `simple_test.py` | Quick connection test |
| `install.sh` | One-click installation script |

## 🚀 Quick Start

```bash
./install.sh
source .alias.sh
relay-test
```

## 📚 Documentation

- [SKILL.md](SKILL.md) - Complete skill documentation
- [GitHub](https://github.com/mkz0930/chrome-control-amz)

## 📝 Author

- Horse (mkz0930@gmail.com)
- Date: 2026-03-13
