# Release log

[← Back to README](../README.md)

English only — this file has no zh-TW mirror. Reconstructed from
`git log --oneline` and `AGENTS.local.md`'s version/incident records. Newest
release first — new sections go at the top.

## v0.9.2 (2026-08-22)

- New skill `westron-plainspeech` + `agent_doc/plan-writing.md` — plain-
  language checks (ISO 24495 / STE-flavored) for plan files and dispatch
  prompts.
- `dispatch.md`'s plan-mode requirements now name the skill before the
  final plan write-up.
- README and skills docs gain a routing row for the new skill, in both
  languages.

## v0.9.1 (2026-08-22)

- `erebor-ledger` gains a Retries (marked) column, parsing dispatch prompts'
  `retry-of:` marker.
- `dispatch.md` §3's `palantir-stone` table row is slimmed; the full
  protocol text moved to `agent_doc/palantir-protocol.md`.
- `palantir-stone` / `mirror-of-galadriel` descriptions shortened, and
  `maintenance.md` gains a 3-cycle zero-dispatch threshold before an agent
  role's retirement can be proposed.

## v0.9.0 (2026-08-22)

- New 14th role `bilbo-scribe` (opus/medium): writes a professional article
  against a spec/outline, or de-AIs existing prose so it reads like a person
  wrote it — writing and editing share one pattern catalog, and the role
  never certifies its own finished text (that stays `eagle-sentinel`'s job).
- `agent_doc/` gains a language/topic subdirectory layer (`zh_tw/`,
  `en_us/`) alongside 8 new flat docs (`bilbo-scribe.md`'s routing table +
  shared writing core, `seo-writing.md`, `tone-development.md`,
  `user-guide-ste.md`, `scene-calibration.md`) for a total of 10 new
  reference docs `bilbo-scribe` routes to by output language and task type.
- Customize overlay for `agent_doc/` now matches on the same RELATIVE path
  under `agent_doc/customize/` (e.g. `customize/zh_tw/patterns.md` overlays
  `zh_tw/patterns.md`), not just a same-named flat file.
- `scripts/check_links.py`'s `MD_TOKEN_RE` and resolution logic now support
  two-level qualified references (`agent_doc/zh_tw/patterns.md`) alongside
  the existing one-level `agent_doc/foo.md` form.
- `install.sh` discovers and installs exactly one level of subdirectory
  under `agent_doc/` generically (no hardcoded language names), records
  each subdir file in the manifest as `subdir/file.md`, and
  `is_safe_manifest_entry` grows an `allow_subdir` parameter (agent_doc
  only) so those entries uninstall cleanly while `agent_doc/customize/`
  still survives untouched.

## v0.8.0 (2026-08-20)

- New `agent_doc/` lazy-load layer: role-specific, conditionally-triggered
  reference docs that a dispatched subagent Reads only when its trigger
  fires, instead of carrying the text in an always-loaded role body. Two
  sublayers mirror rules/: `agent_doc/*.md` is plugin-managed (overwritten
  on install/upgrade), `agent_doc/customize/` is user-owned (copied only if
  absent — gated behind `--with-optional` like rules/customize — and it
  survives uninstall). install.sh gains the full asset triple
  (copy/manifest/symlink/uninstall), tlor-init Steps 3/4/7/12 create and
  populate the layout, and institution_guard (.py AND .sh) protects the new
  `~/.claude/agent_doc/` alias, fail-then-pass tested via the shared case
  matrix.
- Four role bodies slim down to lazy pointers: gondor-builder's and
  dwarf-smith's codex-first sections → `agent_doc/builder-codex.md` (plus
  the shared `agent_doc/codex-cli.md` invocation facts and pitfalls);
  eagle-sentinel's HIGH-RISK codex pre-screen →
  `agent_doc/eagle-codex-prescreen.md` (the council recommendation stays in
  the body — it triggers on HIGH-RISK regardless of codex availability);
  noldor-loremaster's browser read-only subset →
  `agent_doc/noldor-browser.md`, with a restrictive fallback when the file
  is missing. Every pointer also reads the same-named
  `agent_doc/customize/` overlay when present.
- `bombadil-freeagent` gains pinned defaults `model: sonnet` / `effort: medium`
  (user decision), reversing v0.7.8's "pins neither": the harness supports
  effort only in agent frontmatter — the Agent tool has no per-call effort
  parameter — so the old "the Maia chooses and states an effort" requirement
  never affected what actually ran (dispatches silently inherited the session
  effort, and the UI showed no effort). `model` stays overridable per call for
  up/downgrades. `hooks/dispatch_guard.py` accordingly stops requiring an
  explicit `model` parameter for this role and keeps only the `no-role-fits`
  prompt check; `scripts/lint_agents_frontmatter.py`'s rule for this role
  inverts — `model`+`effort` must now be PRESENT and `tools` absent.
  dispatch.md §3 and roles.md (en/zh-TW) reworded to match.
