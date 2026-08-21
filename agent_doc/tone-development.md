# tone-development.md — Developing and applying a specific brand/author tone

Routed reference for tone-mode tasks: writing or reviewing copy against a
specific brand voice (article writer role). Source:
`tools/brand-writer/{skill.md,rubric.md,voice-examples.md}` — a skill
originally written for a single product's voice; every brand-specific name
and fact below has been replaced with a placeholder brand `{Product}` so
the method transfers to any brand profile supplied at task time.

**Division of labor (read before using this file):** the shared core doc's
five-dimension score is the GENERAL pre-delivery self-check that applies to
every piece of writing, tone or not. The 8-criterion rubric below is
ADDITIONAL and applies ONLY when a task is explicitly in tone-development
mode (a brand-voice profile was supplied). The two scoring systems never
mix — don't average them, and don't run the 8-criterion rubric on writing
that has no assigned brand voice.

## The 8-criterion rubric (tone mode only)

Score each 1-5. Copy must score **4+ on every criterion** to pass; a single
3 means rewrite that section and re-score; a 2-or-below means full
reconstruction.

1. **Technical/factual grounding** — specific, verifiable claims vs. pure
   marketing language.
2. **Natural syntax** — varied sentence structure, reads aloud smoothly; red
   flags: em-dash chains, "it's not X, it's Y," parallel triplets.
3. **Quiet confidence** — states facts and lets the reader draw conclusions;
   no hype, no telling the reader how to feel.
4. **Reader respect** — treats the audience as a peer with domain
   competence, not a prospect to be persuaded.
5. **Information priority** — the most important fact or change leads;
   context and backstory follow, not the reverse.
6. **Specificity** — claims are concrete and measurable, not vague benefits.
7. **Voice consistency** — one coherent tone start to finish, no drift
   between casual/formal or technical/marketing registers.
8. **Earned claims** — every assertion is demonstrable or supportable; no
   unverifiable superlatives.

Pass threshold: all eight at 4+ (informal total target: 32/40).

## Diagnose → reconstruct → re-score loop

1. **Draft.** Write the copy for the requested channel and brand profile.
   (Fact-tagging and preservation across rewrites is handled by the shared
   core doc's `[FACT]` protocol — don't re-derive it here.)
2. **Diagnose.** Score the draft against all 8 criteria above; note the
   specific issue behind any score, not just the number. Taboo-phrase
   scanning uses the shared pattern catalog (`en_us/patterns.md`), not a
   separate list.
3. **Reconstruct.** For any criterion under 4, identify the concrete
   problem, rewrite only the flagged section, confirm no fact was dropped
   or altered, and re-score that section.
4. **Repeat** until every criterion clears 4. Multiple criteria failing at
   once is a signal to restart with a different approach, not to patch
   piecemeal.

## Channel-specific output templates

| Channel | Format |
|---|---|
| Homepage | H1 + H2 + one supporting paragraph |
| Product page | Section headers, each with explanatory copy |
| Release notes | What changed → how it works → why it matters |
| Docs intro | Plain explanation of what this is and when to use it |
| Social | Concise, no hashtags, one link to learn more |

## De-branded before/after pairs

**Hype to specifics** (Technical Grounding 2→5)
Before: "{Product} delivers blazingly fast performance that will
revolutionize your workflow. Our cutting-edge technology ensures you never
wait again."
After: "{Product} renders on the GPU. Typical actions complete in under
10ms, even on large inputs."
Notes: vague speed claim → a measurable number; "revolutionize"/
"cutting-edge" deleted outright, not softened.

**Em-dash chain to natural flow** (Natural Syntax 2→5)
Before: "{Product} is fast — really fast — and built for the way people
actually work — not how tools think they should work."
After: "{Product} is built for speed. We optimized for the workflows people
actually use: switching contexts quickly, searching across a large set of
items, and acting on several things at once."
Notes: all em dashes removed; one abstract claim replaced with three
concrete examples.

**Social-media cleanup** (multiple criteria 1→4)
Before: "🚀 Big news! {Product} just dropped MASSIVE updates! Incredible new
features, and SO much more. This is a game-changer, folks! Try it now! 🔥"
After: "{Product} 2.4: batch editing is here. Apply one change across every
matching item in a single pass. Full changelog at {product}.example/releases."
Notes: emoji, exclamation points, and hype words removed; replaced with a
version number, one concrete feature, and a link instead of "so much more."
