#!/usr/bin/env python3
"""把 Markdown 文章送进微信公众号草稿箱。

脚本读取带 front matter 的 ``.push.md`` 文件，生成公众号可用的内联样式
HTML，上传正文图片与封面，再调用 ``draft/add`` 创建草稿。
发不发、什么时候发，仍然是你在手机「订阅号助手」里点——群发不可撤回、
订阅号每天只有一次机会，这个闸门是故意留给人的。

运行只需要 Python 标准库和 curl。图片需要压缩或转格式时，macOS 会使用
系统自带的 sips；已经符合要求的 jpg/png 在其他系统也可直接上传。
JSON body 走 --data-binary 读文件，天然绕开
「json= 把中文转义成 \\uXXXX、微信侧解出来是乱码」这个经典坑。

前置条件（只做一次）:
  1. 后台「设置与开发」→「接口权限」确认有「草稿箱」
  2. 后台「设置与开发」→「基本配置」→ IP 白名单，加上本机公网 IP
     不加报 40164，脚本会把你当前公网 IP 打出来给你抄
  3. 写 ~/.ai-daily/wechat.json  →  {"appid": "wx...", "secret": "..."}
     或设环境变量 WECHAT_APPID / WECHAT_APPSECRET

用法:
    python3 push.py                          # 今天，读 published/YYYY-MM-DD.push.md
    python3 push.py --date 2026-08-16
    python3 push.py 主推.push.md 速递.push.md   # 多篇 = 一条多图文，第一篇是主推
    python3 push.py --dry-run                # 只出 HTML 预览，不碰接口、不上传
    python3 push.py --force-token            # 强制换新 token（怀疑缓存脏了）

.push.md 格式（publish 阶段产出）:
    ---
    title: 最终选定的标题
    author: 你的名字
    digest: 摘要，≤120 字（留空会被自动截前 54 字，很难看）
    cover: covers/2026-08-16.jpg     # 相对本文件 / 绝对路径 / ~ 都行
    source_url: https://原文链接      # 读者点「阅读原文」跳这里
    ---

    正文 markdown
"""

import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zlib
from datetime import datetime

API = "https://api.weixin.qq.com/cgi-bin"
HOME = os.path.expanduser("~")
WORKDIR = os.path.join(HOME, "ai-daily")
CONFDIR = os.path.join(HOME, ".ai-daily")
TOKEN_CACHE = os.path.join(CONFDIR, ".token.json")
TMPDIR = os.path.join(CONFDIR, "tmp")
TIMEOUT = 60
VERSION = "0.1.0.0"

# 正文图微信只收 jpg/png 且必须 <1MB；封面走永久素材，限制松得多
IMG_MAX_BYTES = 1000 * 1000
COVER_MAX_BYTES = 4 * 1000 * 1000

# 你在 SKILL.md publish 阶段定的排版规范，直接内联。
# 公众号编辑器会剥掉 <style> 标签和 class，只认 style="..."，没有第二条路。
STYLE = {
    "p":      "font-size:15px;line-height:1.75;letter-spacing:.5px;color:#2c3e50;margin:0 0 1.3em;",
    "h2":     "font-size:18px;line-height:1.6;font-weight:700;color:#1a1a1a;"
              "margin:2.2em 0 1em;padding-left:10px;border-left:4px solid #07c160;",
    "h3":     "font-size:16px;line-height:1.6;font-weight:700;color:#1a1a1a;margin:1.8em 0 .8em;",
    "quote":  "margin:0 0 1.3em;padding:12px 14px;background:#f7f7f7;border-left:3px solid #dbdbdb;",
    "quote_p": "font-size:14px;line-height:1.7;color:#666;margin:0 0 .6em;",
    "li":     "font-size:15px;line-height:1.75;color:#2c3e50;margin:0 0 .5em;",
    "list":   "margin:0 0 1.3em;padding-left:1.2em;",
    "code":   "font-size:13px;font-family:Menlo,Consolas,monospace;background:#f2f2f2;"
              "color:#c7254e;padding:1px 4px;border-radius:3px;",
    "pre":    "font-size:13px;line-height:1.6;font-family:Menlo,Consolas,monospace;background:#f7f7f7;"
              "color:#333;padding:14px;border-radius:4px;overflow-x:auto;margin:0 0 1.3em;",
    "hr":     "border:0;border-top:1px solid #e5e5e5;margin:2em 0;",
    "img":    "max-width:100%;display:block;margin:1.5em auto;border-radius:4px;",
    "strong": "color:#1a1a1a;font-weight:700;",
    "link":   "color:#576b95;text-decoration:none;",
    "sup":    "font-size:11px;color:#07c160;vertical-align:super;",
    "ref_h":  "font-size:14px;font-weight:700;color:#999;margin:2.5em 0 .8em;",
    "ref":    "font-size:12px;line-height:1.7;color:#999;margin:0 0 .4em;word-break:break-all;",
    # ==高亮== 的底色。默认跟加粗一样，只有换了配色的才真的上荧光笔。
    "mark":   "color:#1a1a1a;font-weight:700;",
}

