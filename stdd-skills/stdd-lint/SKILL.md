---
name: stdd-lint
description: 'STDD mechanical checker — narrative title "Eagle Vision 鷹之視野" (the eagle''s overlook, where no flaw hides). A pure rule-based (non-model-judgment) checker for a single STDD change: scans spec.md/tasks.md for placeholder text and prototype/ leakage, scenario-ID continuity/uniqueness, GWT completeness, Test-mapping/Verification-command completeness, spec-vs-tasks coverage, INFRA/MANUAL reason-line presence, D5-deferred-ratio stats, the two-file approval fingerprint, and cross-artifact reference consistency (design-be/fe REQ/S IDs, api.yml operationId/path/fields, design-fe.md endpoints, Mermaid DB-operation notes) against spec.md/design-be.md/design-fe.md/api.yml. Internal reusable checker — called from stdd-spec/stdd-plan/stdd-execute boundary checks, and also callable directly by the user. Triggers: "/stdd-lint", any caller needing the mechanical boundary check.'
---

# stdd-lint — Eagle Vision 鷹之視野

Opt-in skill (installed from `stdd-skills/`, not auto-loaded from the
plugin's `skills/` directory). Internal reusable checker: called from the
boundary-check steps of `stdd-spec`, `stdd-plan`, and `stdd-execute`, and also
callable directly by the user. It is a **structural** checker for THIS
framework's own spec/tasks placeholders, ID continuity, GWT completeness,
coverage, fingerprint state, and cross-artifact reference consistency
(REQ/S IDs, `api.yml` operations/fields, Mermaid DB-operation notes) against
`design-be.md`/`design-fe.md`/`api.yml`/`tasks.md` — do not confuse this
with third-party OpenAPI syntax/schema validation (e.g. `redocly`), which
remains a separate concern referenced elsewhere and out of scope here; this
skill only cross-references `api.yml`'s already-valid content against the
other artifacts, it does not validate `api.yml` itself.

Run every applicable check below against the target change's
`STDD/<name>/` directory and return ONE combined report — do not stop at the
first failing check. See `references/checklist.md` for a one-table summary
of all 13 checks (trigger condition + FAIL condition, one row each).

## Check 1 — Placeholder text scan (S-26)

Given `spec.md` or `tasks.md` exists, scan both (whichever exist) for:

- `TBD`, `TODO`, `similar to Task N` (with no concrete content), unresolved/
  dangling references, empty verification-command fields, and generic
  filler phrasing such as "add appropriate error handling" with no
  specifics.
- Report every hit as `file:line`.

### Prototype-leakage sub-check

- **Scan scope**: the implementation and test files named by each task in
  `tasks.md`, PLUS — if this is a git project — every file reported by
  `git status --porcelain` (staged AND untracked; this is intentionally
  broader than `git diff --name-only`, which only covers already-tracked,
  unstaged changes).
- Grep that scope for any `prototype/` path reference. Any hit → **FAIL**
  (a visualization prototype, per `stdd-uiux`'s prototype flow, has leaked
  into product code).
- If the project is NOT a git project AND `tasks.md` does not name concrete
  files (scan scope cannot be determined) → report **"cannot determine scan scope"**.
  Do NOT silently treat this as a pass.

## Check 2 — Scenario ID continuity and uniqueness (S-27)

Given a change's `spec.md` (a single file — note this is distinct from
`STDD/specs/`, which is this framework's own spec directory, unrelated to any
individual change's spec):

- Extract every `S-XX` ID.
- Report any gap in numbering (a gap is reported, not judged — a change may
  deliberately skip numbers with a documented reason beyond `[MANUAL]`/
  `[INFRA]`; this checker only surfaces the gap).
- Report any ID that appears more than once within the same change's
  `spec.md` — this is always reported as an error, no judgment call.

## Check 3 — GWT and Test-mapping/Verification-command completeness (S-28)

For every scenario in `spec.md`, check it has ALL of:

- A `GIVEN`, a `WHEN`, and a `THEN` block — missing any one → report as an
  incomplete scenario.
- A `Test mapping` field and a `Verification command` field — missing
  either → report as an incomplete scenario (same report bucket as above).

## Check 4 — Coverage comparison (S-29)

Given both `spec.md` and `tasks.md` exist:

- Extract every `S-XX` ID from `spec.md`.
- Split into two tracks: manual vs. automatable scenarios.
- Compare each track against `tasks.md` (including any "manual verification
  checklist" section it contains).
- `[INFRA]` tasks and `prototype/` content do NOT count toward the
  denominator of either track.
- Report each track's coverage; if either track is below 100%, list which
  scenario IDs are uncovered.

## Check 5 — Two-file fingerprint comparison (S-30)

Given `spec.md` exists and its frontmatter carries `approved_fingerprint`
(and `design_ux_fingerprint` — both fields live in `spec.md`'s frontmatter
only; `design-ux.md` itself carries no fingerprint field of its own):

1. Recompute `spec.md`'s body-only fingerprint with `shasum -a 256` (body =
   everything after the file's second `---` line; no frontmatter → whole
   file is the body). Compare against `approved_fingerprint`. Mismatch →
   report **"changed after approval: spec.md"**.
2. If `design_ux_fingerprint` is non-`null` AND `design-ux.md` exists:
   recompute `design-ux.md`'s body-only fingerprint the same way, compare
   against `spec.md`'s `design_ux_fingerprint`. Mismatch → report **"changed
   after approval: design-ux.md"**.
3. **design-ux consistency check** (do this regardless of whether step 2's
   comparison ran):
   - `design_ux_fingerprint` non-`null` but `design-ux.md` does not exist →
     **FAIL "design-ux.md missing"**.
   - `design_ux_fingerprint` is `null` but `design-ux.md` **does** exist →
     **FAIL "design-ux.md not covered by approval"** (remediation is `stdd-uiux`'s
     backfill flow; report it, do not perform it here).
   - Neither branch is ever silently skipped just because a file is absent.

### v2→v3 migration guard (S-36, checked before step 1 above)

Before comparing fingerprints, check whether `design_ux_fingerprint` is
**entirely absent** from `spec.md`'s frontmatter (the key itself missing —
distinct from the key being present and set to `null`):

