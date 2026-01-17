import json
from pathlib import Path
from typing import List, Optional

from src.services.meme.templates.models import Template

class TemplateLoader:
    def __init__(self, templates_file: Optional[Path] = None):
        if templates_file is None:
            # Assume running from root
            self.templates_file = Path.cwd() / "data" / "templates.json"
        else:
            self.templates_file = templates_file

        self.templates: List[Template] = []
        self._load_templates()

    def _load_templates(self):
        if not self.templates_file.exists():
            return

        with open(self.templates_file, "r") as f:
            data = json.load(f)
            # data is {"templates": [...]}
            self.templates = [Template(**t) for t in data.get("templates", [])]

    def get_template(self, template_id: str) -> Optional[Template]:
        for template in self.templates:
            if template.template_id == template_id:
                return template
        return None

    def list_templates(self) -> List[Template]:
        return self.templates

    def filter_templates(
        self,
        format: Optional[str] = None,
        include_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
    ) -> List[Template]:
        filtered = self.templates

        if format:
            filtered = [t for t in filtered if t.format == format]

        if include_tags:
            # Filter: Keep if template has ANY of the include_tags
            filtered = [
                t for t in filtered
                if set(t.tags) & set(include_tags)
            ]

        if exclude_tags:
            # Filter: Exclude if template has ANY of the exclude_tags
            filtered = [
                t for t in filtered
                if not (set(t.tags) & set(exclude_tags))
            ]

        return filtered
