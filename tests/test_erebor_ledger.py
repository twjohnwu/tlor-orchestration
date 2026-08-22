# -*- coding: utf-8 -*-
"""Black-box tests for skills/erebor-ledger/scripts/erebor_ledger.py.

Same style as the hook tests: the script is invoked as a subprocess exactly
as a user would invoke it, and only its stdout report is asserted against —
no internals are imported. Every fixture transcript is SYNTHETIC and written
under pytest's tmp_path, handed to the script via `--root`; the real
`~/.claude/projects/` is never read.
"""
import importlib.util
import json
import subprocess
import sys

import pytest

from conftest import REPO_ROOT

SCRIPT = REPO_ROOT / "skills" / "erebor-ledger" / "scripts" / "erebor_ledger.py"

FABLE = "claude-fable-5"
SONNET = "claude-sonnet-5"


# --------------------------------------------------------------------------
# Fixture builders
# --------------------------------------------------------------------------

def usage(inp=0, out=0, cache_write=0, cache_read=0, tier_5m=None, tier_1h=None):
    """One `.message.usage` blob. `tier_5m`/`tier_1h` add the explicit
    `cache_creation` tier breakdown; leaving both None omits it (the
    5-minute-fallback path)."""
    u = {
        "input_tokens": inp,
        "output_tokens": out,
        "cache_creation_input_tokens": cache_write,
        "cache_read_input_tokens": cache_read,
    }
    if tier_5m is not None or tier_1h is not None:
        u["cache_creation"] = {
            "ephemeral_5m_input_tokens": tier_5m or 0,
            "ephemeral_1h_input_tokens": tier_1h or 0,
        }
    return u


def assistant(ts, msg_id, request_id, model, usage_blob, content=None):
    """One `"type":"assistant"` transcript line."""
    return {
        "type": "assistant",
        "timestamp": ts,
        "requestId": request_id,
        "message": {
            "id": msg_id,
            "model": model,
            "usage": usage_blob,
            "content": content or [{"type": "text", "text": "x"}],
        },
    }


def user_message(text):
    """One `"type":"user"` transcript line — the dispatch prompt a subagent
    transcript opens with. Used to inject an explicit `retry-of:` marker as
    the FIRST user record of a subagent's `dispatches` records."""
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "text", "text": text}],
        },
    }


def agent_block(tool_id, subagent_type):
    return {
        "type": "tool_use",
        "id": tool_id,
        "name": "Agent",
        "input": {"subagent_type": subagent_type},
    }


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def make_session(root, project, session_id, main_records, dispatches=()):
    """Write one main-session transcript plus its subagent transcripts.

    `dispatches` is a sequence of (agent_name, agent_type, records) triples;
    each gets `<session_id>/subagents/agent-<agent_name>.jsonl` and a
    matching `.meta.json` whose `toolUseId` is `tu-<agent_name>`.
    """
    proj = root / project
    write_jsonl(proj / f"{session_id}.jsonl", main_records)
    for agent_name, agent_type, records in dispatches:
        base = proj / session_id / "subagents" / f"agent-{agent_name}"
        write_jsonl(base.with_suffix(".jsonl"), records)
        base.with_suffix(".meta.json").write_text(
            json.dumps({"agentType": agent_type, "toolUseId": f"tu-{agent_name}"}),
            encoding="utf-8",
        )


def orchestrator_line(ts, n, dispatch_names=()):
    """A main-session assistant record that issues `dispatch_names` as Agent
    tool_use blocks in ONE assistant message (a parallel fan-out)."""
    content = [agent_block(f"tu-{name}", name) for name in dispatch_names]
    if not content:
        content = [{"type": "text", "text": "coordinating"}]
    return assistant(
        ts, f"msg-orch-{n}", f"req-orch-{n}", FABLE, usage(inp=100, out=100), content
    )


def run_report(root, *extra_args):
    # `--config` points at a path that does not exist, so the report never
    # depends on whatever `~/.claude/erebor-ledger.json` the running machine
    # happens to have (figures 3/4 are simply skipped).
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--config",
            str(root / "no-such-config.json"),
            *extra_args,
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


# --------------------------------------------------------------------------
# Report parsing
# --------------------------------------------------------------------------