- (v0.7.9 was tagged in an intermediate commit but never released; it is
  folded into this version.)

## v0.7.8 (2026-08-16)

- STDD execute gains a per-change mechanical gate: `stdd-skills/stdd-execute/templates/mechanical_check.sh.tmpl` generalizes the four checks proven on a real change (test-file fingerprints, test count, scope allowlist vs `git status`, spec/design-ux body-hash vs frontmatter fingerprints), one PASS/FAIL line each plus a debug log. A DISPATCHED subagent instantiates it after RED — the orchestrator never writes those files itself; the script runs before every GREEN/fix/verify dispatch and a FAIL blocks that dispatch instead of spending it; verifier prompts drop the mechanical items and keep judgment work only. `workflows/stdd-execute.js` gates on its exit code without reimplementing stdd-lint's checks (3 new tests cover block/proceed/skip).
- `stdd-skills/stdd-plan/references/design-review-checklist.md`: replacement-type changes must have an executable oracle (golden diff, or a screen-mapping table for UI surfaces) before the first task runs.
- `scripts/lint_agents_frontmatter.py` learns the unpinned-role case: `bombadil-freeagent` must NOT declare `model`/`tools` (the dispatcher passes `model` per call and dispatch_guard enforces it), and the linter now fails if it ever does. The role count is synced to thirteen across tlor-init, dispatch.md, README, installation.md, and erebor-ledger; `agents/bombadil-freeagent.md` drops its `effort:` pin to match the rule that this role pins neither.

## v0.7.7 (2026-08-14)

- `bombadil-freeagent` is promoted from a prompt marker to the real named agent type in agents/bombadil-freeagent.md (no model/tools pinned; explicit per-call model required). hooks/dispatch_guard.py now unconditionally denies `general-purpose`/`claude`/`explore`/`plan` (no marker escape) and instead requires `subagent_type: bombadil-freeagent`, an explicit model, and a `no-role-fits reason: ...` line; rules/dispatch.md, skills/tlor-init/SKILL.md, and tests now match.
- hooks/dispatch_guard.py: built-in `Explore`/`Plan` subagent types now default-deny like generic types, with the same `[bombadil-freeagent]` + explicit-model escape; dedicated deny reason points to rohirrim-outrider/ranger-pathfinder (user rule 2026-08-14; tests 167→176)
- agents/gondor-builder.md 1.5.0: Codex-first implementation section — tries `codex exec` when available, reviews its output line-by-line, reports provenance, degrades silently when codex is absent; `no-codex` switch added to delegation-templates §2
- agents/eagle-sentinel.md 1.6.0: HIGH-RISK verdicts get a codex pre-screen before recommending the council — criteria embedded in the codex review PROMPT, a confirmed blocking defect short-circuits straight to REFUTED; steps 1-4 untouched; silently skips the pre-screen without codex; delegation-templates §5 gains a no-codex switch
- agents/orc-saboteur.md 1.5.0: its council seat is executed by codex when available (`codex exec --sandbox read-only`), with a pre-adoption check; discard falls back to self-review without retry; engine labels distinguish codex vs self output; the council protocol itself is unchanged; rivendell-council SKILL.md notes the engine label
- agents/dwarf-smith.md 1.5.0: Codex-first execution mirroring gondor-builder 1.5.0 — `workspace-write` sandbox, per-file recipe review, flag-don't-improvise extended to codex output, provenance labels
- agents/cirdan-shipwright.md 0.2.0: codex pre-scan added after the hard step-0 role-fit check — findings are leads only, the verdict stays cirdan's
- erebor-ledger: new `## Codex delegation` report section — Codex rollout
  adapter (`--codex-home`), window+cwd attribution with ambiguous/
  unattributed disclosure, official rate-card credits pricing
  (`references/codex-rate-card.json`, null-until-verified), per-role
  no-codex historical median baseline (estimate), `used_percent` snapshot;
  never merged into existing totals.

## v0.7.6 (2026-08-10)

- `install.sh --skills-dest=PATH` lets the user declare the skills install directory once (absolute path, not `$HOME`/`/`); persists to `~/.claude/.tlor-install.conf` (grep/cut-read, never sourced) so later runs need no flag. Declaring it (flag or config) skips `ensure_skills_dest_safe`'s symlink-outside-`~/.claude` abort for that run; the undeclared default still aborts exactly as before.

## v0.7.5 (2026-08-09)

- noldor-loremaster 1.6.0 gains browser_close — closes the browser by default when its work is done; delegation-templates §4 adds the Maia-side keep-open switch for multi-dispatch browser batches.

## v0.7.4 (2026-08-09)

- noldor-loremaster 1.4.0→1.5.0 — read-only Playwright browser subset (navigate/snapshot/screenshot/network_requests/click-for-pagination) for rendering JS-only SPA pages; hard ban on state-changing interactions.

