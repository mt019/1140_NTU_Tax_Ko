import re
from pathlib import Path

from mkdocs.plugins import BasePlugin


WEEK_RE = re.compile(r"^W\d+_.+\.md$")
FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n?", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})(\s+.*)$", re.MULTILINE)
FIRST_H1_RE = re.compile(r"\A\s*#\s+.+?(?:\n+|$)")
MERGED_INCLUDE_RE = re.compile(r'^\s*--8<--\s+"[^"]*/_merged_course\.md"\s*$', re.MULTILINE)
COURSE_NOISE_RE = re.compile(r"(整理版|整理|有缺前面|沒去|改週三|材料|短)$")


class CourseMergePlugin(BasePlugin):
    def on_config(self, config):
        self.docs_dir = Path(config["docs_dir"]).resolve()
        self.course_sections = {}

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
            children = getattr(item, "children", None)
            if not children:
                continue

            direct_index_child = next(
                (
                    child
                    for child in children
                    if getattr(getattr(child, "file", None), "src_uri", None)
                    and Path(child.file.src_uri).name == "index.md"
                ),
                None,
            )
            if direct_index_child and hasattr(item, "url") and getattr(direct_index_child, "url", None):
                item.url = direct_index_child.url

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
                        if same_dir and name == "index.md":
                            continue
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
