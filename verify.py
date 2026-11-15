#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""4411.site 构建产物自检。

挡住「上游改版导致解析出 0 行」「文件被截断」「注入失败」这类坏数据，
CI 里不过就不 commit，服务器侧另有一道独立校验，双保险。
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
MODELS = ROOT / "models"
FILES = ("index.html", "aihot-data.js", "leaderboard.html", "resets.html", "free-tokens.html")


def fail(msg):
    sys.exit("自检失败：" + msg)


def main():
    for name in FILES:
        path = MODELS / name
        if not path.exists() or path.stat().st_size < 1024:
            fail("产物缺失或过小：{}".format(name))

    html = (MODELS / "index.html").read_text(encoding="utf-8")
    if "const MODELS = [" not in html or "const GENERATED =" not in html:
        fail("index.html 的 MODELS / GENERATED 结构异常")
    stamp = re.search(r'const GENERATED = "(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"', html)
    if not stamp:
        fail("GENERATED 时间戳格式异常")

    js = (MODELS / "aihot-data.js").read_text(encoding="utf-8")
    if "window.AIHOT.freebies" not in js:
        fail("aihot-data.js 缺少 freebies")
    marker = "window.AIHOT = "
    if marker not in js:
        fail("aihot-data.js 缺少 window.AIHOT")
    raw = js.split("window.AIHOT.freebies")[0]
    raw = raw[raw.index(marker) + len(marker):].strip().rstrip(";")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail("aihot-data.js 不是合法 JSON：{}".format(exc))

    rows = len(data.get("leaderboard", []))
    history = len(data.get("resets", {}).get("history", []))
    if rows < 10:
        fail("模型榜只解析出 {} 行，上游页面可能改版".format(rows))
    if history < 30:
        fail("重置监控历史只有 {} 天，上游页面可能改版".format(history))

    for name in ("leaderboard.html", "resets.html", "free-tokens.html"):
        if "<html" not in (MODELS / name).read_text(encoding="utf-8").lower():
            fail("{} 不是完整 HTML".format(name))

    print("自检通过 · 快照 {} · 模型榜 {} 行 · 重置历史 {} 天".format(stamp.group(1), rows, history))


if __name__ == "__main__":
    main()
