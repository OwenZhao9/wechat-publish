# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0.0] - 2026-10-23

### Added

- 第一次推送后把草稿 `media_id` 和 `draft_index` 写回文章 front matter；再推同一篇时调用 `draft/update` 在原草稿上更新，不新建副本。`--new` 可强制新建。
- `cover.py`：生成 2.35:1 公众号封面图。
- SKILL.md 加入文章写作要求、排版限制和修改已推送文章的流程。

### Removed

- 去掉正文超过 3000 字的提醒。

## [0.1.0.0] - 2026-10-02

### Added

- Markdown 到微信公众号内联样式 HTML 的转换。
- 封面、正文图片上传和多图文草稿创建。
- 手机宽度 HTML 预览、主题样式和内容守卫。
- 环境变量或本地权限文件凭证配置，以及 Access Token 缓存。
- 跨平台单元测试和 GitHub Actions。

### Changed

- 临时请求正文改为唯一的 `600` 权限文件，并在请求完成后立即删除。
- 配置目录和缓存目录限制为当前用户访问。
