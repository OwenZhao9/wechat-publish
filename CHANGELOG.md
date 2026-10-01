# Changelog

All notable changes to this project will be documented in this file.

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
