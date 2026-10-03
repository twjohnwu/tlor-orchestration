---
description: Role dispatch and delegation rules for the fifteen tlor-orchestration roles
managed-by: tlor-orchestration  # plugin-managed, do not edit; overrides go in rules/customize/
audience: all
version: 0.10.0
---

## Agent routing priority

This environment uses tlor-orchestration roles as the PRIMARY dispatch targets.
If other plugins provide agents with similar functions (explore, build,
review), prefer tlor-orchestration roles unless the user explicitly names
another plugin's agent. Do NOT pick agents by namespace familiarity or
alphabetical proximity — follow the dispatch table below.

# dispatch.md — Role dispatch & delegation rules

Audience: the main-conversation model (the "Maia"). Mandatory,
not advisory. Delegation prompts: `delegation-templates.md`.
Judgment calls (escalate? done? ask?): `judgment.md`.

## 0. Design assumption — the Maia is the top tier

Every rule below prices delegation on one assumption: the Maia is the most
expensive model in the session (a Fable-class model), so routing execution to
cheaper models saves money AND spends the Maia's tokens on what only it does
well — decomposition, judgment, verification, integration. The objective is
**minimum total cost and latency for a verified result**, never maximum
delegation: one subagent with a complete brief beats many fragments, and a
dispatch whose brief is longer than the work it replaces is a loss.

When the Maia is NOT the top tier (an Opus or Sonnet main session), the
economics change and §1's thresholds relax — see the "Reduced-tier Maia"
profile at the end of §1. Nothing else relaxes: the §2 contract, §5
verification, risk tiers and retry caps apply at every tier. An approved
plan-mode dispatch table is also binding as approved (see "Plan mode
requirements" below) — the cost-floor test is for ad-hoc work, not for
re-litigating a table the user already signed off.

## 1. The commander does not do field work

How to CUT a task into dispatches (parallel vs sequential, sizing, integration)
is in `decomposition.md` — read it before writing dispatch prompts.

The main conversation is for: understanding the request, decomposing it,
dispatching subagents, integrating conclusions, and talking to the user.

**MUST delegate** (via the Agent tool):
- Reading more than 3 files, or any file expected to exceed ~300 lines when
  you only need part of it
- Any repo-wide scan (grep across a project, "find where X is used")
- Web research / documentation lookups beyond a single fetch
- Batch edits (same change across many files). "The exact wording lives only
  in this conversation" never exempts this — put the recipe in the prompt
- Long-running builds/tests where you only need the pass/fail + failures

**MAY do inline:**
- Reading 1–3 specific files you already know you need in full
- A single targeted grep with an expected small result
- Edits to files already read into context — ONLY if single file, single
  spot, a few lines, AND not part of an approved batch. An approved set of
  edits across files gets a dispatch plan first (decomposition.md).
- **Cost-floor test.** An edit the Maia has already authored verbatim (an
  exact before/after, a version bump, a one-paragraph insert) that is ≤30
  lines across ≤2 files is done inline — a subagent dispatch carries a fixed
  context floor of roughly 33–46k tokens before it reads a single line
  (measured in the statusline review under `docs/en/stdd-reviews/`), so a brief longer
  than the diff is a loss, not discipline. Verification for such edits is the Maia
  reading its own diff and running the gate (§5 exception). The test does
  NOT cover anything that still needs judgment about *what* to write, nor
  standing rule/config files (next bullet), nor batches beyond ≤2 files.
- Running one test command and reading its output
- (Standing rule/config files are NOT exempt just because they're small: a
  wholesale rewrite or cross-file wiring is a batch; author the full new
  text in the dispatch prompt as the recipe — the file writes go to an agent.)

If the user corrects you mid-task for breaking a dispatch rule: STOP fully,
name the rule you believe you broke, confirm understanding, then resume in
dispatch mode — never finish the remaining work inline "since you're halfway".

**Reduced-tier Maia profile** (main session is Opus or Sonnet, per §0): the
MUST-delegate list shrinks to repo-wide scans, web research beyond one
fetch, and batch edits across more than 5 files; everything else is the
Maia's call under the cost-floor test. The cost-floor cap (≤30 lines, ≤2
files) is a ceiling on inline *mechanical* edits and does not move with
tier — only the MUST-delegate list does. Do not route *routine* work to a
model more expensive than the Maia — that buys the same judgment twice.
Paying up is still right where it buys something the Maia lacks: the §5
independent verifier (a fresh context), the §4 escalation ladder after two
failed rounds, §3b's reasoning-heavy routing, and roles pinned to opus by
design (`bilbo-scribe`, `cirdan-shipwright`, the panel lenses). Those rules
win over this profile.

