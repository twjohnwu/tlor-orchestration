# Algorithm playbook — how an implement role uses it

Audience: `gondor-builder`, `dwarf-smith`, the Maia, and the Codex brief
they write. Read this when a task contains an algorithmic sub-problem
(searching, ordering, graph traversal, counting, matching, optimizing
over a sequence) and the right approach is not already fixed by the spec.

## Retrieval protocol (markdown only — no database, no CLI)

1. Extract 2–5 **signals** from the task: data shape (array, string,
   weighted graph, tree, intervals), the ask (shortest, longest, count,
   exists, k-th), and hard constraints (sorted?, negative weights?,
   contiguous?, streaming?).
2. `Grep` those words in `INDEX.md` (one row per algorithm: id | signals |
   avoid_when | confidence). Take at most 3 candidate ids. The
   `avoid_when` cell holds short cues only; the alternative to use for
   each cue is named in the entry's **Do Not Use When** section.
3. `Read` each candidate's entry `<id>.md`. Compare the task against
   **Preconditions** and **Do Not Use When** first; a single violated
   precondition rejects the candidate even if the signals match.
4. Implement from **Core Invariant** + **Algorithm**; adapt the
   **Canonical Implementation** to the project's language and style —
   never paste it verbatim into product code.
5. Copy the entry's **Common Failure Modes** into your test list.
6. In the report cite the entry id and the precondition check you made.

Do NOT load every entry into context. INDEX → one entry is the budget.
If no candidate survives step 3, say so and solve it from first
principles; do not force the nearest entry.

## Entry format

Every `<id>.md` has YAML frontmatter (`id`, `name`, `category`,
`confidence`, `review_required`, `sources`) and these sections, in this
order: Problem Signals · Use When · Do Not Use When · Preconditions ·
Core Invariant · Algorithm · Canonical Implementation (Python) ·
Complexity · Variants · Common Failure Modes · Production Considerations ·
Related Algorithms · Representative Problems · Sources · License
Provenance.

`confidence: high` = ≥2 primary sources agree; `medium` = one primary
source; `review_required: true` = sources conflicted and a human has not
yet adjudicated — treat the entry as a lead, not an authority.

## Provenance

Entries are distilled (compared, not copied) from MIT-licensed
repositories listed in each entry's License Provenance section
(repository, path, commit, license). Canonical implementations are
rewritten; the sources are evidence, not the code. Authoring pipeline
and taxonomy: `playbook/` in the tlor-orchestration repo.
