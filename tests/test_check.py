import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import check


def run_check(text):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "article.push.md"
        path.write_text(text, encoding="utf-8")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = check.main(["check.py", str(path)])
        return code, buffer.getvalue()


class CheckTests(unittest.TestCase):
    def test_flags_announcers_headings_bold_and_author(self):
        code, out = run_check(
            "---\ntitle: 测试\n---\n\n"
            "## 先看总表：每种方式一句话\n\n"
            "一句话说清它是什么：一个工具。**甲** **乙** **丙**\n\n"
            "## 写在最后\n\n结束。\n"
        )

        self.assertEqual(code, 1)
        self.assertIn("缺 author", out)
        self.assertIn("第 5 行「", out)
        self.assertIn("第 9 行：写在最后", out)
        self.assertIn("偏多", out)
        # 同一行同时含「一句话」「一句话说清」，只报一次
        self.assertEqual(out.count("第 7 行"), 1)

    def test_clean_article_passes(self):
        code, out = run_check(
            "---\ntitle: 测试\nauthor: AI 零边际\n---\n\n"
            "## 刷脸就能开户\n\n" + "这是一段正常的正文。" * 30 + "\n"
        )

        self.assertEqual(code, 0)
        self.assertIn("没查出明显的 AI 味", out)


if __name__ == "__main__":
    unittest.main()