## v0.7.3 (2026-08-08)

- M1: the load agent now extracts each task's REQ-section GWT text (verbatim, siblings included) plus a design-be/fe excerpt; RED/GREEN/verify prompts inline them instead of instructing a full spec.md re-read (measured driver: 223.6M cache-read tokens). JS-side `gwtLooksValid` shape validation with per-task fail-open fallback to the old read-it-yourself instructions; verify keeps a soft "the file wins" re-check clause.
- M4 completion: merged-task id line format defined (single comma-joined backtick token `S-03,S-04`) — tasks.md template example + stdd-plan SKILL.md sentence; task-id validation widened per-token in BOTH workflows/stdd-execute.js and scripts/stdd_custody_check.py (base pattern unchanged); custody TASKS: line inter-task separator changed ',' → ';' so merged ids are unambiguous (coordinated producer+consumer change, ships atomically in this version).
- Tests: test-first; mjs 51→59, pytest 153→159.
- Source: specs/phosphorflux-stdd/token-reduction-proposal.md — with this, M1–M6 are all landed.

## v0.7.2 (2026-08-08)

- M2: stdd-execute workflow now runs open `[INFRA]` tasks serially through the full stage chain BEFORE fanning out scenario tasks via pipeline(); any BLOCKED infra task halts the run before fan-out (prevents whole-round scaffold waste)
- M3a: optional `args.inputsHash` — when supplied, embedded into custody/load/wip-probe prompts so `resumeFromRunId` replays invalidate naturally when input files changed; absent → prompts byte-identical to before
- M3b: stdd-execute SKILL.md — relaunches MUST resume via `{scriptPath, resumeFromRunId}` with `args.inputsHash` computed by the Maia
- M4: stdd-plan SKILL.md — scenarios sharing a test-file SHOULD be merged into one task (module convergence in Test mapping)
- M5: mechanical workflow dispatches (marker writes, wip probe, lint relay) now pass `effort: 'low'`
- M6: stdd-execute SKILL.md — soft quota headroom pre-check before large fan-outs
- Tests: test-first batch; mjs suite 46→51, pytest 151→153; one pre-existing mjs fixture (S-29 G-01) reordered for infra-first semantics, assertions unchanged
- Source: `specs/phosphorflux-stdd/token-reduction-proposal.md` (M1 GWT-inlining still proposed, deferred)

## v0.7.1 (2026-08-07)

- cirdan-shipwright decline gate hardened to an eagle-1.5.1-style step 0 (a supplied criteria list must not be executed) — fixes the acceptance PARTIAL
- stdd-execute closing-review trigger now covers the prose path (all tasks `[x]` + manual gate), not only the JS relay's `COMPLETE`/`REVIEW_REQUIRED`
- stdd-execute SKILL.md field docs scoped to BLOCKED: non-BLOCKED outcomes keep legacy `result`/`phase` (matches the relay implementation; doc-only fix, user-adjudicated)
- closing review: cirdan dispatch gains the no-plugin fallback wording; non-git projects skip the offer (empty-diff illusion)
- backported the 2026-07-27 installed-side STDD fixes into the repo ([wip] marked only after the RED test file is written — avoids stdd_test_guard self-lock; workflow-path fingerprint "detection, not prevention" clarification; stdd-lint/stdd-plan drift) — repo and installed copies re-unified

## v0.7.0 — 2026-08-06

- palantir-stone 0.1.0: task creation opened — create-item contract threaded
  through all ten rules, gid-first retry with a three-form retry-of marker
  (+ comment-retry markers), container verification via get_project,
  intra-batch duplicate-name STOP, a five-precondition STOP catalogue,
  delete stays permanently banned; forged through an EIGHT-round adversarial
  panel (24 lens dispatches, 8 fix waves).
- new role cirdan-shipwright (12th): open-ended design/production-readiness
  review of a diff; criteria-bound work stays with eagle-sentinel,
  conclusion-attack work goes to the panel.
- dispatch.md §4: subagent resume rule (plan-approval continuation only) —
  ten-round adversarial review, contracted from a general resume affordance
  to the single evidence-backed case.
- dispatch.md §3 routing row + Anti-patterns entries.
- stdd-execute gains a second Closing advisory: post-execute design review — an optional, ask-first, non-gating `cirdan-shipwright` dispatch over the change's accumulated diff (base ref named by the dispatcher; findings route to the Maia, spec-implicating ones through the plan-drift protocol).
- roles docs: the three rivendell-council lenses move to their own sub-table in en/zh roles.md; the positional 'last three of the first nine' wording is gone (roster growth can no longer rot it).
- the generic-dispatch escape hatch is formalized: dispatch.md §3 gains a no-role-fits row + escape-hatch discipline (state the reason; second recurrence proposes a new role); the marker is renamed `[generic-ok]` → `[bombadil-freeagent]` (unreleased, no external consumers).

