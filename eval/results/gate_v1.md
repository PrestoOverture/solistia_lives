# MVP Gate v1: absolute screening (5.2)

Date: 2026-10-27. Stories: 5.1 baseline suite `runs/suites/87fea79198ae19fab1878fb4ee556795.json`. The judge was Codex `gpt-6.1-sol` at effort high, one session per packet, prompt `eval/judge_absolute.md`, packets in `~/blind_packets/` (keys in `eval/blind/`). Rollout logs show every command stayed inside its packet.

Floors (prd §6.1): Lore ≥ 4, Voice ≥ 3, Readability ≥ 3, total ≥ 10.

**Judge result: 6/10 pass** (gate needs 8/10). Three of the four failures rest on a lore deduction that the KB contradicts (audit below), so the author's read (5.3) decides.

| Case | Run | Packet | Lore | Voice | Read. | Total | Judge | Audit |
|---|---|---|---|---|---|---|---|---|
| agnea_throne_1 | `20261027-080638-aa4cc5` | `db7e23e8` | 5 | 3 | 3 | 11 | PASS | Real defect the validator missed: the prose says "true to the knowledge base description" (story line 39), an engine term leaking into the story. |
| agnea_throne_2 | `20261027-080638-4b9b73` | `212d9795` | 3 | 4 | 4 | 11 | FAIL | Judge wrong: `kb/world/factions/blacksnakes.md` says "Mother and Father killed Marietta", so "Mother killed" is not an error. |
| castti_partitio_1 | `20261027-081152-1da64f` | `7738d4c8` | 5 | 4 | 3 | 12 | PASS |  |
| castti_partitio_2 | `20261027-081332-2b2248` | `3896259a` | 4 | 4 | 3 | 11 | PASS |  |
| hikari_ochette_1 | `20261027-080638-ec7d3a` | `aab1d49c` | 5 | 4 | 3 | 12 | PASS |  |
| hikari_ochette_2 | `20261027-081134-e569d1` | `eab66115` | 2 | 3 | 3 | 8 | FAIL | Judge wrong: `kb/characters/hikari/benkei.md` has Benkei survive the coup and fight beside Hikari when Ku is liberated; a living Benkei is canon. |
| osvald_temenos_1 | `20261027-080638-17b661` | `99fcb97a` | 5 | 4 | 3 | 12 | PASS |  |
| osvald_temenos_2 | `20261027-080638-78c219` | `1f2c060d` | 5 | 4 | 3 | 12 | PASS | Real scope issue: the mystery is left open ("compare findings in three days"), against prd §3 (nothing left open for a sequel). |
| osvald_temenos_agnea_1 | `20261027-081413-fd5cf1` | `e9a8ef53` | 3 | 3 | 3 | 9 | FAIL | Unverifiable: the KB gives no direction from New Delsta to Conning Creek. The POV switch (readability note) is real. |
| osvald_temenos_agnea_2 | `20261027-081451-90cff5` | `f321bf74` | 3 | 3 | 3 | 9 | FAIL | Judge wrong: `kb/world/lore/grand_gala.md` makes the Festival of Grace the centerpiece of the Grand Gala and lists it as an alias. |

## Recurring judge notes (for 5.3)

- Voice: Osvald's 'variables/equations' routine and Agnea tripping are repeated as character tics, and closing dialogue drifts into generic counselling.
- Readability: endings over-explain the emotional arc (repeated reassurance, smiles, sunlight imagery). Seven stories score 3.
- Length: 4/10 fall outside 2,000-3,000 words (history 2026-10-27, 5.1).
- Validator false negatives (architecture §12 Q7): the engine-term leak in agnea_throne_1 and the open-ended osvald_temenos_2 passed validation.

## Judge notes

### agnea_throne_1 (5/3/3)
- **lore:** Agnea's recollections of the Festival of Grace, the Stage of the Moon and Sun at the Shrine of Ul'sterra, and the Song of Hope fit her Merry Hills finale; Throné's memory of the chain around her neck also fits her history. The visit preserves the travelers' friendship after defeating Vide and introduces no returning enemy or renewed world threat. I cannot verify the claim that Agnea's mother wrote about the knife peddler in her journal, so I do not count it as an error.
- **voice:** Throné's terse 'I'd leave' and watchfulness around the crowd contrast recognizably with Agnea's enthusiastic invitations and affection for the performers. However, Agnea's repeated tripping and needing to be caught overemphasize helplessness for an accomplished dancer, while speeches such as 'I brought you halfway across the Crestlands so you'd know there's a place for you' sound like generic emotional guidance. Throné's repeated internal descriptions of Agnea as 'the girl' and 'too earnest' make their friendship feel more one-sided and protective than the strongest versions of these voices.
- **readability:** The honey pooling in the paper cones, fading festival noise on the climb, and sunlight across the stage give the outing a clear sensory setting within Throné's close perspective. However, 'true to the knowledge base description' abruptly breaks immersion, and repeated explanations of belonging, earnestness, and the stage's significance overstate an emotional change that the final decision not to count the exits conveys more effectively. The episode resolves its small emotional arc, but its approximately 1,935 words fall slightly below the requested 2,000–3,000-word scope.

