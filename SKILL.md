---
name: wechat-publish
description: 把 Markdown 文章排版并发送到微信公众号草稿箱。先生成手机宽度 HTML 预览，再上传封面、正文图并调用 draft/add；脚本不执行最终群发。用户说“发公众号”“推到公众号”“放到草稿箱”时使用。
---

# wechat-publish

## 边界

工具只创建公众号草稿，永远不自动群发。群发不可撤回，应由用户在手机「订阅号助手」中通读后点击。

## 流程

1. 确认输入是带 front matter 的 `.push.md` 文件。
2. 检查标题、摘要、封面和正文。
3. 永远先运行：

   ```bash
   python3 push.py --dry-run <article.push.md>
   ```

4. 告知用户预览路径并检查错误。
5. 用户已明确要求发送时运行：

   ```bash
   python3 push.py <article.push.md>
   ```

6. 成功后报告草稿已创建，并提醒用户在「订阅号助手」中完成最终群发。

## 安全规则

- 不把 AppID、AppSecret、Access Token 或 `~/.ai-daily/` 提交到版本库。
- `40164` 时只使用微信错误信息中报告的 IP，不使用其他 IP 查询服务的结果。
- 不绕过文章内容守卫。
- 不代替用户执行不可撤回的最终群发。
