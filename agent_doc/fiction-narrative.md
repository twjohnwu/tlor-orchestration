# fiction-narrative.md — the 3-pass fiction repair sequence

Distilled from sepia (github.com/Nanako0129/sepia, v0.8.0, MIT, Nanako Tsai):
`narrative-pass.md` (pass 1), `discourse-pass.md` (pass 2), `style-pass.md`
(pass 3). Run in this order — polishing sentences before architecture is
fixed wastes the edit. For fiction/narrative prose; professional domains
live in `agent_doc/prose-domains.md`, adverb-only cleanup in `agent_doc/
adverbs.md` (one move inside pass 3).

Diagnose before you edit: for REVISE, state what the draft does in each
group below before touching a sentence. Enact only 3–5 human-leaning moves
total across the whole piece — calibration, not a checklist to exhaust.

## Pass 1 — narrative architecture (diagnose the shape first)

Work through these; pick the target band, don't force every band every time:

- **Theme**: implied, never narrator-stated in the closing paragraphs;
  dialogue argues over something concrete (rent, a door), not the theme.
- **Plot**: allow one broken causal link and one planted detail that never
  fires; ~2-in-5 stories carry a subplot echoing the theme obliquely.
- **Endings**: don't default to protagonist-chooses+accepts+understands as
  one bundle — break at least one leg (chance/another person decides;
  ending partial, open, or morally mixed).
- **Time**: moderate nonlinearity, back-loaded reveals — open at the
  effect, hold back the cause; don't front-load all context up front.
- **Emotion/senses**: mix embodied sensation with plain naming and
  behavior; reserve embodied rendering for one or two peaks. Weather is
  weather — it doesn't have to mirror the marriage every scene.
- **Characters**: introduce the protagonist in dialogue or action, not a
  description paragraph; sparse cast graph; give the antagonist their own
  relationships, not isolation.
- **Outside world**: name real things over vague gestures ("a famous
  poet"); an occasional reader-aware aside is human, used once or twice.
- **Rarity move**: exactly one structural choice genuinely atypical for
  this premise — more than one reads as performance.

## Pass 2 — discourse flow (how paragraphs advance)

- **QUD check**: list the implicit question each paragraph answers. Flag a
  "linear interview" (what → why → result → meaning) and a "reflection
  tail" ending on how the character feels now. Add one paragraph that
  *compares* or *verifies* (contradicts an earlier one) — nearly absent
  from machine prose, does more repair than a page of rewording.
- **Outline test**: pull each paragraph's first sentence as a list — a
  clean summary of the whole piece means the structure is machine-shaped.
- **Middle third is the choke point**: put one event there the opening
  didn't predict; vary texture between adjacent scenes; let one thread
  slow down instead of resolving on schedule.
- **Page positions**: ragged paragraph lengths (include a one-sentence
  one); quoted lines anywhere, not always closing a paragraph; vary
  scene-transition connectives instead of repeating one formula.
- **Openings**: skip time+place+weather-then-describe-the-character —
  open mid-conflict or mid-conversation.
- **Names**: draw from the story's specific world; avoid the converged
  pool (Elara, Ava, Emily, Sarah) unless the world calls for it.

## Pass 3 — surface style (sentences and words, last)

Minimum to run after passes 1–2 settle:

- Replace awkward word choice; split run-ons; delete trailing clauses that
  restate what the scene already implied.
- Replace cliché with scene-specific language, never a blander paraphrase —
  delete the line if nothing fresh is available.
- Add real specificity only from material you actually have — ask, don't
  invent, if you lack it. Simplify purple prose; pin the tense.
- Hunt machine syntax: "a [abstract noun] of [noun]" wrappers, trailing
  participial clauses, nominalized subjects, rule-of-three everywhere.
- Cut adverb/vocabulary slop per `agent_doc/adverbs.md` and fiction-slop
  words (shimmering, thrums, "despite herself", filter words like
  felt/seemed/noticed) — one hit means nothing, clusters do.
- Restore contractions, discourse particles, plain connectives, and
  negation sparingly — the underused human register, not padding.
- Read dialogue aloud (mentally): grammatical-but-unsayable is its own tell.

Do not flag: clean grammar, a single em-dash, neutral tone in a formal
genre, a banned word inside quoted dialogue, or the author's own verified
habits — over-correcting these is itself a tell.
