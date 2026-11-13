# Security playbook — how a role uses it

Audience: `gondor-builder`, `orc-saboteur`, `eagle-sentinel`, the Maia, and
the briefs they write. Read this when a task touches a security topic
(input handling, authentication, sessions, access control, secrets, files,
outbound requests, deserialization, logging, dependencies, web APIs, LLM
features).

## Retrieval protocol (markdown only — no database, no CLI)

1. Extract 2–5 **signals** from the task: the data that crosses a trust
   boundary, the interpreter or sink it reaches, the asset at risk, and
   the framework in use.
2. `Grep` those words in `~/.claude/agent_doc/security/INDEX.md` (one row
   per entry: id | name | signals | standards). Take at most 3 candidate
   ids.
3. `Read` each candidate `~/.claude/agent_doc/security/<id>.md`. Compare
   the task against **Applies When** and **Does Not Apply When** first;
   if Does Not Apply When names the task, follow the entry id it points
   to instead.
4. Builders implement from **Requirements** and adapt **Implementation
   Notes** to the project's language and style. Copy **Common Failure
   Modes** into the test list; **Test Ideas** are a starting point.
5. Reviewers (`orc-saboteur`, `eagle-sentinel`) walk the **Review
   Checklist** with Read and Grep, item by item.
6. In the report cite the entry id and the standard id of each
   requirement you applied or checked, for example
   `input.injection, CWE-89`.

Do NOT load every entry into context. The budget is INDEX plus at most
three entries, usually one. If no candidate applies, say so and reason
from the task; do not force the nearest entry.

Entries are paraphrases, not the standards. When an entry and the cited
standard differ, the official text wins; the `verified` date in the
frontmatter says when the ids and versions were last checked.

Paths above are the installed location; inside the tlor-orchestration repo
the same files live under `agent_doc/security/`.

## Entry format

Every `<id>.md` has YAML frontmatter, in this order: `id`, `name`,
`category`, `confidence`, `verified`, `sources` (a list of name, version,
url). Then these `## ` sections, in this order: Task Signals · Applies When
· Does Not Apply When · Requirements · Implementation Notes · Review
Checklist · Common Failure Modes · Test Ideas · Related Entries · Sources ·
License Provenance.

- **Requirements** are numbered; each is one imperative sentence followed
  by standard ids in brackets, e.g. `[ASVS v5.0.0 V1; CWE-89]`.
- **Review Checklist** items can be checked with Read or Grep and name what
  to search for.
- **Related Entries** use only ids that have a row in `INDEX.md`.
- `confidence: high` = two or more standards agree; `medium` = one source.

`INDEX.md` is hand-written; the guard test
`tests/test_security_playbook.py` checks that it matches the entry files and
that each entry has the format above.

## Provenance

Each entry's License Provenance section names the cited works and their
licences. Entries are original wording under this repository's MIT licence.
