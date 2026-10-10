# summary-format.md — the "AI Review Fixes" description section

Written by step 7 through `set-section` (default heading
`## AI Review Fixes`). The file passed to `--file` holds the whole section,
heading included; an existing section with that heading is replaced, so
rerunning step 7 never duplicates it.

## Format

- One row for EVERY finding from every round, blocking and non-blocking,
  in round order, then finding number (`#` is the `n` from `parse`, or the
  number given when the findings were listed by hand).
- `Severity`: the severity word as the review bot wrote it.
- `File:Line`: `path:line` from `parse`, or `—` when the finding named none.
- `Finding`: one line, shortened from the bot's text; no line breaks or `|`.
- `Resolution`: exactly one of
  - `Fixed`
  - `Not fixed — false positive (see comment)`
  - `Not fixed — non-blocking (<severity>)`, e.g. `Not fixed — non-blocking (Low)`
  - `Fixed — not re-reviewed (round cap)`, for a round-10 fix pushed after
    the last review
- `Commit`: short SHA of that round's `fix: address AI review round <R>`
  commit for `Fixed` rows (both `Fixed` values); `—` for every `Not fixed` row.
- If the round cap (10) was hit, add one line under the table:
  `Stopped at round cap: round 10's fixes were pushed but not re-reviewed.`

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
```
