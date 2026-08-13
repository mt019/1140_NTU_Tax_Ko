#!/usr/bin/env python3
"""從來源標記生章末來源對照表，給讀不到 HTML 註解的 .docx 版用。

    python3 scripts/emit-source-table.py <成稿.md>

輸出寫 _work/來源對照表_<檔名>.md：每個標題一列，列出它底下標記引用的來源。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sourcemarks import WORK, parse_chapter


def fmt_ref(ref):
    spec = ",".join(f"{a}" if a == b else f"{a}-{b}" for a, b in ref.lines)
    name = ref.short or ref.path or ref.raw
    return f"{name}:{spec}" if spec else name


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    path = sys.argv[1]
    ch = parse_chapter(path)
    if ch.errors:
        for line, msg in ch.errors:
            print(f"錯誤  {Path(path).name}:{line}  {msg}")
        print("標記有錯，先跑 validate-sources.py 修乾淨再生表。")
        sys.exit(1)

    # 每個管轄標記掛到它前面最近的標題
    rows = []                 # (heading_line, level, title, [refs])
    for hline, level, title in ch.headings:
        rows.append([hline, level, title, []])
    for a, b, mk in ch.segments:
        if not mk.refs:
            continue
        owner = None
        for row in rows:
            if row[0] < mk.line:
                owner = row
            else:
                break
        if owner is not None:
            owner[3].extend(mk.refs)

    stem = Path(path).stem
    WORK.mkdir(exist_ok=True)
    dest = WORK / f"來源對照表_{stem}.md"
    with dest.open("w", encoding="utf-8") as f:
        f.write(f"# {stem}：來源對照表\n\n")
        if ch.decl:
            f.write("本章來源檔：\n\n")
            for ref in ch.decl.refs:
                f.write(f"- `{ref.path}`（短名 {ref.short}，{ref.semester} 學期）\n")
            f.write("\n")
        f.write("| 節 | 來源 |\n|---|---|\n")
        for hline, level, title, refs in rows:
            if level == 1:
                continue
            indent = "　" * (level - 2)
            seen, cell = set(), []
            for r in refs:
                s = fmt_ref(r)
                if s not in seen:
                    seen.add(s)
                    cell.append(s)
            f.write(f"| {indent}{title} | {'；'.join(cell) or '—'} |\n")
    print(f"來源對照表 → {dest.relative_to(WORK.parent)}")


if __name__ == "__main__":
    main()
