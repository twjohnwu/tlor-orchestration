---
name: erebor-ledger
description: 'Token/cost-savings ledger for tlor-orchestration dispatching — reports how much dispatching to tlor roles saved versus running the same work inline on the orchestrator model, split by Fable-5-orchestrator sessions vs Opus-orchestrator sessions. Triggers: "usage report", "省了多少 token/成本", "dispatch savings". Not for live cost estimation of a single in-progress dispatch — this is a retrospective report over existing Claude Code transcripts.'
---

# Erebor Ledger (寶庫清點 — dispatch token/cost savings report)

> Named for the dwarves' vaults under the Lonely Mountain, where every coin
> is counted. This skill counts not gold but tokens: how much a dispatch to
> a tlor role actually cost, versus what it would have cost the
> orchestrator to do the same work inline.

## Purpose

Answers two independent questions, never merged:

1. When **Fable 5** is the orchestrator (main-session model), how much did
   dispatching to tlor-orchestration save versus doing the work inline?
2. When **any Opus version** (excluding Fable 5) is the orchestrator, what's
   the same answer?

Fable 5 and Opus have different unit prices and token-consumption patterns
— averaging them across groups would distort the savings estimate, so each
group gets its own report and its own totals.

**A session whose orchestrator model is neither is excluded from BOTH
reports (e.g. a sonnet-orchestrated session)** — not merged into either
group, not averaged, not shown as a third group (that would need its own
pricing/role-breakdown work this tool does not do). **This exclusion is
disclosed every run**, never silent (fixed 2026-07-27 — before this fix the
exclusion existed only in the script's own docstring, invisible in the
rendered report, SKILL.md, and the spec): the standing disclosure block at
the top of every report states the excluded session count, the excluded
orchestrator models and their per-model session counts, and the excluded
token total (orchestrator-side plus dispatched-side), or states plainly that
nothing was excluded. See `render_exclusion_disclosure()` in the script.

## Data sources

Reads Claude Code transcript JSONL directly — no external API, no network
call:

- **Main-session transcript**: `~/.claude/projects/<proj>/<sessionId>.jsonl`
- **Subagent transcripts**: `<sessionId>/subagents/agent-<agentId>.jsonl` +
  `agent-<agentId>.meta.json` (the `agentType` field maps a subagent
  transcript back to the role name it was dispatched as)
- Per assistant record: `.message.model` and
  `.message.usage.{input_tokens,output_tokens,cache_creation_input_tokens,
  cache_read_input_tokens}`
- `.message.model == "<synthetic>"` records are excluded from every total —
  they are never billed and never counted
