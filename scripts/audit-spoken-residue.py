#!/usr/bin/env python3
"""1121 兩門課沒有留逐字稿初稿，無法用照抄率判斷校對程度，改量口語殘留。

先用兩群已知答案的檔校準這個指標：逐字稿初稿（未校對）與 1141／1142 的校對版
（已確認重寫，照抄率 <0.19）。兩群若分得開，這個指標才拿去量 1121。分不開就報告
分不開，不硬給 1121 一個分數。

    python3 scripts/audit-spoken-residue.py
"""
import re
import statistics as st
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "mkdocs/My_Notes"

# 逐字稿裡大量出現、寫成文章時通常會被刪掉的口語支架。
FILLERS = ["那個", "就是說", "對不對", "這樣子", "然後呢", "是不是說", "好不好",
           "這個東西", "我們今天", "簡單來講", "換句話說", "也就是說",
           "各位同學", "所以說", "基本上來講", "大概就是"]
PAT = re.compile("|".join(map(re.escape, FILLERS)))


def rate(path: Path) -> float | None:
    """每千字的口語支架次數。"""
    t = path.read_text(encoding="utf8")
    t = re.sub(r"^---\n.*?\n---\n", "", t, flags=re.S)
    # 有 7 頁把原始逐字稿整段留在檔尾的 <!-- --> 裡（1121 租稅規避 6 頁、所得稅法四
    # 1 頁）。那是未校對的上游材料，不是頁面上讀得到的正文；不剝掉就會量錯對象。
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    if len(t) < 2000:
        return None
    return round(len(PAT.findall(t)) / len(t) * 1000, 2)


def group(paths):
    v = sorted(x for x in (rate(p) for p in paths) if x is not None)
    if not v:
        return None
    return {"n": len(v), "min": v[0], "p25": v[len(v) // 4], "median": st.median(v),
            "p75": v[3 * len(v) // 4], "max": v[-1]}


def show(label, g):
    if not g:
        print(f"{label:<22} 無樣本")
        return
    print(f"{label:<22} n={g['n']:<4} 中位數 {g['median']:>5.2f}   "
          f"四分位 {g['p25']:.2f}–{g['p75']:.2f}   全距 {g['min']:.2f}–{g['max']:.2f}")


drafts = [p for p in DOCS.rglob("逐字稿初稿/*.md")]
finals = [p for d in DOCS.rglob("逐字稿初稿") for p in d.parent.glob("*.md")
          if p.name != "index.md"]
target = [p for p in DOCS.glob("1121/*/*.md") if p.name != "index.md"]

print("校準（兩群已知答案）")
g_draft, g_final = group(drafts), group(finals)
show("  逐字稿初稿（未校對）", g_draft)
show("  1141/1142 校對版", g_final)

if g_draft and g_final and g_final["p75"] < g_draft["p25"]:
    print(f"\n  兩群分得開：校對版 p75 {g_final['p75']:.2f} < 初稿 p25 {g_draft['p25']:.2f}，"
          f"指標可用。")
    cut = (g_final["p75"] + g_draft["p25"]) / 2
    print(f"  取分界 {cut:.2f}／千字。\n")

    print("1121（無初稿可對照）")
    show("  1121 全部", group(target))
    rows = sorted(((rate(p), p) for p in target), key=lambda x: -(x[0] or 0))
    over = [(r, p) for r, p in rows if r is not None and r > cut]
    print(f"\n  超過分界的 {len(over)} 頁（校對可能沒做完，建議人工複看）：")
    for r, p in over:
        print(f"    {r:>5.2f}  {len(p.read_text(encoding='utf8')):>7,}字  "
              f"{p.relative_to(DOCS)}")
    if not over:
        print("    無。1121 的口語殘留全部落在校對版的水準內。")
else:
    print("\n  兩群分不開，這個指標量不出東西。1121 的校對狀態維持未知，需人工抽樣。")
