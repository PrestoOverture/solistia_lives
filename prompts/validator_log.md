# Log check

For call `log`, walk the supplied prose paragraphs in order, checking each against
this act's scene beats and transition events. Return `call: log` and
`paragraphs: [{id, lines}]`: exactly one entry for every supplied paragraph id.
In each paragraph, list every spoken line and every act in `lines`; use an empty
list for pure description. Do not walk the event log and select lines from it.

For each line, first quote the prose from that paragraph, never the event content,
then give actor, events (the event ids behind the line), reason, and verdict
(`supported` or `contradicted`). Leave scene null; code attaches the scene to contradictions.
A quote is a contiguous span copied exactly from that paragraph. When narration
interrupts a spoken line, quote the spoken parts joined with … .

Every spoken line and every act in the prose must match an event in this act's log
with the same speaker, same order, and same meaning. Shortening or paraphrasing
dialogue is fine. Sensory detail and small physical business are fine. A line or
move with no event behind it is contradicted. Event content in the log is a fact,
not prose. Supported entries must cite at least one event. Cite only event ids
from the supplied beats and transition events.