DEFAULT_STYLE = dict(STYLE)

# front matter 里写 theme: <名字> 就换一套配色。不写 = 上面那套微信绿，日报照旧。
# 只覆盖要改的键，其余从 DEFAULT_STYLE 继承。
THEMES = {
    # 《深入浅出 DeepSeek Harness》的宜家蓝黄。黄在浅底上做不了字，只当荧光笔。
    "book": {
        "p":      "font-size:15px;line-height:1.78;letter-spacing:.5px;color:#3A3F45;margin:0 0 1.35em;",
        "h2":     "font-size:18px;line-height:1.6;font-weight:600;color:#0E1116;"
                  "margin:2.4em 0 1em;padding-left:11px;border-left:4px solid #0058A3;",
        "h3":     "font-size:16px;line-height:1.6;font-weight:600;color:#0E1116;margin:1.9em 0 .8em;",
        "quote":  "margin:0 0 1.5em;padding:15px 18px;background:#EAF1F8;"
                  "border:1px solid #C3D8EA;border-radius:11px;",
        "quote_p": "font-size:14.5px;line-height:1.75;color:#3A3F45;margin:0 0 .6em;",
        "li":     "font-size:15px;line-height:1.78;color:#3A3F45;margin:0 0 .5em;",
        "code":   "font-size:13px;font-family:Menlo,Consolas,monospace;background:#F1F3F5;"
                  "color:#0E1116;padding:2px 6px;border-radius:4px;",
        "pre":    "font-size:12.5px;line-height:1.8;font-family:Menlo,Consolas,monospace;"
                  "background:#F1F3F5;color:#0E1116;padding:15px 18px;border-radius:9px;"
                  "overflow-x:auto;margin:0 0 1.5em;",
        "hr":     "border:0;border-top:1px solid #E4E6E9;margin:2.4em 0;",
        "strong": "color:#0E1116;font-weight:600;",
        "mark":   "color:#0E1116;font-weight:600;padding:0 2px;"
                  "background:linear-gradient(transparent 56%,#FFF3B8 56%,#FFF3B8 94%,transparent 94%);",
        "link":   "color:#00457F;text-decoration:none;",
        "sup":    "font-size:11px;color:#0058A3;vertical-align:super;",
    },
}


def apply_theme(meta):
    """按 front matter 的 theme 换配色。返回上一套，用完要还回去（多图文时互不串色）。"""
    prev = dict(STYLE)
    STYLE.clear()
    STYLE.update(DEFAULT_STYLE)
    name = (meta.get("theme") or "").strip().lower()
    if name and name not in THEMES:
        warn(f"没有叫 {name} 的配色，用默认那套。现有：{'、'.join(THEMES)}")
    STYLE.update(THEMES.get(name, {}))
    return prev

ERR_HINTS = {
    40001: "AppSecret 不对。后台「设置与开发」→「基本配置」重置一次，再填回 wechat.json。",
    40007: "media_id 无效——封面素材可能已被删除，换一张。",
    40164: "调用方 IP 不在白名单。去后台「设置与开发」→「基本配置」→ IP 白名单加上它。",
    41005: "没收到媒体文件——检查图片路径是否存在。",
    45009: "接口调用超频，等一会儿再试（stable_token 已做缓存，正常不该撞到）。",
    48001: "接口权限不足。先去后台「接口权限」页确认账号是否拥有草稿箱接口，"
           "不要只根据账号主体类型判断。",
    53404: "账号已被限制，去后台看通知。",
}


