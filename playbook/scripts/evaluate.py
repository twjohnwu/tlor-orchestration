#!/usr/bin/env python3
"""Evaluate the keyword lookup agents use over agent_doc/algorithms/INDEX.md.

Stdlib only. The retriever tokenizes the query and scores each INDEX row by
token overlap with id + name + signals (avoid_when tokens count negative).
Hyphenated negation compounds stay one token (non-negative -> nonnegative);
other hyphens split. Rejection is separate from scoring: an avoid_when phrase
matches the query when ALL its tokens appear in the query (phrases of <=3
tokens) or at least 2 of them do (longer phrases); any matching phrase
rejects. Reports Recall@k, MRR, Top-1, Wrong Algorithm Rate and Constraint Violation
Rate over playbook/eval/{retrieval,selection,rejection}.jsonl. It reports;
it never gates (exit 0 regardless of scores). With few entries the numbers
are smoke checks, not quality claims.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INDEX = REPO_ROOT / "agent_doc" / "algorithms" / "INDEX.md"
DEFAULT_EVAL_DIR = REPO_ROOT / "playbook" / "eval"

STOPWORDS = frozenset("""
a an and are as at be by for from given has have how i in into is it its of
on or that the their then there these this to we what when where which with
you your can do does find get return returns want need using use over each
all any
""".split())

SPLIT_RE = re.compile(r"[^a-z0-9]+")
NEGATION_COMPOUND_RE = re.compile(r"\bnon-(?=[a-z0-9])")
REJECT_ALL_TOKENS_MAX = 3  # phrases up to this length need every token
REJECT_MIN_TOKENS = 2      # longer phrases need this many tokens
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")


def singularize(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def tokenize(text: str) -> list:
    out = []
    for raw in SPLIT_RE.split(NEGATION_COMPOUND_RE.sub("non", text.lower())):
        if len(raw) < 2 or raw in STOPWORDS:
            continue
        out.append(singularize(raw))
    return out


def parse_index(path: Path) -> list:
    """Return rows [{id, name, signals, avoid_when(list of phrases)}] in file order."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip().replace("\\|", "|") for c in CELL_SPLIT_RE.split(line.strip())[1:-1]]
        if len(cells) < 5 or cells[0] in ("id", "---") or set(cells[0]) <= set("-: "):
            continue
        rows.append({
            "id": cells[0],
            "name": cells[1],
            "signals": cells[2],
            "avoid_when": [p.strip() for p in cells[3].split(";") if p.strip()],
        })
    return rows


def prepare(row: dict) -> dict:
    pos = set(tokenize("%s %s %s" % (row["id"], row["name"], row["signals"])))
    neg = set()
    for phrase in row["avoid_when"]:
        neg.update(tokenize(phrase))
    row["pos"] = pos
    row["neg"] = neg - pos
    return row


def score_row(query_tokens: set, row: dict):
    hits = sorted(query_tokens & row["pos"])
    misses = sorted(query_tokens & row["neg"])
    return len(hits) - len(misses), hits, misses


def retrieve(query: str, rows: list, k: int, restrict=None) -> list:
    """Top-k [(id, score, reason)] with score > 0, best first (ties by id)."""
    q = set(tokenize(query))
    scored = []
    for row in rows:
        if restrict is not None and row["id"] not in restrict:
            continue
        score, hits, misses = score_row(q, row)
        if restrict is None and score <= 0:
            continue
        reason = "matched: " + (", ".join(hits) if hits else "-")
        if misses:
            reason += "; avoid: " + ", ".join(misses)
        scored.append((row["id"], score, reason))
    scored.sort(key=lambda t: (-t[1], t[0]))
    return scored[:k]


def rejects(query: str, row: dict) -> bool:
    q = set(tokenize(query))
    for phrase in row["avoid_when"]:
        tokens = set(tokenize(phrase))
        if not tokens:
            continue
        need = len(tokens) if len(tokens) <= REJECT_ALL_TOKENS_MAX else REJECT_MIN_TOKENS
        if len(q & tokens) >= need:
            return True
    return False


