---
name: stdd-execute
description: 'STDD execute phase. Runs the per-task RED → GREEN → REFACTOR TDD loop against an approved STDD tasks.md, using a two-dispatch model (builder-RED, builder-GREEN+REFACTOR) with an independent verifier and a test-file fingerprint passed through the dispatch prompt. Triggers: "stdd-execute", "run the TDD loop task by task", "run RED GREEN REFACTOR", or any request to implement STDD tasks one at a time. Requires an approved spec.md and an existing tasks.md; refuses otherwise.'
---

# stdd-execute — Forge 鑄造

Fourth phase of the STDD pipeline. Implements each `tasks.md` task with a
strict RED → GREEN → REFACTOR loop and a task-boundary spec re-check.
Canonical spec: REQ-04 (this SKILL.md is the single source — no separate spec file exists in this repo); cross-cutting
mechanisms (frontmatter status, dual-fingerprint rule, `[wip]`/`[x]`
semantics, Lint-STOP, design-ux consistency check) are canonical in
`stdd-skills/stdd-spec/SKILL.md` Step 6 — referenced here, not restated.

## 0. Precondition

`stdd-plan`'s own coverage/approval gate (S-08) already blocks tasks.md from
existing without an approved spec — do not re-invent an extra triage
checkpoint here. Do read `tasks.md` for any `[wip]` task before starting new
work (see step 3, interrupt recovery) — a `[wip]` task means the previous
`stdd-execute` run was interrupted, and recovery is this skill's job, not
`/stdd`'s (`/stdd` only reports "task X appears interrupted", it never touches the
file).

Only one `stdd-execute` session may run against a given change directory at
a time. STDD provides no file lock for this — it is a documented limit, not
a mechanism; do not treat the absence of a lock error as permission to run
two sessions concurrently.

## 1. Picking a task

Take the next `[ ]` task from `tasks.md` in order (or the `[wip]` task if
recovering an interruption — see step 3). Route it:

- `S-XX` scenario task → full two-dispatch RED/GREEN/REFACTOR loop (steps
  2–5 below).
- `[INFRA]` task, or an obviously small single-file change → the fast path
  (step 7).
- `[MANUAL]` entries are never executed here — they live in the "Manual
  verification checklist" and are confirmed one by one at the completion gate (step 5).

## 2. Dispatch A — builder-RED (S-10)

Dispatch a builder (role `gondor-builder` if tlor-orchestration/pinned roles are
installed, otherwise a generic subagent with `model: sonnet` stated
explicitly) with these exact instructions:

1. Read the task's `S-XX` scenario GIVEN/WHEN/THEN from `spec.md`.
2. Write a test function named `test_sXX_<scenario_snake>`.
3. Reference `REQ-XX / S-XX` in the test's docstring.
4. Run the task's verification command and confirm the test **fails for
   the correct reason** (a real assertion failure against the intended
   behavior — not an import error or syntax error). If the first run fails
   on import/collection (e.g. the target module or class doesn't exist
   yet), first create a **minimal stub** — the class/function signatures
   the test imports, each raising `NotImplementedError` — then re-run.
   Stubbing is part of RED, not implementation: it exists only to convert
   an import error into a behavioral failure.
5. **ONLY NOW** mark this task `[wip]` in `tasks.md` — after the test file
   is written, never before. `[wip]` is what closes the test file to
   further writes (see `hooks/stdd_test_guard.py`'s `[wip]`-block
   protection), so marking it first would lock out this dispatch's own RED
   write. This is the *only* place `[wip]` gets written, so an interruption
   after this point is detectable later.
6. Quote the actual RED output, then **end the dispatch**. **Do not write
   any implementation code** in this dispatch.

After Dispatch A reports back, the **main session** (not the builder) uses
a read-only command (`shasum -a 256 <test file>`) to compute the test
file's content fingerprint itself, and carries that fingerprint plus a
summary of the RED output into Dispatch B's prompt. The fingerprint travels
through the prompt, not through any file the builder can edit — so the
builder cannot tamper with the baseline it's being checked against.

Verification: the test, run directly, exits non-zero with the expected
failure message; Dispatch A's report contains no implementation code.

## 3. Dispatch B — builder-GREEN+REFACTOR (S-11, S-12)

Dispatch a builder (same role selection rule as Dispatch A) carrying the
fingerprint + RED summary from step 2, with these instructions:

**GREEN:**
1. Write the minimum code needed to make the test pass.
2. **Do not modify the test file** — its content must stay identical to the
   fingerprint captured after RED.
3. Run the verification command and confirm the test **passes**.
4. Run the full previously-passing scenario suite and confirm no
   regressions.

**REFACTOR** (same dispatch, not a separate one):
5. Check for SOLID violations (single responsibility, open/closed, Liskov
   substitution, interface segregation, dependency inversion).
6. Check for DRY violations (duplicated logic, copy-paste patterns).
7. Check for code smells (overly long methods, deep nesting, magic
   numbers).
8. Refactor **only** where a violation was actually found.
9. **Do not modify the test file** (same restriction as GREEN).
10. Re-run the full test suite after each refactor change and confirm it
    still passes.

### Interrupt recovery (S-11)

Any interruption during Dispatch A/B recovers via `[wip]` detection
(consumed by this skill, not `/stdd` — per S-19):

- **Recovering into or after GREEN**: re-run the task's verification
  command. Even on recovery, the task must still pass the full step-5
  task-boundary check (regression scan + plan-drift check + manual gate,
  same as the normal path) before it may be marked `[x]` — recovery never
  skips the ordinary completion gate.
- **Recovering into RED, or any error state**: reset the task to `[ ]` and
  redo it. Dispatch A rewrites the same-named test file **by overwriting
  it** (this is the one legitimate exception to the fingerprint firewall in
  step 4).
- **Leftover partial implementation, git-tracked project**: use `git diff`
  to identify and **revert only the hunks introduced by this task** — never
  a whole-file `git checkout`, which would destroy uncommitted work from
  earlier tasks in the same file. If attribution of a hunk to this task
  can't be determined, **STOP** and report to the user for a decision.
- **Non-git project**: **STOP** and report to the user for manual
  disposition — do not attempt automatic recovery.

## 4. Dispatch integration & fingerprint firewall (S-14)

- Every scenario task uses exactly two dispatches (Dispatch A, Dispatch B
  above); role selection: `gondor-builder` for both if tlor-orchestration (or an
  equivalent pinned-role package) is installed, otherwise a generic
  subagent with `model: sonnet` stated explicitly.
- **Independent verifier**, dispatched after Dispatch B (role
  `eagle-sentinel` with `model: sonnet` — the routine read-back override —
  if tlor-orchestration is installed, otherwise a generic subagent with `model:
  sonnet` stated explicitly). The verifier does:
  - Accepts Dispatch A's quoted RED output as the RED evidence (RED
    evidence = Dispatch A's quote + the main session's checkpoint at that
    time). It is **not** required to reproduce RED.
  - Leaves deterministic test-file fingerprint comparison to the per-change
    mechanical gate in section 4a, while retaining S-14's substantive rule
    that the test must not be tampered with after RED. A mismatch still sends
    the task back for redo; the verifier does not spend prompt tokens parsing
    or comparing the hashes itself.
  - Actually re-runs the verification command and confirms GREEN.
  - Passes the task's spec GIVEN/WHEN/THEN into its own acceptance
    criteria (carried in the dispatch prompt for every dispatch, per
    template convention — not restated here).
- **Builder vs. verifier disagreement**: if they fail to converge after
  **2 rounds**, escalate to the user for a decision — do not grind past
  that cap.
- **Test-file fingerprint firewall**: once Dispatch A establishes the RED
  fingerprint baseline, that test file must not be written to again before
  the task is marked `[x]` — the only legitimate exception is the S-17
  plan-drift-triggered rewrite (Dispatch A overwrites the same-named file
  during recovery, step 3). Any other write is a violation; a mechanical
  layer does not need to distinguish "authorized dispatch" from
  "unauthorized subagent" here — it can block all writes uniformly. This
  firewall is an **optional** PreToolUse hook, **not installed by
  default**; if the hook is installed, document its install/removal steps
  and remove the hook's registration from `settings.json` **before**
  removing the plugin, to avoid an orphaned hook breaking tool calls. When
  the hook is absent (or misses an attempt), `/stdd-lint`'s post-hoc
  fingerprint comparison (`stdd-lint` Check 5, S-30) is the fallback
  detection — not a preventive one.
  - **Honest disclosure**: `status`/`approved_fingerprint`/
    `design_ux_fingerprint` frontmatter fields have **zero** mechanical
    protection under any circumstance — only user approval in conversation
    plus `stdd-lint`'s post-hoc comparison guard them (see
    S-05, REQ-09). Do not imply
    this skill closes that gap; it doesn't, by design.
  - This is not in tension with 4a's spec/design-ux body-hash comparison
    (check 4, below): that check catches a body edited **after** approval
    without re-baselining the frontmatter fingerprint that recorded it — a
    real, mechanical trip-wire. It cannot catch body and frontmatter
    **forged together in the same edit**, which is exactly the "zero
    mechanical protection" case above. The two passages describe different
    threat models, not a contradiction.