def row_cells(report, role, group="Fable"):
    """The 13 cells of `role`'s row inside the `## {group} group per-role
    table` section. Fails the test if the role has no row there."""
    section = report.split(f"## {group} group per-role table", 1)[1]
    section = section.split("## ", 1)[0]
    for line in section.splitlines():
        if line.startswith(f"| {role} |"):
            return [c.strip() for c in line.strip().strip("|").split("|")]
    raise AssertionError(f"no {role} row in the {group} table:\n{section}")


COL = {
    "role": 0,
    "model": 1,
    "effort": 2,
    "dispatches": 3,
    "retries_marked": 4,
    "retries": 5,
    "input": 6,
    "output": 7,
    "cache": 8,
    "actual_cost": 9,
    "inline_cost": 10,
    "headroom": 11,
    "headroom_pct": 12,
}


def cell(report, role, name, group="Fable"):
    return row_cells(report, role, group)[COL[name]]


# --------------------------------------------------------------------------
# 1. The guard test for the earliest-value defect
# --------------------------------------------------------------------------

def test_progressive_usage_snapshots_account_the_maximum(tmp_path):
    """Claude Code emits PROGRESSIVE usage snapshots for one response: the
    earliest line for a message is a partial mid-stream reading. The
    accounted value must be the COMPLETED one (3305), not the earliest (3)."""
    make_session(
        tmp_path,
        "proj-a",
        "s1",
        [orchestrator_line("2026-07-20T10:00:00.000Z", 1, ["gondor-builder"])],
        dispatches=[
            (
                "gondor-builder",
                "gondor-builder",
                [
                    assistant(
                        "2026-07-20T10:00:01.739Z", "msg-p", "req-p", SONNET, usage(out=3)
                    ),
                    assistant(
                        "2026-07-20T10:00:35.760Z", "msg-p", "req-p", SONNET, usage(out=3305)
                    ),
                ],
            )
        ],
    )
    report = run_report(tmp_path)
    assert cell(report, "gondor-builder", "output") == "3,305"


# --------------------------------------------------------------------------
# 2. Content-block inflation
# --------------------------------------------------------------------------

def test_content_block_lines_with_identical_usage_counted_once(tmp_path):
    """One response split across three content-block lines, each repeating
    the SAME usage snapshot, is one billing event — counted once, not three
    times."""
    line = lambda ts: assistant(ts, "msg-cb", "req-cb", SONNET, usage(inp=40, out=100))
    make_session(
        tmp_path,
        "proj-a",
        "s1",
        [orchestrator_line("2026-07-20T10:00:00.000Z", 1, ["dwarf-smith"])],
        dispatches=[
            (
                "dwarf-smith",
                "dwarf-smith",
                [
                    line("2026-07-20T10:00:01.000Z"),
                    line("2026-07-20T10:00:01.500Z"),
                    line("2026-07-20T10:00:02.000Z"),
                ],
            )
        ],
    )
    report = run_report(tmp_path)
    assert cell(report, "dwarf-smith", "output") == "100"
    assert cell(report, "dwarf-smith", "input") == "40"


# --------------------------------------------------------------------------
# 3. Cross-file duplication
# --------------------------------------------------------------------------

def test_cross_session_duplicate_attributed_to_earlier_session(tmp_path):
    """The same (message.id, requestId) echoed into a second session file is
    counted once; the ATTRIBUTION goes to the earliest occurrence's owner
    (here: the role dispatched in the earlier session)."""
    dup_early = assistant("2026-07-20T10:00:00.000Z", "msg-x", "req-x", SONNET, usage(out=700))
    dup_late = assistant("2026-07-20T12:00:00.000Z", "msg-x", "req-x", SONNET, usage(out=700))
    make_session(
        tmp_path,
        "proj-a",
        "s-early",
        [orchestrator_line("2026-07-20T09:59:00.000Z", 1, ["ranger-pathfinder"])],
        dispatches=[("ranger-pathfinder", "ranger-pathfinder", [dup_early])],
    )
    make_session(
        tmp_path,
        "proj-a",
        "s-late",
        [orchestrator_line("2026-07-20T11:59:00.000Z", 2, ["rohirrim-outrider"])],
        dispatches=[("rohirrim-outrider", "rohirrim-outrider", [dup_late])],
    )
    report = run_report(tmp_path)
    assert cell(report, "ranger-pathfinder", "output") == "700"
    assert cell(report, "rohirrim-outrider", "output") == "0"


