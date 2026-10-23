import json
from pathlib import Path
import unicodedata

import frontmatter
import pytest

from story_engine.kb.entities import EntitySentence, entity_dictionary, prefilter


ROOT = Path(__file__).resolve().parents[2]
TESTSET = [json.loads(line) for line in (ROOT / "eval/validator_testset.jsonl").read_text().splitlines()]


@pytest.fixture(scope="module")
def dictionary():
    return entity_dictionary(ROOT / "kb")


@pytest.mark.parametrize("name,slug", [
    ("Throné", "throne"), ("Throne", "throne"), ("Osvald V. Vanstein", "osvald"),
    ("THRONÉ", "throne"), ("Throne\u0301", "throne"),
])
def test_real_kb_aliases(dictionary, name, slug):
    assert prefilter(name, dictionary) == [EntitySentence(text=name, entities=[slug])]


def test_real_kb_dictionary_contains_all_frontmatter_names(dictionary):
    for path in (ROOT / "kb").rglob("*.md"):
        metadata = frontmatter.load(path).metadata
        for name in [metadata.get("name", ""), *metadata.get("aliases", [])]:
            folded = unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode().strip()
            if folded:
                assert path.stem in dictionary[folded]
    assert dictionary["throne"] == {"throne"}
    assert dictionary["osvald v. vanstein"] == {"osvald"}


def test_default_kb_root(dictionary, monkeypatch):
    monkeypatch.chdir(ROOT)
    assert entity_dictionary() == dictionary


def test_real_kb_mixed_prose_and_initial(dictionary):
    text = (
        "The tavern smelled of ale. Osvald V. Vanstein set down his cup. "
        "Rain tapped the glass. Throné waved to Agnea, and Osvald nodded."
    )
    assert prefilter(text, dictionary) == [
        EntitySentence(text="Osvald V. Vanstein set down his cup.", entities=["osvald"]),
        EntitySentence(text="Throné waved to Agnea, and Osvald nodded.", entities=["throne", "agnea", "osvald"]),
    ]
    assert prefilter("the tavern smelled of ale", dictionary) == []


@pytest.mark.parametrize("row", TESTSET, ids=lambda row: str(row["id"]))
def test_every_validator_testset_entry_is_kept_whole(dictionary, row):
    result = prefilter(row["text"], dictionary)
    assert len(result) == 1
    assert isinstance(result[0], EntitySentence)
    assert result[0].text == row["text"]
    assert result[0].entities


def test_whole_words_possessives_and_repeated_mentions(dictionary):
    assert prefilter("Thrones Osvalds preThrone throne_suffix", dictionary) == []
    text = "Throné's cup stood beside THRONE’s coat and Osvald's hat; Throné waited."
    assert prefilter(text, dictionary) == [EntitySentence(text=text, entities=["throne", "osvald"])]


def test_longest_overlapping_alias_wins_and_shared_alias_is_deterministic():
    dictionary = {
        "new delsta": {"city"}, "delsta": {"short"}, "new": {"word"},
        "shared": {"zeta", "alpha"},
    }
    text = "Shared welcomed New Delsta and shared."
    assert prefilter(text, dictionary) == [EntitySentence(text=text, entities=["alpha", "zeta", "city"])]
    # The longer alias wins even when it begins later in the text.
    assert prefilter("a b c", {"a b": {"short"}, "b c": {"equal"}, "b c d": {"long"}})[0].entities == ["short"]
    assert prefilter("a b c d", {"a b": {"short"}, "b c d": {"long"}})[0].entities == ["long"]


def test_overlapping_candidate_after_rejected_partial_word():
    text = "xa a a."
    assert prefilter(text, {"a a": {"entity"}}) == [EntitySentence(text=text, entities=["entity"])]


@pytest.mark.parametrize("text,expected", [
    ('"Ready?" Osvald asked. Rain fell.', '"Ready?" Osvald asked.'),
    ('“Osvald waited. Then he left.” Rain fell.', '“Osvald waited. Then he left.”'),
    ("'Osvald waited. Then he left.' Rain fell.", "'Osvald waited. Then he left.'"),
    ('Osvald nodded. "Yes. Of course."', 'Osvald nodded. "Yes. Of course."'),
    ('Osvald nodded.\n\n"Rain fell."', 'Osvald nodded.'),
])
def test_quoted_dialogue_and_paragraph_boundaries(dictionary, text, expected):
    assert prefilter(text, dictionary) == [EntitySentence(text=expected, entities=["osvald"])]


def test_empty_inputs():
    assert prefilter("", {"osvald": {"osvald"}}) == []
    assert prefilter("Osvald waited.", {}) == []