## v0.6.0 — 2026-08-01

- base rules slimmed to policy-only (mechanism narration that duplicates the
  harness removed from dispatch.md/decomposition.md)
- dispatch.md §4 clarified: adversarial-review rounds and independent same-role
  dispatches are not retries (transcript audit: only 13% of heuristic "retries"
  were true failure re-dispatches, n=45)
- new opt-in dispatch_guard PreToolUse hook (TLOR_DISPATCH_GUARD=1): denies
  generic-subagent dispatches unless `[generic-ok]` + explicit model (transcript
  audit: 65 generic dispatches, 54% were mis-named verification prompts)
- tlor-init Step 10 documents the new hook

## v0.5.0 — 2026-07-28

**BREAKING**
- `changeDir` is now a required, caller-confirmed absolute path — no
  `STDD/<name>` fallback.
- The BLOCKED return shape replaces `result`/`phase` with
  `status`/`stage`/`reason`+`reasons`.
- `scripts/stdd_custody_check.py --change-dir` is now the primary CLI mode.
- A second `TASKS:` stdout line joins the custody contract, including the
  literal `TASKS: missing` when a change has no `tasks.md`.

**Fixes**
- Pricing was resolved by execution date rather than by each record's own
  date, which would have silently re-priced every historical report once a
  future price tier took effect.
- Subscription and quota figures divided a multi-period total by a
  single-month fee and single-cycle ceiling with no normalization.
- The two router-file guard implementations disagreed on which paths they
  protect.
- The test-file guard did not fire at all on the framework's own template
  citation format.

## v0.4.0 — 2026-07-27

- `install.sh`/`skills/tlor-init/SKILL.md`: install the code-enforced STDD
  workflow's runtime files (`workflows/stdd-execute.js` and its dependency
  `scripts/stdd_custody_check.py`) to `~/.claude/workflows/` and
  `~/.claude/scripts/`, with their own manifests and uninstall loops
  (previously undocumented and uninstallable — a `claude plugin add`-only
  install had no path to find these two files at all).
- New `rules/customize/output-calibration.md` seed: deliverable length
  guidance plus the five things brevity never trims.
- `rules/maintenance.md`: whole-corpus compaction budget and a rules-file
  retirement protocol.
- `docs/*/installation.md`: session-start context cost disclosure.
- `docs/*/maintenance.md`: cross-linked the CLAUDE.md + AGENTS.md note to
  installation.md's session-start cost section, clarifying that auto-load
  isn't exclusive to CLAUDE.md.
- Loading-mechanism wording corrected across `install.sh`,
  `docs/*/installation.md`, `docs/*/rules-and-hooks.md`, and
  `skills/tlor-init/SKILL.md`: native `.claude/rules/` auto-load is what
  actually loads rules; routing files are not load-bearing.
- `docs/*/skills.md`: clarified what `disable-model-invocation: true`
  implies.
- `rules/customize/design-principles.md`: two additions (P6 honest limit,
  P7 first-response instinct).
- `rules/customize/letter-to-future-sessions.md`: added guidance to move
  closed-out handoff items out of the open-items section once it runs past
  roughly 20 lines.
- Archivist skills: opt-in bounded cross-repo decision sweep, plus a
  one-decision-one-layer invariant added to both skills.
- `erebor-ledger` bug fix: token usage was counted once per JSONL content-block
  line, but Claude Code repeats one message's full `usage` snapshot on every
  content block, inflating all token and cost figures roughly 2.1x. Records
  are now deduplicated on `(message.id, requestId)` across the whole scanned
  set, which also covers records re-emitted by resumed or forked sessions.
- `erebor-ledger` bug fix: the canonical usage value per message is now the
  per-field maximum across occurrences. Taking the earliest occurrence read a
  partial mid-stream snapshot and lost about 47% of output tokens.
  Attribution still credits the earliest occurrence, so resumed sessions do
  not steal credit from the original.
- `erebor-ledger` bug fix: cache writes are now priced by their actual
  5-minute versus 1-hour tier from `usage.cache_creation`, instead of
  assuming the 5-minute rate. The old assumption happened to be right for
  subagent records but under-priced every orchestrator's own cost.
- `erebor-ledger`: added `claude-opus-5`, `claude-sonnet-4-6` and a dateless
  `claude-opus-4` entry to the price table; removed a phantom
  `claude-opus-4-2` entry that does not exist on the pricing page.
  Provenance dates refreshed.
- `erebor-ledger`: report lists roles that exist but received zero
  dispatches, with the role set discovered from the installed manifest or
  the bundled role directory rather than a hardcoded list.
- `erebor-ledger`: non-framework agent types appear as their own rows split
  by model by default; `--detail-others` is kept as a documented no-op.