# --------------------------------------------------------------------------
# 4. Monotonicity detector
# --------------------------------------------------------------------------

def _monotonicity_warnings(report):
    """The monotonicity WARNING lines only — never the standing disclosure
    paragraph in the header, which mentions the word too."""
    if "## Warnings" not in report:
        return []
    body = report.split("## Warnings", 1)[1]
    return [
        line for line in body.splitlines() if "monotonicity violation" in line.lower()
    ]


def test_decreasing_field_across_occurrences_emits_warning(tmp_path):
    """Usage counters for one response are cumulative and non-decreasing. A
    latest occurrence BELOW the maximum seen violates that assumption and
    must be named (key + field) in the report's warnings."""
    make_session(
        tmp_path,
        "proj-a",
        "s1",
        [orchestrator_line("2026-07-20T10:00:00.000Z", 1, ["gondor-builder"])],
        dispatches=[
            (
                "gondor-builder",
                "gondor-builder",
                [
                    assistant(
                        "2026-07-20T10:00:01.000Z", "msg-mono", "req-mono", SONNET, usage(out=500)
                    ),
                    assistant(
                        "2026-07-20T10:00:02.000Z", "msg-mono", "req-mono", SONNET, usage(out=200)
                    ),
                ],
            )
        ],
    )
    offending = _monotonicity_warnings(run_report(tmp_path))
    assert offending, "no monotonicity warning emitted"
    assert any("msg-mono" in w and "req-mono" in w and "output" in w for w in offending), offending


def test_non_decreasing_occurrences_emit_no_monotonicity_warning(tmp_path):
    """The detector must not fire on the normal progressive shape."""
    make_session(
        tmp_path,
        "proj-a",
        "s1",
        [orchestrator_line("2026-07-20T10:00:00.000Z", 1, ["gondor-builder"])],
        dispatches=[
            (
                "gondor-builder",
                "gondor-builder",
                [
                    assistant(
                        "2026-07-20T10:00:01.000Z", "msg-ok", "req-ok", SONNET, usage(out=3)
                    ),
                    assistant(
                        "2026-07-20T10:00:02.000Z", "msg-ok", "req-ok", SONNET, usage(out=3305)
                    ),
                ],
            )
        ],
    )
    assert _monotonicity_warnings(run_report(tmp_path)) == []


# --------------------------------------------------------------------------
# 5. Cycle window is half-open
# --------------------------------------------------------------------------

def test_cycle_window_boundary_is_half_open(tmp_path):
    """The reset boundary belongs to the NEWER cycle. These fixtures sit
    EXACTLY ON the comparator, not merely near it (a prior version of this
    test used ±1ms offsets, which stayed green even if the boundary flipped
    from exclusive to inclusive — see the mutation proof in the release
    notes for this fix).

    - A record exactly ON the SHARED boundary (2026-07-23T05:00:00.000Z —
      cycle 1's `until` == cycle 0's `since`) must land in cycle 0 only.
    - A record exactly ON cycle 1's OWN `since` bound
      (2026-07-16T05:00:00.000Z) must land in cycle 1.

    Mutating `_record_in_window`'s `ts_dt >= until_dt` to `ts_dt > until_dt`
    (making the upper bound inclusive) makes the shared-boundary record leak
    into cycle 1 too, which this test catches."""
    on_lower_bound = assistant(
        "2026-07-16T05:00:00.000Z", "msg-lower", "req-lower", SONNET, usage(out=111)
    )
    on_shared_bound = assistant(
        "2026-07-23T05:00:00.000Z", "msg-shared", "req-shared", SONNET, usage(out=222)
    )
    make_session(
        tmp_path,
        "proj-a",
        "s1",
        [
            orchestrator_line("2026-07-23T04:00:00.000Z", 1, ["gondor-builder"]),
            orchestrator_line("2026-07-23T06:00:00.000Z", 2, []),
        ],
        dispatches=[("gondor-builder", "gondor-builder", [on_lower_bound, on_shared_bound])],
    )
    ref = ["--cycle-reference", "2026-07-26T00:00:00Z"]
    completed = run_report(tmp_path, "--cycle", "1", *ref)
    current = run_report(tmp_path, "--cycle", "0", *ref)
    # cycle 1 = [2026-07-16T05:00:00Z, 2026-07-23T05:00:00Z): includes the
    # lower-bound record, excludes the shared upper-bound record.
    assert cell(completed, "gondor-builder", "output") == "111"
    # cycle 0 = [2026-07-23T05:00:00Z, 2026-07-30T05:00:00Z): includes the
    # shared-boundary record.
    assert cell(current, "gondor-builder", "output") == "222"


