#!/usr/bin/env python3
"""盤點每一個校對版頁面到底校對到什麼程度。

判準不靠語感，靠對照：六門課都留著 `逐字稿初稿/`，同名檔就是同一堂課的
上游。把兩邊都切成句子，算校對版有多少句子是原封不動從初稿搬過來的
（照抄率）。照抄率高＝那一頁其實還是逐字稿。

沒有初稿可對照的頁面（1121 全部、老師要的其他文件）另外列，不猜。

    python3 scripts/audit-proofreading.py            # 表格
    python3 scripts/audit-proofreading.py --json out.json
"""
import json
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "mkdocs/My_Notes"

SENT_SPLIT = re.compile(r"[。！？；\n]+")
# 校對版按「節」切（W03_0918-1、-2），初稿是一天一個檔（W03_0918）；初稿檔名還常帶
# 課務後綴。這組後綴沿用 mkdocs/plugins/course_merge 既有的 COURSE_NOISE_RE，不另立一套。
SECTION_SUFFIX = re.compile(r"-\d+$")
DRAFT_NOISE = re.compile(r"(整理版|整理|有缺前面|沒去|改週三|材料|短)$")


def draft_key(stem: str) -> str:
    return SECTION_SUFFIX.sub("", DRAFT_NOISE.sub("", stem))
# 比對前先抹掉只影響版面、不影響內容的東西，否則加粗與引號會讓句子看起來不同。
NORMALISE = re.compile(r"[\s*_`>#\-–—「」『』（）()【】\[\],，、。：:；;！？!?~〜]+")


def sentences(text: str) -> set[str]:
    out = set()
    for raw in SENT_SPLIT.split(text):
        s = NORMALISE.sub("", raw)
        if len(s) >= 12:          # 太短的句子（「小結」「對」）到處都有，不具辨識力
            out.add(s)
    return out


def scan():
    rows = []
    for draft_dir in sorted(DOCS.rglob("逐字稿初稿")):
        course_dir = draft_dir.parent
        drafts = {}
        for d in draft_dir.glob("*.md"):
            drafts.setdefault(draft_key(d.stem), d)
        for final in sorted(course_dir.glob("*.md")):
            if final.name == "index.md":
                continue
            draft = drafts.get(draft_key(final.stem)) or (draft_dir / final.name)
            ft = final.read_text(encoding="utf8")
            fs = sentences(ft)
            row = {
                "course": str(course_dir.relative_to(DOCS)),
                "page": final.stem,
                "chars": len(ft),
                "has_draft": draft.exists(),
                "course_has_drafts": True,
            }
            if draft.exists():
                dt = draft.read_text(encoding="utf8")
                ds = sentences(dt)
                copied = fs & ds
                row.update(
                    draft_chars=len(dt),
                    sent_final=len(fs),
                    sent_draft=len(ds),
                    copied=len(copied),
                    copy_rate=round(len(copied) / len(fs), 3) if fs else None,
                    keep_rate=round(len(fs) / len(ds), 3) if ds else None,
                    length_ratio=round(len(ft) / len(dt), 3) if dt else None,
                    draft_file=draft.stem,
                    split=draft.stem != final.stem,
                )
            rows.append(row)

    # 沒有初稿目錄的課，整課列出來，狀態未知
    covered = {r["course"] for r in rows}
    for index in sorted(DOCS.rglob("index.md")):
        course = str(index.parent.relative_to(DOCS))
        if course in covered or course in {".", "1121", "1141", "1142"} \
                or "逐字稿初稿" in course:
            continue
        pages = [p for p in sorted(index.parent.glob("*.md")) if p.name != "index.md"]
        for p in pages:
            rows.append({
                "course": course, "page": p.stem,
                "chars": len(p.read_text(encoding="utf8")),
                "has_draft": False, "course_has_drafts": False,
            })
    return rows


def band(r):
    if not r.get("has_draft"):
        # 這兩者差很多：整門課沒留初稿，跟這一堂的初稿不見了。
        return "無初稿目錄" if not r.get("course_has_drafts") else "缺該堂初稿"
    c = r["copy_rate"]
    if c is None:
        return "空檔"
    if c >= 0.60:
        return "幾乎照抄"
    if c >= 0.30:
        return "部分校對"
    return "已重寫"


def main():
    rows = scan()
    for r in rows:
        r["band"] = band(r)
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf8")

    order = ["已重寫", "部分校對", "幾乎照抄", "空檔", "缺該堂初稿", "無初稿目錄"]
    tally = {b: [r for r in rows if r["band"] == b] for b in order}
    print(f"頁面 {len(rows)}")
    for b in order:
        v = tally[b]
        if v:
            print(f"  {b:<5} {len(v):>3} 頁　{sum(x['chars'] for x in v):>9,} 字")

    # 校對得最輕的十頁：即使全部落在「已重寫」，照抄率最高的還是最該回頭看的。
    cmp_rows = [r for r in rows if r.get("copy_rate") is not None]
    if cmp_rows:
        lo = min(r["copy_rate"] for r in cmp_rows)
        hi = max(r["copy_rate"] for r in cmp_rows)
        print(f"\n照抄率 {lo:.3f}–{hi:.3f}（有初稿可對照的 {len(cmp_rows)} 頁）")
        print("照抄率最高的十頁：")
        for r in sorted(cmp_rows, key=lambda x: -x["copy_rate"])[:10]:
            print(f"  {r['copy_rate']:.3f}  留存{r['keep_rate']:.2f}  "
                  f"{r['chars']:>7,}字  {r['course']}/{r['page']}")

    for b in ("幾乎照抄", "部分校對", "空檔", "缺該堂初稿"):
        if not tally[b]:
            continue
        print(f"\n── {b}（{len(tally[b])} 頁）──")
        for r in sorted(tally[b], key=lambda x: -x["chars"]):
            rate = f"{r['copy_rate']:.2f}" if r.get("copy_rate") is not None else "  ？ "
            print(f"  {rate}  {r['chars']:>7,}字  {r['course']}/{r['page']}")

    print(f"\n── 無初稿目錄（{len(tally['無初稿目錄'])} 頁）──")
    by_course = {}
    for r in tally["無初稿目錄"]:
        by_course.setdefault(r["course"], []).append(r)
    for c, v in sorted(by_course.items(), key=lambda kv: -sum(x["chars"] for x in kv[1])):
        print(f"  {len(v):>3} 頁 {sum(x['chars'] for x in v):>9,} 字  {c}")


if __name__ == "__main__":
    main()