# ---------------------------------------------------------------- 基础设施

def die(msg):
    print(f"\n✗ {msg}\n", file=sys.stderr)
    sys.exit(1)


def warn(msg):
    print(f"  [warn] {msg}", file=sys.stderr)


def run(cmd, timeout=TIMEOUT):
    """跑 curl/sips。返回 (ok, stdout)。"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        if r.returncode != 0:
            return False, (r.stderr or "").strip()
        return True, r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return False, str(e)


def my_ip():
    ok, out = run(["curl", "-sS", "-m", "10", "https://ifconfig.me"], timeout=15)
    return out.strip() if ok and out.strip() else "（取不到，自己搜「我的IP」）"


def check(data, what):
    """微信所有接口都用 errcode 报错，0 或缺省即成功。"""
    if not isinstance(data, dict):
        die(f"{what}：返回的不是 JSON —— {str(data)[:200]}")
    code = data.get("errcode", 0)
    if code == 0:
        return data
    hint = ERR_HINTS.get(code, "")
    if code == 40164:
        # 微信在 errmsg 里回了它实际看到的 IP，那才是要加白名单的那个。
        # 本机 curl 查到的 IP 可能走了不同线路（代理/VPN），照抄会白忙一场。
        seen = re.search(r"invalid ip ([0-9]{1,3}(?:\.[0-9]{1,3}){3})", str(data.get("errmsg", "")))
        if seen:
            hint += f"\n    ★ 白名单要加这个（微信实际看到的）：{seen.group(1)}"
            hint += f"\n      本机自查的是 {my_ip()}——不一致就以上面那个为准。"
        else:
            hint += f"\n    你现在的公网 IP 是：{my_ip()}"
    msg = f"{what} 失败：errcode={code} {data.get('errmsg', '')}"
    if hint:
        msg += f"\n  → {hint}"
    die(msg)


def post_json(url, obj, what):
    """
    JSON body 写临时文件再 --data-binary 读，不走命令行参数：
    既避免中文/引号的 shell 转义地狱，也保证是真 UTF-8 字节而不是 \\uXXXX。
    """
    ensure_private_dir(TMPDIR)
    path = ""
    ok, out = False, ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", dir=TMPDIR, delete=False
        ) as f:
            path = f.name
            json.dump(obj, f, ensure_ascii=False)
        os.chmod(path, 0o600)
        ok, out = run(["curl", "-sS", "-m", str(TIMEOUT), "-X", "POST",
                       "-H", "Content-Type: application/json; charset=utf-8",
                       "--data-binary", f"@{path}", url])
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
    if not ok:
        die(f"{what}：请求发不出去 —— {out[:200]}")
    try:
        return check(json.loads(out), what)
    except json.JSONDecodeError:
        die(f"{what}：返回不是 JSON —— {out[:200]}")


def post_file(url, path, what):
    ok, out = run(["curl", "-sS", "-m", str(TIMEOUT), "-F", f"media=@{path}", url], timeout=TIMEOUT + 30)
    if not ok:
        die(f"{what}：上传失败 —— {out[:200]}")
    try:
        return check(json.loads(out), what)
    except json.JSONDecodeError:
        die(f"{what}：返回不是 JSON —— {out[:200]}")


# ---------------------------------------------------------------- 凭证

def ensure_private_dir(path):
    """创建仅当前用户可访问的配置目录。"""
    os.makedirs(path, mode=0o700, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass

def load_config():
    appid = os.environ.get("WECHAT_APPID")
    secret = os.environ.get("WECHAT_APPSECRET")
    conf = os.path.join(CONFDIR, "wechat.json")
    if (not appid or not secret) and os.path.exists(conf):
        try:
            if os.stat(conf).st_mode & 0o077:
                warn(f"{conf} 权限过宽，建议运行 chmod 600 {conf}")
            with open(conf, encoding="utf-8") as f:
                d = json.load(f)
            appid = appid or d.get("appid")
            secret = secret or d.get("secret") or d.get("appsecret")
        except (json.JSONDecodeError, OSError) as e:
            die(f"{conf} 读不了：{e}")
    if not appid or not secret:
        die(f"没有凭证。写 {conf}：\n"
            f'    {{"appid": "wx...", "secret": "..."}}\n'
            f"  然后 chmod 600 它。或者设 WECHAT_APPID / WECHAT_APPSECRET 环境变量。")
    return appid, secret


def access_token(force=False):
    """
    用 stable_token 不用 /cgi-bin/token：后者每次调用都签发新 token 并让旧的失效，
    多开一个进程就能把正在用的顶掉；stable_token 在有效期内返回同一个。
    """
    ensure_private_dir(CONFDIR)
    now = time.time()
    if not force and os.path.exists(TOKEN_CACHE):
        try:
            with open(TOKEN_CACHE, encoding="utf-8") as f:
                c = json.load(f)
            if c.get("expires_at", 0) - 300 > now:   # 留 5 分钟余量
                return c["token"]
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    appid, secret = load_config()
    d = post_json(f"{API}/stable_token", {
        "grant_type": "client_credential",
        "appid": appid,
        "secret": secret,
        "force_refresh": bool(force),
    }, "获取 access_token")

    tok = d.get("access_token")
    if not tok:
        die(f"获取 access_token：返回里没有 access_token —— {d}")
    with open(TOKEN_CACHE, "w", encoding="utf-8") as f:
        json.dump({"token": tok, "expires_at": now + d.get("expires_in", 7200)}, f)
    os.chmod(TOKEN_CACHE, 0o600)
    return tok


# ---------------------------------------------------------------- 图片

def prep_image(src, max_bytes, workdir):
    """
    微信正文图只收 jpg/png 且 <1MB。用 macOS 自带 sips 转格式/压体积，
    这样不用为了一张图去装 Pillow。返回可上传的本地路径。
    """
    ensure_private_dir(workdir)
    ext = os.path.splitext(src)[1].lower()
    size = os.path.getsize(src)

    if ext in (".jpg", ".jpeg", ".png") and size <= max_bytes:
        return src

    # 名字里掺一段源路径的 hash：不同目录下的同名图（a/img.png 与 b/img.png）
    # 否则会压到同一个输出文件上，后一张把前一张覆盖掉
    base = re.sub(r"[^\w.-]", "_", os.path.basename(os.path.splitext(src)[0]))
    tag = f"{zlib.crc32(os.path.abspath(src).encode()) & 0xffffff:06x}"
    for width, quality in ((2000, 90), (1600, 80), (1280, 70), (1080, 60), (900, 45)):
        out = os.path.join(workdir, f"{base}_{tag}_{width}_{quality}.jpg")
        ok, err = run(["sips", "-s", "format", "jpeg",
                       "-s", "formatOptions", str(quality),
                       "-Z", str(width), src, "--out", out], timeout=60)
        if not ok:
            die(
                f"图片需要转换或压缩，但 sips 不可用（{os.path.basename(src)}）：{err[:120]}\n"
                "  请先把图片转成小于限制的 jpg/png，或在 macOS 上运行。"
            )
        if os.path.getsize(out) <= max_bytes:
            return out
    warn(f"{os.path.basename(src)} 压到最小仍超过 {max_bytes // 1000}KB，照原样传，可能被拒")
    return out


def resolve_image(src, base_dir, workdir):
    """本地路径直接用；http 图先下下来——外链图片贴进正文一定会被微信屏蔽。"""
    if src.startswith(("http://", "https://")):
        ensure_private_dir(workdir)
        name = re.sub(r"[^\w.-]", "_", src.split("/")[-1].split("?")[0]) or "remote"
        if not os.path.splitext(name)[1]:
            name += ".jpg"
        dst = os.path.join(workdir, f"dl_{name}")
        ok, _ = run(["curl", "-sSL", "-m", "40", "-o", dst, src], timeout=60)
        if not ok or not os.path.exists(dst) or os.path.getsize(dst) == 0:
            warn(f"下不动这张图，跳过：{src[:70]}")
            return None
        return dst
    path = os.path.expanduser(src)
    if not os.path.isabs(path):
        path = os.path.join(base_dir, path)
    if not os.path.exists(path):
        warn(f"图片不存在，跳过：{path}")
        return None
    return path


# ---------------------------------------------------------------- Markdown → 公众号 HTML

def inline(text, ctx):
    """行内元素。先 escape 再套正则——markdown 的标记符不会被 escape 动到。"""
    t = html.escape(text, quote=False)

    def _img(m):
        path = resolve_image(m.group(2).strip(), ctx["base_dir"], ctx["workdir"])
        if not path:
            return ""
        if path not in ctx["images"]:
            ctx["images"][path] = f"%%IMG{len(ctx['images'])}%%"
        return f'<img src="{ctx["images"][path]}" style="{STYLE["img"]}"/>'

    def _link(m):
        label, url = m.group(1), m.group(2).strip()
        # 公众号正文只有指向 mp.weixin.qq.com 的超链接能点，其余一律被剥成纯文本，
        # 所以外链走文末脚注——你引用的英文原文链接全靠这个才留得住。
        if "mp.weixin.qq.com" in url:
            return f'<a href="{url}" style="{STYLE["link"]}">{label}</a>'
        if url not in ctx["links"]:
            ctx["links"].append(url)
        return f'{label}<sup style="{STYLE["sup"]}">[{ctx["links"].index(url) + 1}]</sup>'

    # 顺序要紧：图片先于链接，否则 ![]() 会被链接的正则先吃掉
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)", _img, t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)[^)]*\)", _link, t)
    t = re.sub(r"`([^`]+)`", lambda m: f'<code style="{STYLE["code"]}">{m.group(1)}</code>', t)
    t = re.sub(r"==([^=\n]+)==", lambda m: f'<span style="{STYLE["mark"]}">{m.group(1)}</span>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", lambda m: f'<strong style="{STYLE["strong"]}">{m.group(1)}</strong>', t)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", lambda m: f"<em>{m.group(1)}</em>", t)
    return t


def md_to_html(md, base_dir, workdir):
    # markdown 注释（draft 阶段给你的思路线索写在这里）不进正文
    md = re.sub(r"<!--.*?-->", "", md, flags=re.DOTALL)
    ctx = {"links": [], "images": {}, "base_dir": base_dir, "workdir": workdir}
    lines = md.split("\n")
    out, i, n = [], 0, len(lines)

    def is_list(s):
        return bool(re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", s))

    def is_block_start(s):
        st = s.strip()
        return (not st or st.startswith(("#", ">", "```"))
                or is_list(s) or re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", st))

    while i < n:
        raw, s = lines[i], lines[i].strip()

        if not s:
            i += 1
            continue

        if s.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            body = html.escape("\n".join(buf), quote=False).replace("\n", "<br/>")
            out.append(f'<pre style="{STYLE["pre"]}"><code>{body}</code></pre>')
            continue

        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            out.append(f'<hr style="{STYLE["hr"]}"/>')
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            # h1 降级：文章标题单独在 front matter 里给，正文里不该再出现一级标题
            key, tag = ("h2", "h2") if len(m.group(1)) <= 2 else ("h3", "h3")
            out.append(f'<{tag} style="{STYLE[key]}">{inline(m.group(2), ctx)}</{tag}>')
            i += 1
            continue

        if s.startswith(">"):
            buf = []
            while i < n and (lines[i].strip().startswith(">") or
                             (buf and lines[i].strip() and not is_block_start(lines[i]))):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]).strip())
                i += 1
            paras, cur = [], []
            for b in buf:
                if b:
                    cur.append(b)
                elif cur:
                    paras.append(" ".join(cur))
                    cur = []
            if cur:
                paras.append(" ".join(cur))
            inner = "".join(f'<p style="{STYLE["quote_p"]}">{inline(p, ctx)}</p>' for p in paras)
            out.append(f'<blockquote style="{STYLE["quote"]}">{inner}</blockquote>')
            continue

        if is_list(raw):
            ordered = bool(re.match(r"^\s*\d+[.)]\s+", raw))
            items = []
            while i < n and is_list(lines[i]):
                items.append(re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", lines[i]).strip())
                i += 1
            tag = "ol" if ordered else "ul"
            lis = "".join(f'<li style="{STYLE["li"]}">{inline(x, ctx)}</li>' for x in items)
            out.append(f'<{tag} style="{STYLE["list"]}">{lis}</{tag}>')
            continue

        buf = [s]
        i += 1
        while i < n and lines[i].strip() and not is_block_start(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        out.append(f'<p style="{STYLE["p"]}">{inline(" ".join(buf), ctx)}</p>')

    if ctx["links"]:
        out.append(f'<h3 style="{STYLE["ref_h"]}">参考链接</h3>')
        for idx, url in enumerate(ctx["links"], 1):
            out.append(f'<p style="{STYLE["ref"]}">[{idx}] {html.escape(url, quote=False)}</p>')

    return "".join(out), ctx


# ---------------------------------------------------------------- 输入

def parse_push_md(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()

    meta, body = {}, text
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line and not line.strip().startswith("#"):
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip().strip("'\"")
        body = m.group(2)
    else:
        warn(f"{os.path.basename(path)} 没有 front matter，标题只能从正文首个 # 猜")
        h = re.search(r"^#\s+(.*)$", body, re.MULTILINE)
        if h:
            meta["title"] = h.group(1).strip()

    if not meta.get("title"):
        die(f"{path} 没有 title —— 标题是必填的。")
    return meta, body


def judgment_section(body):
    """取「我的判断」这一节的正文，到下一个标题为止。没有这一节返回 None（速递副条就没有）。"""
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)   # 思路线索是注释，不算你写的字
    m = re.search(r"^#{1,6}\s*.*我的判断.*$", body, re.MULTILINE)
    if not m:
        return None
    rest = body[m.end():]
    nxt = re.search(r"^#{1,6}\s+", rest, re.MULTILINE)
    return rest[:nxt.start()] if nxt else rest


def guard(meta, body, path):
    """铁律检查。宁可在这儿被拦下，也别让半成品进草稿箱。"""
    name = os.path.basename(path)

    # 铁律 1：「我的判断」是全篇唯一原创。这一节空着就是一篇没观点的纯翻译，别发。
    # 阈值取 50 字而不是规范里的 400：这道守卫只负责抓「忘了写」，
    # 写短了是你的判断（下面会提醒一句），不该由脚本替你拦。
    seg = judgment_section(body)
    if seg is not None:
        jw = len(re.findall(r"[一-鿿]", seg))
        if jw < 50:
            die(f"{name} 的「我的判断」基本是空的（中文 {jw} 字）—— 铁律 1：这一段是号的全部价值。\n"
                f"  写完再跑 push。")
        if jw < 300:
            warn(f"{name} 的「我的判断」只有 {jw} 字（规范是 400–600）——确认是你想要的长度")

    words = len(re.findall(r"[一-鿿]", body))
    if words > 3000:
        warn(f"{name} 中文 {words} 字，超过 3000 红线 —— 完读率会掉，建议砍。")
    elif words < 800:
        print(f"  · {name}：{words} 字（速递体量，正常）", file=sys.stderr)
    else:
        print(f"  · {name}：{words} 字", file=sys.stderr)
    if not meta.get("digest"):
        warn(f"{name} 没写 digest，微信会自动截正文前 54 字当摘要（通常很难看）")
    if not meta.get("cover"):
        warn(f"{name} 没写 cover —— 没封面图的文章打开率明显低")


# ---------------------------------------------------------------- 主流程

def build_article(path, token, dry_run):
    meta, body = parse_push_md(path)
    guard(meta, body, path)

    prev_style = apply_theme(meta)
    base_dir = os.path.dirname(os.path.abspath(path))
    workdir = os.path.join(TMPDIR, "img")
    try:
        content, ctx = md_to_html(body, base_dir, workdir)
    finally:
        STYLE.clear(); STYLE.update(prev_style)

    if dry_run:
        for local, ph in ctx["images"].items():
            content = content.replace(ph, "file://" + local)
    else:
        for local, ph in ctx["images"].items():
            up = prep_image(local, IMG_MAX_BYTES, workdir)
            r = post_file(f"{API}/media/uploadimg?access_token={token}", up, f"上传正文图 {os.path.basename(local)}")
            content = content.replace(ph, r["url"])
            print(f"  ✓ 正文图 {os.path.basename(local)}", file=sys.stderr)

    art = {
        "title": meta["title"][:64],
        "author": meta.get("author", ""),
        "digest": meta.get("digest", "")[:120],
        "content": content,
        "content_source_url": meta.get("source_url", ""),
        "need_open_comment": 0 if str(meta.get("open_comment", "1")).lower() in ("0", "false", "no") else 1,
        "only_fans_can_comment": 1 if str(meta.get("fans_only_comment", "0")).lower() in ("1", "true", "yes") else 0,
    }

    cover = meta.get("cover")
    if cover and not dry_run:
        p = resolve_image(cover, base_dir, workdir)
        if p:
            up = prep_image(p, COVER_MAX_BYTES, workdir)
            r = post_file(f"{API}/material/add_material?access_token={token}&type=image",
                          up, "上传封面")
            art["thumb_media_id"] = r["media_id"]
            print(f"  ✓ 封面 {os.path.basename(p)}", file=sys.stderr)

    return art, content


def preview(articles_html, date):
    """存一份能在浏览器里按手机宽度看的预览，比在后台里反复刷快得多。"""
    outdir = os.path.join(WORKDIR, "preview")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"{date}.html")
    parts = "".join(
        '<hr style="border:0;border-top:2px dashed #ccc;margin:3em 0"/>' + h if idx else h
        for idx, h in enumerate(articles_html))
    with open(path, "w", encoding="utf-8") as f:
        f.write('<!doctype html><meta charset="utf-8"><title>预览</title>'
                '<body style="margin:0;background:#ededed">'
                '<div style="max-width:375px;margin:0 auto;background:#fff;padding:20px 16px;'
                'min-height:100vh;box-shadow:0 0 20px rgba(0,0,0,.08)">'
                + parts + "</div></body>")
    return path


def main():
    args = [a for a in sys.argv[1:]]
    if "--version" in args:
        print(VERSION)
        return
    if "--help" in args or "-h" in args:
        print(
            "wechat-publish：把 Markdown 文章送进微信公众号草稿箱\n\n"
            "用法：\n"
            "  wechat-publish [--dry-run] [--force-token] [--date YYYY-MM-DD] [文章.push.md ...]\n\n"
            "选项：\n"
            "  --dry-run      只生成 HTML 预览，不访问微信接口\n"
            "  --force-token  强制刷新 access token\n"
            "  --date DATE    指定默认文章日期\n"
            "  --version      显示版本\n"
        )
        return
    dry_run = "--dry-run" in args
    force_token = "--force-token" in args
    date = datetime.now().astimezone().strftime("%Y-%m-%d")
    if "--date" in args:
        date_index = args.index("--date")
        if date_index + 1 >= len(args) or args[date_index + 1].startswith("--"):
            die("--date 后面必须写日期，例如：--date 2026-10-02")
        date = args[date_index + 1]

    files = [a for a in args if a.endswith(".md")]
    if not files:
        default = os.path.join(WORKDIR, "published", f"{date}.push.md")
        if not os.path.exists(default):
            die(f"找不到 {default}\n"
                f"  先跑 /daily-digest publish 产出它，或直接把文件路径当参数传进来。")
        files = [default]
    for f in files:
        if not os.path.exists(f):
            die(f"找不到 {f}")

    print(f"推送 {date}（{len(files)} 篇）{' · dry-run' if dry_run else ''}", file=sys.stderr)

    token = "" if dry_run else access_token(force=force_token)

    articles, htmls = [], []
    for f in files:
        art, h = build_article(f, token, dry_run)
        articles.append(art)
        htmls.append(h)

    path = preview(htmls, date)

    if dry_run:
        print(f"\n✓ dry-run 完成，没碰任何接口。\n  预览：open {path}\n", file=sys.stderr)
        return

    r = post_json(f"{API}/draft/add?access_token={token}", {"articles": articles}, "新增草稿")

    print(f"\n✓ 草稿已进草稿箱  media_id={r.get('media_id', '?')}", file=sys.stderr)
    print(f"  预览：open {path}", file=sys.stderr)
    print("\n下一步（人工，故意的）：", file=sys.stderr)
    print("  手机「订阅号助手」→ 底部创作 → 草稿箱 → 选中 → 群发", file=sys.stderr)
    print("  订阅号每天 1 次机会，发出去撤不回，发之前在手机上通读一遍。\n", file=sys.stderr)


if __name__ == "__main__":
    main()
