<p align="center">
  <img src="assets/banner.png" alt="Yet Another Story of Solistia: the eight travelers around a campfire" width="100%">
</p>

<p align="center"><b>English</b> · <a href="README.zh-CN.md">中文</a></p>

# Yet Another Story of Solistia

**Yet Another Story of Solistia** is about what happens in *Octopath Traveler II* after the game's story ends. It keeps a world going, one day at a time, lays out everything that happens and why, and lets you ask: **what if?**

Vide is defeated, and the eight travelers' journeys have come to an end, but their lives go on. All the lore comes from one knowledge base built from the game's wiki.

## What it does

- **World simulation (the main line):** each traveler is played by an agent that acts on its own goals and memory. A World agent decides whether what they try succeeds, plays everyone else, and keeps time. Nobody plans the plot. Everything that happens goes into an event log, and the world can pick up the next day where it left off.
- **Crossroads (in progress):** you slip something into the world and watch how it plays out. Everything that happened is laid out as threads, each open from its cause to its end, down to what the characters privately meant.
- **Story generation (done):** pick 2-3 travelers and a location, give an opening line, and a model writes a 2,000-3,000-word short story, which a validator then checks against the lore.

The original idea was to run the world first, then pick episodes from it to write up as stories. But in a head-to-head test, the directly written stories won 10-0. So a writer handles stories, and the world stops competing with it on prose. Instead it does what a writer can't: it keeps a full causal record, shows everyone's private motives, and can be changed and run again.

## Where the knowledge base comes from

<p align="center"><img src="assets/kb_build.svg" alt="Building the knowledge base: game wiki, pull, polish, link, 514 Markdown files" width="100%"></p>