- **Content-block duplication AND cross-session duplication (deduped,
  machine-wide since 2026-07-27)**: Claude Code writes one
  `"type":"assistant"` line per CONTENT BLOCK of a single API response — a
  `thinking` block, a `text` block, and a `tool_use` block each get their
  own line — and every one of those lines repeats the SAME `.message.usage`
  snapshot for the whole response. Separately, a RESUMED or FORKED session
  copies an earlier session's transcript content — including its original
  `message.id`/`requestId` — into a NEW top-level session file, so the same
  API response can also appear again in a completely different session.
  `erebor_ledger.py` therefore dedupes assistant records on the
  `(message.id, requestId)` pair (never `message.id` alone) before summing
  any token/cost total. Both `message.id` and `requestId` are
  server-assigned identifiers for one API response, so unrelated calls
  cannot legitimately collide — one API response is one billing event and
  must be counted once no matter how many transcripts echo it.

  The dedup set spans the ENTIRE scanned set for a run — every project,
  every session, every main transcript AND every one of its
  `subagents/agent-*.jsonl` files — not just one session's files, because
  the cross-session duplication above means a handful of duplicate keys
  cross session boundaries, not just main/subagent file boundaries within
  one session. Do not narrow this back to per-session as an
  "optimisation": that was the exact bug the 2026-07-27 widening fixed
  (measured 62 cross-file duplicate keys spanning different top-level
  session files on this machine).

  **Two separate rules — do not merge them.** "Which usage VALUE is
  canonical" and "which occurrence OWNS the tokens" are different questions,
  and the answer is a different occurrence for each. Conflating them was the
  defect fixed on 2026-07-27:

  1. **Canonical VALUE = the per-field MAXIMUM across the key's
     occurrences.** Claude Code writes *progressive* usage snapshots for one
     response: the EARLIEST line for a message is a partial mid-stream
     reading. Measured on this machine, one message's first line reported
     `output_tokens: 3` while its completed value 34 seconds later was
     `3305`. Usage counters for one response are cumulative and
     non-decreasing, so the maximum is the completed reading and cannot
     under-count.
     **Why the old rule was wrong, recorded so nobody reinstates it**: this
     step used to credit the EARLIEST occurrence's VALUE. 2,021 of 3,059
     duplicate keys disagreed across occurrences, output tokens were reported
     as 1,684,019 against an actual 3,204,383 (**47.4% lost**), and the Fable
     group's headroom figure understated by 14.6% ($269.77 vs $316.00).
     Independent ground truth fits the corrected rule better on both model
     families (Fable 5 −0.050% → +0.022%; Opus −0.376% → −0.049%). Also do
     not "simplify" this to taking the latest record wholesale — per-field
     max is robust to an out-of-order or truncated final line.
  2. **ATTRIBUTION (which project/session/role the tokens are credited to) =
     the EARLIEST occurrence.** Resumed and forked sessions re-emit an
     earlier session's records, and the original session is the right owner.
     This half of the old rule was correct and is unchanged. A tie (or an
     all-missing/unparseable timestamp) is broken by `(file path, line
     number)`, so a run is reproducible. Every other occurrence of the key is
     zeroed.

  Records missing `requestId` are passed through un-deduped rather than
  dropped, per spec — such records cannot be matched to any other
  occurrence, so neither rule applies to them.

  **Monotonicity detector** (the guard on rule 1): if a key's LATEST
  occurrence reports LESS than the maximum seen for any raw counter
  (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`,
  `cache_read_input_tokens`), the cumulative assumption rule 1 rests on has
  been violated — a future change to Claude Code's record format would
  otherwise corrupt totals silently. The report then emits a warning naming
  the key and the field; the maximum is still what gets accounted. **Zero
  violations is the expected state, and is what this machine currently
  reports** (0 across 9,552 multi-occurrence keys, full history,
  2026-07-27). A non-zero count means investigate the record format before
  trusting any figure in the report. The derived `cache_write_5m`/
  `cache_write_1h` tier split is deliberately NOT checked: a record lacking
  the `usage.cache_creation` breakdown has its whole amount synthesized into
  the 5-minute column, so two occurrences disagreeing about whether the
  breakdown is present would shift volume between columns and trip a
  decrease that says nothing about cumulativeness.

These are internal Claude Code transcript fields, not a documented public
API — a CC version upgrade may rename or restructure them. If the fields
this skill reads don't match what's installed, `erebor_ledger.py` will
either error out or produce visibly empty reports rather than silently
guessing at a different schema; investigate and fix the field paths before
trusting a "clean" run.

## How to run it

```bash
python3 skills/erebor-ledger/scripts/erebor_ledger.py [--project SUBSTR] \
    [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--month YYYY-MM ...] [--detail-others] \
    [--cycle N] [--subscription-usd USD] [--calibration-ceiling-usd USD]
```

- No flags: scans every project under `~/.claude/projects/` and its full
  history.
- `--project <substring>`: only includes project directories whose name
  contains this substring.
- `--since YYYY-MM-DD`: only includes records at or after this date, using
  the transcript's own `timestamp` field.
- `--until YYYY-MM-DD`: only includes records at or before this date, same
  field. Combine with `--since` for a closed date window; both bounds are
  inclusive.
- `--month YYYY-MM`: only includes records in that month, using the
  transcript timestamp's UTC calendar date (i.e. the month boundary is
  `ts[:7]` of that same `timestamp` field, not local time). Repeatable —
  pass it more than once for a multi-month comparison; mutually exclusive
  with `--since`/`--until` (the script errors out if both are given).
  (`--root` also exists as an advanced/testing override of the transcripts
  root directory — not part of the documented filters above, useful for
  running against a fixture directory instead of the real
  `~/.claude/projects/`.)
- `--cycle N`: filter to the weekly quota-reset cycle N cycles back from now
  — `0` = the cycle currently in progress, `1` = the most recently COMPLETED
  cycle, `2` = the one before that, etc. See "Quota-cycle window (`--cycle`)"
  below for the reset boundary and its rationale. Mutually exclusive with
  `--since`/`--until`/`--month` (the script errors out if combined).
  `--cycle-reference`, `--cycle-reset-weekday`, `--cycle-reset-hour-utc` are
  advanced/testing-only overrides of "now" and the reset boundary.
- `--subscription-usd USD`: your monthly subscription fee; overrides the
  config file's `subscription_usd` and enables figure 3 (SUBSCRIPTION
  WORTH-IT) below. `100` in any example here is an example value, never a
  default — there is no default.
- `--calibration-ceiling-usd USD`: a user-recorded API-equivalent cost
  ceiling for a cycle known to have exhausted quota; overrides the config
  file's `calibration_ceiling_usd` and enables figure 4 (EMPIRICAL QUOTA
  SHARE) below.
- `--config PATH`: advanced/testing only — override the config file path
  (default: `~/.claude/erebor-ledger.json`).
- `--detail-others`: **DEPRECATED, now a no-op.** Non-tlor-role `agentType`s
  (built-in Explore, `general-purpose`, plugin agents, ...) are always
  broken out into one row per distinct `agentType`/model/effort combo by
  default (see the mandatory format below) — this used to require the
  flag. The flag is still accepted so existing invocations don't break, but
  it changes nothing; it may be removed in a future major version. Rows are
  sorted by descending quota headroom preserved (unpriced rows last,
  alphabetical among themselves); Total quota headroom preserved reflects
  the sum of whatever rows are actually priced either way.

Python 3 standard library only — no `pip install` required.

Run the script **once** per report and quote that single run's output —
never re-run it "to double-check" and never re-type or recompute numbers by
hand in the prose. Transcripts grow while a session is live (including from
the very dispatches producing this report), so two runs minutes apart give
slightly different totals; a report whose prose disagrees with its own
quoted raw output reads as fabricated even when both numbers were real.
This applies to multi-month comparisons too: passing `--month` more than
once produces every month's section PLUS the cross-month comparison table
inside that SAME single run — never stitch together separate single-month
runs by hand.

## Savings methodology

- **API-equiv cost (actual model)** = Σ(each subagent assistant record's
  tokens × that record's own `.message.model` price)
- **API-equiv cost (if run inline)** = the same token totals × the
  session's orchestrator-model price (i.e. "what if the orchestrator had
  done this work inline instead")
- **Quota headroom preserved** = API-equiv cost (if run inline) − API-equiv
  cost (actual model)
- input / output / cache_read tokens are priced **separately** and summed —
  never a single blended rate; cache-write tokens are priced **per tier**
  (see below) then folded into that same sum

**These are API list-price equivalents, not money the user spent or kept.**
Under a flat-fee subscription the marginal cash saving from dispatching to a
cheaper model is zero — the dollar figure above is not cash returned to the
user. What dispatching actually conserves is **quota headroom**, and the
report is worded (column names, prose) to never imply otherwise. See "Four
report figures" below for what the report computes instead of a raw dollar
"savings" claim.

Two things this report deliberately does **NOT** compute, and why:

- **A percentage of the official weekly limit.** Anthropic's own article
  publishes no absolute quota number, the product UI shows only bars (no
  figure), and no per-model weighting ratio is published from a primary
  source — any such percentage would be a guess dressed as a measurement.
- **A "realized unit price" (subscription fee ÷ tokens consumed).** This
  inverts under a flat fee: using FEWER tokens raises the apparent per-token
  price, so the report would show that saving tokens made your usage more
  expensive. That is backwards, so this figure is never computed.

Every report **SHALL** carry this disclosure, verbatim or in equivalent
wording:

> Counterfactual assumes inline execution would consume the same token
> volume; this is an estimate, not a measurement.

It also discloses a pricing-tier method: prompt caching bills a cache write
at one of two multipliers of the base input price — 1.25x for the 5-minute
default TTL, 2x for the 1-hour opt-in TTL. Claude Code transcripts carry this
split explicitly in `.message.usage.cache_creation.{ephemeral_5m_input_tokens,
ephemeral_1h_input_tokens}` (verified present on every non-zero cache-write
record examined on this machine, 2026-07-27), so the script prices each
tier's tokens at its own rate rather than assuming one. Empirically on this
machine, main-session (orchestrator) records are consistently 1-hour-tier and
subagent-dispatch records are consistently 5-minute-tier — but the script
does not assume this pattern holds elsewhere; it always reads the actual
per-record split. A record with cache-write tokens but no such breakdown
falls back to pricing the whole amount at the 5-minute tier (the prior,
more conservative assumption) and the report's Warnings section names every
record this fallback fired for. This is stated in the report output every
run — never omit it.

**Volume-vs-cost-basis divergence (disclosed every run).** The
`cache(r/w)` column's write half displays
`usage.cache_creation_input_tokens`, while the COST is computed from the
per-tier `cache_creation.{ephemeral_5m_input_tokens,
ephemeral_1h_input_tokens}` fields. On a small number of records the two do
not agree — 3 unique `(message.id, requestId)` keys on this machine as of
2026-07-27, appearing across 11 content-block lines (e.g. tier fields summing
to 502,248 against a stated total of 410,862). For those records the
displayed write volume and the volume the cost is based on therefore diverge.
**The cost always uses the per-tier breakdown, never the total**, and the
report names every such key in its Warnings section. Never silently reconcile
the two by overwriting one with the other: the divergence is a property of
the source data, and hiding it would make an over- or under-priced record
indistinguishable from a correct one.

It also discloses a known, undetected limitation: **fast mode** (a separate
premium tier — $10 input / $50 output per MTok for Opus 5 and Opus 4.8,
applied across the full context window) is not modeled by
`model-prices.json` or the resolver. Claude Code transcripts may not reveal
whether fast mode was active for a given record, so every Opus record in
this report is priced at standard-tier rates; a session run under fast mode
will be under-priced by this report. This is a disclosed limitation, not
something the script attempts to detect.

It also discloses an effort-source assumption: Claude Code transcripts
don't record per-dispatch effort, so any `Effort` cell marked with a
trailing `*` comes from the role's pinned frontmatter (`effort:` in
`agents/<role>.md`), not an observed per-dispatch value. This is stated in
the report output every run — never omit it. The same pinned frontmatter
file also supplies the `model:` value a row's `Model` cell is compared
against to decide the `(upgrade)`/`(downgrade)` marker described above.

It also discloses a retry-count heuristic and its known limitation — see
`Retries (heuristic)` below; this is stated in the report output every run
— never omit it.

## Four report figures

The report's dollar/token figures answer four separate questions; the
mandatory per-role table above is figure 2. All four are computed from the
same underlying token/cost data — nothing here recomputes pricing.

1. **CONTEXT-OFFLOAD RATIO** (headline, `## Quota-headroom figures` §1) —
   dispatched (subagent) token volume ÷ the orchestrator's own token volume
   for the same group. **This is NOT a cost or token savings multiple** —
   dispatching to a cheaper model changes WHICH model processes a token, not
   how many tokens the work needs, so a value below 1.0 is normal and does
   not mean dispatching wasted tokens. It measures how much work was moved
   OUT of the orchestrator's own (quota-relevant) context versus kept inside
   it — the context-dilution the framework's delegation rationale rests on
   avoiding. (Renamed 2026-07-27 from "Relative multiple": the old framing —
   "the same work run inline would have consumed N× the tokens" — implied a
   savings claim that a sub-1.0 value makes nonsensical; never reintroduce
   that framing.)
2. **API-EQUIVALENT COST** — the existing per-role table (`Actual cost` /
   `Counterfactual cost` renamed to `API-equiv cost (actual model)` /
   `API-equiv cost (if run inline)` / `quota headroom preserved` /
   `headroom %`) — same computation as before, worded so it never reads as
   the user's spend.
3. **SUBSCRIPTION WORTH-IT** (`## Quota-headroom figures` §3) — sums the
   period's full API-equivalent cost (orchestrator's own coordination cost +
   dispatched work's actual-model cost) and reports it as a multiple of the
   subscription fee: is the plan cheaper than paying list price for this
   work? Requires `subscription_usd` (config or `--subscription-usd`);
   skipped with an explanatory line if absent.
4. **EMPIRICAL QUOTA SHARE** (`## Quota-headroom figures` §4) — **only when
   the user has recorded a calibration point.** If a past cycle is known to
   have exhausted quota, the user records that cycle's API-equivalent cost
   as `calibration_ceiling_usd`. Later cycles then report "consumed X% of
   your calibrated ceiling", and dispatch's headroom savings convert to "+Y%
   additional headroom". **Absent a calibration point, this entire
   subsection — not just a value — is omitted: no placeholder, no default,
   no estimate.** Its wording states plainly: user-calibrated, official
   quota is unpublished, and this is a proxy (the real allowance is weighted
   per model, not raw tokens).

## Quota-cycle window (`--cycle`)

Anthropic's weekly quota resets on an **observed** boundary — Thursday 13:00
UTC+8 (== Thursday 05:00 UTC) — not a published one. This is a documented
constant (`CYCLE_RESET_WEEKDAY`/`CYCLE_RESET_HOUR_UTC` in
`erebor_ledger.py`), overridable via `--cycle-reset-weekday`/
`--cycle-reset-hour-utc` if that boundary is ever confirmed to change.

`--cycle N` filters to cycle `N` cycles back from now (`0` = in progress,
`1` = the most recently completed cycle, ...), using a precise UTC
timestamp comparison (`[since, until)`, parsed from each record's own
`timestamp` field) — never the date-granular string-slicing that
`--since`/`--until`/`--month` use, since an hour boundary can't be expressed
by slicing a date string. `--cycle-reference` (advanced/testing only) pins
"now" to a fixed ISO-8601 UTC timestamp instead of the real current time,
for reproducible runs.

## Config, and the read-only promise

This script **never writes any file** — every `open()` call in
`erebor_ledger.py` uses mode `"r"`. It reads `~/.claude/erebor-ledger.json`
if present (silently proceeding with `{}` if absent or malformed) and
accepts CLI overrides (`--subscription-usd`, `--calibration-ceiling-usd`)
that take priority over the config file's values. When neither the config
file nor the matching CLI flag supplies a value, the script prints what it
needs and proceeds without figures 3/4 rather than failing.

**The write is the skill's job, not the script's** — this split is
deliberate, so a future reader does not "fix" the read-only promise away by
making the script write:

- **First run**: if the user wants figures 3/4 and no config exists, ask the
  user once for their monthly subscription fee, then write
  `~/.claude/erebor-ledger.json` (a plain file write by whatever is driving
  this skill — not by `erebor_ledger.py`) containing only what the user
  supplied: `{"subscription_usd": <value>}`. Do not persist an inferred
  plan-tier name or anything else not directly supplied.
- **Calibration point**: once the user confirms a cycle that exhausted
  quota, add `calibration_ceiling_usd` to that same file the same way:
  `{"subscription_usd": <value>, "calibration_ceiling_usd": <value>}`.

## Retries (heuristic) — a role's consecutive re-dispatches

`Retries (heuristic)` is a **heuristic count, not a verified retry count**
of consecutive dispatches to the same role, so escalation waste (a failed
dispatch that gets re-dispatched, eating part of the counterfactual saving)
becomes visible instead of hiding inside a total. Method:

- Claude Code transcripts carry no per-dispatch timestamp anywhere (not in
  `meta.json`, not a documented field) — see the investigation this was
  scoped from. The only recoverable ordering signal is the position of each
  `Agent` tool_use block in the MAIN-SESSION transcript, i.e. the order the
  orchestrator actually issued the dispatches.
- Per session, dispatches are walked in that issue order. A dispatch counts
  as a retry when the IMMEDIATELY PRECEDING dispatch (in issue order, any
  model/effort) was the SAME role AND came from a DIFFERENT assistant
  message. The retry is attributed to the row of the SECOND (re-)dispatch.
- Same-message adjacency (two `Agent` tool_use blocks in one assistant
  turn — the normal shape of an independent parallel fan-out, see
  `rules/decomposition.md` §3) is explicitly EXCLUDED: it is not a retry,
  it is the orchestrator batching independent work.
- **Known limitation, disclosed every run**: whether issue order always
  equals true wall-clock order under parallel dispatch has not been
  stress-tested. Two dispatches to the same role issued in SEPARATE
  messages that were actually independent (not a retry — e.g. two
  unrelated one-off lookups to the same role, minutes apart) are still
  indistinguishable from a real retry by this heuristic and will be
  OVER-COUNTED. Treat the column as a signal to investigate, not as a
  precise retry ledger.

## Per-role table (mandatory format — do not invent a different one)

Every group (Fable / Opus) gets its own per-role table with this exact
column set and order — this is the implementation contract, not a
suggestion:

| Role | Model | Effort | Dispatches | Retries (heuristic) | input | output | cache(r/w) | API-equiv cost (actual model) | API-equiv cost (if run inline) | quota headroom preserved | headroom % |
|---|---|---|---|---|---|---|---|---|---|---|---|

Rows are keyed by **(role, model, effort)**, not just role: a role
dispatched with a per-call model/effort override (per
`rules/dispatch.md` §3/§4 — e.g. an escalated retry) gets its own row,
adjacent to that role's other rows, sorted by descending quota headroom
preserved.
`Model` is the shortened `.message.model` id (`claude-` prefix and any
trailing date snapshot suffix stripped, e.g. `claude-haiku-4-5-20251001` →
`haiku-4-5`), suffixed with ` (upgrade)`/` (downgrade)` when the row's
actual model family/tier (haiku < sonnet < opus < fable) differs from the
role's pinned frontmatter `model:` — e.g. an `eagle-sentinel` row actually
run on `sonnet-5` shows `sonnet-5 (downgrade)` because the role pins
`opus`; same family regardless of version (pinned `opus` vs actual
`opus-4-6`), no pin, or an unrecognized family on either side never gets a
marker. `Effort` is a recorded per-dispatch value if one exists, else
the role's pinned frontmatter marked with a trailing `*`, else `—`.

The full framework role set is **discovered, not hardcoded** (design for N,
not for the N you know — a hardcoded list drifted to nine names while eleven
role files/manifest entries existed): the script reads the installed role
manifest (`~/.claude/agents/.tlor-manifest`, the same file `install.sh`
writes — one `<name>.md` line per role it actually installed) as the
authoritative source, and falls back to globbing this repo's own `agents/`
directory only when no manifest is present (e.g. running straight out of a
checked-out repo without an install). Both sources exclude any filename
containing `.bak` (stale/backup copies). As of this writing that's fourteen
roles (`rohirrim-outrider`, `ranger-pathfinder`, `noldor-loremaster`,
`dwarf-smith`, `gondor-builder`, `eagle-sentinel`, `elf-archer`,
`orc-saboteur`, `hobbit-gardener`, `mirror-of-galadriel`, `palantir-stone`,
`cirdan-shipwright`, `bombadil-freeagent`, `bilbo-scribe`) — a fifteenth role
added later is picked up automatically, no script edit needed.

Each discovered framework role gets its own row(s) when it appears in the
data. Anything else (built-in Explore, `general-purpose`, other plugin
agents, ...) gets its own row too, one per distinct `agentType`/model/effort
combo, **by default** — this answers "how much dispatch is leaking to
generic subagents on an expensive model, and is that leak shrinking as
roles get adopted", which a single merged row could not. (`--detail-others`
is accepted but is now a no-op — see the CLI section above.) The last row
is always **Total quota headroom preserved**, with `—` in its
`Model`/`Effort` cells.

