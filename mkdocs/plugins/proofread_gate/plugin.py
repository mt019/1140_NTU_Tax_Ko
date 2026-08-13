"""校對中閘門：列在 pages 清單裡的頁，建站時整頁換成「校對中」告示，並排除出搜尋索引。

原始檔一字不動——這個閘門只在建站當下攔截輸出。校對完成後把該頁從
mkdocs.yml 的 proofread_gate.pages 清單移除，就恢復顯示。

merged 清單裡的合併頁（1121 租稅法總論的講義彙編）另行處理：被閘的單頁
對應的「## 第N週｜第M節」整節抽掉，換成一行告示。對應關係讀被閘頁
frontmatter 的「周次／節次」，不用日期比對（合併頁的日期有錯字）。
"""
import re
from pathlib import Path

from mkdocs.config import config_options
from mkdocs.plugins import BasePlugin

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
FIRST_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

NOTICE = (
    "!!! warning \"校對中\"\n"
    "    本頁內容尚未完成校對，暫不公開；校對完成後重新上線。\n"
)


def _meta_field(front: str, key: str):
    m = re.search(rf"^{key}[:：]\s*(.+?)\s*$", front, re.MULTILINE)
    return m.group(1) if m else None


class ProofreadGatePlugin(BasePlugin):
    config_scheme = (
        ("pages", config_options.Type(list, default=[])),
        ("merged", config_options.Type(list, default=[])),
    )

    def on_config(self, config):
        self.docs_dir = Path(config["docs_dir"]).resolve()
        self.gated = set(self.config["pages"])
        self.merged = set(self.config["merged"])
        # 每個合併頁所在目錄底下，被閘頁的（周次, 節次）集合。
        self.gated_sections = {}
        for merged_uri in self.merged:
            merged_dir = Path(merged_uri).parent
            pairs = set()
            for uri in self.gated:
                if Path(uri).parent != merged_dir:
                    continue
                text = (self.docs_dir / uri).read_text(encoding="utf-8")
                fm = FRONT_MATTER_RE.match(text)
                if not fm:
                    continue
                week = _meta_field(fm.group(1), "周次")
                sect = _meta_field(fm.group(1), "節次")
                if week and sect:
                    pairs.add((week, sect))
            self.gated_sections[merged_uri] = pairs
        return config

    def on_page_markdown(self, markdown, page, **kwargs):
        src_uri = getattr(page.file, "src_uri", "")

        if src_uri in self.gated:
            page.meta.setdefault("search", {})["exclude"] = True
            h1 = FIRST_H1_RE.search(markdown)
            title = h1.group(1) if h1 else Path(src_uri).stem.replace("_", " ")
            return f"# {title}（校對中）\n\n{NOTICE}"

        if src_uri in self.merged:
            page.meta.setdefault("search", {})["exclude"] = True
            for week, sect in self.gated_sections.get(src_uri, ()):
                markdown = self._drop_section(markdown, week, sect)
            return markdown

        return markdown

    @staticmethod
    def _drop_section(markdown, week, sect):
        pattern = re.compile(
            rf"^(## 第0*{re.escape(week)}週｜第0*{re.escape(sect)}節[^\n]*)\n.*?(?=^## |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        return pattern.sub(lambda m: m.group(1) + "（校對中）\n\n本節尚未完成校對，暫不公開。\n\n", markdown)
