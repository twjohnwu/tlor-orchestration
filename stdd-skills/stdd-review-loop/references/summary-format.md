# summary-format.md — the "AI Review Fixes" description section

Written by step 7 through `set-section` (default heading
`## AI Review Fixes`). The file passed to `--file` holds the whole section,
heading included; an existing section with that heading is replaced, so
rerunning step 7 never duplicates it.

## Format

- One row for EVERY finding from every round, blocking and non-blocking,
  in round order, then finding number (`#` is the `n` from `parse`, or the
  number given when the findings were listed by hand).
- One row per CI job repaired in step 4b, after that round's review rows,
  numbered on from them.
- `Severity`: the severity word as the review bot wrote it; `CI` for a CI
  repair.
- `File:Line`: `path:line` from `parse`, or `—` when the finding named none
  (always `—` for a CI repair).
- `Finding`: one line, shortened from the bot's text; no line breaks or `|`.
  For a CI repair: the job name and the first error line of its log, e.g.
  `lint: E501 line too long`.
- `Resolution`: exactly one of
  - `Fixed`
  - `Fixed — CI repair`
  - `Not fixed — false positive (see comment)`
  - `Not fixed — non-blocking (<severity>)`, e.g. `Not fixed — non-blocking (Low)`
  - `Fixed — not re-reviewed (round cap)`, for a fix (review or CI repair)
    pushed in the last round, after the last review
  - `Not fixed — fix failed (see report)`, for a finding that held, or a
    failed CI job, whose fix did not land (SKILL.md step 4b item 5, step 7
    row 4), and for a failed CI job whose log could not be fetched
    (`job-log` error, SKILL.md step 4b item 1)
- `Commit`: short SHA of that round's fix commit (`fix: address AI review
  round <R>`, `fix: repair CI (…) round <R>`, or the combined message) for
  every `Fixed` value; `—` for every `Not fixed` row.
- If the round cap (`max-rounds`, default 10) was hit, add one line under
  the table: `Stopped at round cap: round <max-rounds>'s fixes were pushed
  but not re-reviewed.`

## Example

```markdown
## AI Review Fixes

| Round | # | Severity | File:Line | Finding | Resolution | Commit |
|---|---|---|---|---|---|---|
| 1 | 1 | High | src/orders/service.py:42 | Unvalidated quantity can be negative | Fixed | a1b2c3d |
| 1 | 2 | Medium | src/orders/api.py:88 | Missing 404 when order id is unknown | Fixed | a1b2c3d |
| 1 | 3 | Warning | src/orders/repo.py:17 | Query built by string concatenation | Not fixed — false positive (see comment) | — |
| 1 | 4 | Low | src/orders/service.py:57 | Rename tmp to remaining_quantity | Not fixed — non-blocking (Low) | — |
| 2 | 1 | Medium | tests/test_orders.py:120 | Assertion compares against stale fixture | Fixed | e4f5a6b |
| 2 | 2 | Nit | — | Trailing whitespace in the module docstring | Not fixed — non-blocking (Nit) | — |
| 2 | 3 | CI | — | unit-tests: AssertionError: expected 3 orders, got 2 | Fixed — CI repair | e4f5a6b |
```

### Human review comments

| Reviewer | Comment (file:line) | Outcome | Commit |
|---|---|---|---|
| <login> | <one-line gist> (`path:line` if inline) | fixed / replied | <short sha or —> |

Omit this section when H was empty in every round.
