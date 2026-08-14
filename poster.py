#!/usr/bin/env python3
"""
ai-poster-generator - AI 海报生成器

输入一个主题（产品/书籍/课程/活动），自动生成：
1. 营销文案（标题/副标题/3个卖点/行动号召）
2. 对应 SVG 海报（多种版式可选）

纯 Python 标准库，零依赖，DeepSeek 驱动。
"""
from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import sys
import urllib.request
from pathlib import Path

API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"

# ─── 版式配置 ────────────────────────────────────────────────────────────────

LAYOUTS = {
    # 竖版 3:4（小红书/朋友圈/抖音封面）
    "portrait": {"width": 1080, "height": 1440, "title_y": 420, "title_size": 88},
    # 横版 16:9（公众号头图/视频封面）
    "landscape": {"width": 1920, "height": 1080, "title_y": 380, "title_size": 120},
    # 方版 1:1（朋友圈/知乎）
    "square": {"width": 1080, "height": 1080, "title_y": 360, "title_size": 96},
}

# 预设配色方案 [背景1, 背景2, 标题色, 副标题色, 强调色, 文字色]
PALETTES = [
    ["#0f172a", "#1e293b", "#f8fafc", "#94a3b8", "#f59e0b", "#cbd5e1"],  # 深夜蓝金
    ["#7c3aed", "#4c1d95", "#ffffff", "#ddd6fe", "#fbbf24", "#ede9fe"],  # 紫金
    ["#0ea5e9", "#0369a1", "#ffffff", "#bae6fd", "#f43f5e", "#e0f2fe"],  # 天空蓝红
    ["#059669", "#065f46", "#ffffff", "#a7f3d0", "#fbbf24", "#d1fae5"],  # 翡翠金
    ["#e11d48", "#9f1239", "#ffffff", "#fecdd3", "#fde047", "#ffe4e6"],  # 玫瑰黄
    ["#1d4ed8", "#1e3a8a", "#ffffff", "#bfdbfe", "#f59e0b", "#dbeafe"],  # 商务蓝金
]


class DeepSeekClient:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or self._load_api_key()
        self.model = model
        if not self.api_key:
            raise RuntimeError("未找到 DEEPSEEK_API_KEY（环境变量或 ~/.dsh/.credentials.yaml）")

    @staticmethod
    def _load_api_key() -> str | None:
        env_key = os.environ.get("DEEPSEEK_API_KEY")
        if env_key:
            return env_key.strip()
        cred = Path.home() / ".dsh" / ".credentials.yaml"
        if cred.exists():
            for line in cred.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("DEEPSEEK_API_KEY:"):
                    return line.split(":", 1)[1].strip()
        return None

    def chat(self, system: str, user: str, max_tokens: int = 3000, temperature: float = 0.8,
             max_retries: int = 5) -> str:
        """调用 DeepSeek API，带空响应重试（模型偶发返回空 content）"""
        last_err: Exception | None = None
        for attempt in range(max_retries):
            body = json.dumps({
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            }).encode("utf-8")
            req = urllib.request.Request(API_URL, data=body, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            })
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                if content and content.strip():
                    return content
                last_err = RuntimeError(f"API 返回空内容（第 {attempt + 1} 次尝试）")
                print(f"  ⚠️ 模型返回空内容，重试中 ({attempt + 1}/{max_retries})...")
            except urllib.error.HTTPError as e:
                last_err = RuntimeError(f"API 错误 {e.code}: {e.read().decode('utf-8', 'replace')}")
                if e.code in (429, 500, 502, 503):
                    print(f"  ⚠️ API {e.code}，重试中 ({attempt + 1}/{max_retries})...")
                else:
                    raise last_err
            except (json.JSONDecodeError, KeyError) as e:
                last_err = RuntimeError(f"API 响应解析失败: {e}")
                print(f"  ⚠️ 响应解析失败，重试中 ({attempt + 1}/{max_retries})...")
            # 指数退避
            if attempt < max_retries - 1:
                import time
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"模型多次返回空响应: {last_err}")


