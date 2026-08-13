#!/usr/bin/env python3
"""驗證一章的來源標記：語法、檔案存在、行號界內、每段都有標記管到，
並回報每個來源有多少行沒被引用。

    python3 scripts/validate-sources.py <成稿.md> [<成稿.md> …]

主控台印摘要；未引用行的明細寫進 _work/validate-sources_<檔名>.md。
有任何錯誤或未被管到的正文就 exit 1（00、01 還沒掛標記，跑它們本來就會紅）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sourcemarks import DOCS, WORK, cited_lines, parse_chapter, ungoverned


def check(path):
    ch = parse_chapter(path)
    stem = Path(path).stem
    print(f"\n== {stem} ==")
    counts = {}
    for mk in ch.markers:
        counts[mk.kind] = counts.get(mk.kind, 0) + 1
    print("標記統計：" + "、".join(f"{k} {v}" for k, v in sorted(counts.items())) if counts
          else "標記統計：整章沒有任何標記")

    bad = False
    for line, msg in ch.errors:
        print(f"  錯誤  {stem}.md:{line}  {msg}")
        bad = True

    if ch.decl is None:
        print("  錯誤  沒有章首 <!-- 來源檔：… --> 宣告")
        bad = True

    loose = ungoverned(ch)
    if loose:
        total = sum(b - a + 1 for a, b in loose)
        show = "、".join(f"{a}" if a == b else f"{a}-{b}" for a, b in loose[:12])
        more = f"（只列前 12 段）" if len(loose) > 12 else ""
        print(f"  未管到  {total} 行正文沒有標記管到：{show}{more}")
        bad = True

    # 待裁定與需老師確認，列出來但不算錯
    for mk in ch.markers:
        if mk.kind == "inconsistency":
            print(f"  待裁定  {stem}.md:{mk.line}  {mk.text.splitlines()[0]}")
        elif mk.kind == "confirm":
            print(f"  需老師確認  {stem}.md:{mk.line}  {mk.text.splitlines()[0]}")

    # 來源涵蓋率：哪些行沒被引用
    cited = cited_lines(ch)
    report = []
    for rel, got in sorted(cited.items()):
        src = (DOCS / rel).read_text(encoding="utf-8").splitlines()
        uncited = [i for i, ln in enumerate(src, start=1) if ln.strip() and i not in got]
        nonblank = sum(1 for ln in src if ln.strip())
        print(f"  涵蓋  {rel}：非空 {nonblank} 行，未被引用 {len(uncited)} 行")
        ranges, prev = [], None
        for i in uncited:
            if prev is not None and i == ranges[-1][1] + 1:
                ranges[-1][1] = i
            else:
                ranges.append([i, i])
            prev = i
        report.append((rel, nonblank, ranges))

    if report:
        WORK.mkdir(exist_ok=True)
        out = WORK / f"validate-sources_{stem}.md"
        with out.open("w", encoding="utf-8") as f:
            f.write(f"# {stem} 來源未引用行明細\n\n")
            for rel, nonblank, ranges in report:
                f.write(f"## {rel}（非空 {nonblank} 行）\n\n")
                if not ranges:
                    f.write("全部行都被引用。\n\n")
                    continue
                for a, b in ranges:
                    f.write(f"- {a}" + ("" if a == b else f"-{b}") + "\n")
                f.write("\n")
        print(f"  明細  {out.relative_to(WORK.parent)}")
    return not bad


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    ok = True
    for p in sys.argv[1:]:
        ok = check(p) and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
