# Chrome Control - 亚马逊版

[EN](README.md) | [中文](README-zh.md)

合并版 Chrome 扩展控制技能 - 整合 chrome-relay-browser-control + chrome-open-tab-skill。

## ✨ 功能

- ✅ 完整的 Chrome 扩展中继控制
- ✅ Python WebSocket 自动化
- ✅ 点击卖家精灵并提取数据
- ✅ 一键安装 + 自动检测

## 📋 文件

| 文件 | 说明 |
|------|------|
| `extension/` | Chrome 扩展源码 (background.js, manifest.json) |
| `server/` | WebSocket 中继服务器 (Python 3.10+) |
| `click_seajin.py` | 点击卖家精灵按钮 |
| `grab_amazon.py` | 完整亚马逊数据提取 |
| `simple_test.py` | 快速连接测试 |
| `install.sh` | 一键安装脚本 |

## 🚀 快速开始

```bash
./install.sh
source .alias.sh
relay-test
```

## 📚 文档

- [SKILL.md](SKILL.md) - 完整技能文档
- [GitHub](https://github.com/mkz0930/chrome-control-amz)

## 📝 作者

- Horse (mkz0930@gmail.com)
- 日期: 2026-03-13
