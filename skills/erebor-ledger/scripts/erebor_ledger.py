#!/usr/bin/env python3
"""erebor-ledger usage report — token/cost savings from tlor-orchestration dispatch.

Reads Claude Code transcript JSONL files (main-session + subagent) and
answers two independent questions (per erebor-ledger spec §1/§3):

  1. When Fable 5 is the orchestrator, how much token/cost did dispatching
     to tlor-orchestration save versus doing the work inline?
  2. Same question when any Opus version is the orchestrator?

The two groups are reported and totalled SEPARATELY — they are never
averaged or merged (spec §1, §3). Sessions whose orchestrator model is
neither `claude-fable-5*` nor `claude-opus-*` (e.g. a sonnet orchestrator)
fall into "other" and are excluded from both reports — but that exclusion is
disclosed every run (2026-07-27 fix; see render_exclusion_disclosure()),
never left only to this docstring.

python3 stdlib only — no pip dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

# Display-ORDER hint only — NOT the source of truth for which roles exist.
# A role added after this list was last updated (this drifted twice: it
# shipped with nine names while eleven role files/manifest entries existed)
# still gets discovered and reported by discover_tlor_roles() below; it is
# just appended after the names below instead of interleaved by hand.
TLOR_ROLES = [
    "rohirrim-outrider",
    "ranger-pathfinder",
    "noldor-loremaster",
    "dwarf-smith",
    "gondor-builder",
    "eagle-sentinel",
    "elf-archer",
    "orc-saboteur",
    "hobbit-gardener",
]
OTHER_ROLE_LABEL = "(other subagents)"
SYNTHETIC_MODEL = "<synthetic>"

COUNTERFACTUAL_DISCLOSURE = (
    "Counterfactual assumes inline execution would consume the same token"
    " volume; this is an estimate, not a measurement."
)
CACHE_TIER_DISCLOSURE = (
    "Cache-write pricing: each cache-write token is priced at its own tier"
    " (5-minute vs 1-hour) using the transcript's own"
    " `usage.cache_creation.{ephemeral_5m_input_tokens,ephemeral_1h_input_tokens}`"
    " breakdown. A record that lacks this breakdown falls back to pricing its"
    " whole cache-write amount at the 5-minute tier (the prior conservative"
    " assumption) and is warned about explicitly — see warnings."
)
CACHE_TIER_SUM_DISCLOSURE = (
    "Cache-write volume vs cost basis: the `cache(r/w)` column's write half"
    " displays `usage.cache_creation_input_tokens`, while the cost is computed"
    " from the per-tier `usage.cache_creation.{ephemeral_5m_input_tokens,"
    "ephemeral_1h_input_tokens}` breakdown. On a small number of records the"
    " two do not agree (the tier fields sum to less — or more — than the total),"
    " so for those records the displayed write VOLUME and the volume the COST is"
    " based on diverge. THE COST USES THE PER-TIER BREAKDOWN, never the total."
    " Every such record is named in the warnings below."
)
MONOTONICITY_DISCLOSURE = (
    "Usage-monotonicity check: a response's usage counters are cumulative and"
    " non-decreasing across the progressive snapshots Claude Code writes, which"
    " is why the canonical value for a `(message.id, requestId)` key is the"
    " MAXIMUM per field across its occurrences. If a key's LATEST occurrence"
    " reports less than that maximum for any raw counter, that assumption no"
    " longer holds — the record format has changed — and the key and field are"
    " named in the warnings below. Zero violations is the expected state."
)
EFFORT_SOURCE_DISCLOSURE = (
    "Effort values marked with `*` come from the role's pinned frontmatter"
    " (`effort:` in agents/<role>.md), not a per-dispatch record — Claude"
    " Code transcripts don't record per-dispatch effort."
)
RETRY_HEURISTIC_DISCLOSURE = (
    "Retries (heuristic) counts CONSECUTIVE dispatches to the same role in the"
    " orchestrator's own issue order (main-session Agent tool_use order), where"
    " consecutive dispatches from the SAME assistant message (a parallel"
    " fan-out) are excluded. This is a heuristic, not a verified retry count:"
    " whether issue order always equals true wall-clock order under parallel"
    " dispatch has not been stress-tested, and two dispatches to the same role"
    " issued in separate messages that were actually independent (not a"
    " retry) would still be over-counted here."
)
API_EQUIVALENT_DISCLOSURE = (
    "The dollar figures in this report (API-equiv cost / quota headroom preserved)"
    " are API list-price equivalents, not money the user spent or kept: under a"
    " flat-fee subscription the marginal cash saving from dispatching to a cheaper"
    " model is zero. What dispatching actually conserves is quota headroom, not cash."
    " This report deliberately does NOT compute a percentage of the official weekly"
    " limit (no absolute quota number is published by Anthropic) or a 'realized unit"
    " price' (fee / tokens-consumed), since fewer tokens used would then make each"
    " token look more expensive — see the Quota-headroom figures section for the"
    " figures used instead."
)

# Weekly quota-reset boundary for --cycle, OBSERVED empirically on this
# framework's reference machine (2026-07-27) — NOT a published Anthropic
# value. Thursday 13:00 UTC+8 == Thursday 05:00 UTC. Overridable via
# --cycle-reset-weekday/--cycle-reset-hour-utc if the boundary ever changes.
CYCLE_RESET_WEEKDAY = 3  # Monday=0 ... Thursday=3 (datetime.weekday())
CYCLE_RESET_HOUR_UTC = 5

TOKEN_FIELDS = ("input", "output", "cache_write", "cache_read", "cache_write_5m", "cache_write_1h")

# The subset of TOKEN_FIELDS that are RAW cumulative counters as the API
# reports them — the only fields the monotonicity detector (FIX 3
# 2026-07-27, see collect_dedup_winners) may judge. `cache_write_5m`/
# `cache_write_1h` are deliberately excluded: they are a DERIVED split of
# `cache_write` (usage_to_tokens), and a record that lacks the
# `usage.cache_creation` breakdown has its whole amount synthesized into the
# 5m column — so two occurrences of one key that disagree about whether the
# breakdown is present would shift volume between the two columns and trip a
# decrease that says nothing about cumulativeness.
MONOTONIC_FIELDS = ("input", "output", "cache_write", "cache_read")

DEFAULT_ROOT = os.path.expanduser("~/.claude/projects")
# Read-only: this script NEVER writes this file. Creating/updating it is the
# skill's job (first-run flow), not the script's — see SKILL.md's config-split
# note. load_ledger_config() below only ever opens it with mode "r".
DEFAULT_CONFIG_PATH = os.path.expanduser("~/.claude/erebor-ledger.json")
PRICE_TABLE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "references", "model-prices.json"
)
CODEX_RATE_CARD_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "references", "codex-rate-card.json"
)
# Repo-relative agents/ dir next to this skill's plugin root (skills/erebor-ledger/scripts/ -> repo root/agents).
PLUGIN_AGENTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "agents"
)

_MODEL_DATE_SUFFIX_RE = re.compile(r"-\d{8}$")

MODEL_FAMILY_TIER = {"haiku": 0, "sonnet": 1, "opus": 2, "fable": 3}
_MODEL_FAMILY_RE = re.compile(r"(haiku|sonnet|opus|fable)")


def model_family(model: str | None) -> str | None:
    """Extract the family token (haiku/sonnet/opus/fable) out of a model id
    or a bare pinned-frontmatter value (e.g. `opus`, `claude-opus-4-8`,
    `sonnet-5`). Returns None if no known family token is present."""
    if not model:
        return None
    m = _MODEL_FAMILY_RE.search(model.lower())
    return m.group(1) if m else None


def short_model_id(model: str | None) -> str:
    """Shorten a `.message.model` id for table display: strip the leading
    `claude-` and a trailing date snapshot suffix like `-20251001`.

    e.g. `claude-haiku-4-5-20251001` -> `haiku-4-5`; `claude-opus-4-8` (no
    date suffix) -> `opus-4-8`.
    """
    if not model:
        return "—"
    m = model
    if m.startswith("claude-"):
        m = m[len("claude-"):]
    m = _MODEL_DATE_SUFFIX_RE.sub("", m)
    return m


# --------------------------------------------------------------------------
# Pricing
# --------------------------------------------------------------------------

def load_price_table(path: str = PRICE_TABLE_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop("_meta", None)
    return data


def load_codex_rate_card(path: str = CODEX_RATE_CARD_PATH) -> dict:
    """Read the separate, flat Codex credits rate card (read-only)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_ledger_config(path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Read-only: opens `path` with mode "r" only. Returns {} if the file is
    absent or unreadable/malformed — the script proceeds without figures 3/4
    rather than failing (see SKILL.md's config-split note: the script never
    writes this file; creating it is the skill's first-run flow)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def parse_iso_utc(ts: str | None) -> datetime | None:
    """Parse an ISO-8601 transcript timestamp into a timezone-aware UTC
    datetime for precise boundary comparisons (never string-slicing) — used
    by --cycle. Returns None if `ts` is missing or unparseable."""
    if not ts:
        return None
    t = ts.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def cycle_window(
    n: int,
    now_utc: datetime,
    reset_weekday: int = CYCLE_RESET_WEEKDAY,
    reset_hour_utc: int = CYCLE_RESET_HOUR_UTC,
) -> tuple[datetime, datetime]:
    """Return (since_dt, until_dt) UTC bounds [since, until) for quota cycle
    `n`: 0 = the cycle currently in progress (most recent reset through now),
    1 = the most recently COMPLETED cycle, 2 = the one before that, etc.
    Reset boundary defaults to Thursday 05:00 UTC (see CYCLE_RESET_WEEKDAY/
    CYCLE_RESET_HOUR_UTC) — pass overrides if that observed value changes."""
    days_back = (now_utc.weekday() - reset_weekday) % 7
    latest_reset = (now_utc - timedelta(days=days_back)).replace(
        hour=reset_hour_utc, minute=0, second=0, microsecond=0
    )
    if latest_reset > now_utc:
        latest_reset -= timedelta(days=7)
    since = latest_reset - timedelta(days=7 * n)
    until = since + timedelta(days=7)
    return since, until


# Average Gregorian month length (365.25 / 12) — used only to convert a
# reported period's day-span into a fractional "number of months" for H2
# (period-length normalization); this is deliberately NOT calendar-month-
# aware (see `period_length_for_months` for why).
_AVG_MONTH_DAYS = 30.4375


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """UTC [since, until) bounds for one `YYYY-MM` month string."""
    year, mon = int(month[:4]), int(month[5:7])
    since = datetime(year, mon, 1, tzinfo=timezone.utc)
    until = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if mon == 12 else datetime(year, mon + 1, 1, tzinfo=timezone.utc)
    return since, until


def period_length(since_dt: datetime, until_dt: datetime) -> tuple[float, float]:
    """(months, cycles) spanned by one contiguous [since_dt, until_dt) window
    — H2 (2026-07-28): the subscription fee is normalized by the number of
    MONTHS in the reported period and the calibration ceiling by the number
    of quota-reset CYCLES (weekly), so a multi-month/multi-cycle report no
    longer divides a period's whole total cost by a single month's fee or a
    single cycle's ceiling (which inflated a 6-month report ~6x and a
    26-cycle report ~26x before this fix).

    Both figures are fractional (days / 30.4375, days / 7), never rounded:
    a partial month/cycle is charged/credited its exact fractional share.
    Rounding UP would overstate how much subscription coverage a partial
    period needs; rounding DOWN would understate it and make a >=1-month
    period with a few extra days look like exactly N months. The
    fractional form is also the only one that composes correctly when
    `period_length_multi` below sums several non-contiguous windows."""
    days = (until_dt - since_dt).total_seconds() / 86400
    return days / _AVG_MONTH_DAYS, days / 7


def period_length_multi(windows: list[tuple[datetime, datetime]]) -> tuple[float, float]:
    """(months, cycles) for SEVERAL possibly non-contiguous windows (e.g.
    `--month 2026-01 --month 2026-06`) — sums each window's own day-span
    rather than spanning min..max, which would also count the unselected
    months in between."""
    total_days = sum((until_dt - since_dt).total_seconds() / 86400 for since_dt, until_dt in windows)
    return total_days / _AVG_MONTH_DAYS, total_days / 7


def resolve_price(model: str | None, price_table: dict, today: str) -> dict | None:
    """Longest-prefix match of `model` against price_table keys.

    Returns the price entry dict, or None if no key is a prefix of `model`
    (per spec §6: unknown model SHALL NOT be priced by guessing).
    """
    if not model:
        return None
    best_key = None
    for key in price_table:
        if model.startswith(key):
            if best_key is None or len(key) > len(best_key):
                best_key = key
    if best_key is None:
        return None
    entry = price_table[best_key]
    next_tier = entry.get("next_tier")
    if next_tier and next_tier.get("effective_from") and today >= next_tier["effective_from"]:
        return next_tier
    return entry


def zero_tokens() -> dict:
    return {k: 0 for k in TOKEN_FIELDS}


def add_tokens(dst: dict, src: dict) -> None:
    for k in TOKEN_FIELDS:
        dst[k] += src.get(k, 0)


def usage_to_tokens(usage: dict, warnings: list | None = None, context: str = "") -> dict:
    """`cache_write` is the total cache-creation tokens (used for the report's
    `cache(r/w)` display cell, unchanged). `cache_write_5m`/`cache_write_1h`
    split that same total by tier for costing (see CACHE_TIER_DISCLOSURE),
    read from `usage.cache_creation.{ephemeral_5m_input_tokens,
    ephemeral_1h_input_tokens}` when present. A record with cache-write
    tokens but no such breakdown falls back to treating the whole amount as
    5-minute tier and is warned about once per record."""
    cache_write_total = usage.get("cache_creation_input_tokens", 0) or 0
    cache_creation = usage.get("cache_creation")
    if isinstance(cache_creation, dict) and (
        "ephemeral_5m_input_tokens" in cache_creation or "ephemeral_1h_input_tokens" in cache_creation
    ):
        cache_write_5m = cache_creation.get("ephemeral_5m_input_tokens", 0) or 0
        cache_write_1h = cache_creation.get("ephemeral_1h_input_tokens", 0) or 0
    else:
        cache_write_5m = cache_write_total
        cache_write_1h = 0
        if cache_write_total and warnings is not None:
            warnings.append(
                "WARNING: record"
                + (f" in {context}" if context else "")
                + " has cache-write tokens but no `usage.cache_creation` tier breakdown"
                " — priced at the 5-minute tier fallback (see CACHE_TIER_DISCLOSURE)"
            )
    return {
        "input": usage.get("input_tokens", 0) or 0,
        "output": usage.get("output_tokens", 0) or 0,
        "cache_write": cache_write_total,
        "cache_read": usage.get("cache_read_input_tokens", 0) or 0,
        "cache_write_5m": cache_write_5m,
        "cache_write_1h": cache_write_1h,
    }


def cost_for_tokens(tokens: dict, price_entry: dict | None) -> float | None:
    """input/output/cache_read priced separately, and cache-write priced PER
    TIER (5-minute vs 1-hour, see CACHE_TIER_DISCLOSURE) then summed (spec
    §4 — no single blended rate)."""
    if price_entry is None:
        return None
    return (
        tokens["input"] / 1_000_000 * price_entry["input"]
        + tokens["output"] / 1_000_000 * price_entry["output"]
        + tokens["cache_write_5m"] / 1_000_000 * price_entry["cache_write_5m"]
        + tokens["cache_write_1h"] / 1_000_000 * price_entry["cache_write_1h"]
        + tokens["cache_read"] / 1_000_000 * price_entry["cache_read"]
    )


# --------------------------------------------------------------------------
# Transcript walking
# --------------------------------------------------------------------------

def _record_in_window(
    ts: str | None,
    since: str | None,
    until: str | None,
    month: str | None,
    since_dt: datetime | None,
    until_dt: datetime | None,
) -> bool:
    """True if `ts` (a record's raw `timestamp` string, possibly None/empty)
    falls inside the active date filter. Side-effect-free (no warnings) —
    shared by `iter_assistant_records` (which additionally warns on a
    missing/unparseable timestamp) and `_iter_dedup_candidates` (the
    machine-wide dedup pre-pass, CHANGE 1 2026-07-27), so both agree on
    exactly the same in-window record set without emitting the warning
    twice."""
    dt_filter_active = since_dt is not None or until_dt is not None
    if since is None and until is None and month is None and not dt_filter_active:
        return True
    if not ts:
        return False
    if dt_filter_active:
        ts_dt = parse_iso_utc(ts)
        if ts_dt is None:
            return False
        if since_dt is not None and ts_dt < since_dt:
            return False
        if until_dt is not None and ts_dt >= until_dt:
            return False
        return True
    if month is not None:
        return ts[:7] == month
    if since is not None and ts[:10] < since:
        return False
    if until is not None and ts[:10] > until:
        return False
    return True


_RAW_RECORDS_CACHE: dict[str, list] = {}


def _read_raw_assistant_records(path: str):
    try:
        f = open(path, "r", encoding="utf-8")
    except OSError:
        return
    with f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "assistant":
                continue
            message = rec.get("message") or {}
            model = message.get("model")
            if model == SYNTHETIC_MODEL:
                continue
            ts = rec.get("timestamp")
            usage = message.get("usage") or {}
            yield line_no, rec, ts, model, usage


def _iter_raw_assistant_records(path: str):
    """Yield (line_no, rec, ts, model, usage) for every non-synthetic
    `"type":"assistant"` record in `path`, JSON-parsed, with NO window
    filtering and NO warnings — the single shared low-level file walk used
    by `iter_assistant_records` (the warning-emitting, window-filtering
    pass), `_iter_dedup_candidates` (the silent dedup pre-pass), and
    (transitively, via `iter_assistant_records`) `classify_sessions`
    (dominant-model lookup).

    M6: this also folds in the third-read gap `classify_sessions` left
    open — its docstring used to note that a main-session file was read a
    THIRD time (alongside `collect_dedup_winners`'s pre-pass and
    `build_report`'s own pass) with no shared walk to fix it. The list
    returned by `_read_raw_assistant_records` is cached per `path` here, so
    `path` is actually read off disk at most once per process regardless of
    how many of the three callers walk it — each caller still applies its
    own filtering/warnings on top of the cached, side-effect-free rows, so
    no caller's observable behavior changes."""
    cached = _RAW_RECORDS_CACHE.get(path)
    if cached is None:
        cached = list(_read_raw_assistant_records(path))
        _RAW_RECORDS_CACHE[path] = cached
    yield from cached


def iter_assistant_records(
    path: str,
    since: str | None,
    until: str | None,
    month: str | None,
    warnings: list,
    since_dt: datetime | None = None,
    until_dt: datetime | None = None,
):
    """Yield (model, tokens, dedup_key, line_no, record_date) for each
    non-synthetic assistant record. `dedup_key` is `record_dedup_key(rec)`;
    `line_no` is this record's 1-based line number in `path`; `record_date`
    is this record's own `YYYY-MM-DD` (sliced from its `timestamp`), or
    `None` when the record has no/too-short a timestamp. Per H1
    (2026-07-28): a caller MUST price a record against ITS OWN
    `record_date` (falling back to a caller-chosen date only when it is
    `None`), never against the execution date (`datetime.now()`) — a price
    table `next_tier.effective_from` boundary would otherwise silently
    re-price every already-recorded record once that date passes. A caller
    MUST also resolve `dedup_key`/`line_no` against the machine-wide winner
    map from `collect_dedup_winners` (via `dedup_against_winners`, CHANGE 1
    2026-07-27) before summing `tokens`, per FIX 1: Claude Code repeats the
    same `message.usage` snapshot on every content-block line of one
    response, AND a resumed/forked session re-emits an earlier session's
    records verbatim (including their message.id/requestId) into a new
    top-level session file.

    Timestamp filtering: transcripts on this machine reliably carry a
    top-level ISO `timestamp` field (spec §7 requires confirming this before
    relying on it). A record missing `timestamp` while any date filter
    (--since/--until/--month/--cycle) is active is excluded (fail closed)
    rather than silently included, and warned once. (In-window test itself
    lives in `_record_in_window`, shared with the dedup pre-pass.)

    `month` (YYYY-MM) is mutually exclusive with since/until — callers
    enforce that before this point; when `month` is set it is the only
    date-string filter applied.

    `since_dt`/`until_dt` (timezone-aware UTC datetimes, from --cycle) take
    priority over since/until/month when provided — this is a precise
    [since_dt, until_dt) comparison against the parsed timestamp, never a
    string-slice, so it can express an hour boundary the date-granular
    filters above cannot.
    """
    dt_filter_active = since_dt is not None or until_dt is not None
    date_filter_active = since is not None or until is not None or month is not None or dt_filter_active
    for line_no, rec, ts, model, usage in _iter_raw_assistant_records(path):
        if date_filter_active:
            if not ts:
                warnings.append(
                    f"WARNING: record without timestamp in {path} excluded under date filter"
                    " (transcript timestamp field assumed reliable on this machine;"
                    " see spec §7 mtime-fallback clause)"
                )
                continue
            if dt_filter_active and parse_iso_utc(ts) is None:
                warnings.append(
                    f"WARNING: record with unparseable timestamp '{ts}' in {path}"
                    " excluded under --cycle filter"
                )
                continue
            if not _record_in_window(ts, since, until, month, since_dt, until_dt):
                continue
        record_date = ts[:10] if ts and len(ts) >= 10 else None
        yield model, usage_to_tokens(usage, warnings, path), record_dedup_key(rec), line_no, record_date


def record_dedup_key(rec: dict) -> tuple | None:
    """(message.id, requestId) pair identifying one API response, used to
    dedupe the CONTENT-BLOCK duplication documented in FIX 1 (2026-07-27):
    Claude Code writes one `"type":"assistant"` line per content block of a
    single response (a `thinking`, `text`, and `tool_use` block each get
    their own line), and every one of those lines repeats the SAME
    `message.usage` snapshot for the whole message — summing per line
    triples (or more) every token/cost total. Returns None when either half
    is missing, in which case the caller must NOT dedupe on `message.id`
    alone (per spec) — such records are passed through unchanged. In
    practice the only in-window records missing `requestId` are
    `<synthetic>` (already excluded above with all-zero usage)."""
    message_id = (rec.get("message") or {}).get("id")
    request_id = rec.get("requestId")
    if not message_id or not request_id:
        return None
    return (message_id, request_id)


# Sentinel used by `_iter_dedup_candidates`/`collect_dedup_winners` when a
# duplicate-key occurrence has no parseable timestamp: sorted as "latest
# possible" so it never outranks an occurrence that DOES carry a real
# timestamp, and so two timestamp-less occurrences of the same key still
# tie-break deterministically on (path, line_no) below.
_MISSING_TIMESTAMP_SENTINEL = datetime.max.replace(tzinfo=timezone.utc)


def _iter_dedup_candidates(
    path: str,
    since: str | None,
    until: str | None,
    month: str | None,
    since_dt: datetime | None,
    until_dt: datetime | None,
):
    """Pre-pass companion to `iter_assistant_records`: yield
    (key, sort_dt, line_no, tokens, record_date) for every in-window,
    non-synthetic assistant record in `path` that has a resolvable
    `record_dedup_key`. `record_date` is `YYYY-MM-DD` sliced from the raw
    timestamp (or `None`), fed to `collect_dedup_winners` so the
    ATTRIBUTION OWNER's own date can be used for per-record pricing (H1,
    2026-07-28) rather than the run's execution date. No warnings (the real
    emitting pass already warns once for a missing/unparseable timestamp
    under an active filter, and once for a missing cache tier breakdown) —
    this exists only to feed `collect_dedup_winners`, which needs each
    occurrence's own token values to pick the canonical per-field maximum
    (FIX 3 2026-07-27)."""
    for line_no, rec, ts, _model, usage in _iter_raw_assistant_records(path):
        if not _record_in_window(ts, since, until, month, since_dt, until_dt):
            continue
        key = record_dedup_key(rec)
        if key is None:
            continue
        dt = parse_iso_utc(ts) if ts else None
        tokens = usage_to_tokens(usage)
        record_date = ts[:10] if ts and len(ts) >= 10 else None
        yield key, (dt if dt is not None else _MISSING_TIMESTAMP_SENTINEL), line_no, tokens, record_date


def classify_sessions(
    root: str,
    project_filter: str | None,
    since: str | None,
    until: str | None,
    month: str | None,
    since_dt: datetime | None,
    until_dt: datetime | None,
) -> dict:
    """{session_path: group_name} for every main session in the scanned,
    filtered set, using the SAME dominant-model rule `build_report` uses
    (most-common `.message.model` among the session's own raw assistant
    records) — dedup never changes a record's `model` field, only its
    token values, so this is safe to compute from undeduped records and
    shared with both `collect_dedup_winners` (M10 attribution, below) and
    `build_report` (which still separately derives `orchestrator_model`
    for pricing/display); the two remain independent computations by
    design (different loop shapes: this classifies a whole session in one
    pass, `build_report` derives it per-session inline alongside pricing).
    M6: the underlying FILE READ this and `collect_dedup_winners`'s
    pre-pass and `build_report`'s own pass each triggered is no longer done
    three times — `iter_assistant_records` and `_iter_dedup_candidates`
    both now go through `_iter_raw_assistant_records`, which caches the
    parsed rows per path, so the physical read happens at most once."""
    scratch_warnings: list = []
    session_group: dict = {}
    for _project_name, project_dir in find_project_dirs(root, project_filter):
        for _session_id, session_path in find_main_sessions(project_dir):
            models = [
                m
                for m, _tok, _key, _line_no, _date in iter_assistant_records(
                    session_path, since, until, month, scratch_warnings, since_dt, until_dt
                )
            ]
            if not models:
                continue
            dominant = Counter(models).most_common(1)[0][0]
            session_group[session_path] = classify_group(dominant)
    return session_group


def collect_dedup_winners(
    root: str,
    project_filter: str | None,
    since: str | None,
    until: str | None,
    month: str | None,
    since_dt: datetime | None,
    until_dt: datetime | None,
) -> tuple:
    """CHANGE 1 (2026-07-27): first pass over the ENTIRE scanned set for this
    run — every project, every session, main transcript AND every
    `subagents/agent-*.jsonl` file — collecting, for each `(message.id,
    requestId)` dedup key, every occurrence's (timestamp, path, line_no,
    tokens).

    Widened from the prior session-scoped dedup because a resumed or forked
    Claude Code session copies an EARLIER session's transcript content
    (including its original message.id/requestId) into a NEW top-level
    session file; those duplicate keys therefore cross session boundaries,
    not just main/subagent file boundaries within one session. Both
    `message.id` and `requestId` are server-assigned identifiers for a
    single API response, so unrelated calls cannot legitimately collide —
    one API response is one billing event and must be counted once no
    matter how many transcripts echo it. Do not narrow this back to
    per-session as an "optimisation": that is the exact bug this pass
    fixes.

    TWO SEPARATE RULES, deliberately not merged — conflating them was the
    defect FIX 3 (2026-07-27) corrects:

    1. **Which usage VALUE is canonical: the per-field MAXIMUM across the
       key's occurrences.** Claude Code writes PROGRESSIVE usage snapshots
       for one response, so the EARLIEST line for a message is a partial
       mid-stream reading (measured on this machine: `output_tokens` 3 on the
       first line of a message whose completed value was 3305). A response's
       usage counters are cumulative and non-decreasing, so the maximum is
       the completed reading and cannot under-count. Taking the earliest
       occurrence's VALUE — which this function did until FIX 3 — lost 47.4%
       of all output tokens machine-wide (2,021 of 3,059 duplicate keys
       disagreed across occurrences). Do NOT reinstate earliest-value, and do
       NOT "simplify" this to taking the latest record wholesale either: max
       per field is robust to an out-of-order or truncated last line.
    2. **Which occurrence owns the ATTRIBUTION (which project/session/role
       the tokens are credited to): the EARLIEST occurrence.** A resumed or
       forked session re-emits an earlier session's records verbatim, and the
       original session is the right owner. A tie (or all-missing timestamps)
       is broken by (file path, line number), so a run is reproducible — two
       runs over the same tree always pick the same owner for the same key.

    FIX 3 also adds a MONOTONICITY DETECTOR (rule 1's own guard): if a key's
    LATEST occurrence reports LESS than the maximum seen for any field in
    MONOTONIC_FIELDS, the cumulative assumption behind rule 1 has been
    violated — a warning naming the key and the field is returned, so a
    future change to Claude Code's record format is noticed instead of
    silently corrupting totals. The same pass reports records whose
    `cache_creation` tier fields do not sum to `cache_creation_input_tokens`
    (see CACHE_TIER_SUM_DISCLOSURE — the cost uses the tier breakdown).

    M10 (2026-07-28): the attribution owner (rule 2) is the earliest
    occurrence in an INCLUDED session (Fable or Opus orchestrator group) —
    never an occurrence whose owning session classified as "other"
    (excluded, spec §3). The excluded-session report path never renders a
    role/pricing breakdown, so a key whose true-earliest occurrence merely
    happened to be re-emitted by an excluded session's transcript used to
    have its tokens permanently zeroed everywhere else: no occurrence in
    the Fable/Opus tables ever matched that owner's `(path, line_no)`, so
    every other occurrence was treated as a "loser" duplicate and zeroed
    (see `dedup_against_winners`). Falls back to the true-earliest
    occurrence only when EVERY occurrence of a key is in an excluded
    session (nothing else to attribute to).

    Returns `(winners, integrity_warnings)`, where `winners` is
    `{dedup_key: (owning_path, owning_line_no, canonical_tokens,
    owner_record_date)}` — ONLY for keys seen more than once; a key seen
    exactly once is absent, and every caller (`dedup_against_winners`) must
    treat "absent" as "always keep its own tokens" (the maximum over one
    occurrence is that occurrence). `owner_record_date` (`YYYY-MM-DD` or
    `None`) is the owning occurrence's own date, threaded through so a
    winning record is priced against the date it actually happened on
    (H1), not the date the report happens to be run on."""
    session_group = classify_sessions(root, project_filter, since, until, month, since_dt, until_dt)
    candidates: dict = defaultdict(list)
    for _project_name, project_dir in find_project_dirs(root, project_filter):
        for session_id, session_path in find_main_sessions(project_dir):
            for key, sort_dt, line_no, tokens, record_date in _iter_dedup_candidates(
                session_path, since, until, month, since_dt, until_dt
            ):
                candidates[key].append((sort_dt, session_path, line_no, tokens, record_date, session_path))
            for agent_file, _meta_file in find_subagent_files(project_dir, session_id):
                for key, sort_dt, line_no, tokens, record_date in _iter_dedup_candidates(
                    agent_file, since, until, month, since_dt, until_dt
                ):
                    candidates[key].append((sort_dt, agent_file, line_no, tokens, record_date, session_path))
    winners: dict = {}
    integrity_warnings: list[str] = []
    for key, occurrences in candidates.items():
        # Sorted by (timestamp, path, line_no): occurrences[0] is the
        # chronologically-earliest occurrence, occurrences[-1] is the
        # latest occurrence the monotonicity detector judges. Attribution
        # (owner selection, M10) is computed SEPARATELY below — it must not
        # disturb this chronological order, which canonical-value/
        # monotonicity logic still depends on.
        occurrences.sort(key=lambda o: (o[0], o[1], o[2]))
        canonical = {f: max(o[3][f] for o in occurrences) for f in TOKEN_FIELDS}
        if canonical["cache_write"] and (
            canonical["cache_write_5m"] + canonical["cache_write_1h"] != canonical["cache_write"]
        ):
            integrity_warnings.append(
                f"WARNING: cache-tier sum mismatch for dedup key {key} in"
                f" {os.path.basename(occurrences[0][1])}:{occurrences[0][2]} —"
                f" ephemeral_5m {canonical['cache_write_5m']} + ephemeral_1h"
                f" {canonical['cache_write_1h']} != cache_creation_input_tokens"
                f" {canonical['cache_write']}; the displayed cache(r/w) write volume"
                " uses the total, the COST uses the per-tier breakdown"
                " (see CACHE_TIER_SUM_DISCLOSURE)"
            )
        if len(occurrences) <= 1:
            continue
        latest_tokens = occurrences[-1][3]
        for field in MONOTONIC_FIELDS:
            if latest_tokens[field] < canonical[field]:
                integrity_warnings.append(
                    f"WARNING: usage-monotonicity violation for dedup key {key}, field"
                    f" '{field}': latest occurrence reports {latest_tokens[field]} but the"
                    f" maximum across its {len(occurrences)} occurrences is"
                    f" {canonical[field]} — usage counters are supposed to be cumulative"
                    " and non-decreasing; the accounted value is still the maximum, but"
                    " Claude Code's record format may have changed"
                    " (see MONOTONICITY_DISCLOSURE)"
                )
        # M10: prefer the earliest occurrence whose OWNING SESSION is
        # included (Fable/Opus); fall back to the true-earliest occurrence
        # only if every occurrence belongs to an excluded ("other") session.
        included = [o for o in occurrences if session_group.get(o[5]) != "other"]
        owner = min(included, key=lambda o: (o[0], o[1], o[2])) if included else occurrences[0]
        winners[key] = (owner[1], owner[2], canonical, owner[4])
    return winners, integrity_warnings


def dedup_against_winners(records: list, path: str, winners: dict) -> list:
    """Take (model, tokens, key, line_no, record_date) quintuples from
    `iter_assistant_records` for ONE file (`path`) and return (model,
    tokens, is_duplicate, record_date) quadruples: a record whose key has
    an entry in `winners` (the machine-wide map from `collect_dedup_winners`)
    has its tokens zeroed and `is_duplicate=True` UNLESS `(path, line_no)` IS
    that entry's attribution owner — in which case it is credited with that
    entry's CANONICAL tokens (the per-field maximum across the key's
    occurrences, FIX 3 2026-07-27) rather than its own possibly-partial
    snapshot, AND the entry's own `owner_record_date` (H1, 2026-07-28) rather
    than this occurrence's own date — the winning occurrence's date is what
    the billing event actually happened on. A key absent from `winners` was
    seen exactly once machine-wide and keeps its own tokens/date. `key is
    None` records (missing message.id or requestId) are always passed
    through unchanged and never flagged as a duplicate, per spec: SHALL NOT
    be dropped or mis-deduped.

    The record itself is always preserved (model unchanged, one entry per
    input quintuple) even when its tokens are zeroed, so record-count-based
    logic (dispatch counts, dominant-model/orchestrator-model
    classification) is unaffected — only summed token/cost values change.
    `is_duplicate` lets callers also suppress a per-record warning (e.g. the
    unpriced-model warning, CHANGE 2 2026-07-27) from firing once per
    duplicate line instead of once per unique record."""
    result = []
    for model, tokens, key, line_no, record_date in records:
        if key is None:
            result.append((model, tokens, False, record_date))
            continue
        winner = winners.get(key)
        if winner is None:
            result.append((model, tokens, False, record_date))
        elif (winner[0], winner[1]) == (path, line_no):
            result.append((model, dict(winner[2]), False, winner[3]))
        else:
            result.append((model, zero_tokens(), True, record_date))
    return result


def classify_group(model: str | None) -> str:
    if not model:
        return "other"
    if model.startswith("claude-fable-5"):
        return "fable"
    if model.startswith("claude-opus-"):
        return "opus"
    return "other"


def find_project_dirs(root: str, project_filter: str | None):
    if not os.path.isdir(root):
        return
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if not os.path.isdir(full):
            continue
        if project_filter and project_filter not in name:
            continue
        yield name, full


def find_main_sessions(project_dir: str):
    for name in sorted(os.listdir(project_dir)):
        if name.endswith(".jsonl"):
            yield name[: -len(".jsonl")], os.path.join(project_dir, name)


def find_subagent_files(project_dir: str, session_id: str):
    subdir = os.path.join(project_dir, session_id, "subagents")
    if not os.path.isdir(subdir):
        return
    for name in sorted(os.listdir(subdir)):
        if name.endswith(".jsonl"):
            agent_file = os.path.join(subdir, name)
            meta_file = os.path.join(subdir, name[: -len(".jsonl")] + ".meta.json")
            yield agent_file, meta_file


def load_agent_meta(meta_file: str, warnings: list) -> dict:
    """Returns {"agentType", "toolUseId", "effort"} — `effort` is only ever
    populated if some future Claude Code version starts writing an
    effort-like key into meta.json; as of this writing meta.json never
    carries one (verified across this machine's full transcript corpus)."""
    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return {
            "agentType": meta.get("agentType") or OTHER_ROLE_LABEL,
            "toolUseId": meta.get("toolUseId"),
            "effort": meta.get("effort") or meta.get("reasoningEffort"),
        }
    except (OSError, json.JSONDecodeError):
        warnings.append(f"WARNING: missing/unreadable meta file {meta_file} — treated as {OTHER_ROLE_LABEL}")
        return {"agentType": OTHER_ROLE_LABEL, "toolUseId": None, "effort": None}


def extract_agent_tool_uses(session_path: str) -> dict:
    """Scan a main-session transcript for `Agent` tool_use blocks, keyed by
    tool_use id, so a dispatch's actual per-call `model`/`effort` override
    (per rules/dispatch.md §3/§4) can be looked up via meta.json's
    `toolUseId`. Returns {toolUseId: {"model": str|None, "effort": str|None,
    "order": int, "msg_index": int}}.

    `order` is a monotonic counter over `Agent` tool_use blocks in the order
    they appear in THIS transcript (i.e. the order the orchestrator issued
    dispatches — see retry-count heuristic below; there is no per-dispatch
    timestamp anywhere in this data, per the investigation in this skill's
    dispatch prompt/spec). `msg_index` is the 1-based position of the
    assistant record (message) the block came from, so two blocks sharing
    the same `msg_index` were emitted in the SAME assistant turn — i.e. a
    parallel fan-out issued in one message, not a sequential retry.
    """
    result: dict = {}
    order_counter = 0
    record_index = 0
    try:
        f = open(session_path, "r", encoding="utf-8")
    except OSError:
        return result
    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "assistant":
                continue
            record_index += 1
            content = (rec.get("message") or {}).get("content") or []
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use" or block.get("name") != "Agent":
                    continue
                tool_id = block.get("id")
                if not tool_id:
                    continue
                inp = block.get("input") or {}
                result[tool_id] = {
                    "model": inp.get("model"),
                    "effort": inp.get("effort") or inp.get("reasoningEffort"),
                    "order": order_counter,
                    "msg_index": record_index,
                }
                order_counter += 1
    return result


_PINNED_FRONTMATTER_CACHE: dict = {}


def load_pinned_frontmatter(agent_type: str) -> dict:
    """Parse a role's pinned frontmatter, checking the user-level install
    first, then the repo-relative plugin root next to this script. Returns
    {"effort": str|None, "model": str|None}. Cached per agent_type (both
    locations are static per run)."""
    if agent_type in _PINNED_FRONTMATTER_CACHE:
        return _PINNED_FRONTMATTER_CACHE[agent_type]
    candidates = [
        os.path.expanduser(f"~/.claude/agents/{agent_type}.md"),
        os.path.join(PLUGIN_AGENTS_DIR, f"{agent_type}.md"),
    ]
    effort = None
    model = None
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        parts = text.split("---", 2)
        frontmatter = parts[1] if len(parts) >= 3 else text
        for line in frontmatter.splitlines():
            line = line.strip()
            if effort is None and line.startswith("effort:"):
                effort = line.split(":", 1)[1].strip()
            elif model is None and line.startswith("model:"):
                model = line.split(":", 1)[1].strip()
        if effort or model:
            break
    result = {"effort": effort, "model": model}
    _PINNED_FRONTMATTER_CACHE[agent_type] = result
    return result


_TLOR_MANIFEST_PATH = os.path.expanduser("~/.claude/agents/.tlor-manifest")


def discover_tlor_roles() -> list[str]:
    """Enumerate the full set of framework role names — never from the
    hardcoded TLOR_ROLES display hint above (design for N, not for the N
    you know).

    Primary source: the installed manifest (`~/.claude/agents/.tlor-
    manifest`) — the same file `install.sh` writes, one `<name>.md` line
    per role it actually installed; this is authoritative because it names
    exactly what's installed on THIS machine, filtered to roles the
    installer itself vetted (excludes foreign agent files like a built-in
    `Explore.md` that happen to live in the same directory).

    Falls back to globbing `PLUGIN_AGENTS_DIR` (this repo's own `agents/`
    dir, mirroring the same two-location pattern `load_pinned_frontmatter`
    already uses) when no manifest is present — e.g. running straight out
    of a checked-out repo without an install. That directory ships only
    framework role files, so an unfiltered glob is safe there.

    Both sources exclude any filename containing `.bak` (stale/backup
    copies, e.g. `*.bak-YYYYMMDD*`, are not live roles).
    """
    try:
        with open(_TLOR_MANIFEST_PATH, "r", encoding="utf-8") as f:
            names = [
                line.strip()[: -len(".md")]
                for line in f
                if line.strip().endswith(".md") and ".bak" not in line
            ]
        if names:
            return names
    except OSError:
        pass
    try:
        return sorted(
            fn[: -len(".md")]
            for fn in os.listdir(PLUGIN_AGENTS_DIR)
            if fn.endswith(".md") and ".bak" not in fn
        )
    except OSError:
        return []


def ordered_tlor_roles() -> list[str]:
    """The full discovered role set (discover_tlor_roles), ordered using
    TLOR_ROLES as a display hint for the roles it already names, with any
    other discovered role (e.g. one added since TLOR_ROLES was last
    updated) appended afterwards, alphabetically among themselves."""
    discovered = discover_tlor_roles()
    discovered_set = set(discovered)
    ordered = [r for r in TLOR_ROLES if r in discovered_set]
    extra = sorted(r for r in discovered if r not in TLOR_ROLES)
    return ordered + extra


def load_pinned_effort(agent_type: str) -> str | None:
    return load_pinned_frontmatter(agent_type)["effort"]


def load_pinned_model(agent_type: str) -> str | None:
    return load_pinned_frontmatter(agent_type)["model"]


def model_marker(agent_type: str, model_cell: str) -> str:
    """`` (upgrade)``/`` (downgrade)`` suffix for a row's Model cell, comparing
    the row's actual model family/tier against the role's pinned frontmatter
    `model:` (per rules/dispatch.md §3/§4 — a per-call override). Empty string
    if the role has no pinned `model:`, or either side's family is unknown, or
    both sides share the same family (version differences within a family,
    e.g. pinned `opus` vs actual `opus-4-6`, are NOT a marker)."""
    pinned = load_pinned_model(agent_type)
    if not pinned:
        return ""
    pinned_family = model_family(pinned)
    actual_family = model_family(model_cell)
    pinned_tier = MODEL_FAMILY_TIER.get(pinned_family) if pinned_family else None
    actual_tier = MODEL_FAMILY_TIER.get(actual_family) if actual_family else None
    if pinned_tier is None or actual_tier is None or pinned_tier == actual_tier:
        return ""
    return " (upgrade)" if actual_tier > pinned_tier else " (downgrade)"


def resolve_effort(meta_effort: str | None, tool_info: dict | None, agent_type: str) -> str:
    """Priority order (spec §3): a recorded per-dispatch value (meta.json or
    the matching Agent tool_use's effort field) as-is; else the role's
    pinned frontmatter, marked with a trailing `*`; else `—`."""
    recorded = meta_effort
    if not recorded and tool_info:
        recorded = tool_info.get("effort")
    if recorded:
        return str(recorded)
    pinned = load_pinned_effort(agent_type)
    if pinned:
        return f"{pinned}*"
    return "—"


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

class RoleKey(NamedTuple):
    """(role, model, effort) — the composite key for one row of the
    per-role table. A NamedTuple, not a bare tuple, so `key.role`/
    `key.model`/`key.effort` are available alongside positional access
    (M9 — see GroupState/RoleRow for the companion fix)."""

    role: str
    model: str
    effort: str


@dataclass
class RoleRow:
    """One (role, model, effort) row's aggregated dispatch stats.

    M9: this used to be a bare dict (`new_role_row()`'s old return value)
    stored in a `defaultdict(new_role_row)` — a mistyped field name on a
    dict raises `KeyError` when READ but silently creates a new key when
    WRITTEN (`row["actual_costs"] = ...`), and looking up an unknown ROW
    KEY in the surrounding `defaultdict` silently vivified a fresh all-zero
    row rather than raising. A dataclass raises `AttributeError` immediately
    on any misspelled field, on read or write; see GroupState for the
    `defaultdict` half of this fix."""

    dispatches: int = 0
    tokens: dict = field(default_factory=zero_tokens)
    actual_cost: float = 0.0
    counterfactual_cost: float = 0.0
    na: bool = False
    retries: int = 0


@dataclass
class GroupState:
    """One orchestrator group's (Fable or Opus) aggregated report state.

    M9: `roles` is a plain dict keyed by `RoleKey` — deliberately NOT a
    `defaultdict` — so looking up an unknown/mistyped key raises `KeyError`
    instead of silently vivifying a fresh all-zero `RoleRow` (the pre-fix
    `defaultdict(new_role_row)` behavior). The one call site that
    legitimately needs get-or-create (`build_report`, first dispatch of a
    new role/model/effort combo) uses `roles.setdefault(key, RoleRow())`
    explicitly instead. `project_saved` is a plain dict for the same
    reason — it used to be `defaultdict(float)`, where a mistyped project
    name would silently read back `0.0` instead of raising."""

    sessions: int = 0
    orch_tokens: dict = field(default_factory=zero_tokens)
    orch_cost: float = 0.0
    orch_priced_sessions: int = 0
    orch_unpriced_sessions: int = 0
    roles: dict = field(default_factory=dict)
    project_saved: dict = field(default_factory=dict)


def new_group_state() -> GroupState:
    return GroupState()


def new_role_row() -> RoleRow:
    return RoleRow()


def new_excluded_state() -> dict:
    """Sessions whose orchestrator model is neither `claude-fable-5*` nor
    `claude-opus-*` (spec §3) are excluded from the Fable/Opus groups and
    their totals — but the exclusion itself must never be silent (fixed
    2026-07-27: it used to be, see the disclosure this state feeds). This is
    disclosure-only bookkeeping: no pricing, no third group, no role
    breakdown — see render_exclusion_disclosure."""
    return {
        "sessions": 0,
        "orch_tokens": zero_tokens(),
        "dispatched_tokens": zero_tokens(),
        "models": Counter(),
    }


def merge_excluded(dst: dict, src: dict) -> None:
    dst["sessions"] += src["sessions"]
    add_tokens(dst["orch_tokens"], src["orch_tokens"])
    add_tokens(dst["dispatched_tokens"], src["dispatched_tokens"])
    dst["models"].update(src["models"])


def build_report(
    root: str,
    project_filter: str | None,
    since: str | None,
    until: str | None,
    month: str | None,
    price_table: dict,
    today: str,
    since_dt: datetime | None = None,
    until_dt: datetime | None = None,
    price_as_of: str | None = None,
):
    """`today` is used ONLY as the fallback pricing date for a record whose
    own `timestamp` is missing/unparseable (see `iter_assistant_records`'
    `record_date`) — it is no longer the date every record is priced
    against (that was H1, 2026-07-28: pricing must track the RECORD's own
    date so a price table `next_tier.effective_from` boundary does not
    silently re-price already-recorded history once the boundary passes).
    `price_as_of`, when given (from `--price-as-of`), is an EXPLICIT
    override that replaces every record's own date outright — the default
    (`price_as_of=None`) is per-record pricing."""

    def _price_date(record_date: str | None) -> str:
        if price_as_of:
            return price_as_of
        return record_date if record_date else today

    warnings: list[str] = []
    groups = {"fable": new_group_state(), "opus": new_group_state()}
    excluded = new_excluded_state()

    # CHANGE 1 (2026-07-27): dedup winners computed ONCE, over the ENTIRE
    # scanned set for this run (every project/session/main+subagent file in
    # this filtered window) — see collect_dedup_winners docstring for why
    # this must be machine-wide rather than per-session. `warned_unpriced_keys`
    # (CHANGE 2) makes the unpriced-model warning below fire once per unique
    # dedup key rather than once per duplicate line, shared for the same
    # machine-wide reason a duplicate key can now appear in any file.
    # FIX 3 (2026-07-27): the same pass also returns the usage-monotonicity
    # and cache-tier-sum integrity warnings (see collect_dedup_winners) —
    # they go first in the warnings list because they qualify every token
    # figure below them.
    dedup_winners, integrity_warnings = collect_dedup_winners(
        root, project_filter, since, until, month, since_dt, until_dt
    )
    warnings.extend(integrity_warnings)
    warned_unpriced_keys: set = set()

    for project_name, project_dir in find_project_dirs(root, project_filter):
        for session_id, session_path in find_main_sessions(project_dir):
            main_records_raw = list(
                iter_assistant_records(session_path, since, until, month, warnings, since_dt, until_dt)
            )
            if not main_records_raw:
                continue
            main_records_full = dedup_against_winners(main_records_raw, session_path, dedup_winners)
            main_records = [(model, tok, record_date) for model, tok, _is_dup, record_date in main_records_full]

            model_counts = Counter(m for m, _, _ in main_records)
            orchestrator_model = model_counts.most_common(1)[0][0]
            group_name = classify_group(orchestrator_model)
            if group_name == "other":
                # Undisclosed-exclusion fix (2026-07-27): count the session,
                # its orchestrator-side tokens, and its dispatched-side
                # tokens for the report's exclusion disclosure — never the
                # role/pricing breakdown the Fable/Opus groups get (that
                # would make this a third group, which the spec forbids).
                # A scratch warnings list is used below so scanning these
                # sessions' subagent files does not change the warnings this
                # run would otherwise emit for the Fable/Opus groups.
                excluded["sessions"] += 1
                excluded["models"][orchestrator_model or "(no model)"] += 1
                orch_tokens_excl = zero_tokens()
                for _, tok, _record_date in main_records:
                    add_tokens(orch_tokens_excl, tok)
                add_tokens(excluded["orch_tokens"], orch_tokens_excl)
                _excl_scratch_warnings: list = []
                for agent_file, _meta_file in find_subagent_files(project_dir, session_id):
                    sub_records_raw = list(
                        iter_assistant_records(
                            agent_file, since, until, month, _excl_scratch_warnings, since_dt, until_dt
                        )
                    )
                    if not sub_records_raw:
                        continue
                    sub_records_full = dedup_against_winners(sub_records_raw, agent_file, dedup_winners)
                    for _model, tok, _is_dup, _record_date in sub_records_full:
                        add_tokens(excluded["dispatched_tokens"], tok)
                continue

            g = groups[group_name]
            g.sessions += 1

            # H1 (2026-07-28): orchestrator cost is summed PER RECORD, each
            # priced against its OWN date (never the session-wide execution
            # date) — a session whose records straddle a price-table tier
            # boundary (e.g. `next_tier.effective_from`) must not have its
            # whole aggregated token volume priced at whichever tier happens
            # to be active when the report is RUN.
            orch_tokens = zero_tokens()
            orch_cost_sum = 0.0
            for _, tok, record_date in main_records:
                add_tokens(orch_tokens, tok)
                record_price = resolve_price(orchestrator_model, price_table, _price_date(record_date))
                if record_price is not None:
                    orch_cost_sum += cost_for_tokens(tok, record_price)
            add_tokens(g.orch_tokens, orch_tokens)

            # `orch_price is None` classifies the orchestrator model as
            # UNPRICED (no matching price-table prefix at all) — this is
            # date-independent: `resolve_price` only ever returns `None`
            # when no key is a prefix of the model, never because of a
            # tier-date check, so any date works for this presence check.
            orch_price = resolve_price(orchestrator_model, price_table, today)
            if orch_price is None:
                warnings.append(
                    f"WARNING: unpriced orchestrator model '{orchestrator_model}'"
                    f" (session {session_id}, project {project_name}) — orchestrator cost N/A"
                )
                g.orch_unpriced_sessions += 1
            else:
                g.orch_cost += orch_cost_sum
                g.orch_priced_sessions += 1

            agent_tool_uses = extract_agent_tool_uses(session_path)

            # Retry-count heuristic (spec-adjacent — see RETRY_HEURISTIC_DISCLOSURE):
            # one (order, msg_index, role, row_key) entry per dispatch in THIS
            # session, filled in below as subagent files are processed, then
            # walked in orchestrator-issue order once the loop finishes.
            session_dispatch_seq: list = []

            for agent_file, meta_file in find_subagent_files(project_dir, session_id):
                meta = load_agent_meta(meta_file, warnings)
                # Rows are keyed by (agent_type, model, effort) — not
                # pre-merged into OTHER_ROLE_LABEL — so render_group can
                # either merge non-tlor types into one row (default) or list
                # them individually (--detail-others) from the same
                # aggregated data, and so a role dispatched under a per-call
                # model/effort override shows as its own row (spec §1).
                role = meta["agentType"]
                sub_records_raw = list(
                    iter_assistant_records(agent_file, since, until, month, warnings, since_dt, until_dt)
                )
                if not sub_records_raw:
                    continue
                # CHANGE 1 (2026-07-27): dedup against the machine-wide
                # winner map (same map the main transcript above was checked
                # against) — a duplicate key can now come from ANY session's
                # file, not just this one. Zeroing a duplicate's tokens never
                # removes the (model, tokens) entry itself, so dispatch
                # counting and dominant-model selection below (both based on
                # record presence/model, not on token values) are unaffected.
                sub_records_full = dedup_against_winners(sub_records_raw, agent_file, dedup_winners)
                sub_records = [(model, tok) for model, tok, _is_dup, _record_date in sub_records_full]

                tool_info = agent_tool_uses.get(meta["toolUseId"]) if meta["toolUseId"] else None
                effort_display = resolve_effort(meta["effort"], tool_info, role)

                # A dispatch's records are all one model in practice; if a
                # transcript has several (e.g. a mid-dispatch escalation),
                # split tokens/cost by each record's own model into separate
                # rows, but count the dispatch itself once, against the
                # model with the most records (mirrors the orchestrator's
                # own most-common-model classification above).
                model_counts = Counter(m for m, _ in sub_records)
                dominant_model = model_counts.most_common(1)[0][0]

                # H1 (2026-07-28): both the actual cost AND the counterfactual
                # (inline-on-orchestrator-model) cost are summed PER RECORD,
                # each priced against ITS OWN date — a dispatch whose records
                # straddle a price-table tier boundary must not be priced as
                # if every record happened on the date the report was run.
                per_model_tokens: dict = {}
                per_model_actual: dict = {}
                per_model_cf: dict = {}
                per_model_na: dict = {}
                for model, tok, is_dup, record_date in sub_records_full:
                    per_model_tokens.setdefault(model, zero_tokens())
                    add_tokens(per_model_tokens[model], tok)
                    price_date = _price_date(record_date)
                    price = resolve_price(model, price_table, price_date)
                    if price is None:
                        per_model_na[model] = True
                        # CHANGE 2 (2026-07-27): warn once per unique dedup
                        # key, not once per raw content-block/duplicate line
                        # — a duplicate occurrence (is_dup=True) never
                        # reaches this branch as its own warning; only the
                        # winning occurrence of a repeated key does.
                        if not is_dup:
                            warnings.append(
                                f"WARNING: unpriced model '{model}' in {os.path.basename(agent_file)}"
                                f" (role {role}, project {project_name}) — cost N/A for this row"
                            )
                        continue
                    per_model_actual[model] = per_model_actual.get(model, 0.0) + cost_for_tokens(tok, price)
                    cf_price = resolve_price(orchestrator_model, price_table, price_date)
                    if cf_price is not None:
                        per_model_cf[model] = per_model_cf.get(model, 0.0) + cost_for_tokens(tok, cf_price)

                row_na_common = orch_price is None
                for model, tok in per_model_tokens.items():
                    key = RoleKey(role, short_model_id(model), effort_display)
                    row = g.roles.setdefault(key, RoleRow())
                    if model == dominant_model:
                        row.dispatches += 1
                        # The dispatch is attributed to the dominant-model
                        # row for the retry-run walk below (one entry per
                        # dispatch, not per model split).
                        if tool_info is not None:
                            session_dispatch_seq.append(
                                (tool_info["order"], tool_info["msg_index"], role, key)
                            )
                    add_tokens(row.tokens, tok)
                    if row_na_common or per_model_na.get(model, False):
                        row.na = True
                    else:
                        actual = per_model_actual.get(model, 0.0)
                        row.actual_cost += actual
                        counterfactual = per_model_cf.get(model, 0.0)
                        row.counterfactual_cost += counterfactual
                        g.project_saved[project_name] = (
                            g.project_saved.get(project_name, 0.0) + (counterfactual - actual)
                        )

            # Retry-count heuristic: walk this session's dispatches in the
            # orchestrator's own issue order (main-session Agent tool_use
            # order — see extract_agent_tool_uses). A dispatch is counted as
            # a retry when the IMMEDIATELY PRECEDING dispatch (any model/
            # effort) was the same role AND came from a DIFFERENT assistant
            # message — same-message adjacency is a parallel fan-out
            # (decomposition.md §3: independent dispatches go in one
            # message), not a retry, so it is excluded. Dispatches whose
            # toolUseId could not be resolved to an order (tool_info is None)
            # are left out of this walk entirely — they cannot be placed in
            # sequence, so they neither count as retries nor break a run.
            session_dispatch_seq.sort(key=lambda e: e[0])
            prev_role = None
            prev_msg_index = None
            for _order, msg_index, role_, key_ in session_dispatch_seq:
                if prev_role == role_ and prev_msg_index != msg_index:
                    g.roles[key_].retries += 1
                prev_role = role_
                prev_msg_index = msg_index

    return groups, warnings, excluded


# --------------------------------------------------------------------------
# Codex delegation (kept separate from all Claude totals above)
# --------------------------------------------------------------------------

def _iter_jsonl(path: str):
    try:
        f = open(path, "r", encoding="utf-8")
    except OSError:
        return
    with f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                yield rec


def _walk_objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_objects(child)


def _codex_tokens(value: dict) -> dict:
    return {
        "input": value.get("input_tokens", 0) or 0,
        "cached": value.get("cached_input_tokens", 0) or 0,
        "cache_write": value.get("cache_write_input_tokens", 0) or 0,
        "output": value.get("output_tokens", 0) or 0,
        "reasoning": value.get("reasoning_output_tokens", 0) or 0,
        "total": value.get("total_tokens", 0) or 0,
    }


def _read_codex_session(path: str, warnings: list) -> dict | None:
    meta = {}
    models: list[str] = []
    maximum = {k: 0 for k in ("input", "cached", "cache_write", "output", "reasoning", "total")}
    used = []
    for rec in _iter_jsonl(path):
        if rec.get("type") == "session_meta" and isinstance(rec.get("payload"), dict):
            meta = rec["payload"]
        for obj in _walk_objects(rec):
            if obj.get("type") == "turn_context" and isinstance(obj.get("payload"), dict):
                model = obj["payload"].get("model")
                if isinstance(model, str):
                    models.append(model)
            # turn_context is normally a top-level record, while the usage
            # shape may occur in any future nested event shape.
            usage = obj.get("total_token_usage")
            if isinstance(usage, dict):
                tok = _codex_tokens(usage)
                for key in maximum:
                    maximum[key] = max(maximum[key], tok[key])
            if "used_percent" in obj:
                used.append(obj["used_percent"])
    if not meta:
        return None
    distinct = sorted(set(models))
    if len(distinct) > 1:
        warnings.append(
            "WARNING: Codex rollout " + os.path.basename(path)
            + " has multiple turn_context models: " + ", ".join(distinct)
        )
    return {"path": path, "name": os.path.basename(path), "timestamp": meta.get("timestamp"),
            "cwd": meta.get("cwd"), "originator": meta.get("originator"),
            "model": models[-1] if models else None, "tokens": maximum,
            "used_first": used[0] if used else None, "used_last": used[-1] if used else None}


def _codex_dispatch_data(root, project_filter, since, until, month, since_dt, until_dt, price_table, today, price_as_of, warnings, months=None):
    """Build filtered Claude dispatch windows and separate per-role costs.

    This pass deliberately applies the report window while it scans dispatches,
    so historical codex calls outside this report cannot create a window here.
    """
    roles = set(discover_tlor_roles())
    windows, costs = [], defaultdict(lambda: {"codex": [], "plain": []})
    active_months = months or [month]
    def in_window(ts):
        return any(_record_in_window(ts, since, until, m, since_dt, until_dt) for m in active_months)
    winners = {}
    for active_month in active_months:
        part, _ = collect_dedup_winners(root, project_filter, since, until, active_month, since_dt, until_dt)
        winners.update(part)
    for _project, project_dir in find_project_dirs(root, project_filter):
        for session_id, _main in find_main_sessions(project_dir):
            for agent_file, meta_file in find_subagent_files(project_dir, session_id):
                meta = load_agent_meta(meta_file, warnings)
                role = meta["agentType"]
                if role not in roles:
                    continue
                all_records = list(_iter_jsonl(agent_file))
                last_ts = last_cwd = None
                for rec in all_records:
                    if rec.get("timestamp"):
                        last_ts = rec.get("timestamp")
                    if rec.get("cwd"):
                        last_cwd = rec.get("cwd")
                raw = [(line, rec, ts, model, usage_blob) for line, rec, ts, model, usage_blob
                       in _iter_raw_assistant_records(agent_file) if in_window(ts)]
                if not raw:
                    continue
                raw_for_dedup = [(model, usage_to_tokens(usage_blob, warnings, agent_file), record_dedup_key(rec), line, ts[:10] if ts else None)
                                 for line, rec, ts, model, usage_blob in raw]
                full = dedup_against_winners(raw_for_dedup, agent_file, winners)
                actual = 0.0
                for model, tok, _dup, record_date in full:
                    price = resolve_price(model, price_table, price_as_of or record_date or today)
                    if price is not None:
                        actual += cost_for_tokens(tok, price)
                codex_calls = []
                for _line, rec, ts, _model, _usage in _iter_raw_assistant_records(agent_file):
                    if not in_window(ts):
                        continue
                    for block in (rec.get("message") or {}).get("content") or []:
                        inp = block.get("input") if isinstance(block, dict) else None
                        if (isinstance(block, dict) and block.get("type") == "tool_use"
                                and block.get("name") == "Bash" and isinstance(inp, dict)
                                and isinstance(inp.get("command"), str) and "codex exec" in inp["command"]):
                            codex_calls.append((ts, rec.get("cwd") or last_cwd))  # fallback is this transcript's final cwd.
                costs[role]["codex" if codex_calls else "plain"].append(actual)
                for start, cwd in codex_calls:
                    if start and last_ts and cwd:
                        windows.append({"role": role, "start": start, "end": last_ts, "cwd": cwd})
    return windows, costs


def _codex_price(model, tokens, card):
    models = card.get("models", {})
    key = max((k for k in models if model and model.lower().startswith(k.lower())), key=len, default=None)
    entry = models.get(key) if key else None
    rates = entry.get("credits_per_mtok") if entry else None
    if rates is None:
        return None, entry
    credits = ((tokens["input"] - tokens["cached"]) / 1_000_000 * rates["input"]
               + tokens["cached"] / 1_000_000 * rates["cached_input"]
               + tokens["output"] / 1_000_000 * rates["output"])
    return credits, entry


def render_codex_delegation(root, codex_home, project_filter, since, until, month, since_dt, until_dt, price_table, today, price_as_of, warnings, months=None):
    home = os.path.abspath(os.path.expanduser(codex_home))
    sessions_dir = os.path.join(home, "sessions")
    if not os.path.isdir(sessions_dir):
        return "## Codex delegation\n\nCodex home " + home + " has no sessions directory — Codex delegation reporting skipped.\n"
    card = load_codex_rate_card()
    windows, costs = _codex_dispatch_data(root, project_filter, since, until, month, since_dt, until_dt, price_table, today, price_as_of, warnings, months)
    def in_window(ts):
        return any(_record_in_window(ts, since, until, active_month, since_dt, until_dt) for active_month in (months or [month]))
    paths = []
    for base in (sessions_dir, os.path.join(home, "archived_sessions")):
        if os.path.isdir(base):
            for dirpath, _dirs, files in os.walk(base):
                paths.extend(os.path.join(dirpath, n) for n in files if n.startswith("rollout-") and n.endswith(".jsonl"))
    matched, ambiguous, unattributed = defaultdict(lambda: {"count": 0, "tokens": {k: 0 for k in ("input", "cached", "cache_write", "output", "reasoning", "total")}, "credits": 0.0, "na": False, "entry": None}), [], []
    observed = []
    warned_models = set()
    for path in sorted(paths):
        s = _read_codex_session(path, warnings)
        if not s or not in_window(s["timestamp"]):
            continue
        candidates = [w for w in windows if w["start"] <= s["timestamp"] <= w["end"] and (s["cwd"] == w["cwd"] or (isinstance(s["cwd"], str) and s["cwd"].startswith(w["cwd"] + "/")))]
        observed.append(s)
        if len(candidates) != 1:
            (ambiguous if len(candidates) > 1 else unattributed).append(s)
            continue
        key = (candidates[0]["role"], s["model"] or "(no model)")
        row = matched[key]; row["count"] += 1
        for k in row["tokens"]: row["tokens"][k] += s["tokens"][k]
        credits, entry = _codex_price(s["model"], s["tokens"], card)
        row["entry"] = entry
        if credits is None:
            row["na"] = True
            if s["model"] not in warned_models:
                warnings.append(f"WARNING: Codex model '{s['model']}' has unknown credits pricing — cost N/A")
                warned_models.add(s["model"])
        else: row["credits"] += credits
    def bucket(items): return len(items), sum(s["tokens"]["total"] for s in items)
    lines = ["## Codex delegation", "", "| tlor role | Codex model | Sessions | input | cached | cache_write | output | reasoning | Credits | USD (secondary) |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    ordered = sorted(matched.items(), key=lambda kv: (kv[1]["na"], -(kv[1]["credits"] if not kv[1]["na"] else 0), kv[0][0], kv[0][1]))
    for (role, model), row in ordered:
        c = "N/A" if row["na"] else f"{row['credits']:.2f}"
        usd = "—"
        if row["entry"] and row["entry"].get("usd_secondary") is not None and not row["na"]:
            usd = f"${row['credits'] * row['entry']['usd_secondary']:.2f} (secondary source)"
        t = row["tokens"]
        lines.append(f"| {role} | {model} | {row['count']} | {fmt_int(t['input'])} | {fmt_int(t['cached'])} | {fmt_int(t['cache_write'])} | {fmt_int(t['output'])} | {fmt_int(t['reasoning'])} | {c} | {usd} |")
    ac, at = bucket(ambiguous); uc, ut = bucket(unattributed)
    files = sorted(s["name"] for s in ambiguous)
    lines += ["", f"Ambiguous (multi-window match, not attributed): {ac} sessions, {fmt_int(at)} tokens" + (" (files: " + ", ".join(files) + ")" if files else ""), f"Unattributed (no matching tlor dispatch window): {uc} sessions, {fmt_int(ut)} tokens", "", "| tlor role | codex-assisted dispatches | baseline n | baseline median (API-equiv) | IQR | wrapper actual median | est. saving/dispatch | est. total saving |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for role in sorted(r for r, v in costs.items() if v["codex"]):
        base, assisted = sorted(costs[role]["plain"]), sorted(costs[role]["codex"])
        if len(base) < 3:
            lines.append(f"| {role} | {len(assisted)} | insufficient baseline (n={len(base)}) — no estimate | — | — | — | — | — |")
            continue
        def percentile(values, p):
            i = p / 100 * (len(values) - 1); lo = int(i); hi = min(lo + 1, len(values) - 1)
            return values[lo] + (values[hi] - values[lo]) * (i - lo)
        median, q1, q3, wrapper = percentile(base, 50), percentile(base, 25), percentile(base, 75), percentile(assisted, 50)
        lines.append(f"| {role} | {len(assisted)} | {len(base)} | {fmt_money(median)} | {fmt_money(q3-q1)} | {fmt_money(wrapper)} | {fmt_money(median-wrapper)} | {fmt_money(sum(median-x for x in assisted))} |")
    first = next((s["used_first"] for s in sorted(observed, key=lambda x: x["timestamp"] or "") if s["used_first"] is not None), None)
    last = next((s["used_last"] for s in sorted(observed, key=lambda x: x["timestamp"] or "", reverse=True) if s["used_last"] is not None), None)
    lines += ["", f"used_percent snapshot: {first} -> {last}" if first is not None else "used_percent snapshot: N/A (no rate_limits data observed)", "", "Disclaimers: Codex rollout schema is experimental (token_count records exist only since 2025-09; format still evolving).", "Codex tokens use a different tokenizer and are NEVER merged into any Claude total or headroom figure above.", "Baseline comparison is an ESTIMATE from historical same-role no-codex medians, not a measurement.", "Credits are transcribed from the official rate card; any USD figure is from a secondary source. Cache writes are not billed per the official statement.", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def fmt_int(n: int) -> str:
    return f"{n:,}"


def fmt_money(n: float | None) -> str:
    if n is None:
        return "N/A"
    return f"${n:,.2f}"


def fmt_pct(saved: float | None, counterfactual: float | None) -> str:
    if saved is None or counterfactual is None or counterfactual == 0:
        return "N/A"
    return f"{saved / counterfactual * 100:.1f}%"


def _accumulate_totals(rows) -> tuple[int, int, float, float, bool, bool]:
    """(dispatches, retries, actual, counterfactual, any_na, any_priced)
    summed across `rows` (an iterable of `RoleRow`s) — the single
    accumulator M8 collapses `group_totals` and `render_group`'s own
    inline totals loop into, so the two can no longer drift on what
    "total" means (the comment `group_totals` used to carry admitted the
    duplication directly)."""
    total_dispatches = 0
    total_retries = 0
    total_actual = 0.0
    total_counterfactual = 0.0
    any_na = False
    any_priced = False
    for row in rows:
        total_dispatches += row.dispatches
        total_retries += row.retries
        if row.na:
            any_na = True
        else:
            any_priced = True
            total_actual += row.actual_cost
            total_counterfactual += row.counterfactual_cost
    return total_dispatches, total_retries, total_actual, total_counterfactual, any_na, any_priced


def group_totals(g: GroupState):
    """Aggregate a group's per-role rows into (dispatches, actual, counterfactual, any_na).

    `actual`/`counterfactual` are None when no row in the group was priced
    (mirrors render_group's own "don't print $0.00 for unknown" rule).
    Used by the cross-month comparison table.
    """
    total_dispatches, _retries, total_actual, total_counterfactual, any_na, any_priced = _accumulate_totals(
        g.roles.values()
    )
    if any_priced:
        return total_dispatches, total_actual, total_counterfactual, any_na
    return total_dispatches, None, None, any_na


def render_month_comparison(months: list[str], month_groups: dict) -> str:
    """Cross-month comparison table: one column per month, Fable+Opus combined.

    Combining the two orchestrator groups here is a deliberate narrowing of
    scope from the per-month sections (which keep Fable/Opus separate per
    spec §1/§3) — this table answers a different question ("how did total
    spend/savings move month to month"), where summing already-computed
    dollar totals does not blend unit prices the way averaging a rate would.
    """
    lines = []
    lines.append("## Cross-month comparison")
    lines.append("")

    combined = {}
    for m in months:
        g = month_groups[m]
        fd, fa, fc, f_na = group_totals(g["fable"])
        od, oa, oc, o_na = group_totals(g["opus"])
        actual = None if (fa is None and oa is None) else (fa or 0.0) + (oa or 0.0)
        counterfactual = None if (fc is None and oc is None) else (fc or 0.0) + (oc or 0.0)
        saved = None if (actual is None or counterfactual is None) else counterfactual - actual
        combined[m] = {
            "sessions": g["fable"].sessions + g["opus"].sessions,
            "dispatches": fd + od,
            "actual": actual,
            "counterfactual": counterfactual,
            "saved": saved,
            "any_na": f_na or o_na,
        }

    header = "| Metric | " + " | ".join(months) + " |"
    sep = "|---|" + "---|" * len(months)
    lines.append(header)
    lines.append(sep)
    lines.append("| Sessions | " + " | ".join(str(combined[m]["sessions"]) for m in months) + " |")
    lines.append("| Dispatch count | " + " | ".join(str(combined[m]["dispatches"]) for m in months) + " |")
    lines.append(
        "| API-equiv cost (actual) | " + " | ".join(fmt_money(combined[m]["actual"]) for m in months) + " |"
    )
    lines.append(
        "| API-equiv cost (if inline) | "
        + " | ".join(fmt_money(combined[m]["counterfactual"]) for m in months)
        + " |"
    )
    lines.append(
        "| Quota headroom preserved | " + " | ".join(fmt_money(combined[m]["saved"]) for m in months) + " |"
    )
    lines.append(
        "| Headroom % | "
        + " | ".join(fmt_pct(combined[m]["saved"], combined[m]["counterfactual"]) for m in months)
        + " |"
    )
    lines.append("")
    if any(combined[m]["any_na"] for m in months):
        lines.append(
            "(Note: at least one month has an unpriced model in its per-month section above —"
            " this comparison's actual/counterfactual/saved figures for that month are partial.)"
        )
        lines.append("")
    return "\n".join(lines)


def dispatched_roles(*groups: GroupState) -> set:
    """Role names (key.role) that received at least one dispatch across any
    of the given groups (typically Fable + Opus, so a role dispatched under
    either orchestrator counts) — role governance treats a role as
    "dispatched" regardless of which orchestrator ran it."""
    result: set = set()
    for g in groups:
        for key, row in g.roles.items():
            if row.dispatches > 0:
                result.add(key.role)
    return result


def render_zero_dispatch_section(tlor_roles: list, dispatched: set) -> str:
    """Report section for role governance (spec-adjacent to per-role tables):
    which framework roles EXIST (per discover_tlor_roles/ordered_tlor_roles)
    but received ZERO dispatches in the reporting period. A role nobody
    dispatches is either redundant or being bypassed — this is the
    measurement loop for that."""
    lines = []
    lines.append("## Zero-dispatch roles")
    lines.append("")
    zero = [r for r in tlor_roles if r not in dispatched]
    if not zero:
        lines.append("(none — every framework role received at least one dispatch in this period.)")
    else:
        lines.append(
            "These framework roles exist (per the installed role manifest, falling back to the "
            "role-definition directory when no manifest is present) but received ZERO dispatches "
            "in this reporting period:"
        )
        lines.append("")
        for r in zero:
            lines.append(f"- {r}")
    lines.append("")
    return "\n".join(lines)


def _group_keys_by_role(roles: dict) -> dict:
    """Group the RoleKey-keyed rows dict by role name, preserving no
    particular order (callers sort/order separately)."""
    grouped: dict = defaultdict(list)
    for key in roles:
        grouped[key.role].append(key)
    return grouped


def _combo_sort_key(roles: dict):
    """Sort a role's (role, model, effort) combo rows: descending money
    saved, unpriced/N-A rows last, then by model/effort for determinism."""

    def key(k):
        row = roles[k]
        if row.na:
            return (1, k.model, k.effort)
        saved = row.counterfactual_cost - row.actual_cost
        return (0, -saved, k.model, k.effort)

    return key


def _role_aggregate_sort_key(roles: dict, keys: list) -> tuple:
    """(is_na_or_unpriced, -total_saved) for ordering non-tlor roles by their
    combined money saved across all of that role's (model, effort) rows."""
    total_actual = 0.0
    total_cf = 0.0
    any_na = False
    any_priced = False
    for k in keys:
        row = roles[k]
        if row.na:
            any_na = True
        else:
            any_priced = True
            total_actual += row.actual_cost
            total_cf += row.counterfactual_cost
    if not any_priced:
        return (1, 0.0)
    return (0, -(total_cf - total_actual))


def _other_role_sort_key(roles: dict, grouped: dict):
    """Sort non-tlor role names for --detail-others: descending money saved
    (aggregated across each role's model/effort combos), unpriced last,
    alphabetical among themselves."""

    def key(name):
        na_flag, neg_saved = _role_aggregate_sort_key(roles, grouped[name])
        return (na_flag, neg_saved, name)

    return key


def render_group(label: str, g: GroupState, detail_others: bool = False) -> str:
    # `detail_others` is accepted but unused — non-tlor agentTypes are always
    # detailed now (see the comment below); kept only so callers passing
    # the deprecated `--detail-others` flag keep working unchanged.
    del detail_others
    lines = []
    lines.append(f"## {label} group per-role table")
    lines.append("")
    # Label-ambiguity annotation (2026-07-27): "<X> group" is a SESSION-GROUP
    # name — every session whose ORCHESTRATOR model was X — and its totals sum
    # rows that ran on OTHER models entirely (see the Model column). It is not
    # a per-model total for X, and sat close enough to one to invite that
    # misreading, so the distinction is now stated in the output rather than
    # left to the reader.
    lines.append(
        f"Grouping: every session whose ORCHESTRATOR (main-session) model was {label} —"
        " a SESSION-GROUP total, not a per-model total. The rows below are the models the"
        " DISPATCHED work actually ran on (see the Model column), so this table's totals"
        f" are mostly NOT {label} tokens; the group's own {label} volume is the"
        " orchestrator-cumulative figure in the group summary underneath."
    )
    lines.append("")
    lines.append(
        "| Role | Model | Effort | Dispatches | Retries (heuristic) | input | output | cache(r/w) | "
        "API-equiv cost (actual model) | API-equiv cost (if run inline) | quota headroom preserved | headroom % |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")

    grouped = _group_keys_by_role(g.roles)
    tlor_roles = ordered_tlor_roles()
    ordered_roles = [r for r in tlor_roles if r in grouped]
    other_role_names = [r for r in grouped if r not in tlor_roles]

    # render_rows: list of (role_label, model_cell, effort_cell, RoleRow)
    render_rows = []
    for role in ordered_roles:
        for key in sorted(grouped[role], key=_combo_sort_key(g.roles)):
            render_rows.append((role, key.model, key.effort, g.roles[key]))

    # Non-framework agent types (built-in Explore, general-purpose, other
    # plugin agents, ...) now get their own row per (agentType, model,
    # effort) by DEFAULT — a merged "(other subagents)" row couldn't answer
    # "how much dispatch is leaking to generic subagents on an expensive
    # model, and is that leak shrinking as roles get adopted." `detail_others`
    # is accepted but is now a no-op (this was already its old behavior) —
    # kept for CLI back-compat; see SKILL.md's deprecation note.
    for role in sorted(other_role_names, key=_other_role_sort_key(g.roles, grouped)):
        for key in sorted(grouped[role], key=_combo_sort_key(g.roles)):
            render_rows.append((role, key.model, key.effort, g.roles[key]))

    for role, model_cell, effort_cell, row in render_rows:
        # (upgrade)/(downgrade) markers are per-row only — never on the
        # OTHER_ROLE_LABEL fallback row (missing/unreadable meta.json; no
        # frontmatter file exists for that literal label to pin against) or
        # the Total row.
        if role != OTHER_ROLE_LABEL:
            model_cell = model_cell + model_marker(role, model_cell)
        cache_cell = f"{fmt_int(row.tokens['cache_read'])}/{fmt_int(row.tokens['cache_write'])}"
        if row.na:
            lines.append(
                f"| {role} | {model_cell} | {effort_cell} | {row.dispatches} | "
                f"{row.retries} | {fmt_int(row.tokens['input'])} | {fmt_int(row.tokens['output'])} | "
                f"{cache_cell} | N/A | N/A | N/A | N/A |"
            )
        else:
            saved = row.counterfactual_cost - row.actual_cost
            lines.append(
                f"| {role} | {model_cell} | {effort_cell} | {row.dispatches} | "
                f"{row.retries} | {fmt_int(row.tokens['input'])} | {fmt_int(row.tokens['output'])} | "
                f"{cache_cell} | {fmt_money(row.actual_cost)} | "
                f"{fmt_money(row.counterfactual_cost)} | {fmt_money(saved)} | "
                f"{fmt_pct(saved, row.counterfactual_cost)} |"
            )

    # M8: the same accumulator `group_totals` uses — this used to be a
    # second, hand-duplicated arithmetic loop right here.
    total_dispatches, total_retries, total_actual, total_counterfactual, any_na, any_priced = _accumulate_totals(
        row for _role, _model_cell, _effort_cell, row in render_rows
    )

    partial_note = "(partial — excludes N/A rows above)" if any_na else ""
    if any_priced:
        total_saved = total_counterfactual - total_actual
        total_actual_cell = fmt_money(total_actual)
        total_counterfactual_cell = fmt_money(total_counterfactual)
        total_saved_cell = fmt_money(total_saved)
        total_pct_cell = fmt_pct(total_saved, total_counterfactual)
    else:
        # No row in this group had a fully-priced model — do not print "$0.00",
        # which would misleadingly read as "zero savings" rather than "unknown".
        total_saved = None
        total_actual_cell = total_counterfactual_cell = total_saved_cell = total_pct_cell = "N/A"
    lines.append(
        f"| **Total quota headroom preserved** {partial_note} | — | — | **{total_dispatches}** | "
        f"**{total_retries}** | — | — | — | "
        f"**{total_actual_cell}** | **{total_counterfactual_cell}** | "
        f"**{total_saved_cell}** | **{total_pct_cell}** |"
    )
    lines.append("")

    orch_cost_display = fmt_money(g.orch_cost)
    if g.orch_unpriced_sessions:
        orch_cost_display += (
            f" (partial — {g.orch_priced_sessions}/{g.sessions} sessions priced,"
            f" {g.orch_unpriced_sessions} orchestrator model(s) unpriced, see warnings)"
        )
    lines.append(
        f"Group summary: {label} group: {g.sessions} sessions, orchestrator "
        f"cumulative {fmt_int(g.orch_tokens['input'])} input / "
        f"{fmt_int(g.orch_tokens['output'])} output tokens, API-equiv cost {orch_cost_display}; "
        f"this group's Total quota headroom preserved = {fmt_money(total_saved)}"
        f"{' (partial)' if any_na else ''}"
    )
    lines.append("")

    if g.project_saved:
        parts = "; ".join(
            f"{proj}: {fmt_money(saved)}" for proj, saved in sorted(g.project_saved.items())
        )
        lines.append(f"Per-project subtotal (priced rows only, quota headroom preserved): {parts}")
    else:
        lines.append("Per-project subtotal: (no priced dispatch records)")
    lines.append("")
    return "\n".join(lines)


def merge_groups_for_headroom(*groups_list: GroupState) -> GroupState:
    """Combine several group states (e.g. one per --month) into a single
    GroupState with just enough populated for render_context_offload_ratio/
    render_quota_headroom_figures: orch_tokens/orch_cost/orch_priced_sessions
    summed, and all roles' RoleRows flattened into one dict keyed by a
    throwaway index (group_totals only iterates .values(), so key identity
    doesn't matter here — `roles` stays a plain dict, just with int keys
    instead of RoleKeys for this one throwaway aggregate)."""
    merged = GroupState()
    idx = 0
    for g in groups_list:
        add_tokens(merged.orch_tokens, g.orch_tokens)
        merged.orch_cost += g.orch_cost
        merged.orch_priced_sessions += g.orch_priced_sessions
        for row in g.roles.values():
            merged.roles[idx] = row
            idx += 1
    return merged


# The four DISTINCT token buckets for a "total volume" sum — deliberately
# excludes cache_write_5m/cache_write_1h, which are a tier SPLIT of
# cache_write (see usage_to_tokens), not additional tokens; summing all six
# TOKEN_FIELDS would double-count every cache-write token.
_TOTAL_VOLUME_FIELDS = ("input", "output", "cache_write", "cache_read")


def _token_volume(tokens: dict) -> int:
    return sum(tokens[k] for k in _TOTAL_VOLUME_FIELDS)


def render_context_offload_ratio(label: str, g: GroupState) -> str:
    """Figure 1 (headline): token-only, no pricing. FIX 2 (2026-07-27) — this
    was previously named/framed as a "relative multiple" implying "would
    have consumed N× more tokens run inline," which is wrong: dispatching to
    a cheaper model changes WHICH model processes a token, not how many
    tokens the work needs, so a value below 1.0 is normal and does not mean
    dispatching wasted tokens or a fraction of the work's cost. What this
    ratio actually measures — dispatched (subagent) token volume ÷ the
    orchestrator's own token volume for the same group — is how much work
    was moved OUT of the orchestrator's own (quota-relevant) context versus
    kept inside it: the context-dilution the framework's delegation
    rationale rests on avoiding. It is never rendered as a cost/savings
    figure; see the explicit disclaimer in the returned text."""
    dispatch_tokens_total = sum(_token_volume(row.tokens) for row in g.roles.values())
    orch_tokens_total = _token_volume(g.orch_tokens)
    if orch_tokens_total <= 0:
        return f"- {label}: N/A (no orchestrator token volume recorded for this group in the period)"
    ratio = dispatch_tokens_total / orch_tokens_total
    return (
        f"- {label}: context-offload ratio **{ratio:.1f}** — dispatched work carried"
        f" {fmt_int(dispatch_tokens_total)} tokens versus {fmt_int(orch_tokens_total)} tokens that"
        f" stayed in the orchestrator's own transcript. This is NOT a cost or token savings figure —"
        f" dispatching to a cheaper model changes which model processes the tokens, not how many"
        f" tokens the work needs, so a ratio below 1.0 is normal. It measures how much work was moved"
        f" out of the orchestrator's own (quota-relevant) context rather than kept inside it."
    )


def render_quota_headroom_figures(
    groups: dict,
    subscription_usd: float | None,
    calibration_ceiling_usd: float | None,
    period_months: float | None = None,
    period_cycles: float | None = None,
) -> str:
    """Figures 1, 3, 4 (figure 2 is the renamed per-role table above — not
    repeated here). Figure 4's entire subsection is OMITTED, not just its
    value, when no calibration point exists (per spec: no placeholder, no
    default, no estimate).

    H2 (2026-07-28): `subscription_usd` is a MONTHLY fee and
    `calibration_ceiling_usd` is a PER-CYCLE (weekly) ceiling — dividing a
    whole multi-month/multi-cycle period's total cost by either UNSCALED
    inflated figure 3 by ~Nx and figure 4 by ~Nx for an N-month/N-cycle
    report. `period_months`/`period_cycles` (see `period_length`/
    `period_length_multi`) scale the fee/ceiling up to match the reported
    period before dividing. When the reported window is NOT fully bounded
    (neither value known — e.g. no date filter at all), figures 3/4 are
    SKIPPED rather than computed against an undefined period length."""
    lines = []
    lines.append("## Quota-headroom figures")
    lines.append("")
    lines.append(f"> {API_EQUIVALENT_DISCLOSURE}")
    lines.append("")
    lines.append("### 1. Context-offload ratio (headline — token-based, no pricing)")
    lines.append("")
    lines.append(render_context_offload_ratio("Fable group", groups["fable"]))
    lines.append(render_context_offload_ratio("Opus group", groups["opus"]))
    lines.append("")

    # total_actual_all: full period cost at API list price (orchestrator's own
    # coordination cost + dispatched work's actual-model cost) — used for
    # figure 3's "would this period have cost more than the subscription".
    # total_saved_roles: dispatch-only headroom (counterfactual - actual for
    # DISPATCHED rows only; the orchestrator's own cost has no counterfactual
    # — it is what it is either way) — used for figure 4's headroom delta, so
    # the two totals are never mixed across incompatible bases.
    total_actual_all = 0.0
    total_roles_actual = 0.0
    total_roles_cf = 0.0
    any_priced = False
    for gname in ("fable", "opus"):
        g = groups[gname]
        if g.orch_priced_sessions:
            total_actual_all += g.orch_cost
            any_priced = True
        _, ta, tc, _ = group_totals(g)
        if ta is not None:
            total_actual_all += ta
            total_roles_actual += ta
            total_roles_cf += tc
            any_priced = True

    lines.append("### 3. Subscription worth-it")
    lines.append("")
    if subscription_usd is None:
        lines.append(
            "(skipped — no `subscription_usd` in `~/.claude/erebor-ledger.json` or"
            " `--subscription-usd`; see SKILL.md's first-run flow.)"
        )
    elif not any_priced or subscription_usd == 0:
        lines.append("(skipped — no priced API-equivalent cost in this period, or subscription fee is 0.)")
    elif period_months is None:
        lines.append(
            "(skipped — figure 3 divides this period's total cost by the MONTHLY subscription fee,"
            " which requires a bounded report period to normalize by; this run's window is"
            " open-ended (no --month/--cycle/--since+--until). Re-run with a bounded date filter"
            " to see this figure.)"
        )
    else:
        normalized_subscription = subscription_usd * period_months
        ratio = total_actual_all / normalized_subscription
        verdict = (
            "the plan is cheaper than paying list price for this work."
            if ratio >= 1
            else "this period alone did not yet exceed the subscription fee at list price."
        )
        lines.append(
            f"This period's work would have cost **{fmt_money(total_actual_all)}** at API list price"
            f" (orchestrator + dispatched, actual models used). Subscription fee:"
            f" {fmt_money(subscription_usd)}/month, normalized for {period_months:.2f} month(s) in this"
            f" reported period = {fmt_money(normalized_subscription)}."
            f" Ratio: **{ratio:.1f}x** the (period-normalized) subscription fee — {verdict}"
        )
    lines.append("")

    if calibration_ceiling_usd is not None and calibration_ceiling_usd > 0:
        lines.append("### 4. Empirical quota share (user-calibrated)")
        lines.append("")
        lines.append(
            "> User-calibrated ceiling, not an official Anthropic quota figure (unpublished);"
            " because the real allowance is weighted per model rather than raw tokens, this is a"
            " proxy, not an exact quota reading."
        )
        lines.append("")
        if not any_priced:
            lines.append("(no priced API-equivalent cost in this period to compare against the ceiling.)")
        elif period_cycles is None:
            lines.append(
                "(skipped — figure 4 divides this period's total cost by the PER-CYCLE (weekly)"
                " calibration ceiling, which requires a bounded report period to normalize by;"
                " this run's window is open-ended (no --month/--cycle/--since+--until). Re-run with"
                " a bounded date filter to see this figure.)"
            )
        else:
            normalized_ceiling = calibration_ceiling_usd * period_cycles
            share_pct = total_actual_all / normalized_ceiling * 100
            headroom_saved = total_roles_cf - total_roles_actual
            headroom_pct = headroom_saved / normalized_ceiling * 100
            lines.append(
                f"This period consumed an estimated **{share_pct:.1f}%** of your calibrated ceiling"
                f" ({fmt_money(total_actual_all)} / {fmt_money(calibration_ceiling_usd)}/cycle, normalized"
                f" for {period_cycles:.2f} cycle(s) in this reported period ="
                f" {fmt_money(normalized_ceiling)}); dispatching converts to roughly"
                f" **+{headroom_pct:.1f}% additional headroom** versus running the same work inline."
            )
        lines.append("")

    return "\n".join(lines)


def render_exclusion_disclosure(excluded: dict) -> str:
    """Every run states how many sessions/tokens were excluded because their
    orchestrator model fell outside the Fable/Opus groups (spec §3), and
    names the excluded models — a silent absence is what caused this to go
    unnoticed before 2026-07-27. Zero exclusions still get a line, not an
    omission."""
    sessions = excluded["sessions"]
    if sessions == 0:
        return (
            "Orchestrator-model exclusion: 0 sessions excluded this run — every"
            " session's orchestrator model matched the Fable or Opus group."
        )
    orch_vol = _token_volume(excluded["orch_tokens"])
    disp_vol = _token_volume(excluded["dispatched_tokens"])
    total_vol = orch_vol + disp_vol
    model_parts = ", ".join(
        f"{short_model_id(m)} ({fmt_int(n)} session{'s' if n != 1 else ''})"
        for m, n in sorted(excluded["models"].items(), key=lambda kv: (-kv[1], kv[0]))
    )
    return (
        f"Orchestrator-model exclusion: {fmt_int(sessions)} session"
        f"{'s' if sessions != 1 else ''} ({model_parts}) excluded from every figure"
        " above — their orchestrator model falls outside the Fable/Opus groups this"
        f" report groups by ({fmt_int(orch_vol)} orchestrator tokens plus"
        f" {fmt_int(disp_vol)} dispatched tokens, {fmt_int(total_vol)} total, excluded)."
    )


def filter_description(since: str | None, until: str | None, month: str | None) -> str | None:
    if month:
        return f"--month {month} (per the transcript's own `timestamp` field)"
    parts = []
    if since:
        parts.append(f"--since {since}")
    if until:
        parts.append(f"--until {until}")
    if not parts:
        return None
    return " ".join(parts) + " (per the transcript's own `timestamp` field)"


def _report_header(excluded: dict, filter_desc: str | None) -> list[str]:
    """The report title plus every `>` disclosure line through the
    exclusion disclosure, and an optional `> Filter:` line — this exact
    block used to be written out twice (M7): once for the single/combined-
    window path (`render_report`) and once for the multi-`--month` path
    (`main`'s cross-month section). Both now build it here."""
    lines = []
    lines.append("# erebor-ledger usage report")
    lines.append("")
    lines.append(f"> {COUNTERFACTUAL_DISCLOSURE}")
    lines.append(f"> {CACHE_TIER_DISCLOSURE}")
    lines.append(f"> {CACHE_TIER_SUM_DISCLOSURE}")
    lines.append(f"> {MONOTONICITY_DISCLOSURE}")
    lines.append(f"> {EFFORT_SOURCE_DISCLOSURE}")
    lines.append(f"> {RETRY_HEURISTIC_DISCLOSURE}")
    lines.append(f"> {API_EQUIVALENT_DISCLOSURE}")
    lines.append(f"> {render_exclusion_disclosure(excluded)}")
    if filter_desc:
        lines.append(f"> Filter: {filter_desc}")
    lines.append("")
    return lines


def render_report(
    groups: dict,
    warnings: list,
    filter_desc: str | None,
    detail_others: bool = False,
    subscription_usd: float | None = None,
    calibration_ceiling_usd: float | None = None,
    excluded: dict | None = None,
    period_months: float | None = None,
    period_cycles: float | None = None,
    codex_section: str | None = None,
) -> str:
    lines = _report_header(
        excluded if excluded is not None else new_excluded_state(), filter_desc
    )
    lines.append(render_group("Fable", groups["fable"], detail_others))
    lines.append(render_group("Opus", groups["opus"], detail_others))
    lines.append(
        render_zero_dispatch_section(
            ordered_tlor_roles(), dispatched_roles(groups["fable"], groups["opus"])
        )
    )
    if codex_section is not None:
        lines.append(codex_section)
    lines.append(
        render_quota_headroom_figures(
            groups, subscription_usd, calibration_ceiling_usd, period_months, period_cycles
        )
    )

    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "erebor-ledger: report token/cost savings from tlor-orchestration dispatch, "
            "grouped by orchestrator model (Fable 5 vs Opus)."
        )
    )
    parser.add_argument(
        "--project",
        help="only include project directories whose name contains this substring",
    )
    parser.add_argument(
        "--since",
        help="YYYY-MM-DD; only include records at or after this date (transcript timestamp)",
    )
    parser.add_argument(
        "--until",
        help="YYYY-MM-DD; only include records at or before this date (transcript timestamp)",
    )
    parser.add_argument(
        "--month",
        action="append",
        help=(
            "YYYY-MM; only include records in this month (transcript timestamp). Repeatable —"
            " passing it more than once produces a per-month section for each plus a"
            " cross-month comparison table, all in one run. Mutually exclusive with"
            " --since/--until."
        ),
    )
    parser.add_argument(
        "--root",
        help=(
            "advanced/testing only: override the transcripts root directory "
            f"(default: {DEFAULT_ROOT})"
        ),
    )
    parser.add_argument(
        "--codex-home",
        help="advanced/testing only: override Codex home (default: ~/.codex)",
    )
    parser.add_argument(
        "--detail-others",
        action="store_true",
        help=(
            "DEPRECATED, now a no-op: non-tlor-role agentTypes (built-in Explore, "
            "general-purpose, plugin agents, ...) are always broken out into one row "
            "per distinct agentType/model/effort by default (this used to require the "
            "flag). Kept for CLI back-compat only."
        ),
    )
    parser.add_argument(
        "--cycle",
        type=int,
        default=None,
        help=(
            "filter to the weekly quota-reset cycle N cycles back from now: 0 = the cycle"
            " currently in progress, 1 = the most recently COMPLETED cycle, 2 = the one"
            " before that, etc. Reset boundary defaults to Thursday 05:00 UTC (13:00"
            " UTC+8) — an observed value, not published by Anthropic; see"
            " --cycle-reset-weekday/--cycle-reset-hour-utc. Mutually exclusive with"
            " --since/--until/--month."
        ),
    )
    parser.add_argument(
        "--cycle-reference",
        help=(
            "advanced/testing only: ISO-8601 UTC timestamp to use as 'now' for --cycle, "
            "instead of the real current time"
        ),
    )
    parser.add_argument(
        "--cycle-reset-weekday",
        type=int,
        default=CYCLE_RESET_WEEKDAY,
        help="advanced/testing only: override the reset weekday (Monday=0 ... Sunday=6); default Thursday",
    )
    parser.add_argument(
        "--cycle-reset-hour-utc",
        type=int,
        default=CYCLE_RESET_HOUR_UTC,
        help="advanced/testing only: override the reset hour in UTC; default 5 (05:00 UTC = 13:00 UTC+8)",
    )
    parser.add_argument(
        "--subscription-usd",
        type=float,
        default=None,
        help=(
            "monthly subscription fee in USD; overrides the config file's subscription_usd"
            " and enables figure 3 (SUBSCRIPTION WORTH-IT). Example: --subscription-usd 100"
            " — 100 is an example value here, not a default."
        ),
    )
    parser.add_argument(
        "--calibration-ceiling-usd",
        type=float,
        default=None,
        help=(
            "a user-recorded API-equivalent cost ceiling for a cycle that is known to have"
            " exhausted quota; overrides the config file's calibration_ceiling_usd and enables"
            " figure 4 (EMPIRICAL QUOTA SHARE)."
        ),
    )
    parser.add_argument(
        "--config",
        default=None,
        help=f"advanced/testing only: override the config file path (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--price-as-of",
        default=None,
        help=(
            "EXPLICIT override (YYYY-MM-DD): price every record as if 'today' were this date,"
            " instead of the record's own date. Default behavior (no flag) prices each record"
            " against its OWN date (per H1: never the report's execution date), so a price-table"
            " tier change (e.g. next_tier.effective_from) does not silently re-price already-"
            "recorded history — use this flag only to deliberately ask 'what would this period"
            " have cost under the pricing in effect on a specific date'."
        ),
    )
    args = parser.parse_args(argv)

    if args.month and (args.since or args.until):
        print("error: --month cannot be combined with --since/--until", file=sys.stderr)
        return 1
    if args.cycle is not None and (args.month or args.since or args.until):
        print("error: --cycle cannot be combined with --month/--since/--until", file=sys.stderr)
        return 1

    root = os.path.expanduser(args.root) if args.root else DEFAULT_ROOT
    codex_home = os.path.expanduser(args.codex_home) if args.codex_home else os.path.expanduser("~/.codex")
    price_table = load_price_table()
    today = datetime.now().strftime("%Y-%m-%d")

    config_path = os.path.expanduser(args.config) if args.config else DEFAULT_CONFIG_PATH
    config = load_ledger_config(config_path)
    subscription_usd = args.subscription_usd if args.subscription_usd is not None else config.get("subscription_usd")
    calibration_ceiling_usd = (
        args.calibration_ceiling_usd
        if args.calibration_ceiling_usd is not None
        else config.get("calibration_ceiling_usd")
    )

    if args.cycle is not None:
        if args.cycle_reference:
            now_utc = parse_iso_utc(args.cycle_reference)
            if now_utc is None:
                print("error: --cycle-reference is not a valid ISO-8601 timestamp", file=sys.stderr)
                return 1
        else:
            now_utc = datetime.now(timezone.utc)
        since_dt, until_dt = cycle_window(
            args.cycle, now_utc, args.cycle_reset_weekday, args.cycle_reset_hour_utc
        )
        # H2: a --cycle run always covers exactly one weekly quota cycle.
        period_months, period_cycles = period_length(since_dt, until_dt)
        groups, warnings, excluded = build_report(
            root, args.project, None, None, None, price_table, today,
            since_dt=since_dt, until_dt=until_dt, price_as_of=args.price_as_of,
        )
        filter_desc = (
            f"--cycle {args.cycle} -> {since_dt.isoformat()} .. {until_dt.isoformat()} (UTC;"
            " quota-cycle window, reset boundary Thursday 05:00 UTC / 13:00 UTC+8, observed not published)"
        )
        codex_section = render_codex_delegation(root, codex_home, args.project, None, None, None, since_dt, until_dt, price_table, today, args.price_as_of, warnings)
        print(
            render_report(
                groups,
                warnings,
                filter_desc,
                args.detail_others,
                subscription_usd,
                calibration_ceiling_usd,
                excluded,
                period_months,
                period_cycles,
                codex_section,
            )
        )
        return 0

    if not args.month:
        # H2: figures 3/4 need a FULLY bounded window to normalize by — an
        # open-ended query (no filter, or only one of --since/--until) has
        # no defined period length, so period_months/period_cycles stay
        # None and render_quota_headroom_figures skips those figures.
        period_months = period_cycles = None
        if args.since and args.until:
            since_bound = parse_iso_utc(args.since + "T00:00:00Z")
            until_bound = parse_iso_utc(args.until + "T00:00:00Z") + timedelta(days=1)
            period_months, period_cycles = period_length(since_bound, until_bound)
        groups, warnings, excluded = build_report(
            root, args.project, args.since, args.until, None, price_table, today,
            price_as_of=args.price_as_of,
        )
        codex_section = render_codex_delegation(root, codex_home, args.project, args.since, args.until, None, None, None, price_table, today, args.price_as_of, warnings)
        print(
            render_report(
                groups,
                warnings,
                filter_description(args.since, args.until, None),
                args.detail_others,
                subscription_usd,
                calibration_ceiling_usd,
                excluded,
                period_months,
                period_cycles,
                codex_section,
            )
        )
        return 0

    months = args.month
    if len(months) == 1:
        # H2: exactly one reported calendar month.
        since_bound, until_bound = month_bounds(months[0])
        period_months, period_cycles = period_length(since_bound, until_bound)
        groups, warnings, excluded = build_report(
            root, args.project, None, None, months[0], price_table, today, price_as_of=args.price_as_of
        )
        codex_section = render_codex_delegation(root, codex_home, args.project, None, None, months[0], None, None, price_table, today, args.price_as_of, warnings)
        print(
            render_report(
                groups,
                warnings,
                filter_description(None, None, months[0]),
                args.detail_others,
                subscription_usd,
                calibration_ceiling_usd,
                excluded,
                period_months,
                period_cycles,
                codex_section,
            )
        )
        return 0

    # Multiple --month values: one run, one pass per month over the same
    # transcripts, per-month sections plus a combined comparison table.
    month_groups: dict[str, dict] = {}
    all_warnings: list[str] = []
    all_excluded = new_excluded_state()
    for m in months:
        g, w, e = build_report(root, args.project, None, None, m, price_table, today, price_as_of=args.price_as_of)
        month_groups[m] = g
        all_warnings.extend(w)
        merge_excluded(all_excluded, e)
    # H2: sum each selected month's own day-span (months may be non-
    # contiguous — never span min..max, which would also count unselected
    # months in between).
    period_months, period_cycles = period_length_multi([month_bounds(m) for m in months])

    sections = _report_header(
        all_excluded,
        f"--month {', '.join(months)} (per the transcript's own `timestamp` field;"
        " multi-month comparison, single run)",
    )
    for m in months:
        sections.append(f"# Month: {m}")
        sections.append("")
        sections.append(render_group(f"Fable ({m})", month_groups[m]["fable"], args.detail_others))
        sections.append(render_group(f"Opus ({m})", month_groups[m]["opus"], args.detail_others))
    sections.append(render_month_comparison(months, month_groups))

    combined_dispatched: set = set()
    for m in months:
        combined_dispatched |= dispatched_roles(month_groups[m]["fable"], month_groups[m]["opus"])
    sections.append(render_zero_dispatch_section(ordered_tlor_roles(), combined_dispatched))
    # Codex sessions are computed once for this multi-month run, rather than
    # being split into the Fable/Opus or per-month Claude presentation groups.
    codex_warnings: list[str] = []
    codex_section = render_codex_delegation(root, codex_home, args.project, None, None, None, None, None, price_table, today, args.price_as_of, codex_warnings, months)
    sections.append(codex_section)
    all_warnings.extend(codex_warnings)

    merged_fable = merge_groups_for_headroom(*[month_groups[m]["fable"] for m in months])
    merged_opus = merge_groups_for_headroom(*[month_groups[m]["opus"] for m in months])
    sections.append(
        render_quota_headroom_figures(
            {"fable": merged_fable, "opus": merged_opus},
            subscription_usd,
            calibration_ceiling_usd,
            period_months,
            period_cycles,
        )
    )

    if all_warnings:
        sections.append("## Warnings")
        sections.append("")
        for w in all_warnings:
            sections.append(f"- {w}")
        sections.append("")

    print("\n".join(sections))
    return 0


if __name__ == "__main__":
    sys.exit(main())