def generate_copy(client: DeepSeekClient, topic: str) -> dict:
    """生成营销文案（结构化 JSON，兼容多种字段命名）"""
    sys_prompt = (
        "你是顶级营销文案策划。根据主题生成海报文案，只输出 JSON，必须包含以下字段：\n"
        '{"title": "主标题（≤14字，有冲击力）",\n'
        ' "subtitle": "副标题（≤20字）",\n'
        ' "points": ["卖点1（≤12字）", "卖点2（≤12字）", "卖点3（≤12字）"],\n'
        ' "cta": "行动号召（≤10字）",\n'
        ' "badge": "角标文字（≤6字）"}\n'
        "要求：卖点要有具体数字或结果承诺，避免空洞形容词。"
    )
    raw = client.chat(sys_prompt, f"海报主题：{topic}", max_tokens=1000, temperature=0.9)
    # 提取 JSON：先剥掉代码围栏，再直接解析，最后用正则兜底
    data: dict | None = None
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", stripped, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                data = None
    if not isinstance(data, dict):
        raise RuntimeError(f"无法解析文案 JSON: {raw[:200]}")

    def pick(*keys: str, default: str = "") -> str:
        for k in keys:
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return default

    # 兼容不同字段命名
    title = pick("title", "headline", "topic", default=topic)[:20]
    subtitle = pick("subtitle", "slogan", "tagline", "description", default="")[:30]

    points_raw = data.get("points") or data.get("features") or data.get("benefits") or []
    if not points_raw and subtitle:
        # 模型只给了 description 时，按标点拆成短句当卖点
        desc = pick("description", "slogan")
        import re as _re
        parts = [p.strip() for p in _re.split(r"[，。；;！]", desc) if p.strip()]
        points_raw = parts if len(parts) >= 2 else [desc]
    points = [str(p)[:16] for p in points_raw[:3]]

    cta = pick("cta", "action", "button", default="立即行动")[:12]
    badge = pick("badge", "tag", "label", default="")[:8]

    return {
        "title": title,
        "subtitle": subtitle,
        "points": points,
        "cta": cta,
        "badge": badge,
    }


def fit_font_size(text: str, max_width: float, base_size: float, min_size: float = 24) -> float:
    """根据文本长度动态调整字号，避免溢出（中文按方块字估算宽度）"""
    if not text:
        return base_size
    # 中文/全角字符占 1 个字符宽，ASCII 约 0.55
    est_width = sum(1.0 if ord(c) > 0x2E80 else 0.55 for c in text)
    needed = est_width * base_size
    if needed <= max_width:
        return base_size
    return max(min_size, int(max_width / est_width))


