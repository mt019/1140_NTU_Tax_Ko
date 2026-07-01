import re
from pathlib import Path
from urllib.parse import quote

from mkdocs.plugins import BasePlugin


# Include normal week files like W03_0310.md and make-up classes like W03補課_0314.md.
WEEK_RE = re.compile(r"^W\d+(?:[^_]*)?_.+\.md$")
FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n?", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})(\s+.*)$", re.MULTILINE)
FIRST_H1_RE = re.compile(r"\A\s*#\s+.+?(?:\n+|$)")
MERGED_INCLUDE_RE = re.compile(r'^\s*--8<--\s+"[^"]*/_merged_course\.md"\s*$', re.MULTILINE)
COURSE_NOISE_RE = re.compile(r"(整理版|整理|有缺前面|沒去|改週三|材料|短)$")
PAGES_TITLE_RE = re.compile(r'^\s*title:\s*["\']?(.+?)["\']?\s*$', re.MULTILINE)


class CourseMergePlugin(BasePlugin):
    def on_config(self, config):
        self.docs_dir = Path(config["docs_dir"]).resolve()
        self.course_sections = {}
        self.course_urls_by_title = {}

        for course_dir in self.docs_dir.rglob("*"):
            if not course_dir.is_dir():
                continue

            index_file = course_dir / "index.md"
            if not index_file.exists():
                continue

            week_files = sorted(
                [
                    path
                    for path in course_dir.iterdir()
                    if path.is_file()
                    and WEEK_RE.match(path.name)
                    and "短" not in path.stem
                ]
            )
            if not week_files:
                continue

            pages_file = course_dir / ".pages"
            if pages_file.exists():
                title_match = PAGES_TITLE_RE.search(pages_file.read_text(encoding="utf-8"))
                if title_match:
                    rel_course = course_dir.resolve().relative_to(self.docs_dir).as_posix().rstrip("/")
                    self.course_urls_by_title[title_match.group(1).strip()] = quote(f"{rel_course}/", safe="/")

            merged = [self._transform_week(week_file) for week_file in week_files]
            rel_index = index_file.resolve().relative_to(self.docs_dir).as_posix()
            self.course_sections[rel_index] = "\n\n---\n\n".join(filter(None, merged)).strip()

        return config

    def on_page_markdown(self, markdown, page, **kwargs):
        src_uri = getattr(page.file, "src_uri", "")
        merged = self.course_sections.get(src_uri)
        if not merged:
            return markdown

        cleaned = MERGED_INCLUDE_RE.sub("", markdown).rstrip()
        if not cleaned:
            return merged + "\n"
        return f"{cleaned}\n\n{merged}\n"

    def on_nav(self, nav, **kwargs):
        self._prune_course_week_pages(getattr(nav, "items", []))
        return nav

    def _prune_course_week_pages(self, items):
        for item in items:
            title = getattr(item, "title", None)
            if title in self.course_urls_by_title:
                item.url = self.course_urls_by_title[title]

            children = getattr(item, "children", None)
            if not children:
                continue

            index_child = next(
                (
                    child
                    for child in children
                    if getattr(getattr(child, "file", None), "src_uri", None) in self.course_sections
                ),
                None,
            )
            if index_child:
                filtered = []
                for child in children:
                    src_uri = getattr(getattr(child, "file", None), "src_uri", None)
                    if src_uri:
                        same_dir = Path(src_uri).parent == Path(index_child.file.src_uri).parent
                        name = Path(src_uri).name
                        if same_dir and WEEK_RE.match(name):
                            continue
                    filtered.append(child)
                item.children = filtered

            self._prune_course_week_pages(children)

    def _transform_week(self, path: Path):
        text = path.read_text(encoding="utf-8")
        text = FRONT_MATTER_RE.sub("", text, count=1)
        text = FIRST_H1_RE.sub("", text, count=1).lstrip()
        text = HEADING_RE.sub(lambda m: "#" + m.group(1) + m.group(2), text)

        title = self._clean_week_title(path.stem)
        section = [f"## {title}"]
        if text:
            section.append(text.rstrip())
        return "\n\n".join(section)

    def _clean_week_title(self, stem: str) -> str:
        stem = stem.replace("-長", "")
        parts = stem.split("_", 1)
        if len(parts) != 2:
            return stem.replace("_", " ")

        week_code, remainder = parts
        remainder = COURSE_NOISE_RE.sub("", remainder).strip("-_ ")
        remainder = re.sub(r"-(\d+)$", r"-\1", remainder)
        return f"{week_code} {remainder}".strip()