### agnea_throne_2 (3/4/4)
- **lore:** Throné's orchard recollection incorrectly says that 'Mother killed' Marietta: Father killed Marietta, making this an error in an established backstory event. The absence of Throné's collar, Garud's tailoring, and the peaceful Cropdale reunion otherwise suit the post-ending setting; the invented villagers and baking contest are permissible additions.
- **voice:** Throné's clipped 'I'll watch ... But from the back' and teasing 'You didn't trip' contrast convincingly with Agnea's eager introductions and affection for home, while Garud's assessment of the dress gives him a recognizable craftsman's perspective. Agnea's repeated stumbling becomes an overused character cue, and the orchard exchange about peace occasionally sounds more like general reassurance than these particular friends speaking.
- **readability:** The pie contest's 'A pie should know what it is' supplies welcome humor and local texture, and Throné's movement from checking exits to choosing to stay gives the self-contained visit a satisfying emotional arc. The close third-person perspective is steady, but repeated explanations of the village's uncomplicated happiness and the closing sequence of smiles soften the impact through repetition. Small awkwardnesses such as 'back to a oak tree' also keep the prose below a fully polished novel standard.

### castti_partitio_1 (5/4/3)
- **lore:** Castti's memories of Healeaks and Trousseau's poison rain, and Partitio's references to Giff, Roque, and the railway, fit their completed journeys; the mine sickness is a local incident resolved within the episode. I cannot confidently verify the Mount Fiatsuro geography or the tavern's eight-traveler portrait, so I have not counted either as a canon error.
- **voice:** Castti's methodical examinations and insistence that closing the mine is 'Better than killing the miners' suit her practical compassion, while Partitio's 'These are my people' and offer of funding express his generous merchant outlook. Their roles and occasional diction distinguish them, though the repeated exchanges of thanks and 'The world's lucky to have you' make the closing dialogue more generic than their strongest game dialogue.
- **readability:** The opening count of sick miners and the greenish-yellow crust give the investigation a clear progression and concrete atmosphere, with sustained close third-person narration through Castti. The roughly 1,900-word episode misses the requested 2,000-word minimum, and the rapid improvement from blue lips and coughing blood to recovery after tea and tinctures feels too convenient. Repeated gratitude, offers of help, and mutual reassurance prolong the sunset ending after the incident is already resolved.

### castti_partitio_2 (4/4/3)
- **lore:** Castti's memories of Malaya and Trousseau, and Partitio's Oresrush ties and railway interests, fit their histories; the quarry outbreak is an allowed local incident without returning enemies. Partitio's 'white fedora' is a minor visual mismatch with his usual dark hat. I cannot establish whether 'Skybalm' is a canonical item, so I have not counted it as an error.
- **voice:** Partitio's 'What do you need?' and his argument that wealth is worthless if workers die combine his recognizable drawl, generosity, and commercial idealism, while Castti's calm bedside instructions and firm confrontation with the foreman suit her compassionate resolve. Their late-night exchange becomes more generic in lines such as 'You're going to change Solistia' and 'You've got a good head for problems,' and the closing claim that she has not felt supported since Healeaks underplays her completed journey with her friends.
- **readability:** The opening grit, iron taste, and rasping breath establish a tangible setting, and the close third-person viewpoint stays with Castti through a clear investigative sequence. The leap from the new hires to a visually identified mercury seam and an immediately available treatment makes the central problem feel too easily solved, while the story ends before showing the patients' response. Repeated warmth-and-sunlight imagery ('stepping into sunlight after a long winter,' 'warm as summer sun') and explanatory praise of Partitio make parts of the prose feel formulaic.

### hikari_ochette_1 (5/4/3)
- **lore:** Hikari's kingship in Ku, Ochette's ties to Beasting Village and Toto'haha, and her 'Hikarin' nickname fit the characters and setting without clear canon contradictions. Her recognition that his 'old, pungent shadow' is gone suits the post-ending premise, and the hunt resolves a local problem without reviving an enemy or introducing a world-level threat. I cannot establish whether the sand tyrant is a canonical creature, so I treat it as an allowed original addition rather than an error.
- **voice:** Ochette's description of the predator as 'just meat with teeth,' her scent-based understanding of Hikari, and her eagerness to feed people give her a recognizable perspective. Hikari's 'Pray lead the way' and 'Though I confess, I am unused to being bait' convey his courteous restraint and gentle humor, distinct from her blunt enthusiasm. Repeated 'Heh heh!' interjections lean on a catchphrase, while his extended explanation about duty becomes somewhat generic and sits awkwardly with a hunt undertaken to help his own garrison.
- **readability:** The close Ochette viewpoint, scent imagery, and final image of a friend who 'smelled like peace' give the self-contained episode warmth and cohesion. The action relies on familiar phrases such as 'moved like water, like wind' and 'faster than anything that size had a right to move,' while repeated attack-and-dodge exchanges make the middle feel formulaic. The garrison described as 'three days' ride south' is reached by sunset on foot alongside exhausted horses, with no explanation for the compressed journey, which weakens the otherwise clear pacing and sense of distance.

