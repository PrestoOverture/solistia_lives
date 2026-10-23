For call: verdicts, verify only the supplied canon_fact claims against kb/ using
Read and Grep and the supplied sources (world premise and traveler identity cards).
Judge claims about the present against the post-ending state in the premise and
cards, while keeping the time asserted by historical claims.
Return call: verdicts and a verdicts list with exactly one entry per supplied
claim_id (the zero-based position in the extracted claims list).
Each entry has claim_id, evidence, reason, verdict, source, in that order.
Evidence is a verbatim excerpt from the cited source. Give a reason for every verdict.
- supported: canon supports the claim; a source is required.
- contradicted: canon contradicts the claim; a source is required.
- not_in_kb: canon does not establish the claim; use null for source and an empty
  evidence string if there is no relevant source. Explain the gap in reason.
  Absence is not contradiction.
Source is an existing repo-relative path under kb/, cards/<traveler>.md, or
prompts/world_premise.md. Include the kb/ prefix for KB files.
Do not reclassify or rewrite claims during the verdict call. Do not check simulation logs.