- **Key missing entirely** → this is a v2-era artifact that predates the
  two-file fingerprint scheme. Treat the change as `draft` regardless of
  its recorded `status`, and report that it needs a one-time re-approval
  under the v3 scheme (state the reason explicitly — never pass silently).
- **Key present and `null`** → legal v3 state (no UI surface). Do not treat
  this as a migration case; proceed with the normal comparisons above.
- **Key present and non-`null`, but the recomputed fingerprint disagrees** →
  this is an ordinary fingerprint mismatch (step 1/2 above), not a migration
  case.

## Check 6 — INFRA/MANUAL reason lines and D5 deferred-ratio stats (S-40)

Given `tasks.md` exists:

- Extract every `[INFRA]`/`[MANUAL]` task and check each has a one-line
  reason attached. Any task missing its reason line → **FAIL**, reported
  with that task's `file:line`.
- Compute the D5-deferred-scenario ratio: extract every scenario in
  `spec.md` explicitly marked as deferred under D5, and report
  `deferred count / total scenario count (percentage)` (e.g. `3/20（15%）`),
  plus an itemized list of each deferred scenario's ID and one-line reason.
  This ratio has no hard ceiling — it is reported for human review only,
  never used to auto-fail.
- Fold both results into the combined coverage report from Check 4.

## Check 7 — Banned Mermaid construct scan (S-53)

Scan every Mermaid code block across the change's artifacts (`spec.md`,
`design-be.md`, `design-fe.md`, `design-ux.md`, etc.) against the banned-
constructs list in `references/checklist.md` (the single source — do not
duplicate that list here). Any match → **FAIL**, reported with the offending
`file:line`.

## Check 8 — Not-installed STOP rule (S-31)

This rule governs the CALLER, not `stdd-lint` itself: any `stdd-*` skill
that needs to call `/stdd-lint` for its boundary check and finds it not
installed in the environment SHALL STOP and report **"`/stdd-lint` not
installed - mechanical check incomplete"** — it SHALL NOT silently skip the mechanical check and
continue (this would let placeholder/coverage/fingerprint problems slip
through unnoticed). This is a single-source rule stated here for reference;
enforcing it is each caller's own responsibility at its call site.

## Checks 9-13 — cross-artifact consistency (design/api/tasks)

These five checks implement items 1-5 of `stdd-plan`'s six delegated
mechanical cross-checks (S-08 gate, `references/design-review-checklist.md`
"Mechanical checks" list); item 6 of that list (`tasks.md` scenario ↔
`spec.md` coverage) is already Check 4 above — not duplicated here.

## Check 9 — design-be/fe REQ/S ID cross-reference (S-54)

