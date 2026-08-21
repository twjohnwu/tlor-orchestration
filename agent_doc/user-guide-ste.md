# user-guide-ste.md — user guides in Simplified Technical English

Read when the task is a user guide, operating manual, or step-by-step doc.
Based on ASD-STE100 principles, adapted for software docs; applies on top of
the shared core in `bilbo-scribe.md` (its rubric and fact rules still hold).

## Two modes

Pick a mode before writing; state the choice if the task type is ambiguous.

**Strict STE** — safety-critical procedures, error-recovery steps, anything
where a wrong reading has a real cost. Apply every rule below, including the
lexical preferences (one word, one meaning).

**STE-flavored** — explanatory prose around a procedure: intro paragraphs,
conceptual overviews, changelogs. Enforce the structural checkpoints in
full; treat the plain-word preferences below as a direction of travel
rather than a hard requirement — prose needs some range, and a strict
lexical lockdown on prose reads as a personality transplant, not a
clarification.

## Structural checkpoints — always enforced, both modes

- **No phrasal verbs.** "Remove the panel", not "take off the panel" — a
  two-word verb's meaning is not predictable from its parts.
- **No semicolons.** Split into two sentences instead. Every other
  punctuation mark, including the em dash, stays permitted.
- **No ellipsis.** Keep the subject, verb, and article explicit even if the
  sentence reads longer — dropping words to save space creates ambiguity
  about which noun a modifier attaches to.
- **Noun clusters ≤ 3 words.** Break "server configuration file backup
  procedure" into a phrase with prepositions.
- **Keep modality phrases as-is.** "The request may have failed" stays "may
  have failed" — promoting a hedge to a stated fact changes the claim.
- **Sentence caps**: procedures ≤ 20 words; descriptions ≤ 25 words.
- **One instruction per sentence.** Never chain two actions with "and then".
- **Active voice, imperative mood** for procedures: "Click Save", not "the
  Save button should be clicked".
- **Simple tenses only.** Infinitive, imperative, simple present, simple
  past, simple future, and past participle as adjective. No present perfect
  or other compound form ("we received the report", not "we have received
  the report") — unless the compound form carries information the simple
  form cannot (current relevance, a hedge); then keep it and flag the
  departure instead of silently simplifying.

## Safety instructions

- State the warning **before** the step it protects, not after: risk first,
  then the action.
- Open a safety-critical instruction with the command or condition itself;
  never bury it mid-sentence.
- Never drop a safety condition, exception, or scope qualifier just to fit
  a sentence cap — keep the longer phrasing and flag the trade-off instead.

## Plain-word preferences (lexical; direction of travel in STE-flavored mode)

- **One term, one meaning** — pick one name per concept and never rotate
  synonyms; the same button is called the same thing in every step.
- Prefer the plain word (use "start", not "initiate"; "end", not
  "terminate"; "use", not "utilize").
- Prefer the verb form over its noun form: "analyze the log", not "perform
  an analysis of the log".

The official ASD-STE100 Issue 9 standard text and its ~900-word approved
dictionary are copyrighted and licensed by ASD; this file paraphrases rule
categories only and does not reproduce either.

## Ubiquitous language

Before writing, check the target repo for `CONTEXT.md` (follow
`CONTEXT-MAP.md` to the right one if the repo has more than one). Use ITS
terms for domain concepts verbatim — do not "improve" domain terminology.
If no such file exists, mine the project's README/UI strings and stay
consistent with them; note the source you used in the report.

## Re-pitch convention

When a reader signals a passage did not land ("wait, what?"), re-pitch it:
give one or two sentences of context first (what this is, why the reader is
here), then restate the point in STE. Never repeat the original wording
louder; change the pitch, not the volume.

## Structure defaults

- Lead each section with the goal in one line ("This section shows how to
  X"), then numbered steps.
- One procedure = one task; fork variants into separate procedures instead
  of branching mid-list.
- After the last step, state the expected result so the reader can verify.
