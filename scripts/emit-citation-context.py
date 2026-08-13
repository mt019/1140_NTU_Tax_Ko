#!/usr/bin/env python3
"""把每個法條引用與它的條文原文並排印出來，供人讀。

`lookup-article.py --scan-all` 只查條號存不存在。條號存在、講的卻是別的東西，
機器判斷不了——民法第 721 條（無記名證券發行人責任）被拿來講指示交付，就是這樣
被讀出來的。這支腳本不下判斷，只把「筆記那一句」與「條文原文」擺在一起，
讓人一眼看得出它們對不對得上。

用法：
    python3 scripts/emit-citation-context.py                 # 全站，寫到 _work/引用對照.txt
    python3 scripts/emit-citation-context.py <檔案.md>       # 單檔，印到畫面
    python3 scripts/emit-citation-context.py --law 民法      # 只看某一部法
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "lookup_article", Path(__file__).parent / "lookup-article.py")
LA = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LA)

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "mkdocs/My_Notes"
SKIP = ("逐字稿初稿", "不用的廢稿", "_原稿")


def pages():
    return [p for p in sorted(DOCS.rglob("*.md"))
            if not any(s in str(p) for s in SKIP) and p.name != "index.md"]


def context(line: str, raw: str, width: int = 70) -> str:
    """引用前後各取一段，長行不整行印。"""
    line = LA.COMMENT_RE.sub("", line).strip()
    i = line.find(raw)
    if i < 0:
        return line[:width * 2]
    lo, hi = max(0, i - width), min(len(line), i + len(raw) + width)
    return ("…" if lo else "") + line[lo:hi] + ("…" if hi < len(line) else "")


def emit(path: Path, only_law=None, out=sys.stdout):
    text = LA.COMMENT_RE.sub("", path.read_text(encoding="utf8"))
    rows = LA.cites(text)
    if only_law:
        rows = [r for r in rows if only_law in r[0]]
    if not rows:
        return 0
    lines = path.read_text(encoding="utf8").splitlines()
    printed = 0
    for law, art, sub, para, item_no, sub_item, raw in rows:
        shown, err = LA.resolve(law, art, sub, para, item_no, sub_item)
        no = next((n for n, ln in enumerate(lines, 1)
                   if raw in LA.COMMENT_RE.sub("", ln)), None)
        src = context(lines[no - 1], raw) if no else ""
        body = err if err else LA.flatten(shown, 110)
        print(f"{path.relative_to(DOCS)}:{no}  {raw}", file=out)
        print(f"    筆記：{src}", file=out)
        print(f"    條文：{body}\n", file=out)
        printed += 1
    return printed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="單一 .md；不給就掃全站")
    ap.add_argument("--law", help="只看某一部法")
    args = ap.parse_args()

    if args.target:
        emit(Path(args.target), args.law)
        return 0

    out_path = ROOT / "_work/引用對照.txt"
    out_path.parent.mkdir(exist_ok=True)
    total = 0
    with out_path.open("w", encoding="utf8") as fh:
        for p in pages():
            total += emit(p, args.law, fh)
    print(f"{total} 個引用寫進 {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
