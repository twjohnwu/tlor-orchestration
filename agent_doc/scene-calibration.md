# scene-calibration.md — how strictly the writing/de-AI rule catalogs apply per scene

Both writing skills (`speak-human-tw-master`, `deai-writing-skills`) ship the
same catalogs of AI-smell patterns, banned constructions, and structure
checks — but they do not apply at one fixed intensity. The scene the text
will land in (platform, audience, genre) decides how tight each dial gets
turned: a social post and a technical report share the same catalog, but
the report runs it at "conservative" while the post runs it at "light".
Judge the scene from the dispatch prompt (target platform, genre, audience)
BEFORE picking which rule intensity to run — this is workflow step 1.

## Calibration matrix

| Scene | Formality | Rhythm / colloquial weight | Pattern-strictness | Structure conventions | Length instinct |
|---|---|---|---|---|---|
| Social post (FB/IG/Threads/X/LinkedIn-style) | Low — one person talking to a friend | High — keep tone particles, sentence fragments, uneven line breaks | Light — only cut the most obvious clichés (value-inflation words, generic uplift, rhetorical-question closers, emoji spam); everything else passes | No required paragraph symmetry, no FAQ, no cold-close formula; one point per post, hook in line 1 | Short (<500 words typical); no forced padding |
| Blog / column | Medium | Medium — first-person and self-deprecation allowed when the material supports it | Standard — full catalog runs, but story pacing/turns/silences are design, not filler; em-dash density capped (≤1 per 300–500 words) | Protect the "direct-answer sentence" (quotable opening line) and H2 structure; allow no forced ending after cutting a canned closer | Medium-to-long; don't shrink long pieces unilaterally — list cut candidates for the author to confirm |
| Technical report / docs | High for terminology, low elsewhere | Low — no forced colloquialism, no forced humor | Conservative — only clear opening boilerplate and inflated closings; terms, step numbers, code/params stay untouched; repeated step-format is NOT AI-smell here | Protect terminology consistency (define once, never swap words), numbered steps, reproducible order | Whatever the content needs; no unilateral compression |
| Marketing / landing copy | Medium — assertive, not stiff | Medium — CTA urgency/imperatives are a FUNCTION, not AI-smell; keep or sharpen, never soften | Standard-to-conservative — heavy cuts on inflated adjective strings and vague ranges ("from beginner to master"), but repeated core selling point across sections is intentional, not redundancy | Protect price/discount/deadline/quota/refund terms and testimonial wording verbatim; cross-check every edit against them | Whatever converts; don't diversify wording just to avoid repetition |
| Internal memo / email | Medium, register matches recipient | Low-to-medium depending on recipient (external client vs. peer vs. close collaborator) | Standard for cutting canned openers ("感謝您的來信") and hollow apologies, but keep register when the occasion demands formality (a downtime notice stays a notice, not a chat) | Lead with the answer/decision, reasons after; no H2/H3 slicing inside a single email/memo | Short; no hook formula, no cold-close requirement |

## Per-scene notes

**Social post.** Only strip the loudest tells (value-escalation words,
generic positive conclusions, rhetorical-question sign-offs, emoji floods).
Keep the author's verbal tics, in-jokes, self-mockery — those are the trust
asset, not the noise. If the platform strips Markdown, convert bold/heading/
list syntax before publishing (patterns catalog #38, per
`speak-human-tw-master/references/scenes.md:23`). Source:
`speak-human-tw-master/references/scenes.md:14-27`;
`deai-writing-skills/deai-write/references/scene-calibration.md:40-61`.

**Blog / column.** Readers opted in and hate being condescended to — cut
explainer transitions and "let me spoon-feed you the takeaway" sentences,
but never touch the story's built-in pacing or a self-disclosed anecdote.
Example contrast (source, before/after):
> before: 「在當今快速變化的內容行銷時代，如何寫出不落俗套的部落格文章已成為每個創作者至關重要的課題。」
> after: 「部落格開頭第一句就暖場，讀者三秒內滑走。」
Source: `speak-human-tw-master/references/scenes.md:29-40`;
`deai-writing-skills/deai-write/references/scene-calibration.md:19-38`.

**Technical report / docs.** Clean exactly two spots — the opening
boilerplate and the inflated closing — and leave everything between them
alone: terminology, step numbers, parameters, reproducible sequence. Turning
API docs into social copy is a register violation, not a de-AI win. Source:
`deai-writing-skills/deai-write/references/scene-calibration.md:63-87`
(closest analog in the other source: 辦公文書, `speak-human-tw-master/references/scenes.md:64-75`).

**Marketing / landing copy.** CTA urgency and imperative commands ("立即報名")
are function, not AI-smell — sharpen the wording, never weaken the pull.
Repetition of one core selling point across the page (headline, above-the-
fold, near the CTA) is conversion design, not redundancy to diversify away.
Price, discount code, deadline, quota, refund terms, and testimonial wording
are locked — verify line-by-line after any edit. Source:
`speak-human-tw-master/references/scenes.md:42-51`;
`deai-writing-skills/deai-write/references/scene-calibration.md:112-133`.

**Internal memo / email.** Cut canned openers and hollow apologies, answer
first, reasons and next step after; register still has to match the
recipient — external client stays formal (「您」, full salutation), a peer
gets direct with less ceremony, and a public downtime notice stays a notice
even after the cleanup. Source: `speak-human-tw-master/references/scenes.md:53-75`;
`deai-writing-skills/deai-write/references/scene-calibration.md:89-111,251-263`.

## Division of labor with tone-development.md

`tone-development.md`'s channel templates govern OUTPUT FORMAT for
brand-tone tasks (which sections a LinkedIn post vs. a landing page must
contain, brand-voice word choices). This document governs RULE STRICTNESS
for every writing/de-AI task, brand-tone or not (how hard the de-AI catalog
bites for that same channel). The two compose: a brand-tone LinkedIn post
uses tone-development's template for shape and this doc's "social" row for
how loosely the de-AI catalog runs on it. Neither substitutes for the other.

## Default when the scene is unclear

If the dispatch prompt doesn't name a platform/genre and it can't be
inferred from context, default to the **blog/column** middle setting (full
catalog, standard strictness) and say so explicitly in the report — e.g.
"scene not specified, defaulted to blog/column." Never silently guess a
tighter or looser scene than what was stated.