def render_svg(copy: dict, layout: str, palette_idx: int, topic: str) -> str:
    """用模板渲染 SVG 海报"""
    W = LAYOUTS[layout]["width"]
    H = LAYOUTS[layout]["height"]
    title_size = LAYOUTS[layout]["title_size"]
    palette = PALETTES[palette_idx % len(PALETTES)]
    bg1, bg2, title_c, sub_c, accent_c, text_c = palette

    # 可用宽度（左右边距 140）
    avail_w = W - 280

    # 动态字号：标题 / 副标题 / 卖点
    title_size = int(fit_font_size(copy["title"], avail_w, title_size))
    sub_size = int(fit_font_size(copy["subtitle"], avail_w, 50, min_size=30))
    point_size = int(fit_font_size(max(copy["points"], key=len, default=""), avail_w - 100, 52, min_size=26))
    topic_size = int(fit_font_size(topic, avail_w, 44, min_size=28))

    e = html.escape
    # 装饰圆
    r1, r2, r3 = W * 0.55, W * 0.35, W * 0.18
    x1, y1 = W * 0.9, H * 0.1
    x2, y2 = W * 0.05, H * 0.85
    x3, y3 = W * 0.75, H * 1.05

    points_svg = ""
    for i, p in enumerate(copy["points"]):
        y = 560 + i * 110
        points_svg += f'''
      <circle cx="140" cy="{y}" r="10" fill="{accent_c}"/>
      <text x="180" y="{y + 10}" font-size="{point_size}" fill="{text_c}" font-family="'PingFang SC','Microsoft YaHei',sans-serif" font-weight="500">{e(p)}</text>'''

    badge_svg = ""
    if copy["badge"]:
        badge_svg = f'''
      <rect x="{W - 340}" y="70" width="280" height="90" rx="45" fill="{accent_c}"/>
      <text x="{W - 200}" y="130" font-size="40" fill="#ffffff" text-anchor="middle" font-family="'PingFang SC','Microsoft YaHei',sans-serif" font-weight="700">{e(copy["badge"])}</text>'''

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg1}"/>
      <stop offset="100%" stop-color="{bg2}"/>
    </linearGradient>
    <linearGradient id="titleGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{accent_c}"/>
      <stop offset="100%" stop-color="{title_c}"/>
    </linearGradient>
  </defs>

  <!-- 背景 -->
  <rect width="{W}" height="{H}" fill="url(#bg)"/>

  <!-- 装饰圆 -->
  <circle cx="{x1}" cy="{y1}" r="{r1}" fill="#ffffff" opacity="0.04"/>
  <circle cx="{x2}" cy="{y2}" r="{r2}" fill="#ffffff" opacity="0.05"/>
  <circle cx="{x3}" cy="{y3}" r="{r3}" fill="#ffffff" opacity="0.03"/>
  {badge_svg}
  <!-- 主题 -->
  <text x="140" y="180" font-size="{topic_size}" fill="{sub_c}" font-family="'PingFang SC','Microsoft YaHei',sans-serif" font-weight="600" letter-spacing="6">{e(topic[:18])}</text>
  <line x1="140" y1="215" x2="420" y2="215" stroke="{accent_c}" stroke-width="6" stroke-linecap="round"/>

  <!-- 主标题 -->
  <text x="140" y="{LAYOUTS[layout]['title_y']}" font-size="{title_size}" fill="url(#titleGrad)" font-family="'PingFang SC','Microsoft YaHei',sans-serif" font-weight="900">{e(copy["title"])}</text>

  <!-- 副标题 -->
  <text x="140" y="{LAYOUTS[layout]['title_y'] + 90}" font-size="{sub_size}" fill="{sub_c}" font-family="'PingFang SC','Microsoft YaHei',sans-serif" font-weight="400">{e(copy["subtitle"])}</text>

  <!-- 分隔线 -->
  <line x1="140" y1="{LAYOUTS[layout]['title_y'] + 160}" x2="{W - 140}" y2="{LAYOUTS[layout]['title_y'] + 160}" stroke="#ffffff" stroke-opacity="0.15" stroke-width="3"/>

  <!-- 卖点 -->
  {points_svg}

  <!-- CTA 按钮 -->
  <rect x="140" y="{H - 260}" width="420" height="120" rx="60" fill="{accent_c}"/>
  <text x="350" y="{H - 178}" font-size="52" fill="#ffffff" text-anchor="middle" font-family="'PingFang SC','Microsoft YaHei',sans-serif" font-weight="700">{e(copy["cta"])}</text>

  <!-- 底部水印 -->
  <text x="{W - 140}" y="{H - 80}" font-size="30" fill="{text_c}" opacity="0.5" text-anchor="end" font-family="'PingFang SC','Microsoft YaHei',sans-serif">AI 生成</text>
</svg>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 海报生成器")
    parser.add_argument("topic", help="海报主题（产品/书籍/课程/活动）")
    parser.add_argument("--layout", choices=list(LAYOUTS.keys()), default="portrait",
                        help="版式：portrait竖版3:4 / landscape横版16:9 / square方版1:1（默认 portrait）")
    parser.add_argument("--palette", type=int, default=-1, help="配色方案索引 0-5（默认随机）")
    parser.add_argument("--out", default="poster.svg", help="输出文件（默认 poster.svg）")
    parser.add_argument("--copy-only", action="store_true", help="只生成文案不生成海报")
    args = parser.parse_args()

    try:
        client = DeepSeekClient()
        print("=" * 56)
        print("  ai-poster-generator | AI 海报生成器")
        print("=" * 56)

        print(f"\n[1/2] 为「{args.topic}」生成营销文案...")
        copy = generate_copy(client, args.topic)
        print(f"  📌 标题: {copy['title']}")
        print(f"  📄 副标题: {copy['subtitle']}")
        for i, p in enumerate(copy["points"], 1):
            print(f"  ✨ 卖点{i}: {p}")
        print(f"  🎯 CTA: {copy['cta']}" + (f"  |  🏷️ 角标: {copy['badge']}" if copy["badge"] else ""))

        if args.copy_only:
            print("\n✅ 文案生成完成（--copy-only）")
            return 0

        palette_idx = args.palette if args.palette >= 0 else random.randrange(len(PALETTES))
        print(f"\n[2/2] 渲染 {args.layout} 版式海报（配色方案 #{palette_idx}）...")
        svg = render_svg(copy, args.layout, palette_idx, args.topic)

        out_path = Path(args.out)
        out_path.write_text(svg, encoding="utf-8")
        print(f"\n✅ 海报已保存: {out_path.resolve()}")
        print(f"   （SVG 可直接用浏览器打开，或用 cairosvg/inkscape 转 PNG）")
        return 0
    except RuntimeError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
