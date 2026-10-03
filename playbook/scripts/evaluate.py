#!/usr/bin/env python3
"""Evaluate the keyword lookup agents use over agent_doc/algorithms/INDEX.md.

Stdlib only. The retriever tokenizes the query and scores each INDEX row by
IDF-weighted token overlap with id + name + signals (avoid_when tokens count
negative with the same weight), plus +1.0 per adjacent query bigram that is
also a bigram of one of the row's signal phrases. idf = log((N+1)/(df+1)) + 1,
N = INDEX rows, df = rows whose id+name+signals contain the token, so a token
present in every row weighs ~1 (the "+1" floor keeps it from vanishing exactly
when N is tiny) and a rare token weighs much more. The weighted sum is divided
by sqrt(row token count) so rows with long signal lists do not win merely by
having more tokens to match; the bigram bonus is added after normalization
because it is already a specific, row-independent signal.
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
import math
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
PHRASE_BONUS = 1.0         # per matched signal-phrase bigram
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
    bigrams = set()
    for phrase in row["signals"].split(";"):
        toks = tokenize(phrase)
        bigrams.update(zip(toks, toks[1:]))
    row["pos"] = pos
    row["bigrams"] = bigrams
    row["neg"] = neg - pos
    return row


def idf_table(rows: list) -> dict:
    """token -> idf over the rows' positive token sets (id+name+signals)."""
    n = len(rows)
    df = {}
    for row in rows:
        for tok in row["pos"]:
            df[tok] = df.get(tok, 0) + 1
    return {tok: math.log((n + 1) / (d + 1)) + 1 for tok, d in df.items()}


def score_row(query_tokens: list, row: dict, idf: dict, default_idf: float):
    """Return (score, hits, misses). Tokens unseen in any row get default_idf (max)."""
    q = set(query_tokens)
    hits = sorted(q & row["pos"])
    misses = sorted(q & row["neg"])
    weight = lambda t: idf.get(t, default_idf)
    raw = sum(weight(t) for t in hits) - sum(weight(t) for t in misses)
    score = raw / math.sqrt(max(len(row["pos"]), 1))
    score += PHRASE_BONUS * len(row["bigrams"] & set(zip(query_tokens, query_tokens[1:])))
    return score, hits, misses


def retrieve(query: str, rows: list, k: int, restrict=None) -> list:
    """Top-k [(id, score, reason)] with score > 0, best first (ties by id)."""
    q = tokenize(query)
    idf = idf_table(rows)
    default_idf = math.log(len(rows) + 1) + 1 if rows else 1.0  # df=0
    scored = []
    for row in rows:
        if restrict is not None and row["id"] not in restrict:
            continue
        score, hits, misses = score_row(q, row, idf, default_idf)
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


def retrieval_block(cases: list, rows: list, k: int) -> dict:
    """Retrieval counters + miss list for one case set (used for in-sample and held-out)."""
    hit_k = top1 = 0
    rr_sum = 0.0
    misses = []
    for case in cases:
        ranked = [r[0] for r in retrieve(case["query"], rows, k)]
        if case["expected"] in ranked:
            hit_k += 1
            rank = ranked.index(case["expected"]) + 1
            rr_sum += 1.0 / rank
            if rank == 1:
                top1 += 1
        if not ranked or ranked[0] != case["expected"]:
            misses.append("%s -> got %s, expected %s" % (
                case["query"], ranked[0] if ranked else "(none)", case["expected"]))
    return {"hit_k": hit_k, "top1": top1, "rr_sum": rr_sum, "misses": misses}


def heldout_result(cases: list, rows: list, k: int) -> dict:
    ret = retrieval_block(cases, rows, k)
    n = len(cases)
    return {
        "n": n,
        "metrics": {
            "recall@%d" % k: ratio(ret["hit_k"], n),
            "mrr": None if not n else ret["rr_sum"] / n,
            "top1": ratio(ret["top1"], n),
        },
        "misses": ret["misses"],
    }


def evaluate(rows: list, eval_dir: Path, k: int, heldout=None) -> dict:
    by_id = {r["id"]: r for r in rows}
    misses = {"retrieval": [], "selection": [], "rejection": []}

    retrieval = load_jsonl(eval_dir / "retrieval.jsonl")
    ret = retrieval_block(retrieval, rows, k)
    hit_k, top1, rr_sum = ret["hit_k"], ret["top1"], ret["rr_sum"]
    misses["retrieval"] = ret["misses"]

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
    result = {
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
    if heldout is not None:
        result["heldout"] = heldout_result(load_jsonl(heldout), rows, k)
    return result


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
    held = result.get("heldout")
    if held is not None:
        hm = held["metrics"]
        lines += ["", "Held-out (blind) retrieval",
                  "| metric | value | n |", "|---|---|---|"]
        lines += ["| %s | %s | %d |" % (name, fmt(hm[key]), held["n"])
                  for name, key in (("Recall@%d" % k, "recall@%d" % k), ("MRR", "mrr"), ("Top-1", "top1"))]
        lines.append("")
        lines.append("Misses: held-out retrieval (%d)" % len(held["misses"]))
        lines += ["  - " + i for i in held["misses"]]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--eval-dir", type=Path, default=DEFAULT_EVAL_DIR)
    parser.add_argument("--heldout", type=Path, default=None,
                        help="blind retrieval set, reported separately "
                             "(default: <eval-dir>/heldout.jsonl if it exists)")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args()

    if not args.index.is_file():
        print("evaluate: index not found: %s (run build_index.py first)" % args.index,
              file=sys.stderr)
        return 1
    rows = [prepare(r) for r in parse_index(args.index)]
    heldout = args.heldout
    if heldout is None and (args.eval_dir / "heldout.jsonl").is_file():
        heldout = args.eval_dir / "heldout.jsonl"
    result = evaluate(rows, args.eval_dir, args.k, heldout)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
