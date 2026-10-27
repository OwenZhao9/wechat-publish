#!/usr/bin/env python3
"""生成公众号封面图：一张 2.35:1 的图，左侧正方形色块单独当 1:1 小图也成立。

公众号同一张封面有两种裁剪：信息流大图 2.35:1，转发卡片和列表小图 1:1。
左侧色块放最该强调的关键词（--main，最大号，可分几行）和一行补充（--sub），
小图只裁这一块；大图在右侧补完整标题和标签。

用法:
    python3 cover.py 封面.jpg --main 低成本 --main 出国 --sub "32 种方式" \\
        --title "普通人低成本出国的" --title "32 种方式" \\
        --tags 打工度假 互惠生 工签 半工半读 留学 移民

运行后打印两个裁剪框，写进文章 front matter 的 cover_crop_235 / cover_crop_11。
需要 Pillow 和 macOS 自带的冬青黑体 Hiragino Sans GB。
"""

import argparse

from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"
W, H = 2350, 1000          # 2.35:1，两边都远大于 900×383 / 500×500 的推荐尺寸
SQ = H                     # 左侧正方形边长
ACCENT = "#E8590C"         # 色块：橙
INK = "#1F2329"
MUTED = "#5F6670"
PAPER = "#FFF8F0"


def font(size, bold=True):
    return ImageFont.truetype(FONT, size, index=2 if bold else 0)


def center_text(d, cx, y, text, f, fill):
    w = d.textlength(text, font=f)
    d.text((cx - w / 2, y), text, font=f, fill=fill)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--main", action="append", required=True)
    ap.add_argument("--sub", default="")
    ap.add_argument("--title", action="append", required=True)
    ap.add_argument("--tags", nargs="*", default=[])
    # 配色：文章讲某个品牌时可换成该品牌官网的颜色
    ap.add_argument("--accent", default=ACCENT, help="色块和短横线")
    ap.add_argument("--ink", default=INK, help="右侧标题文字")
    ap.add_argument("--paper", default=PAPER, help="右侧底色")
    a = ap.parse_args()

    img = Image.new("RGB", (W, H), a.paper)
    d = ImageDraw.Draw(img)

    # 左：正方形色块（= 1:1 小图）
    d.rectangle((0, 0, SQ, SQ), fill=a.accent)
    cx = SQ / 2
    # 主关键词：所有行同一字号，按最长一行撑满色块宽度的 78%
    size = min(320, int(SQ * 0.78 / max(len(t) for t in a.main)))
    main_f, sub_f = font(size), font(int(size * 0.42))
    line_h = int(size * 1.12)
    block = line_h * len(a.main) + (int(size * 0.75) if a.sub else 0)
    y = (SQ - block) / 2
    for t in a.main:
        center_text(d, cx, y, t, main_f, "#FFFFFF")
        y += line_h
    if a.sub:
        d.rectangle((cx - 60, y + 10, cx + 60, y + 20), fill="#FFFFFF")
        center_text(d, cx, y + 60, a.sub, sub_f, "#FFFFFF")

    # 右：完整标题 + 标签（只在大图里出现）
    x = SQ + 110
    y = 210
    for line in a.title:
        d.text((x, y), line, font=font(118), fill=a.ink)
        y += 160
    d.rectangle((x, y + 20, x + 120, y + 32), fill=a.accent)
    y += 90
    tf = font(52, bold=False)
    tx = x
    for tag in a.tags:
        tw = d.textlength(tag, font=tf)
        if tx + tw + 60 > W - 80:
            tx = x
            y += 100
        d.rounded_rectangle((tx, y, tx + tw + 52, y + 80), radius=40, outline=MUTED, width=3)
        d.text((tx + 26, y + 10), tag, font=tf, fill=MUTED)
        tx += tw + 52 + 24

    img.save(a.out, quality=92)
    print(f"cover_crop_235: 0,0,1,1")
    print(f"cover_crop_11: 0,0,{SQ / W:.4f},1")


if __name__ == "__main__":
    main()