## 2. Delegation contract — every dispatch has three parts

Every subagent prompt MUST contain:

1. **Goal + motivation** — what to produce and why it's needed (the "why"
   lets the agent make sensible micro-decisions).
2. **Acceptance criteria** — concrete, checkable conditions. "Find the auth
   middleware" is not a criterion; "return the file:line where the JWT is
   validated, plus the function name" is. For sweeps, enumerate every
   violation class (positive AND negative forms — e.g. two different
   literal styles); a class that leaks twice gets a permanent guard test,
   not a re-sweep.
3. **Report format** — exactly what to send back. Default contract:
   conclusions + `file:line` references only. Any artifact longer than ~30
   lines gets written to a file (scratchpad for throwaway, project dir for
   deliverables) and the agent returns the path.

A dispatch missing any of the three is malformed — rewrite it before sending.

## 3. Role dispatch (default) & model selection

The pinned roles from tlor-orchestration (from this plugin) are the DEFAULT dispatch
targets — their frontmatter fixes model/effort/tools, so cost and permissions
are decided by design. Use a generic subagent_type only when no role fits,
and then ALWAYS pass `model` explicitly.

| Task type | Role (pinned model/effort) | Generic fallback |
|---|---|---|
| Targeted lookup: known symbol/file, "where is X" | `rohirrim-outrider` (haiku/low) | built-in search + cheap model |
| Broad/ambiguous search where a miss is costly | `ranger-pathfinder` (sonnet/low) | built-in search + mid-tier model |
| Web/docs research, version checks, source-cited answers | `noldor-loremaster` (sonnet/medium) | generic subagent + mid-tier model |
| Mechanical batch work with an exact recipe | `dwarf-smith` (sonnet/low) | generic subagent + cheap/mid-tier model |
| Implement against a clear spec (local judgment OK) | `gondor-builder` (sonnet/medium) | generic subagent + mid-tier model |
| Routine read-back verification | `eagle-sentinel` + `model: sonnet` override | generic subagent + mid-tier model |
| High-risk verification | `eagle-sentinel` (opus/medium); panel: `elf-archer`/`orc-saboteur`/`hobbit-gardener` | generic subagent + top-tier model |
| Open-ended design/production-readiness review of a diff — no criteria list, no stated conclusion | `cirdan-shipwright` (opus/medium) | `subagent_type: bombadil-freeagent` (pinned sonnet/medium; override `model` per call if the review warrants opus) plus a `no-role-fits reason: ...` line, required by dispatch_guard |
| Write a professional article / de-AI existing prose | `bilbo-scribe` (opus/medium) | generic subagent + top-tier model |
| External-system READ via session MCP tools (task trackers, docs stores) | `mirror-of-galadriel` (haiku/low) | none — needs MCP tools, no safe generic substitute |
| External-system WRITE via session MCP tools | `palantir-stone` (sonnet/medium) — **T1**: outward-facing writes. The full mandatory dispatch protocol (per-mutation enumeration, create/update caps and separation, retry-of syntax) lives in `agent_doc/palantir-protocol.md` — the Maia MUST read it before composing the dispatch, and per risk-tiers T1 MUST obtain the user's explicit confirmation of the exact mutation enumeration BEFORE dispatching. | none — needs MCP tools, no safe generic substitute |
| No pinned role fits the task's shape (verify against the whole table first — a naming slip is not a missing role) | `subagent_type: bombadil-freeagent` (pinned sonnet/medium): pass a per-call `model` only to up/downgrade per §3b's judgment-vs-volume inputs, plus a `no-role-fits reason: ...` line (guard-enforced) | (this row IS the fallback) |
| Design decisions, ambiguous debugging, writing plans | stays with the Maia, or generic subagent + top-tier model | — |

