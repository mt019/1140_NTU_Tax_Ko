"""1121 校定頁的驗收：python3 scripts/accept-1121.py <原頁.md> <校定頁.md> [...成對]

每對印一行「通過／未過」與各項數字，任一對未過就 exit 1。2026-10-10 第一批六頁用它驗收。
常數照抄自 scripts/audit-spoken-residue.py（FILLERS、rate 的剝除規則）與
scripts/audit-defects.py（SIMP_WORDS、TODO）；那兩支載入即執行，無法 import，改常數時兩邊一起改。

判準：口語殘留 < 1.86／千字（09-13 重算的分界）、簡體 0、待辦標記 0（含 （？））、
正文字數對原頁 ≥ 0.85、標題 ≥ 5、無空格條號（第5條）0。檔尾藏的原始逐字稿只報字數不擋，
留不留由站主定。
"""
import re
import sys
from pathlib import Path

FILLERS = ["那個", "就是說", "對不對", "這樣子", "然後呢", "是不是說", "好不好",
           "這個東西", "我們今天", "簡單來講", "換句話說", "也就是說",
           "各位同學", "所以說", "基本上來講", "大概就是"]
PAT = re.compile("|".join(map(re.escape, FILLERS)))
SIMP_WORDS = ["那么", "这个", "这样", "时候", "国家", "经济", "权利", "义务",
              "规定", "应当", "营业", "所得税", "纳税", "关于", "问题", "实质"]
TODO = re.compile(r"【？[^】]*】|（？）|\(\?\)|TODO|待補|待查|勘誤|來源請求")
FM = re.compile(r"^---\n.*?\n---\n", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)
RESIDUE_CUT = 1.86


def text(p):
    return COMMENT.sub("", FM.sub("", Path(p).read_text(encoding="utf8")))


def body_chars(p):
    t = "\n".join(l for l in text(p).splitlines() if not l.lstrip().startswith("#"))
    return len(re.sub(r"[\s*_>`\-|]", "", t))


def residue(p):
    t = text(p)
    return round(len(PAT.findall(t)) / len(t) * 1000, 2) if len(t) >= 2000 else None


def row(orig, new):
    t = text(new)
    raw = Path(new).read_text(encoding="utf8")
    r = {
        "殘留": residue(new), "原殘留": residue(orig),
        "簡體": sum(t.count(w) for w in SIMP_WORDS),
        "待辦": len(TODO.findall(t)),
        "保留": round(body_chars(new) / max(body_chars(orig), 1), 3),
        "標題": sum(1 for l in t.splitlines() if l.startswith("#")),
        "藏稿": sum(len(c) for c in COMMENT.findall(raw) if len(c) > 3000),
        "條號無空格": len(re.findall(r"第\d+(?:-\d+)?條", t)),
    }
    ok = (r["殘留"] is not None and r["殘留"] < RESIDUE_CUT and r["簡體"] == 0
          and r["待辦"] == 0 and r["保留"] >= 0.85
          and r["條號無空格"] == 0 and r["標題"] >= 5)
    return r, ok


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or len(args) % 2:
        sys.exit("用法：accept-1121.py <原頁> <校定頁> [...成對]")
    bad = 0
    for o, n in zip(args[::2], args[1::2]):
        r, ok = row(o, n)
        bad += not ok
        print(("通過" if ok else "未過"), Path(n).name, r)
    sys.exit(1 if bad else 0)
