Extract claims from the supplied id-tagged sentences. Return structured output
with a claims list. Each claim has sentence_id (the input ID), quote (the source
passage), claim (the assertion), type, and entities (KB slugs).

Classify each assertion by its meaning in context:
- canon_fact: an assertion about established world lore or history, including
  factual dialogue. Only these claims will be checked against canon later.
- invented_detail: a new story detail, such as a bartender or a tavern name.
- opinion_or_joke: opinions, jokes, irony, and a character's mistaken belief.
  Do not turn an ironic statement or mistaken belief into a canon assertion.

A sentence can yield multiple claims. Preserve its sentence_id on every claim.
Use only entity slugs present in the KB; do not invent slugs for new details.
Read or search the KB if needed. Do not verify canon or issue verdicts here.

Preserve the time each claim asserts, including now, still, had once, and before
the journey.
