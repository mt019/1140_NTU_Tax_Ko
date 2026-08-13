#!/usr/bin/env python3
"""從合訂本抽單年版。拆分規則只有一條（分章計畫.md）：標記裡出現哪一年，
那段就屬於哪一年的版本；兩年都列的段落兩個單行本都拿到。

    python3 scripts/split-edition.py <成稿.md> <學期>      # 例：… 02_….md 1121

輸出寫 _work/單行本_<學期>_<檔名>.md，主控台印保留／剔除的段落統計。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sourcemarks import WORK, parse_chapter


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    path, sem = sys.argv[1], sys.argv[2]
    ch = parse_chapter(path)
    if ch.errors:
        for line, msg in ch.errors:
            print(f"錯誤  {Path(path).name}:{line}  {msg}")
        print("標記有錯，先跑 validate-sources.py 修乾淨再拆。")
        sys.exit(1)
    chapter_sems = ch.decl.semesters if ch.decl else set()
    if sem not in chapter_sems:
        print(f"這章的來源檔宣告裡沒有 {sem}（有：{'、'.join(sorted(chapter_sems)) or '無宣告'}）")
        sys.exit(1)

    keep = set()          # 要輸出的行號
    kept, dropped = [], []
    for a, b, mk in ch.segments:
        rng = range(mk.line, b + 1)   # 標記行連同它管的內容一起走
        if sem in mk.semesters:
            keep.update(rng)
            kept.append((mk.line, b))
        else:
            dropped.append((mk.line, b))

    # 標題：子樹裡有保留內容才留；H1 與 frontmatter、Last updated 永遠留
    n = len(ch.lines)
    for idx, (hline, level, _) in enumerate(ch.headings):
        if level == 1:
            keep.add(hline)
            continue
        sub_end = n
        for h2line, l2, _ in ch.headings[idx + 1:]:
            if l2 <= level:
                sub_end = h2line - 1
                break
        if any(i in keep for i in range(hline + 1, sub_end + 1)):
            keep.add(hline)
    for i, ln in enumerate(ch.lines, start=1):
        if ln.startswith("Last updated"):
            keep.add(i)
    if ch.decl:
        keep.update(range(ch.decl.line, ch.decl.end_line + 1))
    if ch.lines and ch.lines[0].strip() == "---":
        for i, ln in enumerate(ch.lines[1:], start=2):
            keep.add(i - 1)
            if ln.strip() == "---":
                keep.add(i)
                break

    # 依序輸出，連續空行塌成一個
    out_lines, blank = [], 0
    for i, ln in enumerate(ch.lines, start=1):
        if i not in keep:
            continue
        if not ln.strip():
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out_lines.append(ln)
    while out_lines and not out_lines[-1].strip():
        out_lines.pop()

    WORK.mkdir(exist_ok=True)
    dest = WORK / f"單行本_{sem}_{Path(path).stem}.md"
    dest.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    print(f"單行本（{sem}）：保留 {len(kept)} 段、剔除 {len(dropped)} 段 → {dest.relative_to(WORK.parent)}")
    for a, b in dropped:
        print(f"  剔除  {a}-{b}")


if __name__ == "__main__":
    main()