# --------------------------------------------------------------------------
# 6. Cache-tier pricing
# --------------------------------------------------------------------------

def _cache_tier_report(tmp_path, tier_5m, tier_1h):
    make_session(
        tmp_path,
        "proj-a",
        "s1",
        [orchestrator_line("2026-07-20T10:00:00.000Z", 1, ["gondor-builder"])],
        dispatches=[
            (
                "gondor-builder",
                "gondor-builder",
                [
                    assistant(
                        "2026-07-20T10:00:01.000Z",
                        "msg-c",
                        "req-c",
                        SONNET,
                        usage(cache_write=1_000_000, tier_5m=tier_5m, tier_1h=tier_1h),
                    )
                ],
            )
        ],
    )
    return run_report(tmp_path)


def test_cache_write_tiers_price_differently(tmp_path):
    """A 1-hour-only cache_creation breakdown prices at the 1h rate and a
    5-minute-only one at the 5m rate — the two must not be equal."""
    r5 = _cache_tier_report(tmp_path / "five", 1_000_000, 0)
    r1 = _cache_tier_report(tmp_path / "hour", 0, 1_000_000)
    cost_5m = cell(r5, "gondor-builder", "actual_cost")
    cost_1h = cell(r1, "gondor-builder", "actual_cost")
    assert cost_5m != cost_1h, (cost_5m, cost_1h)
    to_f = lambda s: float(s.lstrip("$").replace(",", ""))
    assert to_f(cost_1h) > to_f(cost_5m)


# --------------------------------------------------------------------------
# 7. Dispatch counts are unaffected by dedup
# --------------------------------------------------------------------------

def test_dispatch_counts_unaffected_by_dedup(tmp_path):
    """Structural, not coincidental: a dispatch whose every record is a
    deduped LOSER (all tokens zeroed) still counts as one dispatch, and a
    dispatch whose records collapse from three lines to one still counts as
    one — dispatch counting keys off record presence, never token values."""
    dup = lambda ts: assistant(ts, "msg-d", "req-d", SONNET, usage(out=900))
    triple = lambda ts: assistant(ts, "msg-t", "req-t", SONNET, usage(out=50))
    make_session(
        tmp_path,
        "proj-a",
        "s-early",
        [orchestrator_line("2026-07-20T09:00:00.000Z", 1, ["ranger-pathfinder"])],
        dispatches=[("ranger-pathfinder", "ranger-pathfinder", [dup("2026-07-20T09:00:01.000Z")])],
    )
    make_session(
        tmp_path,
        "proj-a",
        "s-late",
        [orchestrator_line("2026-07-20T11:00:00.000Z", 2, ["rohirrim-outrider", "dwarf-smith"])],
        dispatches=[
            ("rohirrim-outrider", "rohirrim-outrider", [dup("2026-07-20T11:00:01.000Z")]),
            (
                "dwarf-smith",
                "dwarf-smith",
                [
                    triple("2026-07-20T11:00:02.000Z"),
                    triple("2026-07-20T11:00:02.500Z"),
                    triple("2026-07-20T11:00:03.000Z"),
                ],
            ),
        ],
    )
    report = run_report(tmp_path)
    # rohirrim-outrider's only record lost the dedup (its tokens are zeroed)…
    assert cell(report, "rohirrim-outrider", "output") == "0"
    # …yet it is still one dispatch, and so is the three-line one.
    assert cell(report, "rohirrim-outrider", "dispatches") == "1"
    assert cell(report, "dwarf-smith", "dispatches") == "1"
    assert cell(report, "ranger-pathfinder", "dispatches") == "1"
    assert cell(report, "dwarf-smith", "output") == "50"