def load_jsonl(path: Path) -> list:
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def ratio(num: int, den: int):
    return None if den == 0 else num / den


def evaluate(rows: list, eval_dir: Path, k: int) -> dict:
    by_id = {r["id"]: r for r in rows}
    misses = {"retrieval": [], "selection": [], "rejection": []}

    retrieval = load_jsonl(eval_dir / "retrieval.jsonl")
    hit_k = top1 = 0
    rr_sum = 0.0
    for case in retrieval:
        ranked = [r[0] for r in retrieve(case["query"], rows, k)]
        if case["expected"] in ranked:
            hit_k += 1
            rank = ranked.index(case["expected"]) + 1
            rr_sum += 1.0 / rank
            if rank == 1:
                top1 += 1
        if not ranked or ranked[0] != case["expected"]:
            misses["retrieval"].append("%s -> got %s, expected %s" % (
                case["query"], ranked[0] if ranked else "(none)", case["expected"]))

    selection = load_jsonl(eval_dir / "selection.jsonl")
    sel_ok = 0
    for case in selection:
        got = retrieve(case["query"], rows, 1, restrict=set(case["candidates"]))
        got_id = got[0][0] if got else "(none)"
        if got_id == case["expected"]:
            sel_ok += 1
        else:
            misses["selection"].append("%s -> got %s, expected %s" % (
                case["query"], got_id, case["expected"]))

    rejection = load_jsonl(eval_dir / "rejection.jsonl")
    reject_cases = violations = 0
    for case in rejection:
        row = by_id.get(case["algorithm"])
        got = "reject" if row is not None and rejects(case["query"], row) else "accept"
        if case["expected"] == "reject":
            reject_cases += 1
            if got == "accept":
                violations += 1
        if got != case["expected"]:
            misses["rejection"].append("%s [%s] -> got %s, expected %s" % (
                case["query"], case["algorithm"], got, case["expected"]))

    sel_top1 = ratio(sel_ok, len(selection))
    return {
        "k": k,
        "n": {"retrieval": len(retrieval), "selection": len(selection),
              "rejection": len(rejection), "rejection_reject_cases": reject_cases},
        "metrics": {
            "recall@%d" % k: ratio(hit_k, len(retrieval)),
            "mrr": None if not retrieval else rr_sum / len(retrieval),
            "top1": ratio(top1, len(retrieval)),
            "constraint_violation_rate": ratio(violations, reject_cases),
            "wrong_algorithm_rate": None if sel_top1 is None else 1 - sel_top1,
        },
        "misses": misses,
    }


def fmt(value) -> str:
    return "n/a" if value is None else "%.3f" % value


def render(result: dict) -> str:
    m, n = result["metrics"], result["n"]
    k = result["k"]
    table = [
        ("Recall@%d" % k, m["recall@%d" % k], n["retrieval"]),
        ("MRR", m["mrr"], n["retrieval"]),
        ("Top-1", m["top1"], n["retrieval"]),
        ("Constraint Violation Rate", m["constraint_violation_rate"], n["rejection_reject_cases"]),
        ("Wrong Algorithm Rate", m["wrong_algorithm_rate"], n["selection"]),
    ]
    lines = ["| metric | value | n |", "|---|---|---|"]
    lines += ["| %s | %s | %d |" % (name, fmt(v), cnt) for name, v, cnt in table]
    lines.append("Rejection: an avoid_when phrase matches when all its tokens are in the query "
                 "(<=3 tokens) or >=2 of them (longer phrases).")
    lines.append("")
    for name in ("retrieval", "selection", "rejection"):
        items = result["misses"][name]
        lines.append("Misses: %s (%d)" % (name, len(items)))
        lines += ["  - " + i for i in items]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--eval-dir", type=Path, default=DEFAULT_EVAL_DIR)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args()

    if not args.index.is_file():
        print("evaluate: index not found: %s (run build_index.py first)" % args.index,
              file=sys.stderr)
        return 1
    rows = [prepare(r) for r in parse_index(args.index)]
    result = evaluate(rows, args.eval_dir, args.k)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