Given `design-be.md` and/or `design-fe.md` exists:

- Extract every `REQ-XX`/`S-XX` ID referenced in `design-be.md` and
  `design-fe.md` (e.g. "Implements `REQ-01`, `REQ-02`").
- Extract every `REQ-XX`/`S-XX` ID defined in `spec.md`.
- Any ID referenced in a design file that does not exist in `spec.md` →
  **FAIL "unknown ID referenced: `<ID>`"**, with `file:line`.
- This check only catches a design referencing an ID that doesn't exist; it
  does not check the reverse (a spec ID with no design coverage at all) —
  that's judgment item (a) delegated to the fresh-context verifier, not this
  mechanical check.
- SKIP if neither `design-be.md` nor `design-fe.md` exists, stating that
  reason.

## Check 10 — api.yml operationId/path ↔ design-be.md (S-55)

Given `api.yml` exists:

- Extract every `operationId` and `path`+method pair from `api.yml`.
- Extract every endpoint (path and/or `operationId`) named in
  `design-be.md`'s plan/sequence sections.
- Any `api.yml` operation with no corresponding mention in `design-be.md` →
  **FAIL "api.yml operation `<operationId>` (`<method> <path>`) not
  referenced in design-be.md"**.
- Any endpoint named in `design-be.md` with no matching entry in `api.yml`
  → **FAIL "design-be.md references unknown endpoint `<path>`"**.
- SKIP if `api.yml` does not exist (not every change adds or changes an
  API), stating that reason.

## Check 11 — api.yml field names ↔ design-be.md table schema (S-56)

Given `api.yml` exists AND `design-be.md` contains a "Table schema" section:

- Extract every request/response schema field name from `api.yml`.
- Extract every column name from `design-be.md`'s "Table schema" table(s).
- Apply the camelCase↔snake_case transform to each field/column name and
  check a match exists on the other side (the comparison is symmetric).
- Any `api.yml` field with no snake_case counterpart in the table schema,
  and not explicitly noted as a computed/derived (non-persisted) field →
  **FAIL "api.yml field `<field>` has no matching table-schema column"**.
- SKIP if `api.yml` does not exist, or `design-be.md` has no "Table schema"
  section (the change touches no persisted data) — state which precondition
  is unmet.

## Check 12 — design-fe.md referenced endpoints ↔ api.yml (S-57)

Given `design-fe.md` exists:

- Extract every endpoint reference in `design-fe.md` (e.g.
  "`GET /api/subscriptions`").
- Compare against `api.yml`'s `path`+method pairs.
- Any endpoint referenced in `design-fe.md` with no matching `path`+method
  in `api.yml` → **FAIL "design-fe.md references unknown endpoint
  `<method> <path>`"**.
- SKIP if `design-fe.md` does not exist, or `api.yml` does not exist — state
  which precondition is unmet.

## Check 13 — design-be.md Mermaid DB-operation notes ↔ table schema (S-58)

Given `design-be.md` exists and contains a "Table schema" section:

- Scan `design-be.md`'s Mermaid `sequenceDiagram`/`graph` blocks for
  DB-operation notes (free-text edge labels naming a table operation, e.g.
  "enqueue retry", "increment attempt").
- For each such note that names a column or table explicitly, check that
  column/table exists in the "Table schema" section.
- Any note referencing a column/table not present in the table schema →
  **FAIL "Mermaid note references unknown column/table: `<name>`"**, with
  `file:line`.
- SKIP if `design-be.md` has no "Table schema" section (nothing to
  cross-check the notes against), stating that reason.

## Report format

Return one combined report covering every check above that applied (a check
whose precondition isn't met — e.g. no `tasks.md` yet — is simply omitted,
not reported as a failure). For every hit, always give a `file:line`
reference where the artifact structure allows it.

## Notes for a fresh session

- This is a rule-based, non-model-judgment checker — do not use subjective
  taste calls inside any of the checks above; every check is either a
  string/pattern match, an ID-extraction comparison, or a `shasum -a 256`
  recomputation.
- Checks 1-4 and 6 require no git repository to run (only the prototype
  leakage sub-check under Check 1 needs git, and degrades to the explicit
  "cannot determine scan scope" report when git is unavailable and files aren't named).
- Checks 5's fingerprint recomputation is read-only — this skill never
  writes `approved_fingerprint`, `design_ux_fingerprint`, or `status` back
  to any file; it only compares and reports.
