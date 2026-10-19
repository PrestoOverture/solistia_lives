from collections import Counter
from pathlib import Path

import yaml

from story_engine.kb import validate_input


def test_author_suite_validates_against_real_kb(monkeypatch):
    repo = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(repo)
    cases = yaml.safe_load((repo / "eval/test_suite.yaml").read_text())["cases"]
    assert len(cases) == 10
    assert len({case["id"] for case in cases}) == 10
    groups = Counter(tuple(sorted(case["characters"])) for case in cases)
    assert len(groups) == 5
    assert set(groups.values()) == {2}
    for case in cases:
        characters, location = validate_input(
            ",".join(case["characters"]), case["location"],
        )
        assert characters == case["characters"], case["id"]
        assert location == case["location"], case["id"]
