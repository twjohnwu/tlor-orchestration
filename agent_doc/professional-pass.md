# professional-pass.md — shared de-AI checklist for non-fiction

Distilled from sepia (github.com/Nanako0129/sepia, v0.8.0, MIT, Nanako Tsai):
`references/professional-pass.md`.

Applies to every non-fiction domain (release notes, PR/issue replies,
postmortems, tickets, technical articles — anything not narrative). Relation
to `agent_doc/prose-domains.md`: that file is per-venue rules; this file is
the shared pass run before or alongside them. Sample 2–3 recent human
artifacts from the same venue first — the venue corpus defines the target
register, not this checklist.

## The 10 checks

Run one at a time — a combined pass goes blind. Slop is cumulative: one hit
means nothing, clusters mean rewrite.

1. **Chatbot residue** — "Great question", "I hope this helps", "Certainly!",
   apology openers, offers of further help. Overlaps `agent_doc/en_us/
   patterns.md` #20 (collaborative-communication artifacts) and #22
   (sycophantic tone) — see those entries for more forms.
2. **Density** — could this say the same at half the length? Generic
   context-free statements carry zero information. Cut both directions:
   trimming a required caveat or next step also fails this check.
3. **Relevance** — does every paragraph serve the reader's actual task?
   Restated background and scope tours are filler.
4. **Stance** — commit to a judgment where one is required (a review with no
   verdict, a postmortem with no admitted mistake). Hedge once per fragile
   claim, not per sentence.
5. **Specificity** — versions, numbers, file:line, verbatim error text,
   names — present and real. A confident invented specific is a top-tier
   tell; missing info gets a TODO, not a filled-in guess.
6. **Formatting tells** — bold-mini-heading bullets where prose would do,
   decorative emoji, Title Case headings, rule-of-three everywhere, fractal
   summaries. See `agent_doc/en_us/patterns.md` §Style patterns (#14–19) for
   the individual forms; absence of these isn't proof of a human — model
   release changes what it over/under-uses.
7. **Conclusion residue** — "In conclusion" sections, restating what was
   said, generic future outlook. End when the content ends.
8. **Templatedness** — the same sentence frame recycled across items; vary
   the phrasing or tabulate instead.
9. **Sameness of rhythm** — uniform paragraph/sentence length throughout;
   depth where it matters, one-liners where it doesn't. Same dimension as
   `agent_doc/en_us/patterns.md` §C (uniform sentence length).
10. **Fluency** — grammatically correct but unsayable phrasing. Read it
    aloud; if no one would say it, redo in speech-shaped syntax.

## Domain weighting

Article-like documents (postmortems, tech articles, announcements) weight
relevance, density, stance/tone, coherence first. Short answers (PR/issue
replies, tickets) weight factuality, specificity, templatedness first —
density and tone matter less at short length. Weighting sets order and
depth of attention, not an exemption: a short reply drowning in filler still
fails density.

## Whitelist — conventional ≠ slop

Do not flag: changelog categories, issue/PR templates, RFC sections, runbook
formats (formulaic containers by convention); formal register in a formal
venue; bullets for genuinely enumerable items; terse unadorned replies (the
human default in dev venues); the author's own verified habits.
