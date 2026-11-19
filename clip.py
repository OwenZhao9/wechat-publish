#!/usr/bin/env python3
"""把 .push.md 排版成公众号正文 HTML，放进系统剪贴板（HTML 格式）。

用法：python3 clip.py <文章.push.md>

之后在公众号后台编辑器的正文区点一下，按 cmd+V 粘贴，排版和 push.py 推送的一样。
正文里的本地图片粘贴不进去，打印出的图片清单要在编辑器里用「图片 → 本地上传」逐张插到对应位置。
"""
import importlib.util
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

SWIFT = r'''
import AppKit
let html = try! String(contentsOfFile: CommandLine.arguments[1], encoding: .utf8)
let pb = NSPasteboard.general
pb.clearContents()
pb.setString(html, forType: .html)
pb.setString("正文", forType: .string)
'''


def main():
    if len(sys.argv) != 2:
        sys.exit("用法：python3 clip.py <文章.push.md>")
    spec = importlib.util.spec_from_file_location("push", os.path.join(HERE, "push.py"))
    push = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(push)

    art, content = push.build_article(sys.argv[1], None, True)
    with tempfile.TemporaryDirectory() as d:
        html_path = os.path.join(d, "body.html")
        swift_path = os.path.join(d, "pb.swift")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
        with open(swift_path, "w", encoding="utf-8") as f:
            f.write(SWIFT)
        subprocess.run(["swift", swift_path, html_path], check=True)

    print(f"✓ 已复制正文 HTML 到剪贴板：{art['title']}")
    print(f"  作者：{art['author']}")
    print(f"  摘要：{art['digest']}")
    images = [l for l in content.split('"') if l.startswith("file://")]
    if images:
        print("  正文本地图片（需在编辑器里手动插入）：")
        for p in images:
            print("   -", p[len("file://"):])


if __name__ == "__main__":
    main()
