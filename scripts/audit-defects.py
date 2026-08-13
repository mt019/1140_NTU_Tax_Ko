#!/usr/bin/env python3
"""掃校對版正文裡可機械偵測的缺陷。只回統計與檔名，不印正文。

目前查四類：
  簡體殘留   本倉全繁體，逐字稿工具偶爾吐出簡體（「那么」「后」…）
  待辦標記   【？來源請求】、TODO、勘誤
  藏稿      檔尾 <!-- --> 裡整段未校對的原始逐字稿
  禁語      使用者明令不用的代稱（「那一輪」；2026-07-29 起，出處一律寫
            進 <!--@ 學期 檔:行號 --> 標記，不寫進正文）

    python3 scripts/audit-defects.py
"""
import re
from collections import Counter
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "mkdocs/My_Notes"
SKIP = ("逐字稿初稿", "不用的廢稿", "_原稿")

# 只收「在繁體文本裡幾乎不會正當出現」的字，避免誤報。
SIMPLIFIED = "么这那个说时会为对将后来国经济发权义务规则应当业产额税额纳"
SIMP_WORDS = ["那么", "这个", "这样", "时候", "国家", "经济", "权利", "义务",
              "规定", "应当", "营业", "所得税", "纳税", "关于", "问题", "实质"]
TODO = re.compile(r"【？[^】]*】|TODO|待補|待查|勘誤|來源請求")
BANNED = ["那一輪"]
COMMENT = re.compile(r"<!--.*?-->", re.S)


def pages():
    for p in sorted(DOCS.rglob("*.md")):
        if any(s in str(p) for s in SKIP) or p.name in ("index.md", "404.md"):
            continue
        yield p


simp, todo, hidden, banned = Counter(), Counter(), Counter(), Counter()
for p in pages():
    raw = p.read_text(encoding="utf8")
    body = COMMENT.sub("", raw)
    rel = str(p.relative_to(DOCS))
    n = sum(body.count(w) for w in SIMP_WORDS)
    if n:
        simp[rel] = n
    t = len(TODO.findall(body))
    if t:
        todo[rel] = t
    h = sum(len(c) for c in COMMENT.findall(raw) if len(c) > 3000)
    if h:
        hidden[rel] = h
    b = sum(body.count(w) for w in BANNED)
    if b:
        banned[rel] = b

print(f"掃描 {len(list(pages()))} 頁\n")
for label, c, unit in (("簡體殘留", simp, "處"), ("待辦標記", todo, "處"),
                       ("檔尾藏未校對逐字稿", hidden, "字"),
                       ("禁語", banned, "處")):
    print(f"── {label}：{len(c)} 頁，共 {sum(c.values()):,} {unit}")
    for k, v in c.most_common(12):
        print(f"     {v:>7,} {unit}  {k}")
    if len(c) > 12:
        print(f"     …另 {len(c) - 12} 頁")
    print()
