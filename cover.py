#!/usr/bin/env python3
"""生成公众号封面图：一张 2.35:1 的图，左侧正方形色块单独当 1:1 小图也成立。

公众号同一张封面有两种裁剪：信息流大图 2.35:1，转发卡片和列表小图 1:1。
左侧色块放最该强调的关键词（--main，最大号，可分几行）和一行补充（--sub），
小图只裁这一块；大图在右侧补完整标题。

只放大号粗体字，不画小标签、细线和细字：微信会把封面缩小并按固定参数重新压缩，
手机上封面只显示一小块，小字和细线最先糊掉。

用法:
    python3 cover.py 封面.jpg --main 低成本 --main 出国 --sub "32 种方式" \\
        --title "普通人低成本出国的" --title "32 种方式"

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
    # 主关键词：所有行同一字号，按最长一行的实际像素宽撑满色块宽度的 78%。
    # 按字数算会把英文当成和汉字一样宽，"Apple ID" 这类词就被缩得很小。
    widest = max(font(100).getlength(t) for t in a.main) / 100
    size = int(SQ * 0.78 / widest)
    # 行数多时高度也不能超出色块（留出补充文字的位置）
    size = min(320, size, int(SQ * 0.8 / (1.12 * len(a.main) + (0.75 if a.sub else 0))))
    main_f, sub_f = font(size), font(int(size * 0.55))
    line_h = int(size * 1.12)
    sub_h = int(size * 0.55 * 1.2) if a.sub else 0
    gap = int(size * 0.25) if a.sub else 0
    block = line_h * len(a.main) + gap + sub_h
    y = (SQ - block) / 2
    for t in a.main:
        center_text(d, cx, y, t, main_f, "#FFFFFF")
        y += line_h
    if a.sub:
        center_text(d, cx, y + gap, a.sub, sub_f, "#FFFFFF")

    # 右：完整标题（只在大图里出现），所有行同一字号，撑满右侧可用宽度，上下居中
    x = SQ + 110
    avail = W - x - 110
    widest = max(font(100).getlength(t) for t in a.title) / 100
    tsize = int(min(180, avail / widest, H * 0.7 / (1.3 * len(a.title))))
    tf = font(tsize)
    th = int(tsize * 1.3)
    y = (H - th * len(a.title)) / 2
    for line in a.title:
        d.text((x, y), line, font=tf, fill=a.ink)
        y += th

    img.save(a.out, quality=95)
    print(f"cover_crop_235: 0,0,1,1")
    print(f"cover_crop_11: 0,0,{SQ / W:.4f},1")


if __name__ == "__main__":
    main()