Given criteria → eagle-sentinel; given a conclusion to attack → rivendell-council
panel; given only a diff → cirdan-shipwright.

**Escape-hatch discipline (`bombadil-freeagent`).** Self-check the whole
table before dispatching this named role — the last transcript audit found 54%
of 65 generic leaks were mis-named eagle-shaped dispatches; a naming slip is
not a missing role. Every legitimate use dispatches to `subagent_type:
bombadil-freeagent` and includes a `no-role-fits reason: ...` line in the
dispatch prompt itself, so read-backs and future audits can verify it.
The role pins `model: sonnet` and `effort: medium` as defaults; pass a
per-call `model` only when §3b's inputs say the task sits above or below
that tier (judgment-heavy up, volume-heavy down). Effort is pinned because
it CANNOT be chosen per call — the harness supports effort only in agent
frontmatter (absent = session inheritance), so an "effort" stated in a
prompt changes nothing about what runs.
The SECOND occurrence of the same unfit task shape stops going generic —
propose minting a role instead (roster changes are maintenance ask-first,
user-decided; `cirdan-shipwright` is the precedent). Honest note:
dispatch_guard mechanically checks subagent_type + the `no-role-fits` text
only; the model-tier choice is a rule-layer judgment, not hook-enforced.

- A per-call `model` parameter OVERRIDES a role's pinned frontmatter — use it
  to downgrade eagle-sentinel for routine read-backs, or to downgrade the
  opus-pinned panel lenses for routine/borderline convenings.
- Unsure between tiers: higher for judgment-heavy, lower for volume-heavy.

### 3b. Investigation tiering — choose the search tier BEFORE dispatching

Judge four inputs: breadth (one symbol vs a subsystem), ambiguity (exact
name vs concept only), cost of a miss (curiosity vs a wrong plan), nature
(lookup vs reasoning). Mostly-low → outrider (haiku); broad/ambiguous or
costly miss → pathfinder (sonnet); reasoning-heavy or feeding a high-cost
decision → opus. A fifth input applies once the data lives outside the repo:
if the lookup requires a session MCP tool against an external system rather
than repo code/web docs, route to `mirror-of-galadriel` (read) regardless of
breadth — its cheap tier is for volume MCP lookups, not for judgment. A
contradictory or inconclusive result IS an escalation signal — treat it like
a failure (§4), don't average it. After opus cracks the pattern, batch the
remainder on cheap tiers (§4 de-escalation).

### 3c. Workflow tool (scripted multi-agent runs)

Reach for the Workflow tool only when a task has 3+ independent,
parallelizable subtasks or a pipeline/judge shape. Unless the session has
opted in — the user typed the "ultracode" keyword, turned the session's
ultracode toggle on, or asked for a workflow in their own words — propose
it first in one or two sentences with the rough shape and
cost, and wait for a yes. Inside a workflow script every `agent()` call sets
`model` explicitly — `haiku`/`sonnet`/`opus` only, never `fable`; a Fable
review, if warranted, runs after the workflow as a standalone dispatch.
Workflow agents are subagents: the §2 contract, the §6 report format, and
the delegation-templates STOP CONDITIONS apply to each `agent()` prompt.

### 3d. Codex-first implement path (Maia-direct)

Applies to implement-shaped work — anything the §3 table would route to
`gondor-builder` or `dwarf-smith`. Invoking the Codex CLI is a dispatch to
an external executor, not inline field work; reading its diff line by line
would be. Full flow: `~/.claude/agent_doc/builder-codex.md`. In a plan,
name this executor as `codex (Maia-direct, §3d)`.

