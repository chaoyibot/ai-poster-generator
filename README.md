# ai-poster-generator

> AI 海报生成器 — 输入主题，自动生成营销文案 + SVG 海报
> Turn any topic into a marketing poster with AI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-4D6BFE.svg)](https://platform.deepseek.com/)

一句话主题 → **营销文案**（标题/副标题/卖点/行动号召）→ **成品海报**（SVG）。
纯 Python 标准库，零依赖，不调图像生成 API（省成本），DeepSeek 驱动。

---

## ✨ 功能特性

- 🎯 **AI 文案** — 标题/副标题/3 个卖点/CTA/角标，带具体数字和结果承诺
- 🎨 **三种版式** — 竖版 3:4（小红书/朋友圈）、横版 16:9（公众号头图）、方版 1:1
- 🌈 **6 套配色** — 深夜蓝金 / 紫金 / 天空蓝红 / 翡翠金 / 玫瑰黄 / 商务蓝金
- 📐 **自动防溢出** — 长文本自动缩字号，任何标题都不会超出画布
- 🧩 **零依赖** — 纯标准库，Python 3.10+ 直接跑
- 🔄 **自动重试** — 模型偶发空响应自动重试（指数退避）

## 📦 安装

```bash
git clone https://github.com/chaoyibot/ai-poster-generator.git
cd ai-poster-generator
```

**配置 API Key**（DeepSeek）：

```bash
export DEEPSEEK_API_KEY="sk-xxxx"
# 或写入 ~/.dsh/.credentials.yaml（dsh 用户）
```

## 🚀 快速开始

```bash
# 竖版海报（默认）
python poster.py "AI短剧脚本生成器：一句话故事自动生成爆款短剧脚本"

# 横版 16:9（公众号头图）
python poster.py "DeepSeek提示词宝典" --layout landscape

# 指定配色 + 输出文件
python poster.py "AI拆书工具" --layout square --palette 4 --out my-poster.svg

# 只要文案不要海报
python poster.py "我的课程" --copy-only
```

### 输出示例

```
一句话变爆款短剧            ← 主标题
AI秒出剧本，日更不愁         ← 副标题
● 3秒生成完整剧本           ← 卖点
● 爆款率提升80%
● 单日产出100+脚本
[立即免费试用]              ← CTA
```

生成的 SVG 用浏览器直接打开，或用 `cairosvg` / Inkscape 转 PNG：

```bash
pip install cairosvg
python -c "import cairosvg; cairosvg.svg2png(url='poster.svg', write_to='poster.png', scale=2)"
```

## ⚙️ 工作原理

```
[主题] → DeepSeek 生成结构化文案 JSON → 本地模板渲染 SVG 海报
```

- **模型**：`deepseek-v4-flash`（低成本高速）
- **成本**：一张海报约 1K tokens ≈ ¥0.002
- **为什么不直接让 AI 画图**：图像生成 API 贵且不可控，SVG 模板 + AI 文案质量稳定、零成本、可改样式

## 💡 适用场景

- 自媒体：公众号头图、小红书封面、朋友圈海报
- 知识付费：课程/训练营招生海报
- 电商：产品促销图、活动海报
- 内容创作者：给每篇文章配专属封面

## 🤝 支持与打赏

如果这个工具帮到了你，欢迎支持：

<p align="center">
  <a href="https://www.ifdian.net/a/dg1688">
    <img src="https://pic1.afdiancdn.com/static/img/welcome/button-sponsorme.png" width="200" alt="爱发电赞助我"/>
  </a>
</p>

- ☕ **爱发电**: https://www.ifdian.net/a/dg1688
- ⭐ **Star 就是最大的鼓励！**

## 📄 License

[MIT](LICENSE) © 2026 ai-poster-generator contributors