### hikari_ochette_2 (2/3/3)
- **lore:** Hikari describes "Benkei and the captains" as his present loyal support, but Benkei dies during the fall of Ku in Hikari's first chapter; treating him as a living retainer is a major continuity contradiction. Hikari's kingship, his friendship with Ochette, and the contained hunting incident otherwise fit the post-ending setting.
- **voice:** Ochette's "Hikarin," scent descriptions, and enthusiasm for fresh meat distinguish her from Hikari's restrained, formal speech. However, "You're just desperate and untrained. That's fixable" sounds like generic counseling, while Hikari's repeated threats against the trapper and extended explanations of compassion make their characterization less convincing.
- **readability:** The volcanic grit, canyon wind, and meat roasting on flat stones give the episode a clear physical setting, and the injured golt provides an understandable, resolved conflict. The trapper's quick transformation into a grateful student feels convenient, and the closing reflections repeatedly explain the same lesson through "true strength," "the first step," and "the measure of strength," making the ending feel formulaic and overextended.

### osvald_temenos_1 (5/4/3)
- **lore:** Harvey's laboratory beneath Montwise's library, Elena staying with Clarissa, and the broken Moonshade Order fit the post-ending setting; the investigation revives no defeated enemy and introduces no world-level threat. I cannot confirm Regulus's telescope and workshop as canon, so I have not counted that detail as an error.
- **voice:** Temenos's teasing about finding a book 'In a library' and his gently coercive appeal to his inquisitorial authority distinguish him from Osvald's terse replies and scrutiny of the treatise's methodology. Osvald's insistence that helping was 'logical' feels somewhat mechanical, while his extended dawn speech is less characteristic than his quieter concern for Elena.
- **readability:** The creaking stairs, leather bindings, and return to Elena's lesson give the episode a clear setting and a satisfying frame. Repeated echoes such as 'Retired,' 'Flights of fancy,' and 'An accident' make the questioning predictable, and the safety-rail observation and journal do not justify the characters' certainty that the Order murdered Cornelius. Explanations such as 'Guilt was a variable that defied easy calculation' and the repeated shadow-and-dawn closing imagery make the emotional resolution feel formulaic.

### osvald_temenos_2 (5/4/3)
- **lore:** Harvey is treated as dead, Elena as safe, and the Moonshade Order as broken, consistent with the required post-ending setting; the new scholars and archival investigation are permissible additions. I cannot confirm the claim that Gratton's Hypothesis originated from observing the Pit of D'arqest or the nine-year research chronology, so I treat those details as uncertain rather than counting them as canon errors.
- **voice:** Temenos's opening 'My, my,' teasing use of 'Detective Vanstein,' and probing distinction between justice and vengeance give him a recognizable inquisitor's voice, while Osvald's 'Not ransacking. Reading.' establishes his blunt reserve. Osvald's willingness to seek truth instead of punishment suits his completed journey, although the repeated probability calculations and equation metaphors reduce some of his emotional complexity to a familiar scholarly mannerism.
- **readability:** The parchment, beeswax, autumn light, and cathedral bells establish an appealing atmosphere, and the research discussion is easy to follow. However, repeated suspect summaries and equation imagery make the dialogue-heavy exposition feel mechanical, and at approximately 1,562 words the episode falls below the requested 2,000–3,000 words. The promise to compare findings in three days and the final insistence that 'He would find it' leave the central mystery unresolved, so this reads as an opening chapter rather than the required self-contained episode.