The knowledge base comes from the [Octopath Traveler Fandom wiki](https://octopathtraveler.fandom.com/). The wiki has about 4,700 pages and covers the whole series, of which OT2 is only a part. Antigravity built it in three steps, each with one job:

1. **Pull:** check every page for OT2 content, and save the 646 relevant pages exactly as they are.
2. **Polish:** cut combat data, gameplay guides, and other games' content, clean up the format, and sort what's left into people, places, world, and stories: 514 Markdown files in the end. This step **may only delete, never add**, and the result is checked against step 1's text.
3. **Link:** turn wiki links into paths inside the knowledge base. Links to pages outside it become plain text.

Every step comes with check scripts, which Claude reruns to look for missing pages, empty pages, misfiled pages, or anything the original text doesn't say. The author went through all eight travelers' files personally.

The knowledge base is the authority on lore: when a fact is wrong, the fix goes into the knowledge base, not into a prompt. There is no vector store. Agents read files directly by path, name, and link, and every read is logged in the trace. How the travelers are doing after the game isn't in the knowledge base; that lives in the world premise and the character cards.

## How a story gets written

<p align="center"><img src="assets/story_flow.svg" alt="Single-agent writing: input, writer, validator, final story, with targeted fixes when there is a contradiction" width="100%"></p>

You start with 2-3 travelers, a location, and an opening line, for example "Osvald and Temenos, New Delsta, Osvald comes to town on scholarly business."

The **writer** is one strong model. It reads the travelers' character cards for their personality, way of speaking, and what they want now that the game is over. Then it looks up places and people in the knowledge base and writes the whole story in one go, following the style spec: 2-4 acts, 2,000-3,000 words.

Then the **validator** goes through it from the top. It picks out the sentences that touch game lore, breaks them into individual claims (say, "Temenos is an inquisitor"), and looks for quotable evidence in the knowledge base, the world premise, and the character cards. Each claim is judged supported, contradicted, or not in the KB. Newly invented minor characters, jokes, and things a character simply misremembers don't count as errors.

When there's a contradiction, the writer **edits only the sentences at fault**, and the validator rechecks only the edited paragraphs, for up to three rounds. If it still isn't fixed after three, the story is marked failed, with the draft and full trace kept for debugging; it is never rewritten from scratch. Stories that pass can be read in the local web UI, with "story contract" notes at the end pointing out POV slips, wording that breaks the fiction, loose ends, and stakes too big for a short story. The notes are advisory and don't affect whether a story passes.

## Sample stories

Four stories the engine wrote, each passing the validator.

| Story | Travelers | Where |
|---|---|---|
| [The Peculiar Librarian](stories/the_peculiar_librarian.md) | Osvald & Temenos | Montwise |
| [Red Dust Fever](stories/red_dust_fever.md) | Castti & Partitio | Crackridge |
| [The Taste of Raspberries](stories/the_taste_of_raspberries.md) | Agnea & Throné | Cropdale |
| [The Measure of a Mountain](stories/the_measure_of_a_mountain.md) | Osvald & Partitio | the Wildlands |

## How the world runs

<p align="center"><img src="assets/world_flow.svg" alt="World simulation: a day has four parts, and each part runs plan, meet, play, and off-screen" width="100%"></p>

`world new` builds a world from the same inputs: where everyone is, what they want, who they've promised to meet, plus a few small local matters on a deadline, like a performance, some trouble, or a date. After that, each `world run` moves the world forward one day.

A day has four parts: morning, afternoon, evening, and night. Each part goes through four steps:

1. **Plan:** each traveler decides on their own where to go and what to do. They can simply be somewhere, or go and try something that matters. A plan is only an intention, and nobody else sees it.
2. **Meet:** code moves the travelers according to their plans, and the World says who else is at each spot. When two travelers run into each other, or someone sets out to do something, a scene starts.
3. **Play:** the scene goes round by round, and in each round only one person speaks or acts. Whoever was just addressed answers first, and someone with something urgent can cut in. The World plays the minor characters present and decides the outcome of each act.
4. **Off-screen:** in a separate session, the World keeps the rest of the world moving: minor characters go about their business, and matters nobody dealt with lapse when their time runs out. This session can't see the travelers or touch them.

At the end of the day, each traveler writes a memory of the day and carries it into the next. The next morning, travelers adjust their goals from their memories, and the World adds a few new matters.

Every change in the world, such as someone moving, making a promise, or a matter moving forward, is written to the event log as a typed operation. The world's current state is computed from the log step by step, so description alone changes nothing. The log is this world's canon, and that is what lets the world keep going.

A world goes on one day after another. It ends when every matter is settled or it reaches its set number of days. After each day, a judge reads through the day's log and checks it for lore breaks and contradictions.

## Theater mode (paused)

<p align="center"><img src="assets/scene_player.jpg" alt="The scene player: four beats at the Festival Grounds at night, Agnea and Throné talking in speech bubbles, with a long line paged across two bubbles" width="100%"></p>

<p align="center"><img src="assets/theater_flow.svg" alt="The theater: from the event log to the screen through scenes, staging, facing, and voices, played day by day" width="100%"></p>

The meetings and conversations in the log can be played scene by scene in the theater.

**What it does:** it splits the log into scenes, hangs a backdrop for the place and time of day, and gives everyone a spot to stand. A speaker turns to whoever they are answering, and everyone else looks at the speaker. Lines go into speech bubbles with voices, and scenes play one after another, day by day. The public version uses only original art: twenty characters with four facings each, a dozen-plus day and night backdrops, and voices generated locally with Kokoro. Both worlds are live.

**What could come next:** characters walking on and off and gesturing as they speak; a showcase world run start to finish for the theater; more voices for minor characters.

**Why it's paused:** the theater does the same job as the writer: it hands the audience a finished story. On that job the writer already won 10-0, and adding more pictures and motion to the theater wouldn't make it clear whether it got better. What the world has that a writer can't give is a full causal record, everyone's private motives, and the ability to change it and run it again. So the theater stays as it is and becomes part of the threads below: every scene in a thread links straight to the theater.

### [Online theater](https://solistia-theater.vercel.app)
- **[The Cropdale festival](https://solistia-theater.vercel.app/world/20261107-180443-2fc52f/theater.html):** Agnea and Throné, 23 scenes
- **[The Oresrush wilds](https://solistia-theater.vercel.app/world/20261107-200913-754a8c/theater.html):** Hikari and Ochette, 21 scenes

## Crossroads: the unseen hand

<p align="center"><img src="assets/crossroads_flow.svg" alt="The unseen hand: you slip something into the world, the world goes on as usual, and the threads show how it plays out" width="100%"></p>

You slip something into the world from the shadows: a missing object, a stranger, a rumor making the rounds. The next morning, it happens. No one knows whose hand it was. The travelers and the townsfolk just deal with it as their own hearts tell them, and where it goes, no one can say, not even you.

To see how it plays out, the world lays everything that happened out as **threads**:

- **One thread per matter.** Every matter on a deadline (a performance, some trouble, an accusation) is a thread: how it began, who it touches, who stands in the way, whose goal it threatens, when it is due, then every scene and off-screen move it went through, in order, until it was settled or dropped.
- **Private motives in view.** Open any scene to see what each character did and said, and, when you want it, what they privately meant.
- **Nothing goes to plan.** A new world opens with someone truly standing in a traveler's way. With that opponent present, nothing is a sure thing: the World only states the odds, and code rolls the dice. A failure doesn't stop the scene; it turns the story, and a conflict can run for days.

**Where it stands:** threads, dice and the opening opponent are built; slipping something in is next. After that, you can go back to a past day, change one thing, and run it again.

## Status

A personal project, still in progress.

- **Done:** the knowledge base; the writer, lore validation, and the fix loop; the evaluation kit and 10-story test suite; the local web UI (writing and reading). The MVP gate passed with 8 of 10 stories ([gate_v1.md](eval/results/gate_v1.md)).
- **World engine:** world creation, traveler and World agents, round-by-round scenes, and world state computed from the event log are all built. The single-day world metrics pass ([world_we_v1.md](eval/results/world_we_v1.md)). Both test worlds ran their full five days and ended normally.
- **Scene player and theater:** done, with voices; both worlds are live, see [Online theater](#online-theater). Then paused in favor of Crossroads.
- **Crossroads (in progress):** the threads page is built; events name the thread they belong to; acts carry odds and can fail; a new world opens with an opponent who truly blocks a traveler.
- **Next:** you drop something into the world, and see how the world takes it.

## Quick start

You need Python 3.12+, [uv](https://docs.astral.sh/uv/), and an Anthropic API key in `.env` (`ANTHROPIC_API_KEY=...`).

```bash
uv sync
uv run story-engine --help

# Local web UI: /worlds lists every world, / reads stories that passed, /new writes a new one
uv run story-engine web          # http://127.0.0.1:8000

# Write a story from the command line (write → validate → fix)
uv run story-engine generate --mode baseline --characters osvald,temenos \
  --location new_delsta --scenario "Osvald comes to town on scholarly business"

# Build a world and run its first day (world only, no story)
uv run story-engine world new --characters agnea,throne --location cropdale \
  --situation "Agnea has brought Throné to a festival here."
uv run story-engine world run <world_id> --stop-after day

# Read the world's threads
#   http://127.0.0.1:8000/world/<world_id>/chronicle

# Voice the lines, then watch from the start in the theater
uv run story-engine world voice <world_id>
#   http://127.0.0.1:8000/world/<world_id>/theater

# Export a static site with the original art and Kokoro voices
uv run story-engine world voice <world_id> --engine kokoro
uv run story-engine world export <world_id> --assets assets/original --out output/site

# Tests (unit tests make no model calls)
uv run pytest tests/unit
```

Model calls cost money; one story is about $0.70, and one simulated day about $5-7 (at list prices). Each run's spending cap is `max_cost_usd` in `config/settings.yaml`.

## Layout

| Path | What's there |
|---|---|
| `src/story_engine/` | CLI, agents, world model, simulation loop, local web UI, evaluation tools |
| `stories/` | Sample stories that passed validation |
| `prompts/`, `cards/` | Agent prompts and the eight travelers' character cards |
| `kb/` | The knowledge base: Markdown files built from the wiki |
| `preprocess/` | Prompts and check reports for the three knowledge-base build steps |
| `assets/original/` | Original characters and backdrops for the public site |
| `config/` | Which model each role uses, plus settings such as rounds per scene and the cost cap |
| `eval/` | Fixed judge prompts, the test suite, and evaluation results |
| `docs/` | Requirements, architecture, tech stack, roadmap, and development log |
| `tests/` | Unit tests, and end-to-end tests that call real models |

## Disclaimer

An unofficial fan project, not affiliated with or endorsed by Square Enix. *Octopath Traveler* and all related names are trademarks of Square Enix. The knowledge base is derived from the [Octopath Traveler Fandom wiki](https://octopathtraveler.fandom.com/), whose text is licensed under [CC BY-SA](https://creativecommons.org/licenses/by-sa/3.0/). The cover illustration is official *Octopath Traveler II* promotional art, © Square Enix, with only the title added; it will be taken down immediately if the rights holder asks.
