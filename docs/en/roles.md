# Roles & dispatch

[← Back to README](../../README.md)

## The worldview

- **You (the engineer) are Ilúvatar** — the source of intent.
- **The main Claude session is a Maia** — it interprets your will, convenes
  the fellowship, and dispatches the races. It does not do field work itself.
- **Subagents are the peoples of Middle-earth** — each born with a fixed fate
  (frontmatter): what model it runs on, how hard it thinks, which tools it
  may touch.

## The fellowship

| Role | Race & post | Model / effort | Duty |
|---|---|---|---|
| `rohirrim-outrider` | Rohirrim outrider | haiku / low | Fast, cheap, targeted lookup: "where is X / how does Y work" |
| `ranger-pathfinder` | Ranger of the North | sonnet / low | Broad, thorough read-only sweep when a miss is costly |
| `noldor-loremaster` | Noldorin loremaster | sonnet / medium | Web/docs research with sources and versions; fact vs inference |
| `dwarf-smith` | Dwarven smith | sonnet / low | Fully-specified mechanical work; never improvises |
| `gondor-builder` | Mason of Gondor | sonnet / medium | Implements a clear spec with local judgment; design stays with the Maia |
| `eagle-sentinel` | Great Eagle | opus / medium | Fresh-context adversarial verification; CONFIRMED/REFUTED |
| `mirror-of-galadriel` | Seeing-glass of Lothlórien | haiku / low | Read-only lookup into EXTERNAL systems via session MCP tools (task trackers, docs stores) — looks, never touches |
| `palantir-stone` | The palantír | sonnet / medium | The ONLY role that WRITES to external systems via session MCP tools; executes dispatch-enumerated mutations verbatim, never decides what to write |
| `cirdan-shipwright` | Círdan the Shipwright | opus / medium | Open-ended design/production-readiness review of a bare diff — no criteria list, no stated conclusion to attack; criteria-bound work stays with `eagle-sentinel`, conclusion-attack work goes to the panel below |
| `bombadil-freeagent` | Tom Bombadil | (none — per-call) | The free agent outside the roster, for task shapes no pinned role covers. Pins neither model nor effort: the dispatcher passes an explicit `model`, chooses an `effort`, and states a `no-role-fits reason:` in the prompt — `hooks/dispatch_guard.py` enforces the first and last. A second occurrence of the same unfit shape should mint a role instead |

### The adversarial review panel (rivendell-council lenses)

These three lenses take no ordinary dispatches — for high-risk verdicts
`eagle-sentinel` recommends convening them, and the Maia convenes it
(≥3 independent lenses + a judge, flow in the `rivendell-council` skill).
For routine or borderline convenings, pass an explicit `model: sonnet`
downgrade when dispatching the lenses — a per-call override beats the
role's pinned frontmatter.

| Role | Race & post | Model / effort | Duty |
|---|---|---|---|
| `elf-archer` | Elven archer | opus / medium | Correctness lens: every arrow pins one logical flaw |
| `orc-saboteur` | Orc saboteur | opus / medium | Security & failure-mode lens: input validation, races, partial failure |
| `hobbit-gardener` | Hobbit gardener | opus / medium | Simplicity lens: prunes over-engineering |

## The external-system pair

`mirror-of-galadriel` (read) and `palantir-stone` (write) are the only roles
that touch systems outside this repo/session, via session MCP tools. Route
every read to the Mirror; route every write to the palantír, and only as an
enumerated list of mutations (target gid + title, expected-before, literal
new value) — max 10 per dispatch, and per risk-tiers T1 the Maia must obtain
the user's explicit confirmation of that exact enumeration before
dispatching. Both agent files (`agents/mirror-of-galadriel.md`,
`agents/palantir-stone.md`) are the source of truth for the full rule set
(scoping, verification, idempotency, etc.) — this section is routing only,
not a restatement.

If a session's MCP server exposes different tool names than the `tools:`
frontmatter lists, or the pinned server isn't connected: tools that fail to
resolve entirely (zero usable tools) make the agent refuse to launch with an
error naming them; tools that PARTIALLY resolve are silently ignored and the
agent launches anyway (verified harness behavior, v2.1.208+) — connect the
matching MCP server, or edit the `tools:` list to the tool names your
session actually exposes.

## Subagent dispatch (lightweight CLAUDE.md snippet)

**Lightweight users** (plugin only, no `/tlor-init`): add this to your
project's `CLAUDE.md` to get dispatch discipline without the full rules
install:

```markdown
## Subagent dispatch (tlor-orchestration)

Prefer the pinned tlor-orchestration roles over generic subagents:
- Targeted code/config lookup ("where is X") → rohirrim-outrider
- Broad/ambiguous search where a miss is costly → ranger-pathfinder
- Web/docs research, version checks → noldor-loremaster
- Mechanical batch edits with an exact recipe → dwarf-smith
- Implement against a written spec → gondor-builder
- Verify finished work (fresh context; never self-certify) → eagle-sentinel
- Adversarial review of major conclusions → elf-archer + orc-saboteur + hobbit-gardener in parallel
- Read an external system via session MCP tools → mirror-of-galadriel
- Write to an external system via session MCP tools (enumerated mutations only) → palantir-stone
- Open-ended design/production-readiness review of a bare diff (no criteria, no conclusion to attack) → cirdan-shipwright
- No pinned role fits the task's shape (verify the whole table first — a naming slip is not a missing role) → bombadil-freeagent

Delegate any read of >3 files or repo-wide scan; keep only conclusions + file:line in the main thread.
```
