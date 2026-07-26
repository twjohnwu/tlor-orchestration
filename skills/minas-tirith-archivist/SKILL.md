---
name: minas-tirith-archivist
description: 'Read-only search over archived decision records (general and project-scoped) — use when the user asks about past decisions, why a convention exists, "為什麼當初這樣做", "以前是怎麼決定的", "這題以前決過嗎", "查決策記錄", "search decision records", "past decisions", or explicit `/minas-tirith-archivist`. Read-only query counterpart to `/westmarch-scribe`; answers with citations, never writes or edits records.'
---

# Minas Tirith Archivist (米那斯提力斯檔案守護者)

> The archives of Minas Tirith, where Gandalf searched long for the scroll
> of Isildur among records others had forgotten. This skill only searches
> what has already been written down — it does not decide anything itself,
> and it does not write anything new.

## Purpose

Read-only query side of the decision-record pair: `/westmarch-scribe`
writes decision records, this skill searches and answers questions about
them. It never edits, re-litigates, or archives — only reads and reports.

## Step 0 — Gate: tlor rules installed?

Resolve the installed rules directory (portable wording: `~/.claude/rules`,
`.claude/rules`, or wherever this environment's rules layer actually lives —
whether that's a symlink or a real directory; adapt to the installed
layout). Confirm the base rule files `dispatch.md` and `judgment.md` exist
there.

If either is missing: **STOP**. Report exactly: "tlor rules not installed —
run `/tlor-init` first". Do not silently continue — without the rules
layer there is no known location to search, and guessing one risks
reporting a false "no record found".

## Step 1 — Locate sources

Mirror `/westmarch-scribe`'s write destinations:

- **General (cross-project)**: the "General decisions log" section of the
  rules customize layer's `judgment.md` (e.g.
  `~/.claude/rules/customize/judgment.md`; adapt the path to wherever the
  installed rules customize layer actually lives).
- **Project (current repo)**: `docs/decisions_log.md`,
  `decisions_log/<repo>.md`, an ADR directory (e.g. `docs/adr/`,
  `docs/decisions/`), and compact decision lines recorded in the repo's
  instruction file (`CLAUDE.md` / `AGENTS.md` / `CLAUDE.local.md` /
  `AGENTS.local.md`).

A missing source is noted, not treated as an error — not every repo has a
decision log, and not every machine has archived a general decision yet.
When answering (Step 3), state which of these scopes were actually
searched — a sweep of OTHER projects only ever runs on explicit request
(Step 1a below), never as part of this default.

## Step 1a — Cross-repo sweep (opt-in, explicit request only)

This branch never runs by default — only when the user explicitly asks a
question shaped like "did another project already decide this", "search
every project", or an equivalent explicit cross-repo request. Absent that
request, stop at Step 1's default scope; a machine-wide sweep as the
default would make every lookup pay scan cost for a vague scope.

1. **Enumerate candidates.** List the harness's own per-project registry
   directory (one entry per project path it has tracked), sorted
   newest-first by modification time — that ordering IS the definition of
   "active" for this sweep. Skip entries that are scratch/temp session
   paths rather than real projects.
2. **Never reverse-engineer a real path from a registry entry's name.**
   That encoding is lossy and irreversible: path separators and literal
   dots both collapse to the same placeholder character, so two different
   real paths (or a project name that itself contains that character) can
   encode identically — decoding one back to a path is a guess, not a
   fact. The only sound direction is forward: take a candidate real path
   you already know (e.g. from the registry listing itself, or from asking
   the user), apply the same encoding, and look THAT up in the registry —
   never invert the encoding to invent a path.
3. **Check both location kinds per matching project**: the conventional
   shapes from Step 1 (a decisions log at the documented path, a decisions
   directory, an ADR directory) AND any path that project's own
   instruction file (`CLAUDE.md` / `AGENTS.md`) registers in its own
   routing table — a project may keep its log somewhere non-standard
   without ever needing this skill updated.
4. **Ceiling before scanning.** If more than 12 active projects match,
   stop, report the count, and ask the user before scanning any of them —
   never silently truncate to the first 12.

## Step 2 — Search

Extract keywords from the question, including synonyms and both English and
Chinese forms (e.g. a question about "why we use X" should also match
entries phrased as "改用 X 的原因" or "decided against Y").

- Small scope (a single `judgment.md` section, a single decision log file)
  → search directly.
- Large scope (an ADR directory with many files, or several candidate
  sources at once) → delegate a targeted lookup per the installed dispatch
  rules — a cheap targeted-search role such as `rohirrim-outrider`.

## Step 3 — Answer

- Direct answer first, then the evidence.
- Every claim cites the source file plus the entry's date or one-liner —
  never an unattributed summary.
- Distinguish a **recorded decision** (quoted or closely paraphrased from an
  entry) from an **inference** (your own reasoning about what the record
  implies) — label inferences as such.
- Multiple entries on the same topic → the newest wins as the current
  answer, but list both so the user can see the history.
- Nothing found → honestly report "no record found" and say exactly where
  you looked. An honest no-record answer is a valid deliverable — never
  fabricate a decision that was never written down.

## Non-goals

- Never writes or edits decision records — that is `/westmarch-scribe`'s
  job, not this skill's.
- Does not re-litigate a question that already has a recorded decision;
  if the user wants to reopen it, that is a new decision to be made (and
  later archived), not something this skill resolves.
- Does not do web research or consult external sources — that is the
  research role's job (e.g. `noldor-loremaster`), not this skill's.
- A decision belongs to exactly one layer — cross-project decisions live
  in the general customize decisions log, project-specific ones live in
  that project's own decisions log. This skill reports whichever single
  layer actually holds the record; it never expects (or reconciles) a
  duplicate copy of the same decision sitting in both.
