#!/usr/bin/env python3
"""把成稿裡的校訂註整理成一份送審清單，給老師逐條看「哪裡動了他的話、依據是什麼」。

    python3 scripts/emit-corrections.py <成稿.md>…

校訂註（`<!--校訂 …-->`）在網頁與 .docx 上都看不見，老師沒有辦法自己找出來，所以送審
必須另附這一份。順帶把還沒處理完的 `<!--!` 待裁定與 `<!--?` 需老師確認也列進去，讓
一份文件就能回答「這一章還有什麼沒定案」。

輸出寫 _work/校訂清單_送審.md（多個成稿併成一份，依命令列順序）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sourcemarks import WORK, parse_chapter, ungoverned

# 出現在清單裡的三類標記，附標題與排序權重
KINDS = {
    "correction": ("已校訂", 0),
    "inconsistency": ("待裁定", 1),
    "confirm": ("需老師確認", 2),
}


def heading_of(ch, line):
    """標記前面最近的標題，回 (層級, 標題)；找不到回 (0, "章首")。"""
    found = (0, "章首")
    for hline, level, title in ch.headings:
        if hline < line:
            found = (level, title)
        else:
            break
    return found


def reflow(text):
    """把多行註解內文收成一段：去掉每行前導空白，行間用空格接。"""
    parts = [ln.strip() for ln in text.splitlines()]
    return " ".join(p for p in parts if p)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)

    # 全部解析並檢查完才動輸出檔。一章不乾淨就整份不寫——這份清單是交給老師的，
    # 寧可沒有也不能是一份看起來正常的空清單，何況覆寫會蓋掉上一次的好產出。
    chapters, bad = [], False
    for path in sys.argv[1:]:
        name = Path(path).name
        if not Path(path).exists():
            print(f"錯誤  找不到檔案：{path}")
            bad = True
            continue
        ch = parse_chapter(path)
        for line, msg in ch.errors:
            print(f"錯誤  {name}:{line}  {msg}")
            bad = True
        # 沒有章首宣告、或有段落沒被任何來源標記管到，代表這章還沒掛完標記。
        # 這種章的「零校訂」不是「沒有東西要改」，是「還沒開始標」，兩者不能長得一樣。
        if ch.decl is None:
            print(f"錯誤  {name}  沒有章首來源宣告，這章還沒掛標記")
            bad = True
        elif ungoverned(ch):
            miss = ungoverned(ch)
            print(f"錯誤  {name}  有 {len(miss)} 段沒有來源標記管到（首見第 {miss[0][0]} 行）")
            bad = True
        chapters.append((path, ch))
    if bad:
        print("先跑 validate-sources.py 修乾淨再生清單；本次未寫出任何檔案。")
        sys.exit(1)

    WORK.mkdir(exist_ok=True)
    dest = WORK / "校訂清單_送審.md"
    total = {k: 0 for k in KINDS}

    with dest.open("w", encoding="utf-8") as f:
        f.write("# 校訂清單（送審用）\n\n")
        f.write("逐字稿轉成筆記的過程中改動老師原話的地方，逐條列出原話、改法與依據。\n")
        f.write("這些說明在網頁與 Word 版上都是隱藏的註解，所以另附本清單。\n\n")

        for path, ch in chapters:
            stem = Path(path).stem
            picked = [mk for mk in ch.markers if mk.kind in KINDS]
            picked.sort(key=lambda mk: (KINDS[mk.kind][1], mk.line))
            counts = {k: sum(1 for mk in picked if mk.kind == k) for k in KINDS}
            for k in KINDS:
                total[k] += counts[k]

            f.write(f"## {stem}\n\n")
            tally = "、".join(
                f"{KINDS[k][0]} {counts[k]}" for k in KINDS if counts[k]
            )
            f.write(f"{tally or '本章沒有校訂註，也沒有待處理的標記'}。\n\n")

            last_kind = None
            for mk in picked:
                if mk.kind != last_kind:
                    f.write(f"### {KINDS[mk.kind][0]}\n\n")
                    last_kind = mk.kind
                level, title = heading_of(ch, mk.line)
                where = f"{title}" if level else "章首"
                body = reflow(mk.text)
                for prefix in ("校訂 ", "校訂"):
                    if body.startswith(prefix):
                        body = body[len(prefix):]
                        break
                f.write(f"- **{where}**（{stem}.md:{mk.line}）\n")
                f.write(f"  {body}\n\n")

        f.write("## 合計\n\n")
        f.write(
            "、".join(f"{KINDS[k][0]} {total[k]}" for k in KINDS) + "。\n"
        )

    line = "、".join(f"{KINDS[k][0]} {total[k]}" for k in KINDS)
    print(f"校訂清單（{line}） → {dest.relative_to(WORK.parent)}")


if __name__ == "__main__":
    main()
