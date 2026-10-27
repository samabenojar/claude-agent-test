import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workflow:
    name: str
    prompt: str
    schema: dict
    allowed_tools: list[str]
    tools_dir: Path


def load_workflow(name: str, root: Path) -> Workflow:
    folder = root / "workflows" / name
    for f in ("workflow.json", "prompt.md", "schema.json"):
        if not (folder / f).is_file():
            raise FileNotFoundError(str(folder / f))
    cfg = json.loads((folder / "workflow.json").read_text())
    return Workflow(
        name=name,
        prompt=(folder / "prompt.md").read_text().strip(),
        schema=json.loads((folder / "schema.json").read_text()),
        allowed_tools=list(cfg["allowed_tools"]),
        tools_dir=root / "tools",
    )
