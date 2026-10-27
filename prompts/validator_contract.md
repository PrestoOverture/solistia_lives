# Story contract check

For call `contract`, read all supplied numbered prose paragraphs against the
Story constraints below and supplied Style Specification. Judge the story as a
whole as well as each scene. Return `call: contract` and
`findings: [{paragraph, quote, kind, reason}]`; return an empty list if there are
no violations. Use only supplied paragraph ids. Quote the prose from the named
paragraph, copying a contiguous span exactly; use … to join interrupted spans.
Explain which part of the contract the passage violates.

Use these kinds:
- `pov`: close third person leaves the scene's viewpoint character, including
  access to another character's unobserved thoughts or feelings.
- `meta`: prose breaks the fictional viewpoint with commentary about its
  writing, sources, or production machinery. Humor should come from characters,
  not narrator commentary.
- `left_open`: the episode's incident or central question does not end within
  the story, leaving it open for a sequel.
- `scope`: another violation of the story constraints below or supplied style
  specification, including stakes beyond a local episode or returning enemies
  from the game.

## Story constraints

The episode must be self-contained: its incident begins and ends within the
story, with nothing left open for a sequel. Keep the stakes local; exclude
world-level threats and returning enemies from the game. New minor characters
and places are welcome, while canon facts about the travelers and world must hold.

New minor characters and places, quiet reflection, and sensory detail are
allowed. Respect the specification's distinction between guidance and hard
constraints; do not turn its approximate narration-to-dialogue ratio into a
hard rule. Judge the general contract, not preferred wording or personal taste.
