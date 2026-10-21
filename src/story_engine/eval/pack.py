"""Blind story packets, with provenance kept only in the repository."""

from pathlib import Path
from random import shuffle
import re
import secrets
from typing import Literal

from pydantic import BaseModel, RootModel

from story_engine.runs import RunMeta


class StorySource(BaseModel):
    run_id: str
    mode: Literal["simulation", "baseline"]


class PacketKey(RootModel[dict[str, dict[str, StorySource]]]):
    """Packet ID -> story filename -> source run and mode."""


def pack_runs(run_ids: list[str], blind_root: Path) -> tuple[list[Path], Path]:
    repo = Path.cwd().resolve()
    destination = blind_root.expanduser().resolve()
    if destination.is_relative_to(repo):
        raise ValueError("blind_root must be outside the repository")
    if len(run_ids) not in (1, 2):
        raise ValueError("pack requires one or two run IDs")

    # Read every input before creating any output, including for a missing second story.
    stories = []
    metadata = []
    for run_id in run_ids:
        if Path(run_id).name != run_id or run_id in ("", ".", ".."):
            raise ValueError(f"Invalid run ID: {run_id!r}")
        run_dir = repo / "runs" / run_id
        stories.append((run_dir / "story.md").read_bytes())
        meta = RunMeta.model_validate_json((run_dir / "meta.json").read_bytes())
        if meta.run_id != run_id:
            raise ValueError(f"Run ID does not match meta.json: {run_id}")
        metadata.append(meta)
    pairwise = len(run_ids) == 2
    prompt_name = "judge_pairwise.md" if pairwise else "judge_absolute.md"
    prompt = (repo / "eval" / prompt_name).read_bytes()

    # Refuse identifying content rather than silently changing a story or judge prompt.
    identifiers = [*run_ids, *(meta.created_at.split("T")[0] for meta in metadata)]
    for content in [*stories, prompt]:
        text = content.decode("utf-8")
        if any(value in text for value in identifiers) or re.search(
            r"\b(?:baseline|simulation)\b", text, re.IGNORECASE,
        ):
            raise ValueError("Packet input contains run-identifying content")

    order = list(range(len(run_ids)))
    if pairwise:
        shuffle(order)
    orders = [order, order[::-1]] if pairwise else [order]
    names = ["story_A.md", "story_B.md"] if pairwise else ["story.md"]
    key = PacketKey({})
    packets = []
    destination.mkdir(parents=True, exist_ok=True)
    for indices in orders:
        packet = destination / secrets.token_hex(16)
        packet.mkdir()
        key.root[packet.name] = {}
        for name, index in zip(names, indices):
            (packet / name).write_bytes(stories[index])
            key.root[packet.name][name] = StorySource(
                run_id=run_ids[index], mode=metadata[index].mode,
            )
        (packet / "prompt.md").write_bytes(prompt)
        packets.append(packet)

    key_dir = repo / "eval" / "blind"
    key_dir.mkdir(parents=True, exist_ok=True)
    key_path = key_dir / f"{secrets.token_hex(16)}.json"
    with key_path.open("x", encoding="utf-8") as file:
        file.write(key.model_dump_json(indent=2))
    return packets, key_path