- The `[INFRA]` fast path (step 7) still always runs the verifier — it only
  skips the multi-round RED/GREEN dispatch split, not verification.

## 4a. Per-change mechanical gate (S-14 deterministic layer)

After RED completes and the orchestrator holds the test fingerprint(s), the
orchestrator dispatches `dwarf-smith` (when tlor-orchestration is installed;
otherwise a generic subagent with `model: sonnet` stated explicitly) to
instantiate `templates/mechanical_check.sh.tmpl` in the change's own
`scripts/` directory, together with its test-fingerprint ledger and scope
allowlist. The dispatch prompt supplies the fingerprint(s), expected test
count, allowlist contents, test command/count parser, and relative artifact
paths **VERBATIM** as the recipe; it follows the Dispatch A/B prompt style in
steps 2–3 and reads its created files back. The orchestrator MUST NOT WRITE
these files itself: `rules/dispatch.md` §1 requires that “the commander does
no field work.”

Before Dispatch B in step 3, before every fix-round dispatch in step 4, and
before every independent-verifier dispatch in step 4, run the generated script
from the change directory. A `MECH …: FAIL` / non-zero result blocks that
dispatch rather than spending it. This is a token-saving gate: stable failures
in fingerprints, result counts, changed-file scope, or frozen document hashes
are settled cheaply before a judgment-capable agent is called.

The independent verifier's acceptance criteria consequently drop mechanical
fingerprint comparison, test-count comparison, scope-allowlist comparison, and
spec/design-ux body-hash comparison. It retains only judgment work: whether the
test asserts the intended GIVEN/WHEN/THEN behavior, whether implementation is
correct, and whether regressions or design concerns require action. This is the
point at which the token saving is realized: the verifier no longer repeats
deterministic parsing and comparison inside its prompt.

This script is a new deterministic layer **on top of**, not a replacement for,
the S-14 fingerprint firewall and its `stdd-lint` fallback. Under step 6's
plan-drift protocol, or whenever a legitimate RED redo changes the baseline,
dispatch another agent to re-baseline the ledger; never rewrite the ledger
inline from the orchestrator.

**Honest limit:** the script reads the artifacts itself, but its output is still
relayed by a dispatched agent on the workflow path. That custody limitation is
the same class as step 8's relay limits; a strict exit-code/output relay reduces
but does not eliminate misreporting risk.

## 5. Task-boundary spec re-check (S-13)

Once a task's RED → GREEN → REFACTOR is done:

1. Run the verification commands for every scenario covered so far. Any
   regression → **STOP** (treat as a wrong-direction signal per
   judgment.md §4 — do not patch around it).
2. Check whether this task's implementation has drifted from
   `design-be.md` / `design-fe.md` / `api.yml` (plan-drift check). Drift
   found → trigger the plan-change protocol (step 6 / S-17) before
   proceeding further.
3. Call `/stdd-lint` to re-compare `S-XX` coverage between `spec.md` and
   `tasks.md`, and to re-verify both fingerprints: `spec.md`'s body against
   `approved_fingerprint`, and (if `design-ux.md` exists) its body against
   `spec.md`'s `design_ux_fingerprint`. This makes sure execution itself
   hasn't drifted spec/design-ux out from under their recorded
   fingerprints. Apply the design-ux consistency check exactly as defined
   in `stdd-skills/stdd-spec/SKILL.md` Step 6's design-ux consistency check
   section (single source of truth, (a)/(b) branches) — never skip branch (b) just because
   `design-ux.md` happens not to exist.
4. Mark the task `[x]` in `tasks.md`.
5. Report: N/M scenarios green, task K/T complete.
6. **Completion gate**: when all K/T tasks are done (execute is wrapping
   up), confirm every entry in the "Manual verification checklist" (from S-08) one by one
   with the user. Any unconfirmed entry → the completion report MUST say
   "manual verification incomplete: N items" and MUST NOT claim the change is complete.