- `erebor-ledger`: a heuristic retry count per row, distinguishing
  sequential re-dispatch from a single-message parallel fan-out. Labelled a
  heuristic, with its over-count disclosed.
- `erebor-ledger`: `--cycle` reports over the weekly quota window, with a
  time-aware boundary rather than date-only filtering. The boundary is an
  observed value and overridable.
- `erebor-ledger` changed: savings framing reworked for flat-fee
  subscriptions. Dollar figures are now labelled API-list-price equivalents
  rather than money saved, since marginal cash saving under a subscription
  is zero; what is conserved is quota headroom. Adds a
  subscription-worth-it ratio, and an optional user-calibrated quota-share
  figure that is omitted entirely when no calibration point is configured.
- `erebor-ledger` changed: the former relative-multiple figure is
  relabelled a context-offload ratio, because a token count cannot express
  a saving that comes from using a cheaper model. It makes no savings
  claim.
- `erebor-ledger`: first test coverage for this tool under `tests/`,
  including a guard test pinned to the partial-snapshot defect.
- `erebor-ledger` docs: `SKILL.md` and the design spec record the
  content-block duplication fact, the dedup and attribution rules, the
  cache-tier basis, a monotonicity detector for future record-format
  changes, and the fast-mode premium as a stated limitation.

## v0.3.2 — 2026-07-25

- Manual install now copies `institution_guard.sh` and `pre_tool_use.sh`
  (the bash-fallback dispatch chain) in addition to the Python hooks —
  previously these two files were only placed via the plugin path. The
  manifest and uninstall path follow automatically via `HOOK_FILES`.

## v0.3.1 — 2026-07-25

- Tests and CI only, no runtime change: added a pytest test layer for the
  hooks (`tests/`, 43 cases, including an `institution_guard` symlink-gap
  regression test); CI's lint job now also runs pytest; no installer- or
  runtime-behavior changes.

## v0.3.0 — 2026-07-24

- Skill-quality pass across all twelve skills (writing-great-skills audit):
  fixed the `/tlor-init` install list omitting the two new role files (a
  real installer bug); `tlor-init`/`tlor-restore` are now user-invoked only
  (`disable-model-invocation: true`); the external-ticket-sourcing and
  decision-capture closing blocks are single-sourced under
  `stdd-spec/references/` and pointed to from every phase skill;
  step-number drift in `stdd-plan`/`stdd-execute` corrected (8 sites);
  skill descriptions trimmed of narrative clauses and synonym triggers.
- Added two new roles, bringing the roster to eleven: `mirror-of-galadriel`
  (haiku/low, read-only lookup into external systems via session MCP tools —
  currently Asana) and `palantir-stone` (sonnet/medium, the only role that
  writes to external systems, executing dispatch-enumerated mutations
  verbatim with pre-write verification, fetch-back confirmation, and a
  10-mutation cap per dispatch). `rules/dispatch.md` §3/§3b, both
  `docs/*/roles.md`, and both READMEs updated for the eleven-role roster.
- 3-round adversarial council review of both new roles (frontmatter stays at
  `version: 0.0.1`, first release) hardened the read/write split (zero
  write tools on the Mirror; enumerated-mutation-only discipline,
  pagination-aware "not found", and idempotency/partial-failure handling on
  the palantír) before either role shipped.
- A further 10-round council loop specifically on `palantir-stone` replaced
  a plain pass/fail report with a five-value outcome taxonomy (applied/
  failed/landed-unverified/stopped/not-attempted); made every pre-write STOP
  halt the whole batch, never just skip one item; gave a retry after
  `landed-unverified` precedence to verify the fetched state first, ahead of
  the generic mismatch-STOP rule; split STOPs into dispatch-level (nothing
  enumerable at all — every item `not-attempted`) vs item-level (one bad
  item `stopped`, the rest `not-attempted`); and extended credential-shape
  scanning to the checklist echo, composed read-modify-write text, and every
  fetched-back value, with whole-row zero-disclosure redaction when a
  credential shape is found.
- Evaluated and deferred: a shared "memory field" mechanism for these roles
  (unnecessary — subagents already auto-load the CLAUDE.md chain, so no
  dedicated memory slot was needed) and a dedicated "watchman" role for
  long-running external-system polling (deferred — `run_in_background`
  already covers that need without a new pinned role).
- `palantir-stone` gained a checklist-echo discipline: before its first
  write, it parses the dispatch's enumeration into a numbered checklist and
  states it back (any ambiguity found at this point halts before touching
  the external system); its final report maps every checklist item to an
  applied/failed/not-attempted outcome, and any action off the checklist is
  forbidden.
