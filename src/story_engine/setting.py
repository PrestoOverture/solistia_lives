"""Render repo simulation prompts with the world's premise."""

from pathlib import Path

import yaml

DEFAULT_PREMISE = Path("prompts/default_premise.yaml")


def load_premise(root: Path, setting: Path | None) -> dict[str, str]:
    path = root / DEFAULT_PREMISE if setting is None else setting / "premise.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def render_prompt(root: Path, filename: str, setting: Path | None = None) -> str:
    template = (root / "prompts" / filename).read_text(encoding="utf-8")
    if "{{premise}}" not in template:
        return template
    premise = load_premise(root, setting)
    ending = premise.get("ending", "")
    return template.replace("{{ending}}", f" {ending}" if ending else "").replace(
        "{{premise}}", premise[Path(filename).stem]
    )
