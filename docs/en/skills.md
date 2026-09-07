# Skills

[← Back to README](../../README.md)

The README's skill routing table is the quick reference. This page carries
the detail that table leaves out, plus the STDD opt-in.

## Autoloaded skills — detail

**rivendell-council** — the convening procedure for the adversarial panel:
assemble a self-contained review package, dispatch the three lenses in
parallel, resolve by majority-survival verdict, and loop until dry for
critical conclusions.

**tlor-init** — one-time setup skill that installs the full framework:
choose installation level (user/project/repo), copy agents and rules,
generate CLAUDE.md and AGENTS.md routing, optionally enable hooks. Detects
existing installations and offers upgrade with backup. Also offers the STDD
opt-in step (see below).

**tlor-restore** — rollback from backups created by `/tlor-init` during
upgrades.

**erebor-ledger** — reads existing Claude Code transcripts and reports how
much dispatching to tlor roles saved versus running the same work inline on
the orchestrator model. It looks backwards only, and cannot estimate the
saving on a dispatch still in flight.

**westron-plainspeech** — plain-language pass for planning artifacts:
applies ISO 24495's four principles to plan prose and an STE-flavored
sentence/terminology checklist to dispatch prompts and acceptance criteria.
The checklist itself lives in `agent_doc/plan-writing.md`; the skill is a
thin trigger that reads it. Named by dispatch.md's plan-mode requirements
before the final plan write-up.

### `disable-model-invocation: true` — what the flag actually does

`tlor-init` and `tlor-restore` both set `disable-model-invocation: true` in
their frontmatter. The model never sees a skill carrying this flag, so no
instruction placed in a CLAUDE.md, AGENTS.md, or rules file can make it run:
the model reading those instructions has no such skill in its list to invoke.
Only two routes activate one: the user typing `/skill-name`, or the owning
plugin's own SessionStart hook. So a setup step that depends on one of these
skills is a step the user runs, never one an agent can do on their behalf.

### Triggering

Auto-invocation of `/rivendell-council` is description-driven — the model
matches the skill description's trigger words against the situation. For a
hard guarantee, add one line to your project's `CLAUDE.md`:

```
High-risk verdicts (irreversible ops, contract/schema changes, money/precision, architecture decisions, root-cause claims, production-affecting conclusions) MUST pass /tlor:rivendell-council before adoption.
```

`eagle-sentinel`'s HIGH-RISK recommendation is the convening signal.

## Opt-in: STDD workflow skills

Installed via `install.sh --stdd-role=ALL` or `/tlor-init`'s STDD step.

These nine skills are not autoloaded. They land in `~/.claude/skills/` only
when you ask for them. Seven implement the Spec-driven Test-Driven
Development pipeline. The other two archive and query decision records.

This round ships the `ALL` profile alone. The role-scoped `RD`/`PM`/`UIUX`
subsets are deferred, so `install.sh --stdd-role=RD|PM|UIUX` prints a
deferred message and installs nothing.

