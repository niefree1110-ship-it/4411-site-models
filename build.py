#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4411.site · 模型工作台构建脚本

做三件事：
  1. 从 OpenRouter /api/v1/models 拉免费模型，重写页面里的 MODELS 数组与 GENERATED 时间戳
  2. 抓 aihot.news/free-tokens，解析出全部羊毛条目，与页面 FREEBIES 做差异比对，生成核对报告
  3. 可选：把 aihot 新增条目自动追加进页面 FREEBIES（--apply-freebies）

用法：
  python build.py                     # 刷新模型数据 + 生成核对报告（不写羊毛数据）
  python build.py --apply-freebies    # 同上，并把新增羊毛追加进页面
  python build.py --dry-run           # 只打印，不写文件
  python build.py --skip-fetch        # 只用 .cache 里的旧响应，不联网（离线调试）

部署（可选）：在 build.config.json 里填 deploy_command，脚本跑完会自动执行，
例如 "scp models/index.html root@1.2.3.4:/www/wwwroot/4411.site/models/index.html"
留空则只更新本地文件，由人工上传。
"""
import argparse
import datetime as dt
import html as htmllib
import json
import pathlib
import re
import subprocess
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent
PAGE = ROOT / "models" / "index.html"
CACHE = ROOT / ".cache"
CONFIG = ROOT / "build.config.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
OR_URL = "https://openrouter.ai/api/v1/models"
AIHOT_URL = "https://aihot.news/free-tokens"
LEADERBOARD_URL = "https://aihot.news/leaderboard"
RESETS_URL = "https://aihot.news/resets"
DATA_JS = ROOT / "models" / "aihot-data.js"

CACHE.mkdir(exist_ok=True)


# ---------------------------------------------------------------- 网络

def fetch(url, cache_name, skip_fetch=False):
    """抓取网页，返回 (内容, 是否来自缓存)。--skip-fetch 或失败时回落缓存。"""
    path = CACHE / cache_name
    if skip_fetch:
        if not path.exists():
            sys.exit(f"缓存不存在：{path}")
        return path.read_text(encoding="utf-8"), True
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read().decode("utf-8", "replace")
        if not body.strip():
            raise ValueError("响应为空")
        path.write_text(body, encoding="utf-8")
        print(f"  抓取 OK  {url}  ({len(body):,} 字节)")
        return body, False
    except Exception as exc:
        if path.exists():
            print(f"  ! 抓取失败（{exc}），回落缓存 {path.name}")
            return path.read_text(encoding="utf-8"), True
        sys.exit(f"抓取失败且无缓存：{url}\n{exc}")


# ---------------------------------------------------------------- OpenRouter

def as_float(v, default=1.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def map_model(m):
    """把 OpenRouter 原始模型映射成页面用的紧凑结构。"""
    arch = m.get("architecture") or {}
    tp = m.get("top_provider") or {}
    sp = m.get("supported_parameters") or []
    desc = (m.get("description") or "").strip()
    if len(desc) > 200:
        desc = desc[:200].rsplit(" ", 1)[0] + "..."
    inp = arch.get("input_modalities") or []
    return {
        "id": m.get("id"),
        "name": m.get("name") or m.get("id"),
        "created": m.get("created"),
        "description": desc,
        "context_length": m.get("context_length"),
        "max_output": tp.get("max_completion_tokens"),
        "modality_in": inp,
        "modality_out": arch.get("output_modalities") or [],
        "tokenizer": arch.get("tokenizer") or "Other",
        "expiration_date": m.get("expiration_date"),
        "knowledge_cutoff": m.get("knowledge_cutoff"),
        "supportsToolCall": "tools" in sp,
        "supportsImages": "image" in inp,
        "supportsReasoning": ("reasoning" in sp) or ("include_reasoning" in sp),
    }


def build_models(raw_json):
    data = json.loads(raw_json).get("data", [])
    free = [m for m in data
            if as_float((m.get("pricing") or {}).get("prompt")) == 0
            and as_float((m.get("pricing") or {}).get("completion")) == 0]
    models = [map_model(m) for m in free]
    models.sort(key=lambda x: -(x.get("created") or 0))
    return models, len(data)


# ---------------------------------------------------------------- aihot 羊毛

def strip_tags(s):
    return htmllib.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def guess_deadline(text, today=None):
    """从文本里找 '到 11月30日' 这类截止时间，补年份。"""
    today = today or dt.date.today()
    m = re.search(r"到\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text) or \
        re.search(r"到\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if not m:
        return None
    if len(m.groups()) == 3:
        y, mo, d = (int(x) for x in m.groups())
    else:
        mo, d = int(m.group(1)), int(m.group(2))
        y = today.year if (mo, d) >= (today.month, today.day) else today.year + 1
    try:
        return dt.date(y, mo, d).isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------- 下级页面数据

def parse_leaderboard(html_src):
    """模型榜：30 行标准表格 → 名次/模型/厂商/上线/评测覆盖/价格/评分。"""
    def g(p, blk, default=""):
        m = re.search(p, blk, re.S)
        return m.group(1) if m else default

    def n(x):
        m = re.search(r"-?\d+(?:\.\d+)?", strip_tags(x) or "")
        return float(m.group()) if m else None

    rows = []
    for m in re.finditer(r'<tr data-slug="([^"]+)"(.*?)</tr>', html_src, re.S):
        slug, blk = m.group(1), m.group(2)
        prices = re.findall(r'class="mono hidden px-3 py-3 text-\[14\.5px\][^"]*">([^<]+)</td>', blk)
        rows.append({
            "slug": slug,
            "rank": int(g(r'class="mono text-\[13px\] text-ink-4">(\d+)</span>', blk, "0") or 0),
            "name": strip_tags(g(r'<strong class="[^"]*text-\[15px\][^"]*">(.*?)</strong>', blk)),
            "vendor": strip_tags(g(r'<small class="[^"]*"[^>]*>([^<]*)</small>', blk)),
            "date": g(r'<time dateTime="([^"]+)"', blk),
            "evals": int(g(r"(\d+)<!--\s*--> 项评测", blk, "0") or 0),
            "coverage": int(g(r"覆盖\s*<!--\s*-->(\d+)<!--\s*-->%", blk, "0") or 0),
            "cache": n(prices[0]) if len(prices) > 0 else None,
            "input": n(prices[1]) if len(prices) > 1 else None,
            "output": n(prices[2]) if len(prices) > 2 else None,
            "score": n(g(r'AIHOT 评分 ([\d.]+)"', blk)),
        })
    return rows


def parse_resets(html_src):
    """重置监控：统计卡 + 本月日历事件 + 全部历史日期 + 公告摘要。"""
    stats = {}
    for m in re.finditer(r'<dt class="[^"]*">([^<]+)</dt><dd class="[^"]*">([^<]+)</dd>', html_src):
        stats[strip_tags(m.group(1))] = strip_tags(m.group(2))

    events = []
    for m in re.finditer(r'<a([^>]*data-day="([\d-]+)"[^>]*)>(.*?)</a>', html_src, re.S):
        attrs, day, body = m.group(1), m.group(2), m.group(3)
        u = re.search(r'href="([^"]+)"', attrs)
        types = [x for x in ("额度重置", "发重置卡", "待生效") if x in strip_tags(body)]
        if types:
            events.append({"date": day, "types": types,
                           "url": "https://aihot.news" + (u.group(1) if u else "")})
    events.sort(key=lambda x: x["date"])

    history = [{"date": d, "url": "https://aihot.news" + u}
               for u, d in re.findall(r'<a href="(/codex-reset/history/(\d{4}-\d{2}-\d{2}))"', html_src)]

    body = html_src[html_src.find("<body"):]
    plain = strip_tags(re.sub(r"<script.*?</script>", "", body, flags=re.S))
    win = re.search(r"预计\s*(今天\s*\d{1,2}:\d{2}\s*[–\-~]\s*\d{1,2}:\d{2})", plain)
    quote = re.search(r"(对我来说[^。]{0,80}。)", plain)
    return {
        "stats": stats,
        "events": events,
        "history": history,
        "notice": {
            "title": "等待重置卡到账",
            "window": win.group(1).strip() if win else "以官方公告为准",
            "quote": quote.group(1) if quote else "",
            "note": "模型推算：原话只说周四；参考以往重置多在太平洋时间傍晚落地。原帖未说明适用范围，卡片余额以 Codex 内显示为准。",
        },
    }


def extract_freebies_js(page_text):
    """从工作台页取 FREEBIES 数组字面量，供下级页面复用，保证两处数据同源。"""
    m = re.search(r"const FREEBIES = (\[.*?\n\]);", page_text, re.S)
    return m.group(1) if m else "[]"


def write_data_js(page_text, leaderboard, resets, stamp, date_str):
    payload = {
        "updated": stamp,
        "verified": date_str,
        "sources": {
            "leaderboard": LEADERBOARD_URL,
            "resets": RESETS_URL,
            "freeTokens": AIHOT_URL,
        },
        "leaderboard": leaderboard,
        "resets": resets,
    }
    head = ("/* 4411.site 模型工作台 · aihot.news 数据快照\n"
            "   由 build.py 自动生成，请勿手改。下级页面统一引用本文件。 */\n")
    body = "window.AIHOT = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n"
    body += "window.AIHOT.freebies = " + extract_freebies_js(page_text) + ";\n"
    DATA_JS.write_text(head + body, encoding="utf-8")
    return len(leaderboard), len(resets.get("events", [])), len(resets.get("history", []))


def parse_release_date(html):
    """从 <meta name="aihot-release" content="20261112155233-..."> 取核实日期。

    页面里每条免费额度写的是「YYYY-MM-DD 核实」，以前这个日期写死在页面里，
    构建脚本再怎么跑都不会变。改为跟随 aihot 的发布版本，标注才不会骗人。
    """
    m = re.search(r'name="aihot-release"\s+content="(\d{4})(\d{2})(\d{2})', html)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else dt.date.today().isoformat()


def parse_aihot(html):
    """按 <li> 切条目，按 h2/h3 分组，抽出标题/额度/条件/链接/核实日期。"""
    sections = []
    for m in re.finditer(r"<h[23][^>]*>(.*?)</h[23]>", html, re.S):
        sections.append((m.start(), strip_tags(m.group(1))))

    def group_of(pos):
        name = "其他福利"
        for p, title in sections:
            if p < pos and title in ("每天都能领", "每月都能领", "其他福利"):
                name = title
        return name

    # 2026-11-13：aihot 改版，<li> 由 "flex flex-wrap" 换成 "flex scroll-mt-20"。
    # 两种结构都兼容，且用宽松匹配，避免下次加个工具类就整个解析失效。
    starts = [m.start() for m in
              re.finditer(r'<li class="[^"]*(?:flex-wrap|scroll-mt-20)[^"]*"', html)]
    items = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(html)
        blk = html[start:end]

        tm = re.search(r'class="text-\[15px\] font-semibold text-ink">(.*?)</span>', blk, re.S)
        if not tm:
            continue
        title = strip_tags(tm.group(1))
        if not title:
            continue

        # 条件串：锚点之后 800 字符，剥标签后按 · 切
        cond_raw = ""
        cm = re.search(r'leading-normal text-ink-4">(.*?)(?:<svg|<button)', blk, re.S)
        if cm:
            cond_raw = strip_tags(cm.group(1))
        conds = [c.strip() for c in cond_raw.split("·") if c.strip()]
        verified = ""
        if conds and re.search(r"核实$", conds[-1]):
            verified = conds.pop()

        am = re.search(r'class="mono[^"]*text-\[20px\][^"]*">(.*?)</span>', blk, re.S)
        amount = strip_tags(am.group(1)) if am else ""
        note_m = re.search(r'title="([^"]*)"[^>]*class="mono', blk)
        amount_note = htmllib.unescape(note_m.group(1)) if note_m else ""

        um = re.search(r'<a href="([^"]+)"[^>]*target="_blank"', blk)
        url = htmllib.unescape(um.group(1)) if um else ""

        plain = strip_tags(blk)
        items.append({
            "t": title,
            "a": amount,
            "note": amount_note,
            "conds": conds,
            "u": url,
            "v": verified,
            "group": group_of(start),
            "dl": guess_deadline(plain),
            "raw": plain,
        })
    return items


# ---------------------------------------------------------------- 页面读写

def page_freebies(text):
    """提取页面 FREEBIES 数组里的每个对象（够用的正则解析）。"""
    m = re.search(r"const FREEBIES = \[(.*?)\n\];", text, re.S)
    if not m:
        return []
    out = []
    for blk in re.findall(r"\{c:'[^']*'[^{}]*\}", m.group(1)):
        def g(k):
            hit = re.search(rf"{k}:'([^']*)'", blk)
            return hit.group(1) if hit else None
        out.append({"c": g("c"), "t": g("t"), "a": g("a"), "dl": g("dl"), "u": g("u")})
    return out


def norm_url(u):
    """比较用的 URL 归一：去 fragment、去尾斜杠、小写。"""
    if not u:
        return ""
    return u.split("#")[0].split("?")[0].rstrip("/").lower()


def lcs_len(a, b):
    """最长公共子串长度（短字符串，暴力即可）。"""
    if not a or not b:
        return 0
    best = 0
    dp = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        prev = 0
        for j in range(1, len(b) + 1):
            cur = dp[j]
            dp[j] = prev + 1 if a[i - 1] == b[j - 1] else 0
            if dp[j] > best:
                best = dp[j]
            prev = cur
    return best


def make_matcher(page_items):
    """三层判定：链接相同 / 标题包含 / 公共子串足够长。"""
    titles = [x["t"] for x in page_items if x.get("t")]
    urls = {norm_url(x.get("u")) for x in page_items if x.get("u")}

    def covered(item):
        u = norm_url(item.get("u"))
        if u and u in urls:
            return True
        title = item["t"]
        for p in titles:
            if p in title or title.startswith(p):
                return True
            need = max(4, int(len(p) * 0.5))
            if lcs_len(p, title) >= need:
                return True
        return False

    return covered


def inject_models(text, models, stamp):
    js = "const MODELS = " + json.dumps(models, ensure_ascii=False, separators=(",", ":")) + ";"
    text, n1 = re.subn(r"const MODELS = \[.*?\];(?=\nconst GENERATED)",
                       lambda _: js, text, flags=re.S)
    text, n2 = re.subn(r'const GENERATED = "[^"]*";',
                       lambda _: f'const GENERATED = "{stamp}";', text)
    return text, n1, n2


def inject_fb_updated(text, date_str):
    """同步页面里的免费额度核实日期，返回 (新文本, 命中次数)。"""
    return re.subn(r"const FB_UPDATED = '[^']*';",
                   lambda _: f"const FB_UPDATED = '{date_str}';", text)


def js_escape(s):
    return (s or "").replace("\\", "\\\\").replace("'", "\\'")


def freebie_to_js(it):
    conds = ",".join("'" + js_escape(c) + "'" for c in it["conds"])
    dl = "'" + it["dl"] + "'" if it.get("dl") else "null"
    return ("{c:'%s',t:'%s',n:'%s',a:'%s',conds:[%s],dl:%s,u:'%s'}"
            % (it["c"], js_escape(it["t"]), js_escape(it["n"]), js_escape(it["a"]),
               conds, dl, js_escape(it["u"])))


def apply_freebies(text, new_items):
    m = re.search(r"const FREEBIES = \[(.*?)\n\];", text, re.S)
    if not m or not new_items:
        return text, 0
    body = m.group(1).rstrip()
    if not body.endswith(","):
        body += ","
    body += "\n  " + ",\n  ".join(freebie_to_js(x) for x in new_items)
    return text[:m.start()] + "const FREEBIES = [" + body + "\n];" + text[m.end():], len(new_items)


def classify(aihot_item):
    """把 aihot 分组映射到页面分类；限时免费可直调的归 api。"""
    title = aihot_item["t"] + " " + " ".join(aihot_item["conds"])
    if aihot_item["group"] == "每天都能领":
        return "daily"
    if aihot_item["group"] == "每月都能领":
        return "monthly"
    if re.search(r"免费调用|限时免费|公测|免费解析|限时免费用|免费领", title) and \
            re.search(r"API|调用|公测|解析|OCR|语音|向量|生图", title):
        return "api"
    return "new"


# ---------------------------------------------------------------- 报告

def build_report(models, total, aihot_items, page_items, today):
    lines = []
    lines.append("=" * 62)
    lines.append(f"4411.site 模型工作台 · 构建报告  {dt.datetime.now():%Y-%m-%d %H:%M}")
    lines.append("=" * 62)

    lines.append(f"\n【OpenRouter】接口返回 {total} 个模型，其中免费 {len(models)} 个")
    exp = [m for m in models if m.get("expiration_date")]
    if exp:
        lines.append(f"  其中 {len(exp)} 个带到期日：")
        for m in sorted(exp, key=lambda x: x["expiration_date"])[:8]:
            lines.append(f"    - {m['id']}  到期 {m['expiration_date']}")

    page_titles = [x["t"] for x in page_items if x["t"]]
    lines.append(f"\n【页面 FREEBIES】现有 {len(page_items)} 条")

    covered = make_matcher(page_items)

    fresh = [x for x in aihot_items if not covered(x)]
    lines.append(f"【aihot】抓到 {len(aihot_items)} 条，其中 {len(fresh)} 条页面还没有：")
    for x in fresh:
        lines.append(f"  + [{x['group']}] {x['t']}  · {x['a']}"
                     + (f"  · 截止 {x['dl']}" if x["dl"] else "")
                     + (f"  · {x['v']}" if x["v"] else ""))
        lines.append(f"      {x['u']}")

    stale = [x for x in page_items
             if x["dl"] and dt.date.fromisoformat(x["dl"]) < today]
    if stale:
        lines.append(f"\n【已过截止日】页面上 {len(stale)} 条（页面会显示「已截止」，可考虑清理）：")
        for x in stale:
            lines.append(f"  - {x['t']}  ({x['dl']})")

    soon = [x for x in page_items if x["dl"]
            and 0 <= (dt.date.fromisoformat(x["dl"]) - today).days <= 7]
    if soon:
        lines.append(f"\n【7 天内到期】{len(soon)} 条：")
        for x in soon:
            days = (dt.date.fromisoformat(x["dl"]) - today).days
            lines.append(f"  - {x['t']}  剩 {days} 天 ({x['dl']})")

    lines.append("\n提示：aihot 的条件标签是人工精编的（含「要实名」「限产品内」等），")
    lines.append("      自动追加只保证标题/额度/链接/截止日准确，条件按抓取原样带入，建议上线前扫一眼。")
    return "\n".join(lines)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply-freebies", action="store_true", help="把 aihot 新增条目追加进页面")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    ap.add_argument("--skip-fetch", action="store_true", help="用 .cache 缓存，不联网")
    args = ap.parse_args()

    today = dt.date.today()
    if not PAGE.exists():
        sys.exit(f"页面不存在：{PAGE}")

    print("→ 拉取 OpenRouter 模型列表")
    or_raw, or_stale = fetch(OR_URL, "openrouter-models.json", args.skip_fetch)
    models, total = build_models(or_raw)

    print("→ 拉取 aihot 免费额度")
    aihot_html, _ = fetch(AIHOT_URL, "aihot-free-tokens.html", args.skip_fetch)
    aihot_items = parse_aihot(aihot_html)
    fb_date = parse_release_date(aihot_html)
    print(f"  aihot 版本日期：{fb_date}")

    print("→ 拉取模型榜 / 重置监控（供下级页面使用）")
    lb_html, _ = fetch(LEADERBOARD_URL, "aihot-leaderboard.html", args.skip_fetch)
    rs_html, _ = fetch(RESETS_URL, "aihot-resets.html", args.skip_fetch)
    lb_rows = parse_leaderboard(lb_html)
    rs_data = parse_resets(rs_html)
    print(f"  模型榜 {len(lb_rows)} 行 · 重置事件 {len(rs_data['events'])} 条 · 历史 {len(rs_data['history'])} 天")
    if len(aihot_items) < 20:
        print(f"  ! 只解析出 {len(aihot_items)} 条羊毛，页面结构可能变了，本次不追加")
        aihot_items = [] if len(aihot_items) < 5 else aihot_items
        args.apply_freebies = False if len(aihot_items) < 5 else args.apply_freebies

    text = PAGE.read_text(encoding="utf-8")
    page_items = page_freebies(text)
    report = build_report(models, total, aihot_items, page_items, today)

    page_titles = [x["t"] for x in page_items if x["t"]]
    covered = make_matcher(page_items)
    fresh = [x for x in aihot_items if not covered(x)]

    stamp = dt.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    old_stamp_m = re.search(r'const GENERATED = "([^"]*)"', text)
    old_stamp = old_stamp_m.group(1) if old_stamp_m else ""
    if or_stale:
        # 用的是缓存数据，不能伪装成刚更新
        stamp = old_stamp
        print("  ! 本次模型数据来自缓存，GENERATED 时间戳保持不变")
        report = "[注意] 本次未能连云，模型数据沿用缓存，时间戳未更新。\n\n" + report
    text, n_models, n_stamp = inject_models(text, models, stamp)
    text, n_fb = inject_fb_updated(text, fb_date)

    applied = 0
    if args.apply_freebies and fresh:
        new_items = []
        for x in fresh:
            new_items.append({
                "c": classify(x),
                "t": x["t"],
                "n": "",
                "a": x["a"],
                "conds": x["conds"],
                "dl": x["dl"],
                "u": x["u"],
            })
        text, applied = apply_freebies(text, new_items)

    if n_models != 1 or n_stamp != 1:
        sys.exit(f"注入失败：MODELS 命中 {n_models} 次，GENERATED 命中 {n_stamp} 次")

    if args.dry_run:
        print("\n[dry-run] 不写文件。以下是报告：\n")
        print(report)
        return

    PAGE.write_text(text, encoding="utf-8")
    (CACHE / "freebies-report.txt").write_text(report, encoding="utf-8")
    n_lb, n_ev, n_hist = write_data_js(text, lb_rows, rs_data, stamp, fb_date)
    print(f"\n  ✓ 写入 {PAGE}（MODELS {len(models)} 个，GENERATED {stamp}，免费额度核实 {fb_date}）")
    print(f"  ✓ 报告 → {CACHE / 'freebies-report.txt'}")
    print(f"  ✓ 下级页面数据 → {DATA_JS}（模型榜 {n_lb} · 本月事件 {n_ev} · 历史 {n_hist}）")
    if args.apply_freebies:
        print(f"  ✓ 追加新羊毛 {applied} 条")
    print()
    print(report)

    # 可选部署
    if CONFIG.exists():
        try:
            cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
            cmd = (cfg.get("deploy_command") or "").strip()
            if cmd:
                print(f"\n→ 执行部署：{cmd}")
                subprocess.run(cmd, shell=True, check=True, cwd=ROOT)
                print("  ✓ 部署完成")
            else:
                print("\n（build.config.json 里 deploy_command 为空，跳过部署）")
        except Exception as exc:
            print(f"\n! 部署失败：{exc}")


if __name__ == "__main__":
    main()