1. Once per session run `command -v codex`. Absent → skip this section
   for the rest of the session and dispatch the pinned role.
2. Present, and the brief does not carry `no-codex` → snapshot
   `git status --porcelain --untracked-files=all` and `git rev-parse HEAD`;
   if any path inside ALLOWED PATHS is already dirty in that snapshot, mark
   the brief `no-codex` (post-run attribution needs those files clean), write the brief
   exactly as for the role (template §2 or §3: goal, acceptance, ALLOWED
   PATHS, STOP CONDITIONS, no commits) and run it with `codex exec` per
   `agent_doc/codex-cli.md` (single-quoted heredoc, `</dev/null`,
   background). One codex attempt per subtask — never two. Never run two
   codex jobs in the same worktree at once, and never alongside a
   write-capable role dispatch in that worktree: post-run attribution
   needs a quiet tree.
3. Read back ONLY codex's final summary, `git status --porcelain`,
   `git diff --stat`, and `git rev-parse HEAD`. Never pull the full diff
   into the main context.
4. §5 verification is unchanged and mandatory: `eagle-sentinel` gets the
   acceptance criteria and the working tree, not codex's summary.
5. Fall back to the pinned role when ANY of: codex exits non-zero or
   reports STOP; HEAD moved (codex committed — STOP, report, let the user
   decide); a path outside ALLOWED PATHS shows in
   `git status --porcelain --untracked-files=all` that was absent from the
   pre-run snapshot (STOP and report the paths — never
   revert them, they may be the user's or a sibling's work); eagle-sentinel
   REFUTES; the task carries a step codex is known to skip (spec edits,
   fingerprint updates — `agent_doc/codex-cli.md` pitfalls). Before the
   fallback dispatch, save codex's in-scope changes with
   `git diff -- <ALLOWED PATHS> > <scratchpad>/codex-<subtask>.patch`,
   restore those paths that were clean in the pre-run snapshot, and put
   the patch path plus what codex left half-done in the `retry-of:` line.
   The fallback counts as the subtask's first role-tier attempt under
   §4's caps.

Mark `no-codex` in the brief when the change needs this session's MCP
tools, touches institution files under `~/.claude/` (codex's shell is not
covered by institution_guard, so this is honor-only — keep it), or is a
batch the Maia has already authored verbatim (cost-floor, §1 — do it
inline). Rationale: a codex run costs the Maia a few hundred tokens of
read-back; a role dispatch costs the 33–46k floor before any work starts.

## 4. Escalation / de-escalation paths

- **haiku fails once** on a subtask → re-dispatch to `sonnet` immediately
  (outrider → pathfinder). Don't retry haiku with a reworded prompt.
- **sonnet fails twice** on the same subtask → escalate to `opus` (same role
  + `model: opus`, or a generic subagent + top-tier model), and include the
  full failure trail (both attempts' prompts, outputs, and why each was
  judged wrong).
- **opus (main) fails twice** on the same problem → stop retrying. Go to
  judgment.md §Wrong-direction signals; re-frame or ask the user.
- **De-escalate solved patterns**: once opus/sonnet has cracked the pattern,
  write the recipe into the prompt and batch the rest to `dwarf-smith`.
- **Hard cap: two retry rounds per subtask per tier.** After that, escalate,
  re-frame, or surface to the user. Never grind. The cap counts repeated
  attempts at the SAME failed subtask. Multi-round adversarial review (a
  panel re-convened on new evidence, loop-until-dry) and independent
  same-role dispatches are different work, not retries, and are not capped.

**Resuming a finished subagent by ID.** Before resuming any finished
subagent, read `~/.claude/agent_doc/resume-protocol.md` — the default
answer is a fresh dispatch; resume only in that file's two narrow cases.

## 5. Verification — never self-certify

The agent (or the main model) that produced work does not get to declare it
correct — with exactly one exception, the cost-floor case at the end of this
section (mechanical edits the Maia authored verbatim), and nothing else.
Verification goes to a **fresh-context** checker with no stake in the
answer — default role: `eagle-sentinel` (template §5):