| Skill | Middle-earth title | Purpose | When to invoke |
|---|---|---|---|
| `/stdd` | Palantír 真知晶石 | Read-only status dashboard: reports which STDD stage a change is in, re-verifies the fingerprint, suggests the next command | Checking progress on an in-flight STDD change |
| `/stdd-explore` | Lore 智者探詢 | Thinking-partner phase that clarifies a vague feature idea before any spec is written | Starting a new STDD change from a rough idea |
| `/stdd-uiux` | Lórien 精靈美學 | Conditional design phase; generates `design-ux.md` | Only when the change has a user-facing UI surface |
| `/stdd-spec` | Oath 遠征誓約 | Writes a GWT-format `spec.md` with test-mapping/verification-command fields, self-reviews via `/stdd-lint`, and gates on adversarial-panel approval | Writing or approving a spec for an STDD change |
| `/stdd-plan` | Map 行軍圖 | Generates condition-based `design-be.md`/`design-fe.md`/`api.yml` and a scenario-covered `tasks.md` from an approved spec | Turning an approved spec into a design + task list |
| `/stdd-execute` | Forge 鑄造 | Runs the per-task RED → GREEN → REFACTOR loop against an approved `tasks.md`, two-dispatch model with an independent verifier | Implementing STDD tasks one at a time |
| `/stdd-lint` | Eagle Vision 鷹之視野 | Pure rule-based (non-model-judgment) mechanical checker: placeholder leakage, ID continuity, GWT completeness, test-mapping/coverage, fingerprint state | Called internally by stdd-spec/stdd-plan/stdd-execute's boundary checks, and directly by the user |
| `/westmarch-scribe` | Westmarch 記事錄 | Decision capture: archives a filled compact-MADR decision to the project's decision log (or instruction file, or the general decisions log) | Invoked from stdd-explore/stdd-uiux/stdd-spec/stdd-plan's advisory closing step, directly by the user, or proactively on decision-keywords in conversation |
| `/minas-tirith-archivist` | Minas Tirith 檔案守護者 | Decision query: the read-only counterpart to `/westmarch-scribe`; searches archived decision records (general and project-scoped) and answers with citations, never writes or edits | Asking about past decisions or why a convention exists, or directly by the user |

Both `/westmarch-scribe` and `/minas-tirith-archivist` need the tlor rules
layer installed, which they detect by looking for `dispatch.md` and
`judgment.md`. If those are absent, both stop and report "tlor rules not
installed — run `/tlor-init` first". Neither guesses a place to write to or
search.

Pipeline order: `stdd-explore → stdd-uiux (conditional) → stdd-spec →
stdd-plan → stdd-execute`, with `stdd` and `stdd-lint` callable at any point.

### BDD layer (v0.12.0)

Five additions sit on top of those stages, and none of them adds a stage.
Two are conditional artifacts, one is a rubric carried in the execute
prompts, and two are checks you can run.

- `stdd-explore` builds an Example Map before handoff when the change
  involves business rules, state, or more than one condition interacting.
  The map has four layers: a one-sentence Story, one line per Rule, at
  least one concrete Example per rule, and the Open Questions the mapping
  surfaced. Pure infra changes — dependency bumps, CI config, refactors
  with no behavior change — skip the step entirely.
- `stdd-spec` adds a `## Domain Language` section to the spec when the
  change introduces a new domain term, or when one term already means
  different things across product, code, tests, and docs. It is a table:
  term, exact meaning, synonyms that must not stand in for it.
- `stdd-execute` tells both the builder and the verifier to read every THEN
  as externally observable behavior — state, output, timing. A THEN
  that only names an internal call gets flagged, because it locks the
  implementation instead of the behavior.
- `stdd-lint` Check 16 verifies that test mappings exist. For each scenario
  it checks that the mapped file is on disk and that the mapped function
  name appears inside it. Severity follows the phase: WARN while that
  scenario's task is still unchecked in `tasks.md`, since the test file is
  written during RED and is supposed to be absent beforehand, then FAIL
  once the task is marked `[x]`.
- `scripts/stdd_verify.py` runs the scenarios as a set. It executes each
  scenario's verification command and prints a per-scenario
  PASS/FAIL/MISSING table plus one coverage line. MISSING means the
  verification command or the mapped test file is not there. Exit status is
  0 only when every selected scenario is PASS.

**STDD test-file guard hook** (`hooks/stdd_test_guard.py`) — an opt-in
PreToolUse hook. Once a test file has an established RED baseline, the hook
blocks rewrites of it until its task is marked done. Install with
`install.sh --install-hook`, independently of `--stdd-role`. **Session-
snapshot caveat**: Claude Code reads PreToolUse hooks from `settings.json`
once, at session start. Running `--install-hook` inside an existing session,
or a `--continue`/`--resume`d one, does NOT activate the hook there. Verify
it in a brand-new session only.
