#!/usr/bin/env python3
"""检查公众号文稿的 AI 味：报幕句、加粗密度、分类名小标题、泄气话。

用法：
    python3 check.py 文章.push.md

只做提示，不改文件。退出码 1 表示有命中项。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# 报幕句：删掉它，后面的句子照样成立。
ANNOUNCERS = [
    "一句话说清",
    "一句话总结",
    "一句话概括",
    "先把话说在前面",
    "话说在前面",
    "说实话",
    "老实说",
    "不感兴趣可以跳过",
    "不感兴趣的可以跳过",
    "完全不好看的地方",
    "意义在于",
    "换句话说",
    "我自己的感受是",
    "接下来我们",
    "下面我们来",
    "让我们一起",
    "值得注意的是",
    "需要指出的是",
    "需要注意的是",
    "总而言之",
    "综上所述",
    "总的来说",
    "希望本文",
    "希望对你有所帮助",
    "希望能帮到你",
    "带你了解",
    "带你看懂",
    "带你入门",
    "深入浅出",
    "干货满满",
    "划重点",
    "首先要说的是",
    "一句话",
    "先说",
    "先看",
    "一张表看懂",
    "下面来看",
    "简单来说",
]

# 泄气话：把事情说死，改成事实 + 下一步。
DEFEATIST = [
    "也不打算",
    "暂时也不打算",
    "过不了这一关",
    "基本过不了",
    "做不了高频",
    "我知道不体面",
    "就先这样了",
    "没办法",
    "只能这样",
    "凑合",
]

# 跟读者无关的背景。
IRRELEVANT = [
    "黑客松",
    "hackathon",
    "评委",
    "参赛",
    "提交历史",
    "赛道",
]

# 分类名小标题：写给作者的大纲，不是写给读者的。
CATEGORY_HEADINGS = [
    "里面有什么",
    "功能介绍",
    "技术实现",
    "产品介绍",
    "背景介绍",
    "一些实话",
    "总结",
    "写在最后",
    "结语",
    "前言",
    "概述",
    "怎么试",
    "使用方法",
]

BOLD_MAX_PER_1000 = 2.0

# front matter 里的署名固定值。
AUTHOR = "AI 零边际"


def strip_front_matter(text: str) -> tuple[str, str]:
    """返回 (front matter, 正文)。没有 front matter 时第一项为空串。"""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    return text[: end + 4], text[end + 4 :]


def cjk_len(body: str) -> int:
    """粗略字数：去掉图片、链接和标记符号后数字符。"""
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[#*`>\-\s]", "", t)
    return len(t)


def find_lines(body: str, needle: str) -> list[tuple[int, str]]:
    hits = []
    for i, line in enumerate(body.split("\n"), 1):
        if needle in line:
            hits.append((i, line.strip()))
    return hits


def phrase_hits(text: str, phrases: list[str]) -> list[str]:
    """每行只报第一个命中的短语，避免「一句话」和「一句话说清」重复计数。"""
    seen = set()
    out = []
    for p in phrases:
        for n, line in find_lines(text, p):
            if n not in seen:
                seen.add(n)
                out.append(f"第 {n} 行「{p}」：{line[:60]}")
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    path = Path(argv[1])
    if not path.is_file():
        print(f"读不到文件：{path}")
        return 2

    text = path.read_text(encoding="utf-8")
    front, body = strip_front_matter(text)
    # front matter 里的 title/digest 也要查报幕句
    checked = front + body

    problems = 0

    author = re.search(r"^author:\s*(.+?)\s*$", front, re.M)
    if not author:
        problems += 1
        print(f"\n署名\n  front matter 缺 author，应为「{AUTHOR}」")
    elif author.group(1) != AUTHOR:
        problems += 1
        print(f"\n署名\n  现在是「{author.group(1)}」，应为「{AUTHOR}」")

    def section(title: str, hits: list[str]) -> None:
        nonlocal problems
        if hits:
            problems += len(hits)
            print(f"\n{title}（{len(hits)}）")
            for h in hits:
                print(f"  {h}")

    section(
        "报幕句 —— 删掉它，句子照样成立",
        phrase_hits(checked, ANNOUNCERS),
    )

    section(
        "泄气话 —— 改成事实 + 下一步",
        [
            f"第 {n} 行「{p}」：{line[:60]}"
            for p in DEFEATIST
            for n, line in find_lines(checked, p)
        ],
    )

    section(
        "跟读者无关的背景",
        [
            f"第 {n} 行「{p}」：{line[:60]}"
            for p in IRRELEVANT
            for n, line in find_lines(checked, p)
        ],
    )

    heading_hits = []
    # 行号按整个文件算，和上面几项对得上
    for n, line in enumerate(body.split("\n"), front.count("\n") + 1):
        s = line.strip()
        if not s.startswith("#"):
            continue
        name = s.lstrip("#").strip()
        for cat in CATEGORY_HEADINGS:
            if name == cat or name.startswith(cat):
                heading_hits.append(f"第 {n} 行：{name} —— 换成具体的事")
                break
    section("分类名小标题 —— 写给作者的大纲，不是写给读者的", heading_hits)

    bold = len(re.findall(r"\*\*[^*\n]+\*\*", body))
    words = cjk_len(body)
    per_1000 = bold / words * 1000 if words else 0
    print(f"\n加粗 {bold} 处 / 正文约 {words} 字（每千字 {per_1000:.1f} 处）")
    if per_1000 > BOLD_MAX_PER_1000:
        problems += 1
        print(f"  偏多。每千字控制在 {BOLD_MAX_PER_1000:.0f} 处以内，留给真正要记住的那一句。")

    paras = [p for p in body.split("\n\n") if p.strip() and not p.strip().startswith(("#", "!", "|", ">"))]
    long_paras = [p for p in paras if cjk_len(p) > 180]
    if long_paras:
        print(f"\n偏长的段落（{len(long_paras)}）—— 一段只讲一件事")
        for p in long_paras[:5]:
            print(f"  {p.strip()[:50]}…（{cjk_len(p)} 字）")

    if problems:
        print(f"\n共 {problems} 处可改。脚本只做提示，最后自己念一遍。")
        return 1

    print("\n没查出明显的 AI 味。最后还是自己念一遍。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
