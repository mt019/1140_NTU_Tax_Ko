import re
from pathlib import Path

from mkdocs.plugins import BasePlugin


WEEK_RE = re.compile(r"^W\d+_.+\.md$")
FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n?", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})(\s+.*)$", re.MULTILINE)
FIRST_H1_RE = re.compile(r"\A\s*#\s+.+?(?:\n+|$)")
MERGED_INCLUDE_RE = re.compile(r'^\s*--8<--\s+"[^"]*/_merged_course\.md"\s*$', re.MULTILINE)


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
                [path for path in course_dir.iterdir() if path.is_file() and WEEK_RE.match(path.name)]
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

    def _transform_week(self, path: Path):
        text = path.read_text(encoding="utf-8")
        text = FRONT_MATTER_RE.sub("", text, count=1)
        text = FIRST_H1_RE.sub("", text, count=1).lstrip()
        text = HEADING_RE.sub(lambda m: "#" + m.group(1) + m.group(2), text)

        title = path.stem.replace("-長", "").replace("_", " ")
        section = [f"## {title}"]
        if text:
            section.append(text.rstrip())
        return "\n\n".join(section)