### Example (illustrative numbers — the format is the contract, the numbers are not)

Fable group per-role example:

| Role | Model | Effort | Dispatches | Retries (heuristic) | input | output | cache(r/w) | API-equiv cost (actual model) | API-equiv cost (if run inline) | quota headroom preserved | headroom % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rohirrim-outrider | haiku-4-5 | low* | 12 | 1 | 8,400 | 2,100 | 15,000/3,200 | $0.42 | $3.10 | $2.68 | 86.5% |
| ranger-pathfinder | sonnet-5 | low* | 5 | 0 | 6,000 | 4,500 | 9,800/1,500 | $0.61 | $2.95 | $2.34 | 79.3% |
| noldor-loremaster | sonnet-5 | medium* | 2 | 0 | 3,200 | 1,800 | 2,000/500 | $0.28 | $1.10 | $0.82 | 74.5% |
| dwarf-smith | sonnet-5 | low* | 3 | 0 | 4,100 | 3,000 | 5,600/900 | $0.35 | $1.85 | $1.50 | 81.1% |
| gondor-builder | sonnet-5 | medium* | 4 | 0 | 9,000 | 6,200 | 12,000/2,100 | $0.90 | $4.20 | $3.30 | 78.6% |
| eagle-sentinel | sonnet-5 (downgrade) | medium* | 5 | 0 | 6,500 | 3,200 | 7,000/1,000 | $0.48 | $2.40 | $1.92 | 80.0% |
| eagle-sentinel | opus-4-8 | medium* | 1 | 1 | 1,000 | 700 | 1,000/200 | $0.07 | $0.40 | $0.33 | 82.5% |
| elf-archer | opus-4-8 | medium* | 1 | 0 | 1,200 | 900 | 600/100 | $0.10 | $0.55 | $0.45 | 81.8% |
| orc-saboteur | opus-4-8 | medium* | 1 | 0 | 1,300 | 950 | 700/100 | $0.11 | $0.58 | $0.47 | 81.0% |
| hobbit-gardener | opus-4-8 | medium* | 1 | 0 | 1,100 | 800 | 500/100 | $0.09 | $0.50 | $0.41 | 82.0% |
| mirror-of-galadriel | haiku-4-5 | low* | 12 | 0 | 8,400 | 2,100 | 15,000/3,200 | $0.42 | $3.10 | $2.68 | 86.5% |
| palantir-stone | sonnet-5 | low* | 3 | 0 | 4,100 | 3,000 | 5,600/900 | $0.35 | $1.85 | $1.50 | 81.1% |
| general-purpose | sonnet-5 | — | 1 | 0 | 1,200 | 700 | 800/100 | $0.10 | $0.48 | $0.38 | 79.2% |
| Explore | sonnet-5 | low* | 1 | 0 | 800 | 300 | 200/100 | $0.05 | $0.22 | $0.17 | 77.3% |
| **Total quota headroom preserved** | — | — | **39** | **2** | — | — | — | **$3.71** | **$19.03** | **$15.32** | **80.5%** |

