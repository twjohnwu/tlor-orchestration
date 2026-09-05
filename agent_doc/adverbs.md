# adverbs.md — the Hemingway adverb discipline (bilingual)

Distilled from sepia (github.com/Nanako0129/sepia, v0.8.0, MIT, Nanako Tsai):
`skills/sepia/references/voices/hemingway.md` (Rice 2017 adverb finding, its
fiction-route table row on plain vs. -ly adverbs, and the KC Star rule set)
plus `skills/sepia/references/languages/zh.md` §2–3 (Chinese connective/
padding shapes closest to an adverb ban). A user-supplied claim — "banning
adverbs outright gives AI writing more picture-sense" — prompted this doc;
we adopt the Hemingway variant (cut manner/degree, keep function) rather
than a blanket ban, because a blanket ban destroys precision-bearing
qualifiers a reader needs (see KEEP below).

## The rule

Cut adverbs that only tell the reader how intensely or how skillfully
something happened, when a concrete verb or detail can show it instead. The
reader should see the action, not be handed its intensity rating.

**English — cut manner/degree -ly adverbs**: "walked slowly" → "walked, then
stopped, then walked again" (or whatever the concrete beat actually was);
"said angrily" → the words said, or the action that carries the anger;
"very/highly/extremely [adjective]" → the specific fact the adjective was
standing in for.

**Chinese — cut 「地」狀語 and degree adverbs 非常/十分/極其/相當**: 「她非
常小心地打開門」→「她把門推開一條縫」; the manner clause disappears into
the concrete action. This mirrors sepia zh.md §2's disyllabic-padding fix
(「進行討論」→「討論」) and §3's connective-stacking fix — same instinct,
applied to adverbs.

## KEEP — do not cut these

- **Plain temporal/sequence adverbs**: then, now, never, already, still —
  Hemingway kept these (hemingway.md:27, "keep the plain adverbs: then, now,
  never; drop the -ly manner adverbs"). They carry sequence, not intensity.
- **Precision-bearing technical qualifiers**: only, atomically, idempotently,
  not yet, usually. In technical prose these bound a claim's scope or
  confidence — cutting them turns a hedge into a false assertion, which is
  an accuracy bug, not a style win (parallel rule already in
  `agent_doc/seo-writing.md` §2 for modifiers generally; this file narrows
  the same principle to adverbs specifically).
- **A postmortem's honest hedge**: "may have contributed" stays if the cause
  is genuinely uncertain — cutting it to sound decisive is worse than the
  adverb.

## Postmortem special case: self-praise adverbs

"The team swiftly identified the root cause" — the adverb is doing the
speed-judgment work a timestamp should do. Delete it and let the timeline
carry the claim: "At 14:02 the queue began failing; the team found the
cause at 14:41." (sepia `references/domains/postmortems.md:16`.) The same
move applies to any self-assessment adverb (thoroughly, carefully,
successfully) attached to the writer's own team's actions.

## Strictness varies by scene

This is not a fixed dial. Run it at the intensity `agent_doc/scene-
calibration.md` sets for the target scene — a social post tolerates more
adverbs than a technical report or a postmortem; fiction runs the fiction-
specific move set in `agent_doc/fiction-narrative.md` instead (select 3–5
Hemingway moves per piece, adverb-cutting is one of them, not a blanket
pass).