# --------------------------------------------------------------------------
# 8. H3 — absolute dollar amounts (the test gap the review's diagnosis
# understated: no prior test pinned an exact dollar string anywhere)
# --------------------------------------------------------------------------

def test_absolute_dollar_amounts_pinned(tmp_path):
    """A fixed fixture (round-number tokens, dates safely before the
    sonnet-5 tier switch on 2026-09-01) pinned against EXACT rendered dollar
    strings for the actual cost, the counterfactual (API-equivalent inline)
    cost, and the headroom preserved — not merely a directional (`>`)
    comparison. gondor-builder runs on sonnet-5 (input $2, output $10 per
    MTok); the Fable orchestrator's counterfactual uses fable-5 pricing
    (input $10, output $50 per MTok)."""
    make_session(
        tmp_path,
        "proj-a",
        "s1",
        [orchestrator_line("2026-07-20T10:00:00.000Z", 1, ["gondor-builder"])],
        dispatches=[
            (
                "gondor-builder",
                "gondor-builder",
                [
                    assistant(
                        "2026-07-20T10:00:01.000Z",
                        "msg-abs",
                        "req-abs",
                        SONNET,
                        usage(inp=1_000_000, out=1_000_000),
                    )
                ],
            )
        ],
    )
    report = run_report(tmp_path)
    # actual: 1M in * $2/MTok + 1M out * $10/MTok = $2.00 + $10.00
    assert cell(report, "gondor-builder", "actual_cost") == "$12.00"
    # counterfactual (inline on fable-5): 1M in * $10/MTok + 1M out * $50/MTok
    assert cell(report, "gondor-builder", "inline_cost") == "$60.00"
    assert cell(report, "gondor-builder", "headroom") == "$48.00"


# --------------------------------------------------------------------------
# 9. H1 — pricing must follow the RECORD's own date, not the execution date
# --------------------------------------------------------------------------

def test_record_priced_by_own_date_not_execution_date(tmp_path):
    """Two records in the SAME dispatch, on the SAME model (sonnet-5),
    straddling the price table's `next_tier.effective_from` (2026-09-01):
    one dated 2026-07-20 (intro tier, output $10/MTok) and one dated
    2026-09-05 (standard tier, output $15/MTok). Each record MUST be priced
    at its own tier. Before the H1 fix, the whole dispatch's aggregated
    tokens were priced ONCE using the report's EXECUTION date — as long as
    this test runs before 2026-09-01, that bug would price BOTH records at
    the intro ($10) tier, giving $20.00 instead of the correct $25.00."""
    make_session(
        tmp_path,
        "proj-a",
        "s1",
        [orchestrator_line("2026-07-20T10:00:00.000Z", 1, ["gondor-builder"])],
        dispatches=[
            (
                "gondor-builder",
                "gondor-builder",
                [
                    assistant(
                        "2026-07-20T10:00:01.000Z", "msg-pre", "req-pre", SONNET, usage(out=1_000_000)
                    ),
                    assistant(
                        "2026-09-05T10:00:01.000Z", "msg-post", "req-post", SONNET, usage(out=1_000_000)
                    ),
                ],
            )
        ],
    )
    report = run_report(tmp_path)
    assert cell(report, "gondor-builder", "actual_cost") == "$25.00"


# --------------------------------------------------------------------------
# 10. H2 — quota-headroom figures 3/4 must be normalized by period length
# --------------------------------------------------------------------------

