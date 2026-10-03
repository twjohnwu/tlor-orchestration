---
id: array.prefix_sum
name: Prefix Sum
category: [array]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: data_structures/arrays/prefix_sum.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: range_queries/prefix_sum_array.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
---

# Prefix Sum

## Problem Signals
- many range-sum queries over a fixed array
- sum of a contiguous subarray, inclusive bounds
- cumulative total up to index i
- static data, no updates between queries
- does any subarray sum to a target value

## Use When
- The array does not change between queries and you answer many sum queries over index ranges.
- One O(n) preprocessing pass is acceptable in exchange for O(1) per query.
- The combining operation has an inverse (sum, xor, count), so a range value is the difference of two prefixes.
- You need "is there a contiguous block with sum T": keep prefixes in a set and test `prefix - T`.

## Do Not Use When
- Elements are updated between queries: use a Fenwick tree or segment tree (point update plus range query in O(log n)).
- The operation has no inverse (min, max, gcd): use a sparse table or segment tree.
- You need only one sum over one range: a plain loop is O(n) with no extra memory.
- The window has fixed or monotone-moving bounds and you need the best window, not arbitrary sums: use `array.sliding_window`.

## Preconditions
- Elements are integers (not `bool`), so sums are exact.
- The array is not modified after the prefix array is built.
- Every query is `(start, end)` with `0 <= start <= end < len(array)`; bounds are inclusive.
- A query against an empty array is invalid.

## Core Invariant
`prefix[i]` equals the sum of the first `i` elements (`prefix[0] == 0`), so the sum of elements `start..end` inclusive is `prefix[end + 1] - prefix[start]`. The leading zero removes the special case for ranges that begin at index 0.

## Algorithm
1. Allocate `prefix` of length `n + 1` with `prefix[0] = 0`.
2. For `i` from 0 to `n - 1`: `prefix[i + 1] = prefix[i] + array[i]`.
3. For each query `(start, end)`, reject it unless `0 <= start <= end < n`.
4. Answer with `prefix[end + 1] - prefix[start]`.

## Canonical Implementation
```python
from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple


def _check_int(value: object, what: str) -> None:
    # bool is an int subclass; refuse it so True/False never pass as numbers
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%s must be an int, got %r" % (what, value))


def range_sums(values: Sequence[int], queries: Iterable[Tuple[int, int]]) -> List[int]:
    """Sum of values[start..end] (inclusive, 0-based) for each (start, end)."""
    prefix = [0]  # prefix[i] == sum(values[:i])
    for v in values:
        _check_int(v, "element")
        prefix.append(prefix[-1] + v)

    n = len(values)
    answers = []
    for query in queries:
        try:
            start, end = query
        except (TypeError, ValueError):
            raise ValueError("query must be a (start, end) pair, got %r" % (query,))
        _check_int(start, "start")
        _check_int(end, "end")
        if not 0 <= start <= end < n:
            raise ValueError("invalid range [%d, %d] for length %d" % (start, end, n))
        answers.append(prefix[end + 1] - prefix[start])
    return answers
```

## Complexity
Time: O(n + q) — one pass to build, then O(1) per query for q queries. Space: O(n) — the prefix array holds n + 1 totals.

## Variants
- 2-D prefix sum — `P[i][j]` is the sum of the rectangle from the origin to `(i-1, j-1)`; a rectangle query is `P[r2+1][c2+1] - P[r1][c2+1] - P[r2+1][c1] + P[r1][c1]` (inclusion-exclusion), built in O(rows * cols).
- Subarray-equals-target check — store prefixes seen so far in a set seeded with 0; a hit on `prefix - target` means a block sums to target (the Python source does this in O(n)).
- Difference array — the inverse idea: apply many range additions in O(1) each, then one prefix pass recovers the final values.
- 1-based with sentinel — the C++ source keeps a dummy slot at index 0 and queries `PSA[end] - PSA[beg - 1]`; same idea, shifted indexing.
- Other invertible operations — prefix xor or prefix counts work identically.

## Common Failure Modes
- Test a range starting at index 0: the answer must equal the prefix total, not index out of range at `start - 1`.
- Test a single-element range `(i, i)`.
- Test `end == len - 1` accepted and `end == len` rejected.
- Test `start > end` and negative `start` are rejected rather than silently wrapping (Python negative indexing would hide the bug).
- Test the empty array: any query is rejected.
- Test mixing 0-based and 1-based conventions: the C++ source builds with its first element dropped and queries 1-based, so copying its query form onto a 0-based array is off by one. The sources differ in convention, not in the algorithm.
- Test negative elements: the range formula still holds. Prefix sums answer range-total questions for any values; they do not need (and do not give) a monotone predicate, so use `array.sliding_window` when the question is a best window under a monotone condition.

## Production Considerations
- Python ints do not overflow; in fixed-width languages use a 64-bit accumulator, since prefixes can exceed element range.
- The prefix array is immutable-by-contract: any update invalidates every later entry (O(n) rebuild), which is why updates need a Fenwick tree.
- Memory is one extra array; for huge streams where only a few queries arrive, answering offline in one pass avoids storing it.
- Validate bounds explicitly; negative indices in Python and out-of-range reads in C++ otherwise give silently wrong answers.

## Related Algorithms
- array.sliding_window — switch when you want the best contiguous window under a constraint, not arbitrary range sums.
- hashing.hash_map — pair with prefixes for the subarray-equals-target check.

## Representative Problems
- Given a fixed list of numbers and many (left, right) queries, report the sum of each range.
- Decide whether any contiguous block of a list sums to a given target.
- Given a grid, report the sum of many axis-aligned rectangles.
- Count contiguous blocks whose sum equals a target (prefix counts in a hash map).

## Sources
- TheAlgorithms/Python data_structures/arrays/prefix_sum.py — cumulative array build, inclusive 0-based range query with explicit empty and bounds rejection, set-based target-sum check.
- TheAlgorithms/C-Plus-Plus range_queries/prefix_sum_array.cpp — O(N) build / O(1) query claim, no-update limitation, the 1-based sentinel convention (a convention difference, not a conflict in the core algorithm).

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | data_structures/arrays/prefix_sum.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | range_queries/prefix_sum_array.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
