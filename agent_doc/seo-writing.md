# seo-writing.md — De-AI writing under SEO constraints

Routed reference for SEO-oriented writing tasks (article writer role). Read
this when the task asks to optimize, rewrite, or place keywords in a draft —
not for tone/brand work (see `tone-development.md`) or general de-AI-ness
(shared core doc). Source: `tools/deai-writing-skills/deai-writing-seo/`
(SKILL.md + references/*.md).

Priority ladder (higher wins when rules conflict): factual accuracy >
author's intent/voice > the reader's real question > specificity/density >
de-AI-ness > rhythm/layout > SEO/platform fit. SEO never overrides content
quality.

## 1. Search-intent judgment and rewrite

Classify the query before writing a word: **informational** (why/how/what —
answer directly), **commercial-investigation** (comparing options — write a
comparison/pros-cons table), or **transactional** (ready to buy/go — give
product specs and a path to purchase). Judgment method: look at what the
first page of search results actually is and match that content shape — a
well-written definition article won't rank against a page of comparison
posts. One core intent per page; fold near-synonymous sub-questions into
subsections instead of splitting them into separate keyword-stuffed pages.

For a rewrite (vs. fresh draft), do intent reconstruction first: read the
whole draft and state the inferred **core purpose** and **intended effect**
in two lines as part of the final report — a dispatched subagent cannot
pause mid-task to wait for confirmation, so state the judgment explicitly
and proceed. Lock an immutable list (data, steps, legal/contract language,
stance, house phrases) that stays untouched unless the requester says
otherwise. Then apply minimal-intervention rewriting: keep the core meaning
and the author's rhythm, delete only repetition/filler, replace
unsupported abstract praise with the reasoning behind it, and touch SEO/
layout last, only where needed.

- zh-TW: 判斷方法只有一個，不靠猜：直接搜尋該關鍵字，看第一頁排什麼形式。
- EN counterpart: "Best noise-cancelling headphones" returns ranked listicles
  on page one — a spec-sheet page for one model won't outrank them; write
  the comparison instead.

## 2. Modifier function rules (keep a human voice under density limits)

Constrain modifiers by **function**, not part of speech — banning all
adjectives/adverbs backfires (see below). Delete modifiers that only
amplify tone, declare quality without evidence, or repeat a verb/noun's
existing meaning ("very," "highly effective," "successfully completed").
Keep modifiers that carry negation, time, scope, frequency, condition, or
confidence level ("only," "not yet," "usually," "may") — cutting these turns
a hedge into an assertion, which is an accuracy bug, not a style choice.
Where a claim is only an evaluation, replace it with the judgment basis:
who did what, under what condition, with what observable result.

Anti-patterns from mechanical modifier deletion: chopping every sentence
into short fragments ("The system starts. The user logs in."); swapping
adjectives for equally abstract nominalizations ("execute an optimization"
instead of "optimize"); and inventing fake specifics (numbers, brand names,
sensory detail) to simulate concreteness when the source material doesn't
have them — mark `[needs source]` instead of fabricating.

- zh-TW: 該限制的是修飾詞的「功能」，不是「詞性」。
- EN counterpart: keep "not yet stable" and "only on Linux" (they bound the
  claim); cut "incredibly powerful" and "truly seamless" (they add nothing
  a reader can verify).

## 3. Platform checklist

Long-form/owned pages (site articles): natural short paragraphs, key info
at the start of each paragraph, generous white space — a qualitative
direction, not a fixed line-count quota.
Social posts: hook the target reader in the first line without a
misleading opener; preserve the author's own line-break/punctuation/emoji
habits; any linked URL must be topically close to the post. Treat
algorithm-ranking checklists as **speculative reference only** — never
state them as verified fact; fall back to readability, clarity, relevance,
and audience fit when unsure.
Newsletter: open like a letter, tighten punctuation, close with a next-step
or subscribe prompt.

## Pre-delivery checklist

- [ ] Content shape matches page-one search intent (no format mismatch)
- [ ] One core keyword/intent per page; keywords placed by weight
      (title > link anchor text > H1 > H2/H3 > first ~100 words), not by count
- [ ] Title matches H1 and the actual content (no clickbait mismatch)
- [ ] Every kept modifier does at least one job (negation, scope, time,
      confidence, or a verifiable distinction) — the rest are cut
- [ ] No fabricated experience, data, or "as studies show" without a source
- [ ] Immutable-list items (data, steps, legal language, stance) unchanged
- [ ] Platform format applied last, without changing meaning