def test_subscription_figure_normalized_by_period_months(tmp_path):
    """Figure 3 divides this period's total cost by the MONTHLY subscription
    fee — for a `--month 2026-07` report (31 days), the fee must be scaled
    by 31/30.4375 ≈ 1.02 months before dividing, and the report must LABEL
    that conversion, not divide by the raw monthly fee unscaled (which
    inflates the ratio for any period longer than one cycle)."""
    make_session(
        tmp_path,
        "proj-a",
        "s1",
        [orchestrator_line("2026-07-20T10:00:00.000Z", 1, ["gondor-builder"])],
        dispatches=[
            (
                "gondor-builder",
                "gondor-builder",
                [assistant("2026-07-20T10:00:01.000Z", "msg-h2", "req-h2", SONNET, usage(out=1_000_000))],
            )
        ],
    )
    report = run_report(tmp_path, "--month", "2026-07", "--subscription-usd", "100")
    section = report.split("### 3. Subscription worth-it", 1)[1].split("###", 1)[0]
    assert "1.02" in section, section
    assert "$101.85" in section, section
    assert "Ratio: **0.1x**" in section, section


# --------------------------------------------------------------------------
# 11. M10 — dedup attribution must land on the earliest INCLUDED occurrence,
# never an excluded ("other" orchestrator) session
# --------------------------------------------------------------------------

def test_dedup_attribution_skips_excluded_session_owner(tmp_path):
    """The same (message.id, requestId) key's TRUE-earliest occurrence sits
    in a session whose orchestrator is neither Fable nor Opus (excluded,
    spec §3) — the excluded report path never renders a role/pricing
    breakdown, so attributing to that occurrence would zero this key's
    tokens everywhere they COULD be reported. Attribution must instead land
    on the earliest occurrence in an INCLUDED session."""
    # Excluded session: main-session record itself is on sonnet (not
    # fable/opus), so this session classifies as "other" and is excluded.
    excluded_main = assistant(
        "2026-07-20T09:00:00.000Z", "msg-x", "req-x", SONNET, usage(out=500)
    )
    make_session(tmp_path, "proj-a", "s-excluded", [excluded_main])
    # Included session: fable orchestrator, dwarf-smith dispatch re-emits
    # the SAME key later.
    dup_later = assistant("2026-07-20T09:31:00.000Z", "msg-x", "req-x", SONNET, usage(out=500))
    make_session(
        tmp_path,
        "proj-a",
        "s-included",
        [orchestrator_line("2026-07-20T09:30:00.000Z", 1, ["dwarf-smith"])],
        dispatches=[("dwarf-smith", "dwarf-smith", [dup_later])],
    )
    report = run_report(tmp_path)
    assert cell(report, "dwarf-smith", "output") == "500"
    assert cell(report, "dwarf-smith", "dispatches") == "1"


# --------------------------------------------------------------------------
# 11b. Retries (marked) — explicit `retry-of:` line in the dispatch prompt's
# first user record, independent of the consecutive-same-role heuristic.
# --------------------------------------------------------------------------

def test_retries_marked_counts_explicit_retry_of_marker(tmp_path):
    """A dispatch whose subagent transcript opens with a `retry-of:` line
    counts toward Retries (marked); a dispatch with no marker does not —
    even though neither role's heuristic count is affected by the marker."""
    make_session(
        tmp_path,
        "p",
        "s",
        [
            orchestrator_line("2026-07-20T10:00:00.000Z", 1, ["gondor-builder-a"]),
            orchestrator_line("2026-07-20T10:05:00.000Z", 2, ["gondor-builder-b"]),
            orchestrator_line("2026-07-20T10:10:00.000Z", 3, ["dwarf-smith-a"]),
        ],
        dispatches=[
            (
                "gondor-builder-a",
                "gondor-builder",
                [assistant("2026-07-20T10:01:00.000Z", "a1", "a1", SONNET, usage(out=10))],
            ),
            (
                "gondor-builder-b",
                "gondor-builder",
                [
                    user_message("Goal: fix the bug.\nretry-of: prior attempt failed\nAcceptance: it passes."),
                    assistant("2026-07-20T10:06:00.000Z", "b1", "b1", SONNET, usage(out=10)),
                ],
            ),
            (
                "dwarf-smith-a",
                "dwarf-smith",
                [assistant("2026-07-20T10:11:00.000Z", "c1", "c1", SONNET, usage(out=10))],
            ),
        ],
    )
    report = run_report(tmp_path)
    # Same role, separate messages → the heuristic AND the marker both land
    # on the merged (role, model, effort) row.
    assert cell(report, "gondor-builder", "retries_marked") == "1"
    assert cell(report, "gondor-builder", "retries") == "1"
    # Single dispatch, no marker → both columns are zero.
    assert cell(report, "dwarf-smith", "retries_marked") == "0"
    assert cell(report, "dwarf-smith", "retries") == "0"