The Opus group's structure mirrors the table above exactly (same column
order); its numbers are computed separately and not duplicated here.

### Example — cross-month comparison (when `--month` is passed more than once)

A multi-month run appends this `## Cross-month comparison` section AFTER
every month's full per-role tables (Month A Fable → Month A Opus → Month B
Fable → Month B Opus → this table). Columns are the raw `YYYY-MM` values you
passed, one per month; the rows are fixed:

| Metric | 2026-06 | 2026-07 |
|---|---|---|
| Sessions | 8 | 21 |
| Dispatch count | 40 | 512 |
| API-equiv cost (actual) | $2.10 | $28.40 |
| API-equiv cost (if inline) | $9.80 | $92.15 |
| Quota headroom preserved | $7.70 | $63.75 |
| Headroom % | 78.6% | 69.2% |

### Report assembly (mandatory — the comparison table never replaces the per-month detail)

The report you hand the user IS the single run's output, quoted in full and
in order — not a digest of it. Prose may add observations, but never
*replaces* a table:

- **Single month / date range**: reproduce both the `Fable` and `Opus`
  per-role tables (mandatory column order), their group summaries, and the
  per-project subtotals.
- **Comparison mode (`--month` passed more than once)**: reproduce EVERY
  requested month's full per-role tables first — Month A Fable → Month A
  Opus → Month B Fable → Month B Opus → … — and only THEN the
  `## Cross-month comparison` table. The comparison table is an addition on
  top of the per-month detail, never a substitute for it: a report that
  shows only the comparison table, or folds the months into prose, has
  dropped exactly the detail the user asked for.

