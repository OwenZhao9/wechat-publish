#!/usr/bin/env python3
"""生成公众号封面图（2.35:1，1800×766）：深蓝底、黄色竖条、两行标题、一行副标题。

用法:
    python3 cover.py 封面.jpg "第一行标题" "第二行标题" "副标题（可省略）"

需要 Pillow（pip install pillow）和 macOS 自带的冬青黑体 Hiragino Sans GB。
"""

import sys

from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"
W, H = 1800, 766


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    out, line1, line2 = sys.argv[1:4]
    sub = sys.argv[4] if len(sys.argv) > 4 else ""

    img = Image.new("RGB", (W, H), "#0E3B5C")
    d = ImageDraw.Draw(img)
    # 右上角三道弧线做装饰，避开左侧文字区
    for i, color in enumerate(["#1F5A85", "#2C6E9E", "#3D84B8"]):
        r = 520 + i * 150
        d.ellipse((W - r // 2 + 80, -r // 2 - 60, W + r + 80, r - 60), outline=color, width=6)
    d.rectangle((120, 250, 132, 520), fill="#F5C242")
    title = ImageFont.truetype(FONT, 120, index=1)
    small = ImageFont.truetype(FONT, 56, index=0)
    d.text((180, 240), line1, font=title, fill="#FFFFFF")
    d.text((180, 380), line2, font=title, fill="#FFFFFF")
    if sub:
        d.text((184, 560), sub, font=small, fill="#C9DCEB")
    img.save(out, quality=90)
    print(out)


if __name__ == "__main__":
    main()
