# fiction-rubric.md — 5-group diagnosis taxonomy for fiction

Distilled from sepia (github.com/Nanako0129/sepia, v0.8.0, MIT, Nanako Tsai):
`references/rubric.md` (StoryScope's 30-feature taxonomy, AI-core/human-core
corpus tables). Heuristic triage, not the classifier itself and not an
authorship detector — signals are calibration references, never
authorship probabilities.

Division of labor: this rubric **diagnoses** (names signals, quotes
evidence, doesn't touch a sentence); `agent_doc/fiction-narrative.md`'s
3-pass sequence **repairs**. Diagnose fully before repairing.

**Omitted from this distillation**: the source's closing `Voice fit:` line
and its whole voice-profile/registry machinery — excluded by design; no
rubric group below depends on it, all 5 stand on their own.

## Protocol

1. Read one group at a time, in five separate passes — one combined read
   collapses attention onto one or two dimensions and goes blind to the rest.
2. Every signal needs its quoted passage — no quote, no signal. Record
   beside the corpus references; never combine into a score or probability.
3. Mark a feature **n/a** with no occasion to assess it (no jeopardy → no
   pre-threat investment to judge) — expected in short texts, not a defect.
4. An extreme score *away* from the AI direction (e.g. discontinuity 5/5) is
   an **over-correction advisory**, reported separately — not human-leaning.

## Group A — Thematic over-determination (AI drifts high)

Highest-value features: **thematic explicitness** (themes stay implicit vs.
thesis-like statements telling the reader what to think); **narrator
thematic commentary** (does the voice generalize — "that is how people
are" — yes in ~52% human vs 77% AI); **dialogue as philosophical debate**
(argues ideas rather than advancing want/conflict, ~34% human vs 59% AI);
**reference explicitness** (vague unnamed allusion as the dominant mode,
~50% human vs 72% AI — human-leaning is a *balanced mix* of named+implicit).

## Group B — Sensory & embodied performativity (AI drifts high)

Highest-value features: **dominant emotion mode** (embodied-sensation
dominance in strong-affect scenes, ~38% human vs 81% AI); **setting as
psychological mirror** (weather/landscape consistently externalizing inner
states); **olfactory imagery** (salience judged relative to length, ~57%
human vs 82% AI); **depth of interior access** (external-only vs
stream-of-consciousness).

## Group C — Structural streamlining (AI drifts high/tidy)

Highest-value features: **resolution mode** (external act / internal
acceptance / partial / open / catastrophic — internal acceptance ~27%
human vs 47% AI); **protagonist introduction** (external description at
first appearance is the flagged form, ~30% human vs 52% AI; in-dialogue is
the strongest human marker); **resolution agency** (protagonist choice vs.
chance/others, ~46% human vs 69% AI); **subplots** *(advisory only)* —
no-subplot is common enough in human work (~57%) that absence alone isn't a
signal without context.

## Group D — Human-positive markers

Record each marker separately with its own quote; never collapse into a
group score. **Named intertextuality** (real text/author named, ~47% human
vs 24% AI); **fourth-wall gesture** (any wink/aside, ~67% human vs 39% AI);
**direct reader address** ("you"/"dear reader", ~28% human vs 7% AI).

## Group E — Temporal complexity & diversity (AI drifts low/tidy)

Highest-value features: **chronological discontinuity** and **anachrony
intensity** (time jumps/flashbacks as structure — AI trends slightly lower
than human on both); **moral polarity toward protagonist** (final stance —
ambivalent ~59% human vs a clear affirmative/condemning stance ~62% AI);
**location variety** *(Sepia heuristic advisory)* — flag a long story that
never leaves one locale unless the premise demands confinement.

## Report shape

Per group: name each observed signal by its rubric feature name with quoted
evidence, n/a where no occasion; advisories (over-correction, subplots,
single-location) go separately, never folded into a group's signals; close
with an ordered repair plan, deepest layer first, each tied to a quoted
passage — then hand off to `fiction-narrative.md`.
