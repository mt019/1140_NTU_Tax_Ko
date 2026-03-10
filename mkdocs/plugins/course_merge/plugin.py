import re
from pathlib import Path

from mkdocs.plugins import BasePlugin


WEEK_RE = re.compile(r"^W\d+_.+\.md$")
FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n?", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})(\s+.*)$", re.MULTILINE)
FIRST_H1_RE = re.compile(r"\A\s*#\s+.+?(?:\n+|$)")


class CourseMergePlugin(BasePlugin):
    def on_config(self, config):
        docs_dir = Path(config["docs_dir"])
        for course_dir in docs_dir.rglob("*"):
            if not course_dir.is_dir():
                continue
            index_file = course_dir / "index.md"
            if not index_file.exists():
                continue

            week_files = sorted(
                [p for p in course_dir.iterdir() if p.is_file() and WEEK_RE.match(p.name)]
            )
            if not week_files:
                continue

            merged = []
            for week_file in week_files:
                merged.append(self._transform_week(week_file))

            merged_path = course_dir / "_merged_course.md"
            merged_path.write_text("\n\n---\n\n".join(filter(None, merged)).strip() + "\n", encoding="utf-8")

        return config

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
