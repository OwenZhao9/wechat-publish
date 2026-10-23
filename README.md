# wechat-publish

写公众号文章、去掉 AI 味，再把 Markdown 转换成微信公众号可用的内联样式 HTML，上传正文图片和封面，调用微信官方接口创建草稿或在原草稿上更新。

原来单独的 wechat-voice（写法规则和自查脚本）已经合并进来，写法规则见 [`SKILL.md`](SKILL.md)，自查脚本是 `check.py`。

**只创建草稿，永远不自动群发。** 最后一步留给人在「订阅号助手」中通读并点击群发，避免脚本错误消耗当天的发布机会。

## 它解决什么问题

公众号编辑器会删除普通 CSS、屏蔽外链图片，也不允许大多数正文外链直接点击。这个工具把这些限制统一处理掉：

- Markdown 转公众号内联样式 HTML；
- 本地图片和远程图片重新上传到微信；
- 外部链接转成文末编号参考；
- 封面上传为永久素材；
- 支持多篇文章组成一条多图文草稿；
- 先生成 375px 手机宽度预览，再决定是否上传；
- Access Token 本地缓存，配置文件和临时请求文件限制为当前用户可读。

## 工作流程

```text
article.push.md
      ↓
Markdown → 内联样式 HTML → 图片上传 → 微信草稿箱
                                          ↓
                         手机通读后人工点击群发
```

## 环境要求

- Python 3.10+
- `curl`
- 如果图片需要转换格式或压缩：macOS 自带的 `sips`

Linux 也能运行，但请提前准备符合微信要求的 JPG/PNG 图片：正文图小于 1 MB，封面小于 4 MB。

## 安装

直接运行：

```bash
git clone https://github.com/OwenZhao9/wechat-publish.git
cd wechat-publish
python3 push.py --help
```

或者安装成全局命令：

```bash
python3 -m pip install .
wechat-publish --help
```

## 第一次配置

### 1. 准备公众号凭证

在公众号后台获取 AppID 和 AppSecret，写入：

```text
~/.ai-daily/wechat.json
```

内容：

```json
{"appid": "wx...", "secret": "..."}
```

然后限制文件权限：

```bash
chmod 600 ~/.ai-daily/wechat.json
```

也可以使用环境变量：

```bash
export WECHAT_APPID="wx..."
export WECHAT_APPSECRET="..."
```

不要把真实 AppSecret、Token 缓存或文章临时文件提交到 GitHub。

### 2. 配置 IP 白名单

在微信开发者后台的基本配置中，把运行脚本时使用的公网 IP 加入白名单。若微信返回 `40164`，脚本会直接显示微信实际看到的 IP。

### 3. 确认草稿箱接口

在公众号后台的接口权限页面确认存在草稿箱接口。工具使用的是 `draft/add` 创建草稿，不调用自动发布接口。

## 写法：去掉 AI 味

AI 写的中文有几个固定毛病，光靠「写得自然一点」这种提示改不掉：

- **报幕。** 说话之前先宣布自己要说什么：「一句话说清它是什么」「先看」「说实话」。
- **满屏加粗。** 加粗太多等于没加粗。
- **小标题是分类名。** 「里面有什么」「功能介绍」「写在最后」，这是作者的大纲，不是读者要看的东西。
- **开头自我介绍。** 「X 是我做的一个 Y」，读者没有理由继续读。
- **缺点写成检讨、说泄气话。**

规则全部写在 [`SKILL.md`](SKILL.md)，每条都带改前改后的例子。交稿前自查：

```bash
python3 check.py 文章.push.md
```

脚本报出署名、报幕句、泄气话、无关背景、分类名小标题、加粗密度和偏长段落；有命中项时退出码为 1，可以挂进 CI 或 git hook。它只做关键词提示，不替代通读。

## 写一篇文章

复制 [`examples/article.push.md`](examples/article.push.md)，填写标题、摘要、封面和正文：

```markdown
---
title: 文章标题
author: 你的名字
digest: 120 字以内摘要
cover: ./cover.jpg
source_url: https://example.com
open_comment: 1
fans_only_comment: 0
---

正文从这里开始，不要重复写一级标题。
```

## 使用

先生成预览，不访问微信接口：

```bash
python3 push.py --dry-run examples/article.push.md
```

预览默认生成在：

```text
~/ai-daily/preview/YYYY-MM-DD.html
```

确认后创建草稿：

```bash
python3 push.py examples/article.push.md
```

第一次推送成功后，脚本会把草稿的 `media_id` 写回文章 front matter。之后修改文章再运行同一条命令，会直接更新原来那篇草稿，不会新建副本；需要另建一篇时加 `--new`。

生成封面（需要 Pillow）。公众号同一张封面有两种裁剪：信息流大图 2.35:1，转发卡片和列表小图 1:1。脚本把左侧正方形色块做成能单独当小图的样子，右侧补标题和标签：

```bash
python3 cover.py 封面.jpg --main 低成本 --main 出国 --sub "32 种方式" \
    --title "普通人低成本出国的" --title "32 种方式" --tags 打工度假 互惠生 工签
```

把脚本打印的两个裁剪框写进 front matter，推送时就会分别设置大图和小图：

```markdown
cover_crop_235: 0,0,1,1
cover_crop_11: 0,0,0.4255,1
```

多图文草稿：

```bash
python3 push.py 主推.push.md 速递.push.md
```

第一个文件是主推文章。

## 支持的 Markdown

- 二级、三级标题
- 段落、引用、分割线
- 有序和无序列表
- 加粗、斜体、行内代码、代码块
- `==高亮==`
- 本地图片、远程图片
- 公众号内链与外部参考链接

## 常见错误

| 错误码 | 含义 | 处理方式 |
|---|---|---|
| `40164` | 当前 IP 不在白名单 | 添加报错中微信实际看到的 IP |
| `40001` | AppSecret 不正确 | 在后台重置后更新本地配置 |
| `48001` | 接口权限不足 | 到接口权限页确认草稿箱接口 |
| `40007` | 封面素材无效 | 更换封面并重新上传 |
| `45009` | 调用频率过高 | 等待后重试 |

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 安全边界

- 仓库不读取或提交浏览器 Cookie；
- AppSecret 只从环境变量或 `~/.ai-daily/wechat.json` 读取；
- Access Token 缓存在 `~/.ai-daily/.token.json`，权限为 `600`；
- 含正文的临时请求文件发送后立即删除；
- 自动化止于草稿箱，最终群发必须人工完成。

## License

MIT

---

## English

`wechat-publish` converts Markdown into WeChat Official Account-compatible inline HTML, uploads cover and body images, and creates a draft through the official `draft/add` API. It deliberately stops at the draft box; final broadcast remains a human action.

Requirements: Python 3.10+, `curl`, and macOS `sips` only when image conversion/compression is needed. See the Chinese guide above for setup and usage.
