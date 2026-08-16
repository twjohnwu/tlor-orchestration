# STDD review: the statusline rewrites

[← Back to README](../../../README.md)

Written 2026-08-15.

STDD (spec-test-driven development) is this workspace's opt-in pipeline for
high-stakes changes: `explore → uiux → spec → plan → execute`, with
adversarial review panels at the spec gate, fingerprint-locked artifacts, a
RED → GREEN → REFACTOR loop per task, and independent fresh-context
verification of every deliverable. The framework has now been dogfooded
twice, both times on *replacement-type* projects where the acceptance bar
was "behave exactly like the predecessor":

- **D1** — `coralline` → `phosphorflux`: a TypeScript rewrite of a Claude
  Code statusline tool (2026-07-30 to 08-03).
  Published audit trail: [phosphorflux `docs/tlor-stdd/`](https://github.com/twjohnwu/phosphorflux/tree/main/docs/tlor-stdd).
- **D2** — `phosphorflux` → `phosphorpulse`: a Rust rewrite of the same
  tool (byte-parity renderer, then a full-screen TUI with Codex CLI
  integration; 2026-08-14/15).
  Published audit trail: [phosphorpulse `docs/tlor-stdd/`](https://github.com/twjohnwu/phosphorpulse/tree/main/docs/tlor-stdd).

This report compares the two runs: token spend per pipeline stage, the
rework patterns both runs exposed, what got fixed in the framework between
and during them, and what is still on the list.

## 1. Scale and rounds

| | D1 (TS rewrite) | D2a (Rust renderer) | D2b (Rust TUI) |
|---|---|---|---|
| Requirements / scenarios | 11 / 27 | 9 / 17 | 9 / 17 |
| Tasks | 39 items (converging to 8 TDD + 4 INFRA) | 12 | 12 |
| Spec panel verdicts | 11/11 REFUTED → revised | several REFUTED (incl. a golden-nondeterminism catch that would have invalidated the whole execute phase) | several REFUTED in v1 (e.g. a fused TextMate-scope design flaw) |
| Fix rounds inside execute | 6 rounds across 4 tasks (max 2 per task) | 5 rounds on one task (the single most expensive point) | 3 sanctioned single-round fixes |
| Post-execute walkthrough | 8 patch releases, 8 failure classes | 8 review rounds | 14 review rounds + 9 user-driven walkthrough rounds |

## 2. Token accounting

**Metrics differ between runs — read the caveat first.** D1's ledger
records *output tokens* (much of the work ran through workflow fan-out).
D2 records *per-dispatch total context* (`subagent_tokens`). The columns
are not divisible into each other; within-column structure is what matters.

### D1 (~2.07M output tokens, ≈$185 API-equivalent)

| Component | Amount |
|---|---|
| Main dialogue | 186,897 output tokens |
| Role dispatches ×41 | ~308k |
| Workflow agents (9 runs, 3,672 records) | ~1.58M |

Execute was ~89% of dispatch usage. Recorded waste: one scaffold-race
round burning 6.4M tokens across 86 agents; a rate-limit wipeout costing
1.68M across 21 agents; 223.6M cumulative cache-read tokens from every
agent re-reading the spec.

### D2a — Rust renderer (61 dispatches, ~3.46M subagent tokens)

| Pipeline stage | Agents | Count | Tokens |
|---|---|---:|---:|
| explore | search + Rust spike | 2 | 131k |
| spec panel | 3 adversarial lenses (opus) | 3 | 279k |
| plan verification | verifier ×2 | 2 | 126k |
| execute (RED/GREEN/fix) | Codex via agent wrapper | 26 | 1,292k |
| execute verification | fresh-context verifier | 12 | 681k |
| review closeout | 8 review/fix rounds | 10 | 494k |
| TUI pre-work (explore/spec) | search/research/panel | 6 | 452k |
| **Total** | | **61** | **≈3,455k** |

Worst single point: one task consumed 7 dispatches = 405k (GREEN + 5 fix
rounds + verification); ~150k of that was avoidable by pre-loading known
pitfalls (e.g. macOS first-exec latency on freshly written stubs) into the
RED prompt — which is exactly what the dispatch checklist rule now does.
Root-cause measurement: *every* subagent carries a ~33k fixed context
floor (the auto-loaded rules corpus is ~21k of it); the agent wrapper
around the Codex CLI added another ~13k, for a 46,428-token floor per
builder dispatch regardless of task size.

### D2b — TUI (+9 walkthrough rounds, ~2.33M subagent tokens)

| Stage | Direct Codex CLI calls | Claude dispatches | Tokens |
|---|---:|---:|---:|
| execute T1–T12 builders | ~26 | 0 | ≈0 |
| execute verification | — | 14 | ~925k |
| review (14 rounds + 13 fix rounds) | ~27 | 1 | ~69k |
| documentation (bilingual README/guides) | ~4 | 5 | ~300k |
| walkthrough fixes (9 rounds) | ~22 | 0 | ≈0 |
| walkthrough verification + research | — | 12 | ~880k |
| framework maintenance | — | 3 | ~156k |
| **Total** | **~79** | **35** | **≈2.33M** |

The cost-reduction plan landed between D2a and D2b: replacing the agent
wrapper with direct CLI invocation cut the builder side from ~46k per
dispatch to ~0 — an estimated 2.8–3.6M saved over ~79 calls. The cost
center moved wholesale to verification: 27 verifier dispatches ≈1.87M
(~81%), with per-round cost growing from 54k to 90–104k as fingerprint
ledgers and criteria accumulated in prompts.

## 3. Rework patterns common to both runs

1. **Parity detail surfaces after execute — except where an oracle
   exists.** D1's costliest lesson: the predecessor was executable the
   whole time, yet a golden-diff oracle was only built after multiple
   rounds of human eyeballing. D2a applied golden-first and its renderer
   needed *zero* walkthrough rounds — 17 scenarios passed on first user
   contact. D2b's nine walkthrough rounds all landed in the oracle-less
   surface (TUI visuals, keybindings, i18n). Rule of thumb:
   **walkthrough rounds ≈ oracle-less surface area**.
2. **Tests certify themselves if you let them.** D1: a synthetic fixture
   produced false greens three times on the same field. D2: one test
   compared the implementation against itself (a compile-time tautology),
   another encoded the wrong move semantics as its expectation. Green
   tests prove nothing about parity; only fresh-context review against an
   independent oracle (the frozen predecessor's source) caught these.
3. **Prose bans don't stop mechanical violations.** A repo-wide formatter
   sweep leaked through three separate dispatches in D2 despite an
   explicit ban in every prompt. The durable fix was a script, not
   stronger wording: a mechanical-check script (fingerprint ledger, test
   counts, tracked-file allowlist, spec fingerprints — one PASS/FAIL line
   each plus a debug log) now runs before any verifier dispatch.
4. **The cost center migrates after every fix.** D1 was dominated by
   workflow fan-out races; D2a by the wrapper's fixed floor; D2b — with
   builders at ~0 — by verification. Each eliminated bottleneck exposes
   the next; the current one is the fixed context floor under verifier
   dispatches and mechanical checks mixed into judgment work.

## 4. Framework improvements landed so far

| Improvement | Origin | Status |
|---|---|---|
| Test-file fingerprint firewall (sha256 carried through prompts, not files) | D1 | enforced throughout D2; caught one real violation and three formatter leaks |
| Golden/oracle-first for replacement-type changes | D1 lesson | validated in D2a (zero renderer walkthrough rounds) |
| Dispatch checklist (10 field-proven clauses: stub warm-up, piped stdio, sandbox limits, regression attribution, …) | distilled from D2a's 5-round rework | applied throughout D2b |
| Direct CLI invocation for builders (bypassing the ~46k/dispatch agent wrapper) | D2a measurement | used for all of D2b; two invocation pitfalls (write-mode flag, shell quoting) fed back into the recipe |
| Sanctioned-fix procedure (authorized locked-test amendments with re-baselined fingerprints) | D2a | used 4 times in D2b, each with evidence and re-verification |
| Mandatory source-line citations when mirroring a reference implementation | D2b walkthrough round 3 | builders may not restyle UI layers from memory |
| Mechanical-check script (fingerprints / test counts / scope allowlist / spec hashes) | D2b | landed with fail-then-pass validation |

## 5. Recommendations and open items

1. **Generate the mechanical-check script inside the pipeline** (approved
   direction): as soon as RED completes and the orchestrator holds the
   test fingerprints, emit/update a per-change script (ledger, per-task
   verification commands with expected counts, scope allowlist, spec
   hashes; PASS/FAIL + debug log). Run it before every GREEN/fix/verify;
   verifiers keep only judgment work. Expected: 15–25k saved per
   verification round, plus immediate interception of formatter-leak-class
   violations.
2. **Formalize the walkthrough as a pipeline stage.** Both runs prove that
   for replacement-type changes, "execute complete" ≠ "acceptable": D1
   took 8 patch releases, D2b took 9 rounds. Make the
   report → adjudicate-against-oracle → batched-fix → mechanical-check →
   verify loop an explicit stage between the completion gate and the
   manual checklist, and budget its rounds at plan time for UI-bearing
   changes.
3. **Screen-mapping artifact for UI changes.** Design prose does not
   constrain a UI layer; a plan-stage table (per screen: reference
   implementation file:line ↔ new file ↔ keybinding/visual invariants)
   consumed by builder prompts and verifier checks would likely have saved
   3–4 of D2b's nine rounds.
4. **Shrink the per-dispatch context floor** (open decision): options are
   conditional rule loading for subagents, corpus distillation, or
   per-role inheritance opt-out. At D2b's 35 Claude dispatches, full
   realization saves ≈700k per change.
5. **Generalize oracle-first**: "a replacement-type change must have an
   executable oracle (golden diff or screen mapping) before its first
   task" belongs in the plan-stage design checklist — paid for in D1,
   validated in D2a.

## Methodology

Numbers come from three sources: D1's committed ledgers in the
phosphorflux audit trail; D2's per-dispatch harness telemetry
(`subagent_tokens`, exact values); and direct-call counts tallied from the
session record (±3). All figures were re-verified against their primary
sources by a fresh-context reviewer before publication; two errors it
caught (a scenario count and a percentage) were corrected. The two runs'
metrics are intentionally not merged into a single total because their
units differ.
