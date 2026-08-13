#!/usr/bin/env python3
"""把 phenom 通用字體子集出 woff2，放進 mkdocs/My_Notes/assets/fonts/。

角色照 phenom 通用設計（對齊 my-canvas-lab src/index.css 現行版；
源雲明體已於 2026-07-18 自 canvas 移除，這裡不包）：
  正文與 CJK 標題  Huiwen-mincho（匯文明朝體，Public Domain）——全站字元
  拉丁標題        Radio Newsman——ASCII 加常用引號

字元集掃 mkdocs/site 的建站產物（先 mkdocs build 再跑本腳本）。
內容新增了生僻字而子集沒跟上時，該字會逐字退到 Songti TC，不會整頁壞；
重跑本腳本再 commit 即補上。

    python3 scripts/subset-fonts.py

需要 fonttools 與 brotli（pip install fonttools brotli）。
"""
import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "mkdocs" / "site"
OUT = ROOT / "mkdocs" / "My_Notes" / "assets" / "fonts"

FONT_LIB = Path.home() / "Documents" / "Font_Library" / "fonts"
BODY_SRC = FONT_LIB / "HuiwenMincho-Improved.ttf"
LATIN_SRC = Path.home() / "Documents" / "Font_Library" / "categories" / "typewriter-latin" / "radio-newsman.ttf"

ASCII = set(chr(c) for c in range(0x20, 0x7F))
EXTRA = set("‌‍​—–‑‧·、。，．？！；：「」『』（）〔〕【】《》〈〉…‥﹏＿～￥＄％＆＊＃＠０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ＋－＝÷×°℃§№½¼¾αβγ　‘’“”")


class TextGrab(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.chars = set()
        self.heads = set()
        self.in_head = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("h1", "h2", "h3"):
            self.in_head += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag in ("h1", "h2", "h3") and self.in_head:
            self.in_head -= 1

    def handle_data(self, data):
        if self.skip:
            return
        self.chars.update(data)
        if self.in_head:
            self.heads.update(data)


def collect():
    grab = TextGrab()
    pages = list(SITE.rglob("*.html"))
    if not pages:
        sys.exit("mkdocs/site 底下沒有 html——先 mkdocs build 再跑本腳本。")
    for p in pages:
        grab.feed(p.read_text(encoding="utf-8", errors="ignore"))
    body = {c for c in grab.chars if not c.isspace()} | ASCII | EXTRA
    heads = {c for c in grab.heads if not c.isspace()} | ASCII | EXTRA
    return body, heads


def subset(src, chars, out, font_number=None):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("\n".join(sorted(chars)))
        textfile = f.name
    cmd = [
        sys.executable, "-m", "fontTools.subset", str(src),
        f"--text-file={textfile}",
        "--flavor=woff2",
        f"--output-file={out}",
        "--layout-features=*",
        "--no-hinting",
        "--desubroutinize",
    ]
    if font_number is not None:
        cmd.append(f"--font-number={font_number}")
    subprocess.run(cmd, check=True)
    print(f"{out.name}: {out.stat().st_size/1024:.0f} KB（{len(chars)} 字元）")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    body, _heads = collect()
    subset(BODY_SRC, body, OUT / "HuiwenMincho-subset.woff2")
    subset(LATIN_SRC, ASCII | set("’‘“”—–…"), OUT / "RadioNewsman.woff2")


if __name__ == "__main__":
    main()
