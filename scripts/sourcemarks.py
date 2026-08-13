#!/usr/bin/env python3
"""主題重編章節的來源標記共用解析器。

規格在 docs/主題重編/分章計畫.md「出處寫在標記裡」節。三支入口
（validate-sources.py、split-edition.py、emit-source-table.py）都從這裡拿
解析結果，自己不再碰正則。

標記長相（第 00–02 章實際用過的都要吃）：

    <!-- 來源檔：1141/課_二89_租稅法總論/W03_0916.md；1121/…/004_….md -->   章首宣告
    <!-- 來源：1141/課_二89_租稅法總論/W03_0916.md:4；1121/…/004_….md:9 -->  H2 全路徑式
    <!-- 來源：W03:10-54；004:36-56 -->                                    H3/H4 短名式
    <!-- 來源：004:9,13-14 -->                                             逗號列表
    <!--@ 1121 004:95 -->                                                 行內版本標記
    <!--@ 1141 W03:356-358 + 1121 004:152 -->                             兩年共有
    <!--! 兩年不一致 | … -->                                              待裁定
    <!--? 需老師確認：… -->                                               需老師確認
    <!--校訂 2026-07-29：… -->                                            校訂註解

短名＝來源檔 basename 第一個底線前的字（W03_0916.md → W03），對照章首宣告解析。
管轄規則：宣告與來源／版本標記管到下一個同類標記或下一個標題為止；校訂、待裁定、
需老師確認、其他註解不改變管轄。
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "mkdocs/My_Notes"
WORK = ROOT / "_work"

COMMENT = re.compile(r"<!--(.*?)-->", re.S)
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*$")
UPDATED = re.compile(r"^\s*Last updated\s*[:：]", re.I)
RULE = re.compile(r"^\s*(-{3,}|\*{3,}|={3,})\s*$")
LINESPEC = re.compile(r"^[\d,，\s\-–—]+$")
EDITION_PART = re.compile(r"^\s*(\d{4})\s+(.+?)\s*$")


@dataclass
class Ref:
    """一個「檔:行號」引用。lines 為含頭含尾的 (起,迄) 列表；空＝整檔。"""
    raw: str
    path: str = ""            # 相對 DOCS，解析成功才有
    short: str = ""
    semester: str = ""
    lines: list = field(default_factory=list)


@dataclass
class Marker:
    kind: str                 # decl | source | edition | inconsistency | confirm | correction | other
    line: int                 # 1-based 起始行
    end_line: int
    text: str                 # 註解內文（去 <!-- -->）
    refs: list = field(default_factory=list)
    semesters: set = field(default_factory=set)

    GOVERNING = {"decl", "source", "edition"}

    @property
    def governs(self):
        return self.kind in self.GOVERNING


@dataclass
class Chapter:
    path: Path
    lines: list               # 原始行（無行尾換行）
    markers: list             # 依出現順序
    headings: list            # (line, level, title)
    errors: list              # (line, message)
    decl: object = None       # 章首宣告 Marker，可能沒有
    shortmap: dict = field(default_factory=dict)   # 短名 → 相對路徑
    content_lines: set = field(default_factory=set)  # 去掉註解後仍有正文的行號
    segments: list = field(default_factory=list)   # (start, end, marker|None) 管轄區段


def semester_of(relpath):
    for part in Path(relpath).parts:
        if re.fullmatch(r"\d{4}", part):
            return part
    return ""


def short_of(relpath):
    return Path(relpath).name.split("_")[0].removesuffix(".md")


def parse_linespec(spec):
    """'9,13-14' → [(9,9),(13,14)]。壞掉丟 ValueError。"""
    out = []
    for piece in re.split(r"[,，]", spec):
        piece = piece.strip()
        if not piece:
            continue
        m = re.fullmatch(r"(\d+)\s*[-–—]\s*(\d+)", piece)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                raise ValueError(f"行號範圍顛倒：{piece}")
            out.append((a, b))
        elif piece.isdigit():
            out.append((int(piece), int(piece)))
        else:
            raise ValueError(f"看不懂的行號：{piece}")
    if not out:
        raise ValueError(f"空的行號欄：{spec}")
    return out


def parse_ref(raw, shortmap, errors, line):
    """單一引用 'name:linespec' 或裸路徑。錯誤記進 errors，照樣回 Ref 佔位。"""
    raw = raw.strip()
    ref = Ref(raw=raw)
    name, spec = raw, ""
    if ":" in raw:
        head, tail = raw.rsplit(":", 1)
        if LINESPEC.fullmatch(tail.strip()):
            name, spec = head.strip(), tail.strip()
    if "/" in name or name.endswith(".md"):
        ref.path = name
    elif name in shortmap:
        ref.path = shortmap[name]
        ref.short = name
    else:
        errors.append((line, f"短名「{name}」不在章首宣告裡（引用原文：{raw}）"))
        return ref
    ref.semester = semester_of(ref.path)
    if not ref.short:
        ref.short = short_of(ref.path)
    if spec:
        try:
            ref.lines = parse_linespec(spec)
        except ValueError as e:
            errors.append((line, f"{raw}：{e}"))
    return ref


def split_refs(body):
    return [p for p in re.split(r"[;；]", body) if p.strip()]


def parse_chapter(path):
    """整檔解析。回 Chapter；語法錯誤收在 .errors，不丟例外。"""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    ch = Chapter(path=path, lines=text.split("\n"), markers=[], headings=[], errors=[])

    # 先掃出全部註解與行號
    raw_markers = []
    for m in COMMENT.finditer(text):
        start = text.count("\n", 0, m.start()) + 1
        end = text.count("\n", 0, m.end()) + 1
        raw_markers.append((start, end, m.group(1).strip(), m.span()))

    # frontmatter 範圍（審定狀態日後會放這裡）
    fm_end = 0
    if ch.lines and ch.lines[0].strip() == "---":
        for i, ln in enumerate(ch.lines[1:], start=2):
            if ln.strip() == "---":
                fm_end = i
                break

    # 章首宣告先解析，短名對照表要先有
    for start, end, inner, _ in raw_markers:
        if inner.startswith("來源檔："):
            mk = Marker(kind="decl", line=start, end_line=end, text=inner)
            for piece in split_refs(inner[len("來源檔："):]):
                ref = parse_ref(piece, {}, ch.errors, start)
                if ref.path:
                    short = short_of(ref.path)
                    if short in ch.shortmap and ch.shortmap[short] != ref.path:
                        ch.errors.append((start, f"短名「{short}」重複指向不同檔"))
                    ch.shortmap[short] = ref.path
                    mk.refs.append(ref)
                    mk.semesters.add(ref.semester)
            ch.decl = mk
            ch.markers.append(mk)
            break

    for start, end, inner, _ in raw_markers:
        if inner.startswith("來源檔："):
            continue
        if inner.startswith("來源："):
            mk = Marker(kind="source", line=start, end_line=end, text=inner)
            for piece in split_refs(inner[len("來源："):]):
                ref = parse_ref(piece, ch.shortmap, ch.errors, start)
                mk.refs.append(ref)
                if ref.semester:
                    mk.semesters.add(ref.semester)
        elif inner.startswith("@"):
            mk = Marker(kind="edition", line=start, end_line=end, text=inner)
            for part in inner[1:].split("+"):
                pm = EDITION_PART.fullmatch(part)
                if not pm:
                    ch.errors.append((start, f"版本標記欄位看不懂：{part.strip()}"))
                    continue
                sem, refraw = pm.group(1), pm.group(2)
                ref = parse_ref(refraw, ch.shortmap, ch.errors, start)
                mk.refs.append(ref)
                mk.semesters.add(sem)
                if ref.semester and ref.semester != sem:
                    ch.errors.append((start, f"版本標記寫 {sem}，但 {ref.raw} 是 {ref.semester} 的檔"))
        elif inner.startswith("!"):
            mk = Marker(kind="inconsistency", line=start, end_line=end, text=inner)
        elif inner.startswith("?"):
            mk = Marker(kind="confirm", line=start, end_line=end, text=inner)
        elif inner.startswith("校訂"):
            mk = Marker(kind="correction", line=start, end_line=end, text=inner)
        else:
            mk = Marker(kind="other", line=start, end_line=end, text=inner)
        ch.markers.append(mk)
    ch.markers.sort(key=lambda k: k.line)

    # 檔案存在與行號界內
    counts = {}
    for mk in ch.markers:
        for ref in mk.refs:
            if not ref.path:
                continue
            if ref.path not in counts:
                p = DOCS / ref.path
                counts[ref.path] = len(p.read_text(encoding="utf-8").splitlines()) if p.exists() else -1
            n = counts[ref.path]
            if n < 0:
                ch.errors.append((mk.line, f"來源檔不存在：{ref.path}"))
                continue
            for a, b in ref.lines:
                if b > n:
                    ch.errors.append((mk.line, f"{ref.raw}：行號超界（{ref.path} 只有 {n} 行）"))

    # 標題
    for i, ln in enumerate(ch.lines, start=1):
        if fm_end and i <= fm_end:
            continue
        hm = HEADING.match(ln)
        if hm:
            ch.headings.append((i, len(hm.group(1)), hm.group(2)))

    # 去掉註解後每行剩什麼（判斷「這行有沒有正文」用）
    stripped = COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text).split("\n")
    for i, ln in enumerate(stripped, start=1):
        if fm_end and i <= fm_end:
            continue
        if not ln.strip() or HEADING.match(ln) or UPDATED.match(ln) or RULE.match(ln):
            continue
        ch.content_lines.add(i)

    # 管轄區段：宣告／來源／版本標記管到下一個同類標記或下一個標題
    events = sorted(
        [(mk.line, "marker", mk) for mk in ch.markers if mk.governs]
        + [(h[0], "heading", None) for h in ch.headings]
    )
    n_lines = len(ch.lines)
    for idx, (ln, kind, mk) in enumerate(events):
        if kind != "marker":
            continue
        nxt = n_lines + 1
        for ln2, _, _ in events[idx + 1:]:
            if ln2 > mk.end_line:
                nxt = ln2
                break
        ch.segments.append((mk.end_line + 1, nxt - 1, mk))
    return ch


def ungoverned(ch):
    """沒被任何標記管到的正文行，回連續範圍列表 [(a,b), …]。"""
    governed = set()
    for a, b, _ in ch.segments:
        governed.update(range(a, b + 1))
    loose = sorted(ch.content_lines - governed)
    out = []
    for i in loose:
        if out and i == out[-1][1] + 1:
            out[-1][1] = i
        else:
            out.append([i, i])
    return [tuple(r) for r in out]


def cited_lines(ch):
    """每個來源檔被引用到的行集合（宣告不算引用）。回 {相對路徑: set}。"""
    out = {}
    for mk in ch.markers:
        if mk.kind not in ("source", "edition"):
            continue
        for ref in mk.refs:
            if not ref.path:
                continue
            s = out.setdefault(ref.path, set())
            for a, b in ref.lines:
                s.update(range(a, b + 1))
    return out