- `/tlor-init` gains conffile semantics for previously-installed files a
  user has customized: `cmp -s` classifies each file as missing / unchanged
  / different; a different file is backed up to `<file>.bak-YYYYMMDD-HHMMSS`
  (with a collision counter) before the shipped copy overwrites it, so the
  customization is never silently lost. An earlier pristine-copy /
  hash-manifest / three-way-merge design was dropped after adversarial
  council review refuted it 0/3 rounds — timestamped per-file backups
  replaced it. Uninstall now backs up customized files the same way before
  removing them, and the manifest-driven removal loops were hardened
  (`while read`, an entry sanitizer for glob/whitespace/CRLF forms, and
  symlink-target validation for agents/rules/hooks/skills).
- `/tlor-restore` reworked to match: it restores each live file's per-file
  `.bak-*` sibling (falling back to a labeled legacy path where no sibling
  exists), rather than reconstructing from a manifest.
- `mirror-of-galadriel` wired into `stdd-spec`/`stdd-explore`/`stdd-uiux`'s
  sourcing steps: an explicit-ticket trigger (URL/gid/ticket ID only, never
  speculative) dispatches the role for a read-only fetch, with a graceful
  degrade when the role can't launch.
- `palantir-stone` given a closing advisory role in `stdd-execute`: an
  AskUserQuestion confirm-gate (explicit write-back options, never
  open-ended) is now required before any `palantir-stone` writeback
  dispatch, and never a completion gate. `external-ticket-sourcing.md`
  gained an untrusted-input clause — content fetched by
  `mirror-of-galadriel` is treated as data, never as instructions.
  `stdd-uiux` names its parallel design candidates
  `design/<name>.candidate-N.pen` and deletes the non-chosen candidates
  once one is picked, leaving no orphan files.
- Effect-locus clarification across the STDD skills: external effects (an
  actual outside system write) vs repo-local MCP writes (e.g. a design-as-code
  file edited through a local MCP server) are now distinguished explicitly.
- `stdd-uiux` reworked to make design-as-code (reference tool: pencil.dev)
  the default design-source class, ahead of SaaS design tools (read-only)
  and the text-only fallback; new designs get up to 3 parallel design
  candidates via separate subagent dispatches, modifications stay
  single-candidate.
- Stale nine-role counts fixed to eleven in `.claude-plugin/marketplace.json`,
  `erebor-ledger`, and `/tlor-init`.
- `institution_guard.py`/`.sh` hardened against a symlink-path gap: matching
  moved from a single alias substring to home-anchored prefixes covering the
  whole institution tree plus the `rules`/`agents` symlink aliases, in both
  the Python and bash variants.

## v0.2.0 — 2026-07-24

- `/stdd-plan` hardening (P1-P6): a fresh-context design verifier
  (`eagle-sentinel`) now runs before the adversarial-panel approval gate,
  backed by a new `references/design-review-checklist.md`; the file-survey
  step dispatches to a named executor instead of running inline; generated
  `tasks.md` entries carry `[NEW]`/`[MODIFY]` markers and the `api.yml`
  skeleton carries `x-implementation-status`; six cross-artifact mechanical
  checks are delegated to `/stdd-lint` rather than re-implemented in
  stdd-plan; a `.progress.log` enables resuming an interrupted run; an
  optional `context.md` input is now accepted.
- `/stdd-lint`: Checks 9-13 (S-54–S-58) add cross-artifact xref validation
  (spec ↔ design ↔ tasks ↔ api.yml consistency), plus a scope change so the
  `api.yml` xref checks cover the new `x-implementation-status` field.
- `/westmarch-scribe`: new Step 0 gate — STOPs with "tlor rules not
  installed — run `/tlor-init` first" unless the installed rules layer has
  `dispatch.md`/`judgment.md`; §4a now creates the `rules/customize/
  judgment.md` seed from its shipped shape if the target project doesn't
  have one yet; the skill's description is now keyword-triggered
  (proactive), not invocation-only.
- New skill `/minas-tirith-archivist`: read-only query counterpart to
  `/westmarch-scribe` — searches the customize layer's general decisions
  log plus project decision logs/ADR directories and answers with
  citations; shares the same tlor-rules-installed gate; never writes or
  edits the records it searches.
- `rules/customize/judgment.md` seed: added a line naming
  `/minas-tirith-archivist` as the query executor for the decision logs it
  documents.