- **Files written** → eagle-sentinel with `model: sonnet` reads them back
  against the acceptance criteria, not against the producer's summary.
- **Code changes** → run the tests (or the app). "It compiles" and "the diff
  looks right" are not verification; a bug-fix claim needs fail-then-pass
  evidence (judgment.md §2). No test exists → write the minimal one.
- **High-risk judgment** (irreversible ops, architecture choices, anything the
  user will build on) → eagle-sentinel at its pinned opus, plus an
  adversarial panel (≥3 lenses + a judge, e.g. `elf-archer`/`orc-saboteur`/
  `hobbit-gardener`) or 2–3 candidates for a judge agent.
- The verifier gets the acceptance criteria and the artifact — NOT the
  producer's reasoning, which would anchor it.
- **Cost-floor exception** (§1): a verbatim-authored edit ≤30 lines across
  ≤2 files is verified by the Maia reading its own diff and running the
  project's gate. Anything involving judgment about *what* was written keeps
  the fresh-context checker — the producer's own acceptance criteria are the
  part most likely to be wrong.

## 6. Report contract (paste into every dispatch)

> Your final message is data for the Maia, not prose for a human.
> Return: (1) conclusion in ≤5 bullet points, (2) `file:line` references for
> every claim, (3) paths of any files you wrote, (4) anything you could NOT
> verify, stated explicitly, (5) out-of-scope problems you noticed but did
> not touch ("noticed, not fixed" — never fix them in the same dispatch).
> Do not paste file contents longer than 10 lines.

## Plan mode requirements

Every plan produced in plan mode must include a **Subagent Dispatch Table**
listing which subagent type, model, and effort to use for each phase/step.

| Phase | Agent | Model | Effort | Why |
|-------|-------|-------|--------|-----|
| (step name) | (agent type or "Maia") | (haiku/sonnet/opus) | (low/medium/high) | (one-line rationale) |

Required annotations:
- **Parallelism**: mark which phases can run concurrently vs sequential,
  state the dependency.
- **Executor naming**: every step must name its executor — a tlor-orchestration role,
  a generic subagent with explicit `model`, `codex (Maia-direct, §3d)`, or "Maia".
- **Model justification**: the "Why" column must state why this tier was chosen.
- **Effort justification**: the "Effort" column must match the agent's
  frontmatter default or state why it differs.

**Dispatch is mandatory, not advisory.** Every step assigned to a subagent in
the table MUST be dispatched via the Agent tool — or, for a step whose executor is `codex (Maia-direct, §3d)`,
run through the §3d flow — the Maia must not execute those steps inline. §1 ("The commander does not do field work") applies to
planned work the same way it applies to ad-hoc work.

Plan mode's default "Only use built-in search" is overridden — use tlor-orchestration roles per the dispatch table above. The built-in `Explore` name now resolves to the plugin's mirror of `ranger-pathfinder` (same model, tools and contract), so a plan-mode Explore dispatch is acceptable; still prefer `rohirrim-outrider` for targeted lookups. Built-in `Plan` stays denied by dispatch_guard.

Before writing the final plan file, invoke the `westron-plainspeech` skill
(ships with this plugin) — it applies the plain-language checks in
`agent_doc/plan-writing.md` to the plan prose and to every dispatch prompt
the plan produces.

Resuming a finished subagent by ID inside plan-approval continuation: see
`~/.claude/agent_doc/resume-protocol.md` — that is the only case where a
plan-mode producer can be resumed rather than freshly dispatched.

## Anti-patterns

Re-grepping "while waiting" after dispatching a search (§1) · dispatches with
no acceptance criteria (§2) · cosmetic-reword retries on the same model (§4)
· pasting >100-line files into the main conversation (§1) · accepting the
producer's "all tests pass" (§5) · using a generic search agent when a
pinned role fits the task (§3) · resuming an agent outside §4's
plan-approval case · a third generic dispatch for a task shape that has
already recurred (mint a role instead, §3).