7. **0/0 boundary**: if every scenario in the change is manual (no TDD
   tasks at all, so K/T doesn't apply), completion = full confirmation of
   the manual verification checklist. The completion report must explicitly
   say "0 TDD tasks" — the K/T-not-applicable case is not an excuse to skip
   this gate.

If `/stdd-lint` is not installed at any of these checkpoints, **STOP** and
report "`/stdd-lint` not installed - mechanical check incomplete" (single-source Lint-STOP
rule, S-31 in `stdd-lint`'s `references/checklist.md`) — never silently skip
the mechanical check.

## 6. Plan-drift protocol (S-17)

When execution reveals that a design file (`design-be.md` / `design-fe.md`
/ `api.yml`) is wrong or incomplete for what the task actually needs:

1. First read `STDD/spec.md`'s "Rejected options" section for this change, to
   avoid re-proposing an option already rejected during `stdd-explore`.
2. **STOP** — do not continue writing implementation code before the
   design file is updated.
3. Update the relevant design file(s) to reflect the corrected design.
4. If `api.yml` changed, re-run the S-16 lint/validate step from
   `stdd-plan`.
5. Only after the update is complete, **resume** the original task.
6. Record the drift and the reason for the change in the task report.
7. **Same-task retry cap** (mirrors the S-14 2-round cap): if this
   protocol triggers a **3rd time** on the same task, **STOP** — do not
   attempt another in-place correction. Instead return to `stdd-plan` to
   re-cut `tasks.md`, and let the user decide how to proceed.

## Workflow relay (`workflows/stdd-execute.js`)

Use instead of this skill when the custody chain and the verifier round cap
must be enforced by code rather than by prose (see `workflows/stdd-execute.js`'s
own `meta.whenToUse`). Its `BLOCKED` outcomes are a pinned v2 schema
(REQ-05): every BLOCKED result carries `status: 'blocked'`, `stage`
(`'red'`/`'green'`/`'verify'`/`'reset'`/...), `reason` (the first blocking
reason string) and `reasons` (the full array) — for the BLOCKED shape only,
these REPLACE the older `result`/`phase` field names. Non-BLOCKED outcomes
(`COMPLETE`/`INCOMPLETE`/`REVIEW_REQUIRED`) still carry the legacy
`result`/`phase` pair (see `workflows/stdd-execute.js` around its final
`log(...)` for the two-shape read). Any report or log line relaying an
outcome MUST branch on shape: read `status`/`stage`/`reason`/`reasons` for
BLOCKED, `result`/`phase` for everything else.

`scripts/stdd_custody_check.py`'s exit code 0 with a `CUSTODY:` verdict line
means PASS (not exit 0 alone — see its module docstring). Exit 2 is a
separate, non-verdict `argparse` error path (bad/unknown flag, or supplying
both `--change-dir` and the legacy `change`/`--root` together) and prints no
`CUSTODY:` line at all; never read exit 2 as PASS or FAIL.

**Resume instead of relaunch.** Any relaunch of the workflow — after fixing
an input file, after hitting a rate-limit, or after any other interruption
— MUST resume the prior run via `{scriptPath, resumeFromRunId}` rather than
starting a fresh relaunch from scratch; a bare relaunch throws away the
already-computed state the prior run held. To make resume safe, the Maia
computes an input-files hash before each launch (e.g. `shasum
STDD/<name>/tasks.md spec.md design-*.md`, digested into one value) and
passes it as `args.inputsHash`: unchanged inputs replay from cache under
the same `inputsHash`, and changed inputs naturally get a new hash, which
invalidates stale prompts instead of silently reusing them.

**Quota pre-check before a large fan-out.** Before fanning out more than 10
scenario tasks at once, do a soft pre-check for 5h quota headroom (read the
statusline's `rate_limits` field, or run a small cheap probe call) and only
proceed with the fan-out if there is enough quota left; if not, schedule
the run for after the quota window resets rather than fanning out into a
predictable rate-limit failure. This is usage discipline, not something
enforced in `workflows/stdd-execute.js` — there is no reliable quota API to
gate on in JS, so the check is advisory and performed by the dispatching
Maia, not the workflow script.

## 7. `[INFRA]` / small-task fast path (S-18)

For a task marked `[INFRA]`, or an obviously small single-file change:

- If `tasks.md` names a test file for this task, write it first (same
  ordering reason as Dispatch A step 5 above — marking `[wip]` first would
  lock out this dispatch's own write), then mark `[wip]`; otherwise mark
  `[wip]` at start. Mark `[x]` on completion either way — this keeps S-19's
  interrupt detection working for `[INFRA]` tasks too.
- Run **one** builder dispatch (implementation) and **one** verify dispatch
  — skip the multi-round RED → GREEN → REFACTOR structure, but still
  report execution results and the actual verification command output.
- `tasks.md` must carry a mandatory one-line reason for why this task
  qualifies for the fast path (the mechanical check for a missing reason
  line is `/stdd-lint` S-40, not this skill).
- Never mislabel work that should be a scenario task (`S-XX`) as `[INFRA]`
  just to dodge the full loop.

## 8. Code-enforced alternative — the `stdd-execute` workflow

This skill is the **prose path**: every gate above is enforced by the executing
model following instructions. `workflows/stdd-execute.js` (installed into
`.claude/workflows/`) is the **code-enforced path** for the same phase, and it
is where the two gates that prose cannot hold become mechanical:

- The custody chain — `spec.md`'s recomputed body hash vs `approved_fingerprint`,
  and `design-ux.md`'s vs `design_ux_fingerprint` — is compared by
  `scripts/stdd_custody_check.py`, a read-only program that opens those files
  **itself** and prints one `CUSTODY: PASS|FAIL …` line. The workflow validates
  that line against a strict grammar, requires the verdict word and the exit
  status to agree, and blocks on anything that is not an exact PASS — a
  malformed, multi-line or absent line blocks. No agent is asked to judge the
  custody chain, and no agent-supplied hash is compared against another
  agent-supplied hash. A blocked result names the failing artifact and carries
  both hashes, and no later phase runs.
- The 2-round builder/verifier cap (step 4) is the bound of a `for` loop; there
  is no path to a third round.
- The test-file fingerprint firewall is checked against both the GREEN and the
  verify results, and an empty or malformed digest **blocks** instead of
  skipping the check. The RED baseline is deliberately *not* quoted into the
  GREEN or fix prompts, so the comparison is against a value the caller holds
  rather than against the prompt's own echo.
- A task is marked `[x]` only after the independent verifier passes it, and the
  RED dispatch writes the test file *before* marking `[wip]` — the optional
  test-file guard closes a `[wip]` task's test file to further writes, so the
  opposite order would deadlock RED's own write.

Both paths implement the same steps and the same STDD semantics — choose the
workflow when the change is risky enough that a self-enforced gate is not good
enough, and this skill when you want the conversational loop. The workflow still
cannot ask the user anything: it stops at the manual-verification gate and hands
the checklist back to the calling session (step 5's completion gate), which asks
with selectable options.

### What the workflow path still does NOT enforce

- **The relay is trusted.** The comparison happens inside a program, but a
  subagent runs that program and relays its verdict line and exit status. A
  relayed line is in principle forgeable; the strict grammar check removes the
  trivial bypass and raises the bar, it is not a barrier. The program carries a
  residual hole of its own: an actor that edits a body **and** rewrites the
  matching `approved_fingerprint` produces a self-consistent PASS. Detecting
  that needs a trust anchor outside the working tree (a signature, or git
  history), which the custody chain does not have.
- **The approval is unauthenticated.** `decision.approved` is a field the
  calling session fills in; the workflow cannot tell an approval a human gave
  from one a caller invented, and its own completion report says so. What it
  *does* enforce: the unconfirmed set is derived from the checklist it read and
  is never accepted from the caller, confirmations for ids that are not on the
  checklist are discarded, and completion requires positive evidence — zero
  tasks plus an empty checklist can no longer yield a completion claim.
- **There is no lock.** Two concurrent invocations against the same change
  directory will race: both pass the custody gate, both write the same
  `tasks.md` and `.progress.log`, and the second to mark a task overwrites the
  first's accounting. Step 0's one-session-at-a-time rule is a documented limit
  on this path too, not a mechanism.
- **Lint severity is agent-chosen.** The workflow blocks on `FAIL` findings and
  refuses to read an unrecognised status as anything but a failure, but it is
  the dispatched agent that assigns `PASS`/`FAIL`/`SKIP`/`REPORT` to each
  `stdd-lint` check. A real failure reported as `SKIP` or `REPORT` is invisible
  to the gate.
- **`spec.md`'s `status: approved` field is still agent-reported.** The custody
  program owns the fingerprint comparison only; it does not read `status`. That
  one check remains as weak as it was on the prose path.
- **Already-done task counts are relayed, not independently verified.** On
  entry, how many TDD tasks are already `[x]` (`alreadyDoneCount`) comes
  entirely from the load dispatch's report of `tasks.md`'s markers — one
  relay layer, the same class of trust as the custody verdict line above. A
  task marked `[x]` by some other means would be counted as done here with no
  way for the workflow to tell that apart from a task it verified itself.
- Frontmatter *writes* (`status`, `approved_fingerprint`,
  `design_ux_fingerprint`) remain unguarded on this path, exactly as on the
  prose path.

## Notes / honest limits

- Lint-STOP rule: see step 5's boundary check (single source: `stdd-lint`'s S-31).
- The test-file fingerprint firewall's mechanical hook is optional and off
  by default — without it, protection is detection-after-the-fact via
  `/stdd-lint`, not prevention. Say this plainly in any report, don't imply
  stronger guarantees than exist.
- **Recovery discriminator is an agent-reported claim** (REQ-01, mirrored
  from `STDD/spec.md`): the GREEN-recovery path's discriminator — whether
  re-running `task.verificationCommand` exits 0 — is itself an
  agent-reported claim; this runtime has no execution path of its own, only
  dispatched agents that report back. No recovery design can be stronger
  than the reporting agent's honesty; this is an accepted limit, not a gap
  this skill attempts to close.
- Status/frontmatter approval fields (`status`, `approved_fingerprint`,
  `design_ux_fingerprint`) are never protected by a mechanical hook under
  any configuration — this is a deliberate framework decision (REQ-09), not
  a gap this skill can close. A *write* to those fields is still unguarded on
  the workflow path too; what the workflow adds is that the fingerprint
  *comparison* is performed by a program that reads the files itself, so a
  drifted artifact cannot be talked past — detection, not prevention. Step 8's
  "What the workflow path still does NOT enforce" is the single source of truth
  for that path's limits; do not restate them in a report from memory, read them.

## Closing — external-ticket writeback (advisory)

If this change's requirement originated from an external ticket, the Maia
MAY dispatch `palantir-stone` (this framework's external-system write role)
to write completion status or estimates back to that ticket — enumerated
mutations only, per that role's rules. Before any such dispatch, ask the
user with AskUserQuestion — explicit options (e.g. (a) write completion
status back, (b) write an estimate back, (c) don't write back), never an
open-ended question; the user not choosing a write-back option means no
dispatch. This is advisory, not a step: never invoke it automatically, and
never make it a gate on completion.

## Closing — post-execute design review (advisory)

Once the change is complete — on the prose path (the default), every task in
tasks.md checked `[x]` and the manual completion gate confirmed; on the
workflow-relay path, the workflow reporting `COMPLETE` (or `REVIEW_REQUIRED`
resolved by human confirmation) — the Maia MAY offer a whole-diff design
review. Ask the user with AskUserQuestion, stating the cost plainly (one
opus dispatch); the user declining never affects the change's completion
status — this is advisory, not a gate, and is never invoked automatically.
In a non-git project there is no valid base ref and the diff would be an
empty illusion — skip this offer entirely; do not present it to the user.

If accepted, dispatch `cirdan-shipwright` (if tlor-orchestration or an
equivalent pinned-role package is installed, otherwise a generic subagent
with `model: opus` stated explicitly) with only the change name and a base
ref the calling session names itself (a commit, or "this change's
uncommitted working tree") — stdd-execute records no base commit anywhere,
so the dispatcher supplies it. Do NOT include acceptance criteria or a
conclusion in the prompt; either would trip the role's decline gate.

Division of labor: the per-task `eagle-sentinel` verifier already checked
each task against its own spec scenario; `cirdan-shipwright` sweeps the
cross-task whole — contracts, coupling, operability, over-engineering. No
duplication.

Findings go to the dispatching Maia for adjudication. A fix for a
Blocker/Important finding is a NEW dispatch, never a resume. A finding that
implicates the spec's own design routes through `## 6. Plan-drift protocol`
above — never edit the frozen spec directly.
