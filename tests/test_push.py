import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import push


class PushTests(unittest.TestCase):
    def test_parse_push_md_reads_front_matter(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.push.md"
            path.write_text(
                "---\ntitle: 测试标题\nauthor: 测试作者\n---\n\n正文",
                encoding="utf-8",
            )

            meta, body = push.parse_push_md(str(path))

            self.assertEqual(meta["title"], "测试标题")
            self.assertEqual(meta["author"], "测试作者")
            self.assertEqual(body.strip(), "正文")

    def test_markdown_conversion_handles_links_lists_and_comments(self):
        markdown = """
<!-- 不进入正文 -->
## 小标题

- 第一项
- 第二项

[外链](https://example.com) 与 [公众号内链](https://mp.weixin.qq.com/s/example)
"""

        result, context = push.md_to_html(markdown, ".", ".")

        self.assertIn("<h2", result)
        self.assertIn("<ul", result)
        self.assertNotIn("不进入正文", result)
        self.assertIn("外链<sup", result)
        self.assertIn('href="https://mp.weixin.qq.com/s/example"', result)
        self.assertEqual(context["links"], ["https://example.com"])

    def test_build_article_dry_run_does_not_require_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.push.md"
            path.write_text(
                "---\n"
                "title: 测试标题\n"
                "digest: 测试摘要\n"
                "open_comment: 0\n"
                "fans_only_comment: 1\n"
                "---\n\n"
                "这是一段用于验证草稿结构的正文。",
                encoding="utf-8",
            )

            article, rendered = push.build_article(str(path), token="", dry_run=True)

            self.assertEqual(article["title"], "测试标题")
            self.assertEqual(article["digest"], "测试摘要")
            self.assertEqual(article["need_open_comment"], 0)
            self.assertEqual(article["only_fans_can_comment"], 1)
            self.assertIn("用于验证草稿结构", rendered)

    def test_post_json_uses_private_unique_temp_file_and_removes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(push, "TMPDIR", tmp), patch.object(
                push, "run", return_value=(True, json.dumps({"ok": True}))
            ) as run_mock:
                result = push.post_json("https://example.com", {"正文": "测试"}, "测试请求")

            self.assertEqual(result, {"ok": True})
            self.assertEqual(list(Path(tmp).iterdir()), [])
            data_arg = run_mock.call_args.args[0]
            self.assertIn("--data-binary", data_arg)

    def test_environment_credentials_take_priority(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WECHAT_APPID": "wx-test", "WECHAT_APPSECRET": "secret-test"},
            clear=False,
        ), patch.object(push, "CONFDIR", tmp):
            self.assertEqual(push.load_config(), ("wx-test", "secret-test"))

    def test_help_does_not_touch_network(self):
        buffer = io.StringIO()
        with patch.object(push.sys, "argv", ["wechat-publish", "--help"]), patch.object(
            push, "access_token"
        ) as token_mock, redirect_stdout(buffer):
            push.main()

        self.assertIn("微信公众号草稿箱", buffer.getvalue())
        token_mock.assert_not_called()

    def test_write_draft_id_records_and_replaces_media_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.push.md"
            path.write_text("---\ntitle: 测试标题\n---\n\n正文", encoding="utf-8")

            push.write_draft_id(str(path), "old_id", 0)
            push.write_draft_id(str(path), "new_id", 1)
            meta, body = push.parse_push_md(str(path))

            self.assertEqual(meta["media_id"], "new_id")
            self.assertEqual(meta["draft_index"], "1")
            self.assertEqual(path.read_text(encoding="utf-8").count("media_id"), 1)
            self.assertEqual(body.strip(), "正文")

    def test_date_option_requires_a_value(self):
        with patch.object(push.sys, "argv", ["wechat-publish", "--date"]), self.assertRaises(
            SystemExit
        ):
            push.main()


if __name__ == "__main__":
    unittest.main()