**Group label = SESSION group, never a model total (annotated in the output
since 2026-07-27).** "Fable group" / "Opus group" names *every session whose
ORCHESTRATOR (main-session) model was that model* — the rows underneath are
the models the DISPATCHED work actually ran on, so the table's totals are
mostly NOT that model's tokens. Because the label sits within a few lines of
a genuine per-model figure (the `fable-5` rows in the `Model` column, and the
group summary's orchestrator-cumulative volume), the two were easy to
confuse; each per-role table now carries a `Grouping:` line under its heading
stating the distinction explicitly. Keep that line: dropping it restores the
ambiguity.

Each group report also carries:

- **Group summary**: session count, orchestrator's cumulative tokens/cost for
  that group (this IS a per-model figure — it is the orchestrator model's own
  volume, unlike the table totals above it), and the group's Total quota
  headroom preserved
- **Per-project subtotal**: quota headroom preserved, split out by `<proj>`
  directory

A single run (whether single-range or multi-month) also always carries one
`## Zero-dispatch roles` section (see below), and then one
`## Quota-headroom figures` section (figures 1/3/4 — see "Four report
figures" above), after the last per-role table(s)/comparison table, before
any `## Warnings`.

If a `.message.model` has no matching price entry (see below), its row's
cost cells print `N/A` instead of a dollar figure — never a `$0.00` that
could be misread as "no savings", and never a guessed number.

## Zero-dispatch roles

This is the measurement loop for role governance: a role nobody dispatches
is either redundant or being bypassed. The report lists every discovered
framework role (same discovery mechanism as the per-role table above —
manifest first, glob fallback) that received **zero** dispatches across
BOTH groups (Fable and Opus combined — a role dispatched under either
orchestrator counts) in the reporting period; for a multi-month run this is
one combined section covering all requested months, not one per month.

```
## Zero-dispatch roles

These framework roles exist (per the installed role manifest, falling back to the
role-definition directory when no manifest is present) but received ZERO dispatches
in this reporting period:

- palantir-stone
```

If every discovered role received at least one dispatch, the section says
so explicitly (`(none — every framework role received at least one
dispatch in this period.)`) rather than being omitted — an empty section is
itself a reportable fact, and a normal reporting period is expected to have
at least one zero-dispatch role (fourteen roles rarely all fire in the same
window); if a real run ever shows none, that is a signal to double-check
the discovery source before trusting it, not a thing to celebrate silently.

## Codex delegation (`--codex-home`, `references/codex-rate-card.json`)

tlor roles (gondor-builder, dwarf-smith, ...) may delegate execution to the
Codex CLI (`codex exec`). That work leaves no token trace in Claude
transcripts, so the report carries a separate `## Codex delegation` section
— placed after `## Zero-dispatch roles`, before `## Quota-headroom figures`
— computed from `<codex-home>/sessions/**/rollout-*.jsonl` (plus
`archived_sessions/` when present; `--codex-home` overrides the default
`~/.codex`; a missing sessions directory reduces the section to a single
"skipped" line). `auth.json` and everything else under the Codex home is
never read.

**Numbers in this section are NEVER merged into any table or total above**:
Codex models use a different tokenizer, so token volumes and costs are not
comparable with Claude figures — the section is a standalone report.

- **Attribution**: a Codex session is attributed to a tlor role when its
  `session_meta.timestamp` falls inside a window opened by a `codex exec`
  Bash call in that role's subagent transcript (window = call timestamp →
  end of that transcript) AND the session's `cwd` matches the dispatch's.
  Multi-window matches are disclosed as `ambiguous` (never force-assigned);
  sessions with no matching window (codex-companion, manual use) are
  disclosed as `unattributed` with count and token totals. Both lines print
  even at zero.
- **Pricing** comes from `references/codex-rate-card.json`: credits/MTok
  (input / cached-read / output) transcribed from the official rate card;
  cache writes are not billed per the official statement. USD figures, when
  present, come from the `usd_secondary` field and are always labeled
  `(secondary source)`. A model with `null` rates (or no longest-prefix
  match) renders `N/A` plus a warning — the script never guesses a price or
  substitutes another model's.
- **Baseline comparison (estimate)**: for each role with codex-assisted
  dispatches, the same role's no-codex dispatches inside the same filter
  window supply a per-dispatch API-equiv cost median + IQR; estimated
  saving = that median minus the codex-assisted dispatch's own wrapper
  (Claude-side) cost. Fewer than 3 baseline dispatches → `insufficient
  baseline (n=X) — no estimate`. The old same-token-volume counterfactual
  is NOT used here (cross-tokenizer, invalid). Codex credits are never
  netted against these USD estimates.
- **`used_percent` snapshot**: the section reports the first and last
  observed Codex rate-limit `used_percent` in the window.
- **Disclaimers (mandatory, verbatim in every run)**: experimental schema
  (token_count records exist only since 2025-09), cross-tokenizer
  non-comparability, baseline-is-an-estimate, credits-official /
  USD-secondary, cache-writes-not-billed.

## Pricing (`references/model-prices.json`)

Config-driven, not hardcoded in the script. Matching is **longest-prefix
match**: a price-table key matches a `.message.model` id if the model id
*starts with* that key (e.g. a hypothetical `claude-opus-4-6` model would
match a `claude-opus-4` price-table entry, not require an exact match).

- **1M-token context needs no separate rate.** Models 4.6 and later include
  the full 1M-token context window at the standard pricing in the table, so a
  model id carrying a `[1m]` / long-context marker is priced by its ordinary
  entry and must NOT be given a premium one. (Stated rather than assumed
  because earlier long-context betas did carry a premium — a reader who
  remembers that would otherwise suspect an undisclosed surcharge here.)
- **A dated key is not a prefix of the dateless id.** `claude-opus-4-0` does
  NOT cover `claude-opus-4` (the string `claude-opus-4-0` is not a prefix of
  `claude-opus-4`, so the dateless id would resolve to `N/A`); the table
  carries its own `claude-opus-4` entry for that id. Longest-prefix matching
  keeps every dated variant on its own longer key. Watch for this shape
  whenever a new dateless/dated pair appears.
- Model id with no matching prefix → tokens are still listed normally, the
  cost column shows `N/A`, and the script prints a warning naming the
  unpriced model id. The script **never** substitutes another model's price
  for an unknown one. This warning fires once per unique `(message.id,
  requestId)` record, not once per raw content-block/duplicate line — a
  duplicate occurrence of an already-warned key never re-emits it.
- If a `claude-fable-5*` variant has no public pricing, its JSON entry uses
  `null` — a human SHALL fill in the real number (measured or officially
  announced) before that entry can price anything.
- Each entry carries both `cache_write_5m` and `cache_write_1h` prices (see
  disclosure above); the resolver prices each tier's tokens at its own rate
  — if Anthropic's pricing model changes either multiplier, update
  `model-prices.json`, not the script.
- To add/repair a price, edit `references/model-prices.json` directly; do
  not hardcode prices in `erebor_ledger.py`.

## Before you report — checklist

Run through this before handing the report to the user; it guards the two
failure modes that have actually happened — a requested month silently
dropped, and a comparison run pasted without its comparison table:

- [ ] **One run only**: the whole report is the quoted output of a single
      script invocation (the run-once rule above); months were not stitched
      together by hand.
- [ ] **Every requested month reproduced in full**: for each month or date
      range the user asked for, both its `Fable (<month>)` and
      `Opus (<month>)` per-role tables are quoted in full in the mandatory
      column order — not summarized into prose, not replaced by the
      comparison table.
- [ ] **Comparison mode → comparison table too**: if you passed `--month`
      more than once, the `## Cross-month comparison` table is present in
      addition to (never instead of) the per-month tables, after them, one
      column per requested month.
- [ ] **Disclosures intact**: the counterfactual-estimate line, the cache-tier
      pricing line, the cache-tier volume-vs-cost-basis line, the
      usage-monotonicity line, the `*` / `(upgrade)` / `(downgrade)` marker
      notes, the `Retries (heuristic)` disclosure (with its over-counting
      limitation), and the API-equivalent/flat-fee disclosure are all still in
      the output — never trimmed to save space.
- [ ] **Monotonicity count checked**: state the number of usage-monotonicity
      violation warnings in the run. Zero is the expected state; a non-zero
      count means the cumulative-usage assumption behind the dedup's
      maximum-value rule has broken, so investigate the record format BEFORE
      handing over any figure from that run.
- [ ] **Grouping line present**: each per-role table still carries its
      `Grouping:` annotation, so "Fable group" cannot be read as a Fable-5
      model total.
- [ ] **No hand-recomputed numbers**: every figure in the prose matches the
      quoted raw output character-for-character.
- [ ] **Zero-dispatch section present**: the `## Zero-dispatch roles` section
      is in the output (once per run, even for multi-month) — never dropped
      even when it lists nothing.
- [ ] **Quota-headroom figures present**: the `## Quota-headroom figures`
      section is in the output; figure 4 is present only when a calibration
      point exists (config or `--calibration-ceiling-usd`) — its total
      absence in that case is correct, not a bug.
- [ ] **Codex delegation section present**: the `## Codex delegation`
      section is in the output — either its full tables + disclosures +
      disclaimer block, or the single "skipped" line when no Codex home
      exists; its numbers appear in NO other table or total.

## Non-goals

- Does not estimate the cost of a dispatch that hasn't happened yet.
- Does not write, delete, or modify any transcript or config file — read-only
  (every `open()` call uses mode `"r"`; creating/updating
  `~/.claude/erebor-ledger.json` is the skill's first-run flow, not the
  script's — see "Config, and the read-only promise" above).
- Does not call any network API; all pricing comes from the local
  `model-prices.json`, refreshed by hand when Anthropic's pricing page changes.
- Does not compute a percentage of the official weekly quota limit, or a
  "realized unit price" (fee ÷ tokens) — see the two exclusions under
  "Savings methodology" above.
