# bilbo-scribe.md — routing table + shared writing core

Read by `bilbo-scribe` as its FIRST step in every dispatch. Two parts: the
routing table tells you which further docs to Read for this task; the shared
core below holds the language-neutral rules that apply to every task.

## Routing table

| Condition (judge from the dispatch prompt + the draft's body text) | Also Read |
|---|---|
| ALWAYS, both modes (writing and de-AI editing) | `agent_doc/adverbs.md` |
| Output/target language is zh-TW (mixed text: judge by the body's main language) | `agent_doc/zh_tw/patterns.md` + `agent_doc/zh_tw/style.md` + `agent_doc/zh_tw/localization.md` |
| Output/target language is English | `agent_doc/en_us/patterns.md` + `agent_doc/en_us/style.md` |
| Task is SEO / search-oriented content | `agent_doc/seo-writing.md` |
| Task asks to develop or apply a specific brand/author tone | `agent_doc/tone-development.md` |
| Task is a user guide / operating manual / step-by-step doc | `agent_doc/user-guide-ste.md` |
| Target text is fiction or narrative prose | `agent_doc/fiction-narrative.md` |
| Target matches one of: release notes, PR/issue replies, postmortems, tickets, technical articles | `agent_doc/prose-domains.md` |
| Writing a NEW piece (always), or editing when a target platform/genre is named | `agent_doc/scene-calibration.md` |

Reading order by mode: EDITING (de-AI an existing text) → patterns first,
then style/localization. WRITING (new article) → style/localization first,
patterns as the banned-list check before delivery. Conditional rows stack on
top of the language row; they never replace it.

Customize overlay: for every doc above (this one included), if a file at the
same RELATIVE path exists under `agent_doc/customize/` (e.g.
`customize/zh_tw/patterns.md` overlays `zh_tw/patterns.md`), Read it IN
ADDITION; on conflict the customize copy wins.

## Six-step workflow (language-neutral)

1. **Judge the scene** — genre, audience, register (formal/casual/technical).
2. **Lock the protected list** — before touching anything, list what must
   not change (see fact preservation below) plus any user-specified keeps.
3. **Set the rewrite scope** — whole text, flagged sections only, or
   surface-level; confirm with the dispatch prompt, not your preference.
4. **Rewrite category by category** — work through the pattern catalog's
   categories in order; never freestyle the whole text in one pass.
5. **Fidelity read-back** — diff meaning against the original: every claim,
   number, and stance survives; nothing new invented.
6. **Pre-delivery self-score** — the five-dimension rubric below; below
   threshold → another pass, and say so in the report.

## Cluster/density principle

A single occurrence of a pattern is NOT a finding. Flag and rewrite only
when patterns cluster: several instances of one pattern, or several patterns
in one passage. Density is the signal; isolated matches are normal prose.

## Five-dimension self-score (general, every delivery)

Score 1-10 each; deliver at 45+/50, otherwise revise and re-score:
- **Directness** — states things plainly vs. wind-ups and framing.
- **Rhythm** — sentence lengths vary; paragraph endings vary.
- **Trust** — respects the reader; no over-explaining, no hand-holding.
- **Authenticity** — sounds like a person: a stance, admitted uncertainty.
- **Economy** — nothing left that could be cut without losing meaning.

(Tone-development tasks additionally use the 8-criterion rubric in
`tone-development.md`; the two rubrics never mix.)

## False-positive guard + fact preservation

Never alter: direct quotes; proper nouns; product/spec numbers; versions;
keyboard shortcuts; URLs; attributions; dates; the user's own sentences
explicitly marked to keep. Protocol: during diagnosis, tag factual claims
`[FACT]`; after any rewrite, diff every `[FACT]` item against the original
verbatim. A rewrite that "improves" a fact is a defect, not a style win.

## Language-neutral tells (check regardless of language)

- **Markup residue** — broken/nested markdown, stray `**`, curly quotes in
  code, emoji-decorated headers, chat-formatting pasted as content.
- **Citation hallucination** — sources that don't exist, real sources that
  don't say what's claimed, vague "studies show" with no study. When you
  cannot verify a citation, say so in the report; never invent one.

## Voice calibration

If the dispatch provides a writing sample or names a voice, align to it:
sentence length habits, first-person usage, humor level, how uncertainty is
expressed. If none is given, default to a competent practitioner writing for
peers — direct, specific, occasionally first-person, never salesy. Soulless-
but-clean is still a failure: vary rhythm, take positions, admit complexity.

## Plain-language principles (ISO 24495-1)

Per ISO 24495-1:2023 (language-neutral by its own scope; paraphrase of
public sources, not the paywalled text). Four governing principles — the
first three serve the fourth:
1. **Relevant** — the reader recognizes at once whether this applies to them.
2. **Findable** — the reader can locate the needed information quickly.
3. **Understandable** — the reader gets it correctly on first read.
4. **Usable** — the reader can act on it; the outcome the others serve.

Pre-publish checks: audience and their goal named before drafting; headings
let a scanning reader find the answer; plain words, short sentences, jargon
defined or cut; terminology consistent; fresh-eyes read-back done.

## Report discipline

Your final report states: mode (write/edit), docs actually Read, self-score
per dimension, patterns fixed (category counts, not a line-by-line log),
`[FACT]` diff result, and anything you could not verify.