- L1 CI layer: `.github/workflows/validate.yml` renamed to `ci.yml` and
  extended with a `lint` job (agent frontmatter shape, dead doc-link check,
  old-name residue guard — `scripts/lint_agents_frontmatter.py`,
  `scripts/check_links.py`, `scripts/check_oldname.py`) and a
  `banned-patterns` job that reads identity red-line patterns from the
  `BANNED_PATTERNS` repo secret (never a literal in a public file; skips
  with a warning on fork PRs, which don't receive secrets). Both README CI
  badges updated to point at `ci.yml`.

## v0.1.5 — 2026-07-21

- `/tlor-init` Step 5 now offers the `rules/customize/judgment.md` seed
  during install (functional omission from v0.1.3 — the installer skill
  never asked about it).
- Docs catch-up for v0.1.3: rules-and-hooks (en/zh-TW) optional table
  lists the judgment.md seed (6 files, was 5); both READMEs' autoloaded
  skills table gains the `/westmarch-scribe` row.
- README version badges switched from a hardcoded static badge (stuck at
  0.1.2) to a shields.io dynamic JSON badge reading plugin.json's version.
- erebor-ledger SKILL.md: added a closing "Before you report" checklist
  (every requested month rendered; comparison table present in `--month`
  multi-month mode) and a cross-month comparison example table.
- stdd-explore SKILL.md: added a "Step 8 — Before handoff" checklist that
  verifies the six-phase method, question-budget discipline, rejected-options
  capture, and next-phase handoff actually ran (the only stdd skill that
  lacked a closing self-check; the others already gate via embedded
  checklists or stdd-lint).
- erebor-ledger SKILL.md: made the multi-month report-assembly rule explicit
  — reproduce every requested month's full per-role tables first, then the
  cross-month comparison; the comparison table is additive and never replaces
  or summarizes away the per-month detail.

## v0.1.4 — 2026-07-21

- erebor-ledger: `--detail-others` flag breaks the merged `(other
  subagents)` row into one row per distinct non-tlor-role `agentType`
  (built-in Explore, `general-purpose`, plugin agents, ...), sorted by
  descending money saved (unpriced rows last).
- erebor-ledger: per-role tables gain `Model`/`Effort` columns; rows are now
  keyed by `(role, model, effort)`, so a role dispatched with a per-call
  model/effort override (rules/dispatch.md §3/§4) shows as its own row
  adjacent to that role's other rows. `Model` is the shortened
  `.message.model` id, suffixed with `(upgrade)`/`(downgrade)` when the
  row's actual model family/tier differs from the role's pinned
  frontmatter `model:` (same family regardless of version, no pin, or an
  unrecognized family never gets a marker); `Effort` is a recorded
  per-dispatch value if one exists, else the role's pinned frontmatter
  marked `*`, else `—` — a new report-header disclosure explains the `*`
  marker and the model-pin comparison behind the `(upgrade)`/`(downgrade)`
  marker.

## v0.1.3 — 2026-07-21

- erebor-ledger: new `--until YYYY-MM-DD` upper bound and repeatable
  `--month YYYY-MM` (single-month reports and multi-month comparison in ONE
  script run; `--month` is mutually exclusive with `--since`/`--until`).
- New customize seed `rules/customize/judgment.md`: compact-MADR
  candidate-comparison format + general decisions log (copy-if-absent,
  never overwritten on upgrade). Base judgment.md §5 gains a one-line
  conditional pointer.
- New skill `westmarch-scribe` (decision capture): archives a filled MADR
  to the project decision log / instruction file / general decisions log,
  AskUserQuestion-driven. Advisory closing hook added to
  stdd-explore / stdd-uiux / stdd-spec / stdd-plan.

## v0.1.2 — 2026-07-20

Skill-body refinements from the first skill-creator evaluation round
(18 scenario runs + adversarial grading, 71/72 assertions passed):

- `stdd-execute`: RED phase now explicitly covers the import-error trap —
  build a minimal `NotImplementedError` stub first so the failure is
  behavioral, not an import error.
- `erebor-ledger`: run the script once per report and quote that single
  run's output verbatim; live transcripts grow between runs, so re-running
  or hand-recomputing numbers makes the prose disagree with its own quoted
  evidence.
- `stdd-spec`: the conditional C1/C2 diagram lives in its own document
  section (e.g. `## System context`), not as an `S-XX` scenario — a diagram
  is not a testable behavior and would pollute coverage math.
- `stdd` (dashboard): pinned the canonical `N/M` progress denominator to
  ALL tasks (scenario + `[INFRA]`); scenario-only counts are secondary,
  clearly labeled.
- `tlor-init` / `tlor-restore`: added the missing `name:` frontmatter field
  (skill-triggering reliability).

## v0.1.1 — 2026-07-19 (7824419)

Old-name (`tlor-agents`) residue cleanup, marketplace description sync, and
this README split into a `docs/` tree (this file included) to keep both
root READMEs short.

## v0.1.0 — 2026-07-19 (`b19d948`)

Added the seven opt-in STDD (Spec-driven Test-Driven Development) workflow
skills (`stdd`, `stdd-explore`, `stdd-uiux`, `stdd-spec`, `stdd-plan`,
`stdd-execute`, `stdd-lint`), the `erebor-ledger` retrospective cost-savings
skill, and the install/hook layer (`--stdd-role`, `--install-hook`).

## v0.0.1 — 2026-07-19 (`e078b74`)

Version reset for orchestration-stage repositioning. The project's
architecture is framed as three evolution stages: (1) agents role base
(1.x — nine pinned role definitions), (2) rule-assigned agents (2.x–3.0 —
roles wired to institution dispatch rules), (3) orchestration (0.x — full
orchestration framework, with process pipelines such as STDD to be
integrated). Versioning restarts at 0.0.1 to reflect stage (3). See
[history.md](en/history.md) / [zh-TW 版](zh-TW/history.md) for the
user-facing explanation and migration note.

## v3.0.0 (never released) — 2026-07-16 to 2026-07-17 (`644cff9`, `a621278`, `f1a049d`)

Repo renamed `tlor-agents` → `tlor-orchestration`; new institution &
ownership model (base rules plugin-owned and unconditionally overwritten,
`rules/customize/` user-owned and never touched). Follow-up commits made the
base layer zero-user-writable (moved `skill-triggers.md` to `customize/`)
and dropped the shipped version placeholder from base rules, making the
installer the sole version source. This version line was superseded by the
0.0.1 reset below before a `3.0.0` tag/release went out.

## v2.1.0 — 2026-07-14 (`fffdeea`)

Added `rules/customize/` for optional rules, generated CLAUDE.md+AGENTS.md
routing, and dispatch-table improvements.

## v2.0 — 2026-07-14 (`39e96d3`, docs in `15e63c3`)

Orchestration framework: added the rules directory (dispatch, decomposition,
delegation-templates, judgment, risk-tiers, maintenance), skills, and hooks
as a bundled install target, with matching README sections.

## v1.4.0 — 2026-07-12 (`81159e4`, plus `5cf0ff2`)

Skill renamed `adversarial-review` → `rivendell-council` (Council-of-Elrond
imagery; description keeps all trigger words). Added Triggering guidance and
a copy-paste CLAUDE.md line to both READMEs. New opt-in `verify_gate` Stop
hook (silent unless `TLOR_VERIFY_GATE=1`) — a substantial derivation from
Miguok/fable-harness's `verify_gate.py`, credited via MIT copyright notice in
the file header. `eagle-sentinel` gained fail-then-pass wording;
`gondor-builder` gained a noticed-not-fixed line. Same-day follow-up
(`5cf0ff2`) added GitHub Actions CI (`validate.yml`) and the three README
badges (CI status, version, license).

## v1.3.0 — 2026-07-12 (`870cba0`)

Shipped the adversarial-review convening skill
(`skills/adversarial-review/`, English canonical + zh-TW translation).
`install.sh` now installs skills via the manifest, making the panel-convening
procedure executable.

## v1.2.0 — 2026-07-11 (`9f97f13`)

Fourth role review: `noldor-loremaster` gained scratch-only `Write`;
read-only-Bash disclaimers added to `rohirrim-outrider`/`ranger-pathfinder`;
panel lenses (`elf-archer`/`orc-saboteur`/`hobbit-gardener`) re-pinned from
sonnet to opus, with a documented per-call sonnet downgrade for routine
convenings. Merging outrider+pathfinder into one role was considered and
rejected — pin-by-design is the product thesis.

## v1.1.3 — 2026-07-11 (`734a1af`)

Contention re-audit (repo sweep + IP research): both READMEs now name
Middle-earth Enterprises alongside the Tolkien Estate in the disclaimer.
"TLOR" deliberately kept unexpanded; no other legal-boilerplate changes made.

## v1.1.2 — 2026-07-11 (`8eacf46`)

Reframed `orc-saboteur` (and lightly `elf-archer`) from attacker-persona
wording ("attack", "besieger", "self-escalation", `attack_findings`) to
defensive/failure-mode wording after a safety-filter false positive
auto-switched a review session to a different model mid-task. Function
unchanged; only the framing changed.

## v1.1.1 — 2026-07-11 (`7382a33`)

Added a common "Evidence rule" across all 9 roles after a `dwarf-smith`
dispatch volunteered an unsourced, evidence-free out-of-scope claim (likely
from reading a stale `*.bak-*` sibling file). Claims now require file:line
from a file read that dispatch; backups aren't evidence. Hardened
`dwarf-smith`'s noticed-not-fixed list and gave `eagle-sentinel` ownership of
panel synthesis back to the Maia.

## v1.1.0 — 2026-07-11 (`54883f3`)

Added `gondor-builder` and `noldor-loremaster`, bringing the roster to nine
roles. Added a `dwarf-smith` scope gate, reworded `eagle-sentinel`'s panel
wording, added `install.sh` manifest tracking and install guards, and got a
clean `claude plugin validate . --strict` pass.

## v1.0.0 — 2026-07-11 (`0b2c8cf`)

TLOR Agents initial release: seven Middle-earth-themed pinned subagent roles
(rohirrim-outrider, ranger-pathfinder, dwarf-smith, eagle-sentinel,
elf-archer, orc-saboteur, hobbit-gardener), each with fixed model/effort/tools.
