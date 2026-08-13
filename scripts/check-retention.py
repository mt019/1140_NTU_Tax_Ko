#!/usr/bin/env python3
"""量一章主題重編成稿留下了多少來源正文。

`docs/主題重編/分章計畫.md` 訂的規則是「預設是移動，不是重寫」，分界寫成

    成稿字數 ÷ 該章所有來源段落字數 ≥ 0.85

低於就是壓縮過頭。字數比會漏掉一種情形：整章改寫過、長度卻剛好差不多。所以另外
算一個句子涵蓋率——把來源切成句子，看每一句在成稿裡找不找得到——並把找不到的句子
連同它在來源的行號列出來，這就是「差在哪」。

兩個數字都不含標題行、HTML 註解、`Last updated:` 與分隔線；標點與粗體記號在比對
前抹掉（沿用 audit-proofreading.py 的 NORMALISE），否則版面調整會被誤算成刪字。

來源可以寫在成稿檔頭的宣告裡：

    <!-- 來源檔：1141/課_二89_租稅法總論/W03_0916.md；1121/1121_租稅法總論/004_….md -->

單一來源只取一段時，路徑後面加行號範圍 `path:120-480`（含頭含尾）。也可以不宣告，
改從命令列給：

    python3 scripts/check-retention.py <成稿.md>
    python3 scripts/check-retention.py <成稿.md> --sources a.md b.md:120-480
    python3 scripts/check-retention.py <成稿.md> --min 0.85 --show 40
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "mkdocs/My_Notes"

FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)
SOURCE_DECL = re.compile(r"<!--\s*來源檔：(.*?)-->", re.S)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
RULE = re.compile(r"^\s*(-{3,}|\*{3,}|={3,})\s*$")
UPDATED = re.compile(r"^\s*Last updated\s*[:：]", re.I)
SENT_SPLIT = re.compile(r"[。！？；\n]+")
# 與 audit-proofreading.py 同一組：只抹版面與標點，不動內容字。
NORMALISE = re.compile(r"[\s*_`>#\-–—「」『』（）()【】\[\]|,，、。：:；;！？!?~〜]+")

MIN_SENT = 12          # 太短的句子（「小結」「對」）到處都有，不具辨識力


def strip_meta(text: str) -> str:
    return COMMENT.sub("", FRONTMATTER.sub("", text))


def body(text: str) -> str:
    """留下正文：去掉標題行、分隔線、Last updated、註解與 frontmatter。"""
    keep = [ln for ln in strip_meta(text).splitlines()
            if not (HEADING.match(ln) or RULE.match(ln) or UPDATED.match(ln))]
    return "\n".join(keep)


def chars(text: str) -> int:
    return len(NORMALISE.sub("", text))


def sentences(text: str):
    """回傳 (正規化句子, 行號)，行號是該句在原檔的位置。"""
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if HEADING.match(line) or RULE.match(line) or UPDATED.match(line):
            continue
        for raw in SENT_SPLIT.split(line):
            s = NORMALISE.sub("", raw)
            if len(s) >= MIN_SENT:
                out.append((s, lineno))
    return out


def resolve(spec: str):
    """`path` 或 `path:起-迄` → (Path, 文字)。行號含頭含尾，1 起算。"""
    rng = None
    m = re.search(r":(\d+)-(\d+)$", spec)
    if m:
        spec, rng = spec[: m.start()], (int(m.group(1)), int(m.group(2)))
    for cand in (DOCS / spec, ROOT / spec, Path(spec)):
        if cand.is_file():
            path = cand
            break
    else:
        sys.exit(f"找不到來源：{spec}（試過 {DOCS}/、{ROOT}/、以及原樣路徑）")
    text = path.read_text(encoding="utf8")
    if rng:
        lines = text.splitlines()
        lo, hi = rng
        if lo < 1 or hi > len(lines) or lo > hi:
            sys.exit(f"{spec} 的行號範圍 {lo}-{hi} 超出檔案（共 {len(lines)} 行）")
        text = "\n".join(lines[lo - 1: hi])
    return path, text


def declared_sources(text: str):
    m = SOURCE_DECL.search(text)
    if not m:
        return []
    return [s.strip() for s in re.split(r"[；;、\n]+", m.group(1)) if s.strip()]


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("chapter", help="成稿 .md")
    ap.add_argument("--sources", nargs="*", default=None,
                    help="來源，path 或 path:起-迄；省略時讀成稿檔頭的「來源檔」宣告")
    ap.add_argument("--min", type=float, default=0.85, help="保留率分界，預設 0.85")
    ap.add_argument("--show", type=int, default=25, help="最多列幾句找不到的")
    args = ap.parse_args()

    chapter = Path(args.chapter)
    if not chapter.is_file():
        for cand in (DOCS / args.chapter, ROOT / args.chapter):
            if cand.is_file():
                chapter = cand
                break
        else:
            sys.exit(f"找不到成稿：{args.chapter}")
    raw = chapter.read_text(encoding="utf8")

    specs = args.sources if args.sources is not None else declared_sources(raw)
    if not specs:
        sys.exit("沒有來源可比：成稿檔頭沒有「來源檔」宣告，命令列也沒給 --sources")

    final_chars = chars(body(raw))
    # 比對用的成稿文字含標題——來源的某一句可能被提成標題，那不算刪掉。
    final_text = NORMALISE.sub("", strip_meta(raw))

    print(f"成稿　{chapter.relative_to(ROOT) if ROOT in chapter.parents else chapter}")
    print(f"　正文 {final_chars:,} 字（不含標題、註解）\n")

    print("來源")
    total, missing = 0, []
    for spec in specs:
        path, text = resolve(spec)
        n = chars(body(text))
        total += n
        sents = sentences(body(text))
        gone = [(s, ln) for s, ln in sents if s not in final_text]
        missing.extend((path.name, ln, s) for s, ln in gone)
        print(f"　{spec:<52} {n:>8,} 字　{len(sents):>4} 句，缺 {len(gone)}")
        if len(specs) == 1:
            print()
    if len(specs) > 1:
        print(f"　{'合計':<52} {total:>8,} 字\n")

    if not total:
        sys.exit("來源字數為 0，無法計算")

    rate = final_chars / total
    ok = rate >= args.min
    print(f"保留率 {rate:.3f}　分界 {args.min}　{'通過' if ok else '未通過'}")

    all_sents = sum(len(sentences(body(resolve(s)[1]))) for s in specs)
    cover = 1 - len(missing) / all_sents if all_sents else 1.0
    print(f"句子涵蓋 {cover:.3f}（來源 {all_sents} 句，成稿裡找不到 {len(missing)} 句）")

    if missing:
        print(f"\n找不到的句子（按來源位置，最多 {args.show} 句）")
        for name, ln, s in missing[: args.show]:
            print(f"　{name}:{ln:<4} {s[:38]}")
        if len(missing) > args.show:
            print(f"　…另 {len(missing) - args.show} 句")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