# --------------------------------------------------------------------------
# 12. M9 — a mistyped/unknown role-row key must raise, never silently
# synthesize a zero row. Unlike every other test in this file, this ONE
# case imports the module directly (breaking the file's own black-box-only
# convention stated in the module docstring): the bug this guards against
# is an INTERNAL data-structure invariant with no observable difference in
# the rendered report, so subprocess/stdout assertion cannot exercise it.
# --------------------------------------------------------------------------

def _load_erebor_ledger_module():
    spec = importlib.util.spec_from_file_location("erebor_ledger_module", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec: the script's dataclasses (under
    # `from __future__ import annotations`) resolve their field type hints
    # via `sys.modules[cls.__module__]` at class-definition time, which
    # fails with a bare AttributeError if the module was never registered.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_unknown_role_key_raises_instead_of_silent_zero_row():
    """`GroupState.roles` is a plain dict keyed by `RoleKey`, not a
    `defaultdict` — looking up a key that was never dispatched (e.g. a
    typo'd role/model/effort combination) must raise `KeyError`, never
    silently vivify a fresh all-zero row (the pre-fix
    `defaultdict(new_role_row)` behavior, which made a mistyped key
    indistinguishable from a real zero-dispatch role)."""
    m = _load_erebor_ledger_module()
    g = m.new_group_state()
    known_key = m.RoleKey("gondor-builder", "sonnet-5", "medium")
    g.roles[known_key] = m.new_role_row()
    g.roles[known_key].dispatches = 3
    with pytest.raises(KeyError):
        _ = g.roles[m.RoleKey("gondor-builder", "sonnet-5", "TYPO")]


# --------------------------------------------------------------------------
# Codex delegation report (black-box fixtures)
# --------------------------------------------------------------------------

def codex_bash(ts, cwd, command="codex exec --full-auto x"):
    rec = assistant(ts, "msg-codex-bash", "req-codex-bash", SONNET, usage())
    rec["cwd"] = cwd
    rec["message"]["content"] = [{"type": "tool_use", "name": "Bash", "input": {"command": command}}]
    return rec


def write_rollout(home, ident, ts, cwd, model="gpt-5.4", inp=0, cached=0, cache_write=0, out=0, reasoning=0, total=None, used=(10, 20)):
    total = inp + out if total is None else total
    records = [
        {"type": "session_meta", "payload": {"timestamp": ts, "cwd": cwd, "originator": "Claude Code", "model": None}},
        {"type": "turn_context", "payload": {"model": model, "effort": "medium"}},
        {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": inp, "cached_input_tokens": cached, "cache_write_input_tokens": cache_write, "output_tokens": out, "reasoning_output_tokens": reasoning, "total_tokens": total}}}},
        {"type": "rate_limits", "payload": {"used_percent": used[0]}},
        {"type": "rate_limits", "payload": {"used_percent": used[1]}},
    ]
    write_jsonl(home / "sessions" / "2026" / "07" / "20" / f"rollout-{ident}.jsonl", records)


def run_report_codex(root, home, *extra):
    return run_report(root, "--codex-home", str(home), *extra)


def delegation_section(report):
    return report.split("## Codex delegation", 1)[1].split("## Quota-headroom figures", 1)[0]


def test_codex_delegation_normal_attribution(tmp_path):
    cwd = "/work/project"
    make_session(tmp_path, "p", "s", [orchestrator_line("2026-07-20T10:00:00Z", 1)], dispatches=[
        ("g", "gondor-builder", [codex_bash("2026-07-20T10:01:00Z", cwd), assistant("2026-07-20T10:03:00Z", "end", "end", SONNET, usage())])])
    home = tmp_path / "codex"
    write_rollout(home, "normal", "2026-07-20T10:02:00Z", cwd, inp=1_000_000, cached=200_000, cache_write=123, out=500_000, reasoning=100, total=1_500_000)
    section = delegation_section(run_report_codex(tmp_path, home))
    assert "| gondor-builder | gpt-5.4 | 1 | 1,000,000 | 200,000 | 123 | 500,000 | 100 | 238.75 | — |" in section


def test_codex_delegation_ambiguous_window_is_not_attributed(tmp_path):
    cwd = "/work/project"
    make_session(tmp_path, "p", "s", [orchestrator_line("2026-07-20T10:00:00Z", 1)], dispatches=[
        ("a", "gondor-builder", [codex_bash("2026-07-20T10:01:00Z", cwd), assistant("2026-07-20T10:04:00Z", "ea", "ea", SONNET, usage())]),
        ("b", "gondor-builder", [codex_bash("2026-07-20T10:01:30Z", cwd), assistant("2026-07-20T10:04:00Z", "eb", "eb", SONNET, usage())])])
    home = tmp_path / "codex"; write_rollout(home, "amb", "2026-07-20T10:02:00Z", cwd, total=9)
    section = delegation_section(run_report_codex(tmp_path, home))
    assert "Ambiguous (multi-window match, not attributed): 1 sessions, 9 tokens (files: rollout-amb.jsonl)" in section
    assert "| gondor-builder | gpt-5.4 |" not in section


def test_codex_delegation_unattributed(tmp_path):
    home = tmp_path / "codex"; write_rollout(home, "none", "2026-07-20T10:02:00Z", "/elsewhere", total=77)
    section = delegation_section(run_report_codex(tmp_path, home))
    assert "Unattributed (no matching tlor dispatch window): 1 sessions, 77 tokens" in section
    assert "| gondor-builder | gpt-5.4 |" not in section


def test_codex_unknown_model_pricing_is_na_and_warned(tmp_path):
    cwd = "/work/project"
    make_session(tmp_path, "p", "s", [orchestrator_line("2026-07-20T10:00:00Z", 1)], dispatches=[
        ("g", "gondor-builder", [codex_bash("2026-07-20T10:01:00Z", cwd), assistant("2026-07-20T10:03:00Z", "end", "end", SONNET, usage())])])
    home = tmp_path / "codex"; write_rollout(home, "terra", "2026-07-20T10:02:00Z", cwd, model="gpt-9.9-unknown")
    report = run_report_codex(tmp_path, home)
    assert "| gondor-builder | gpt-9.9-unknown | 1 | 0 | 0 | 0 | 0 | 0 | N/A | — |" in delegation_section(report)
    assert "Codex model 'gpt-9.9-unknown' has unknown credits pricing" in report.split("## Warnings", 1)[1]


def test_codex_baseline_estimate(tmp_path):
    cwd = "/work/project"
    dispatches = []
    for i, out in enumerate((100_000, 200_000, 300_000)):
        dispatches.append((f"plain{i}", "gondor-builder", [assistant(f"2026-07-20T10:0{i}:00Z", f"p{i}", f"p{i}", SONNET, usage(out=out))]))
    dispatches.append(("codex", "gondor-builder", [codex_bash("2026-07-20T10:10:00Z", cwd), assistant("2026-07-20T10:11:00Z", "ca", "ca", SONNET, usage(out=50_000))]))
    make_session(tmp_path, "p", "s", [orchestrator_line("2026-07-20T10:00:00Z", 1)], dispatches=dispatches)
    home = tmp_path / "codex"; write_rollout(home, "baseline", "2026-07-20T10:10:30Z", cwd)
    section = delegation_section(run_report_codex(tmp_path, home))
    assert "| gondor-builder | 1 | 3 | $2.00 | $1.00 | $0.50 | $1.50 | $1.50 |" in section


def test_codex_missing_home_has_only_skip_line_and_keeps_report(tmp_path):
    make_session(tmp_path, "p", "s", [orchestrator_line("2026-07-20T10:00:00Z", 1, ["gondor-builder"])], dispatches=[
        ("gondor-builder", "gondor-builder", [assistant("2026-07-20T10:01:00Z", "x", "x", SONNET, usage(out=9))])])
    missing = tmp_path / "missing-codex-home"
    report = run_report_codex(tmp_path, missing)
    assert delegation_section(report) == f"\n\nCodex home {missing} has no sessions directory — Codex delegation reporting skipped.\n\n"
    assert cell(report, "gondor-builder", "output") == "9"