### osvald_temenos_agnea_1 (3/3/3)
- **lore:** Calling Conning Creek 'two days’ travel north' of New Delsta is a geographical error: Conning Creek lies southwest of New Delsta. The peaceful performance and reunion otherwise fit the post-ending setting without reviving enemies or introducing a world-level threat. I am uncertain whether 'The Song of Hope. Her mother’s song' correctly identifies the song’s origin, so I have not counted that attribution as another error.
- **voice:** Temenos’s 'material witness' to 'cowardice' joke and Agnea’s excited appeals to 'Mama' give them recognizable voices, while Osvald’s terse replies distinguish him from both. However, 'Your execution was precise' and 'Sentiment is a logical response' exaggerate Osvald’s scholarly reserve into mechanical speech, and his surprise at Agnea’s competence feels ungenerous after their shared journey. Repeated jokes about her tripping and his grunting reduce otherwise affectionate interactions to a few familiar traits.
- **readability:** The opening smell of 'greasepaint and roses' establishes the theater effectively, and Osvald leaning forward when the stage goes dark gives the performance an engaging emotional beat. However, the opening uses Agnea’s private thoughts before switching to Osvald’s viewpoint, breaking the requested single-character perspective, and the extended lobby conversation slows the resolution. Repeated smiles, silences, 'Hmm' replies, and emphatic fragments such as 'Radiant' and 'Pride' make the prose feel formulaic despite its clear, warm ending.

### osvald_temenos_agnea_2 (3/3/3)
- **lore:** Agnea's canonical competition is the Grand Gala in Merry Hills, but the story repeatedly calls her victory winning the 'Festival of Grace,' confusing the event's name even though it also mentions the Grand Gala correctly. Merry Hills, the Stage of the Moon and Sun, and the quiet episode after the Moonshade Order's fall otherwise fit the setting; Elena expecting Osvald's visit can reasonably be a subsequent development in their relationship.
- **voice:** Temenos's 'I've been on my feet for at least twenty minutes today' and his distinction between interrogation and conversation capture his teasing, perceptive manner, while Agnea's affectionate hug fits her warmth. Osvald's repeated 'variables,' 'data, not optimism,' and 'collective variable' turn his scholarly reserve into an overextended mathematics routine, and the long exchanges about choosing one's path give the characters a shared, generic counseling register.
- **readability:** The opening smell of lamp oil and roses establishes the theater clearly, and Agnea incorporating her stumble into the dance gives the episode a satisfying payoff. Repeated reassurance, repeated declarations of a 'real' smile or laugh, and the closing sequence of equations, variables, questions, and roads overexplain the emotional arc. At 3,227 whitespace-delimited words including the title, it exceeds the requested 2,000–3,000 words, and the lengthy dressing-room conversations crowd out the requested emphasis on narration.

## 5.3 Author read (2026-10-28, partial: the four judge failures)

| Case | Judge | Author | Disagreement |
|---|---|---|---|
| agnea_throne_2 | FAIL (lore 3) | **PASS, with reservations** | Lore: the judge was wrong (KB: Sebastian cuts Marietta's throat, Mother finishes her). Author's reservations: Agnea nearly falls 4 times, so clumsiness reads as a disorder rather than a trait; the ending's run of explanations of peace and friendship undercuts the earlier restraint. Over-emphasis, not hallucination. |
| hikari_ochette_2 | FAIL (lore 2, Benkei dead) | **PASS** | Judge wrong: `kb/characters/hikari/benkei.md` has Benkei alive at Ku's liberation. Re-judged by the author on 2026-10-28: no major lore error. |
| osvald_temenos_agnea_1 | FAIL (3/3/3) | **FAIL** | Agrees: the story slips into Agnea's interior monologue, breaking close third person from one POV per scene (prd §5). |
| osvald_temenos_agnea_2 | FAIL (3/3/3) | **PASS** | The judge was wrong on Festival of Grace vs Grand Gala (KB aliases), but mixing the two names invites the confusion. Over the word limit (3,227); the author would still pass it. |

Remaining six, read 2026-10-28 (pass/fail only):

| Case | Judge | Author | Note |
|---|---|---|---|
| agnea_throne_1 | PASS | PASS | Has flaws (engine-term leak, a broken sentence), fixable by more fix rounds |
| osvald_temenos_2 | PASS | PASS | Has flaws (left open, short), fixable |
| osvald_temenos_1 | PASS | PASS | Has flaws, fixable |
| castti_partitio_1 | PASS | PASS | Has flaws, fixable |
| castti_partitio_2 | PASS | PASS | Has flaws, fixable |
| hikari_ochette_1 | PASS | **FAIL** | Broken logic: the garrison is "three days' ride south", yet they run there and arrive by sunset |

## 5.4 Gate decision

Author verdicts on all 10: **8/10 pass**. Fails: osvald_temenos_agnea_1 (POV slip) and hikari_ochette_1 (travel-time contradiction). The prd §6.5 gate (8/10) **passes, exactly at the threshold**. The author's standard was "a passing grade on homework": every story has flaws, and most look fixable with more fix rounds. Judge vs author disagreements: 5 of 10 (agnea_throne_2, hikari_ochette_2, and osvald_temenos_agnea_2 judge FAIL → author PASS; hikari_ochette_1 judge PASS → author FAIL; osvald_temenos_agnea_1 agrees FAIL but for different reasons). Three judge failures rested on wrong lore claims, a cross-family judge without KB access.
