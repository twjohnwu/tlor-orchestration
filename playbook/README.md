# playbook/ — authoring pipeline for `agent_doc/algorithms/`

What ships to users is only `agent_doc/algorithms/*.md` (README, INDEX,
one entry per algorithm). This directory is how those files are built and
checked. Nothing here is installed by `install.sh`.

## Layout

```
playbook/
  sources.yaml              evidence repos (url, local_dir, commit, license)
  taxonomy/algorithms.yaml  canonical ids, aliases, related, status
  metadata/algorithms/      <id>.yaml — structured twin of each entry
  eval/                     retrieval.jsonl, selection.jsonl, rejection.jsonl
  scripts/
    scan_sources.py         clones → .build/inventory.jsonl
    extract_candidates.py   inventory + taxonomy → .build/evidence/<id>.json
    distill.py              evidence → .build/prompts/<id>.md; checks entry sections
    validate.py             entry ↔ metadata consistency; extracts the Python
                            block to .build/impl/<id>.py and runs its tests
    build_index.py          metadata → agent_doc/algorithms/INDEX.md
    evaluate.py             runs the three eval sets against INDEX.md
  .build/                   gitignored scratch
```

Dependencies: Python 3.7+ (scripts and canonical implementations must run on 3.7 and 3.12 — no walrus, no `X | Y` types, use `from __future__ import annotations`) and `pyyaml`. Nothing else.

## Pipeline (per intro: inventory → taxonomy → evidence → distill → validate)

1. `scan_sources.py --sources-root <dir>` — walks every repo in
   `sources.yaml`, emits one inventory line per candidate file
   (source, path, language, candidate name, category guess, license).
2. `extract_candidates.py --id <id>` — maps inventory lines to a taxonomy
   id by alias match, bundles code + comments + README excerpt + tests per
   source into `.build/evidence/<id>.json`. Unmatched → `unclassified`,
   never a new id.
3. `distill.py --id <id>` — writes a prompt pack: the evidence side by
   side, the entry template, and the distillation rules (compare all
   sources; conflicts → `review_required: true`; never summarize one repo).
   A gondor-builder dispatch (not a script) writes the entry + metadata +
   tests from the pack.
4. `validate.py --id <id>` — entry has every section in order; metadata
   fields match frontmatter; Python block compiles; `tests/playbook/
   algorithms/test_<id>.py` passes; License Provenance rows cite commits
   present in `sources.yaml`.
5. `build_index.py` — regenerates `INDEX.md` from metadata (sorted by id).
   Commit the regenerated file.
6. `evaluate.py` — keyword retriever over INDEX signals (the same lookup an
   agent does with Grep). Prints Recall@3, MRR, Top-1, Constraint
   Violation Rate, Wrong Algorithm Rate, and n. With few entries the
   numbers are smoke checks, not quality claims.
   The eval queries were written next to the signal lists, so the numbers are a regression floor, not an independent quality measurement; add held-out queries written without reading INDEX.md before trusting them.

## Why no database

Agents reach this playbook through installed markdown plus Grep/Read; a
plugin install carries no Python dependency guarantee and no embedding
model. Under ~100 entries a one-row-per-algorithm INDEX is exact and
cheap. Revisit SQLite/FTS5 (and only then vectors) when the taxonomy
passes ~100 entries or Grep demonstrably misses in `evaluate.py`.

## Confidence rules (from the source plan)

≥2 primary sources agree → `high`; one primary → `medium`; secondary only
or conflicting → `review_required: true`. Secondary repos add variants
and competitive-programming edge cases; they never decide alone.

## License

All six sources are MIT. Every entry keeps repo, path, commit and license
per source. Canonical implementations are rewrites, not copies.
