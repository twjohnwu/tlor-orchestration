---
id: search.binary_search
name: Binary Search
category: [search]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: searches/binary_search.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: searches/simple_binary_search.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: search/binary_search.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/search/BinarySearch.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
  - repo: imeplusplus/icpc-notebook
    path: data-structures/bit_binary_search.cpp
    commit: d6db5cb0e077ed674fd16828f3c1e452a222d103
    license: MIT
---

# Binary Search

## Problem Signals
- sorted array, find a value or its position
- first or last occurrence, insertion point, lower bound, upper bound
- membership test in ordered data in logarithmic time
- smallest or largest x for which a monotone yes/no condition holds
- invert a monotone function (for example a square root) to a tolerance
- count of an item in sorted data

## Use When
- The data supports random access and is ordered, so the middle element tells you which half cannot contain the target.
- You need a position, an insertion point, or the run of equal values, not only a yes/no answer.
- The search space is an integer or real range and a monotone predicate splits it into "no ... no, yes ... yes" (search on the answer).
- Many queries hit the same data, so a one-time sort is paid back.

## Do Not Use When
- The data is unsorted and you query it once: use a linear scan (sorting first costs more than it saves).
- You need repeated membership or key lookup with no order requirement: use a hash set or map.
- You need a pair or triple that satisfies a sum condition: use `array.two_pointers`.
- You need the current smallest or largest element under inserts and removals: use `heap.priority_queue`.
- The data is a linked list or other structure without O(1) indexing: use a linear scan or a balanced tree.
- The predicate is not monotone over the range: split the range into monotone pieces or scan.

## Preconditions
- The sequence is sorted in non-decreasing order under the same comparison used for the search (checkable in one O(n) scan).
- Items form a total order under `<`; only `<` (sortedness check and search) and `==` (final hit test) are used.
- Indexing is O(1).
- For search on the answer: the predicate is monotone over the whole range and the range bounds are valid (`lo < hi` for the real-valued form).

## Core Invariant
Keep a half-open window `[lo, hi)` such that every index below `lo` holds a value smaller than the target and every index at or above `hi` holds a value not smaller than the target. Each step probes the midpoint and moves exactly one bound past it, so the window shrinks and the invariant survives. When `lo == hi` the window is empty and that index is the leftmost position where the target could sit.

## Algorithm
1. Check preconditions (sorted order).
2. Set `lo = 0` and `hi = len(items)`.
3. While `lo < hi`, take `mid = lo + (hi - lo) // 2`.
4. If `items[mid] < target`, set `lo = mid + 1`; otherwise set `hi = mid`.
5. The loop ends with `lo` as the first index whose value is not smaller than the target.
6. Report `lo` if it is in range and `items[lo] == target`; otherwise report not found.

## Canonical Implementation
```python
from __future__ import annotations

from typing import Any, Sequence


def binary_search(items: Sequence[Any], target: Any) -> int:
    """Return the leftmost index of target in items, or -1 if it is absent.

    items must be sorted in non-decreasing order.
    """
    for k in range(1, len(items)):
        if items[k] < items[k - 1]:
            raise ValueError("items must be sorted in non-decreasing order")

    # Invariant: items[:lo] < target and items[hi:] >= target.
    lo, hi = 0, len(items)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if items[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    if lo < len(items) and items[lo] == target:
        return lo
    return -1
```

## Complexity
Time: O(log n) for the search — the window halves each step (O(n) for the optional sortedness check, which production code usually drops). Space: O(1) — three indices; the recursive form uses O(log n) stack.

## Variants
- Lower bound (bisect left) — the loop above; returns the first index with value >= target, the insertion point before equal values.
- Upper bound (bisect right) — compare with `<=` instead of `<`; returns the first index with value > target.
- Range of duplicates — lower bound and upper bound together give `[lower, upper)`; the count is the difference.
- Early-exit form — closed window `[lo, hi]`, return on the first `==`; fewer probes on average but returns an arbitrary equal index (the C++ source does this).
- Recursive form — same logic with the window passed as arguments; slicing the list at each call (as the simple Python source does) turns each level into O(n) copying.
- Search on a real-valued answer — bisect a monotone function over `[lo, hi]` until the window is below a tolerance; the cost is O(log((hi - lo) / eps)) (the Java source).
- Bit-descent search — walk powers of two from high to low over a prefix-sum structure to find the first prefix reaching a value in O(log n) (the competitive-programming notebook source, a secondary source).

## Common Failure Modes
- Test that an empty sequence returns -1 and does not index. A closed-window form with an unsigned `size() - 1` upper bound wraps around on empty input (the C++ source).
- Test that a one-element sequence finds a present target and rejects a smaller and a larger one.
- Test that with duplicates the leftmost index is returned (`[1, 2, 2, 2, 4]`, target 2 gives 1), not an arbitrary middle one.
- Test targets smaller than the first and larger than the last element; both must return -1 without out-of-range access.
- Test that unsorted input raises instead of returning a plausible wrong answer.
- Test that a hit at the first and at the last index is found (off-by-one at both ends).
- Test a large sequence with an index sum near the integer limit in a fixed-width language; `lo + (hi - lo) // 2` avoids overflow where `(lo + hi) // 2` can wrap.
- Test that a real-valued search stops (an `eps` too small for the floating-point spacing can loop forever) and that `lo >= hi` is rejected.

## Production Considerations
- Prefer the standard library (`bisect` in Python, `std::lower_bound` in C++, `Arrays.binarySearch` in Java) over hand-written code; the Java source itself points to the library for discrete data.
- Do not run the sortedness check on every call in a hot path; it makes the search O(n). Validate once at the boundary.
- The comparison must be the one that defined the sort order; searching case-folded data in a case-sensitive order breaks the invariant.
- Floating-point keys: exact `==` can miss; compare the lower-bound result within a tolerance, or search on the answer instead.
- Slicing in recursive versions copies data; pass indices instead.
- Mutation during the search invalidates the invariant; take a snapshot or lock.

## Related Algorithms
- array.two_pointers — pair or triple conditions on sorted data, O(n) with no per-element search.
- heap.priority_queue — repeated min or max extraction under changing data, where a sorted array would need O(n) inserts.

## Representative Problems
- Given a sorted list of numbers and a target, return the position of its first occurrence or report that it is absent.
- Given a sorted list, return the position where a new value should be inserted to keep the list sorted.
- Given a sorted list with repeats, count how many times a value occurs.
- Find the smallest capacity or speed for which a monotone feasibility check succeeds.
- Compute a square root or other inverse of an increasing function to a given precision.

## Sources
- TheAlgorithms/Python searches/binary_search.py — the half-open lower-bound loop, the leftmost-duplicate rule, the sortedness check that raises, and the upper-bound and run-of-duplicates variants; also the empty and single-element cases from its doctests.
- TheAlgorithms/Python searches/simple_binary_search.py — recursive membership test returning a bool; it slices the list at each call, which is the O(n)-copy pitfall noted in Variants.
- TheAlgorithms/C-Plus-Plus search/binary_search.cpp — closed-window early-exit form (any matching index, O(1) best case); its unsigned `size() - 1` bound is the empty-input failure mode.
- williamfiset/Algorithms src/main/java/com/williamfiset/algorithms/search/BinarySearch.java — real-valued search on the answer of a monotone function with an epsilon stop, and the `hi > lo` guard; also the advice to use the library for discrete data.
- imeplusplus/icpc-notebook data-structures/bit_binary_search.cpp — bit-descent lower bound over a Fenwick-style prefix structure (secondary; used for the Variants bullet only).
- Skipped as false matches: binary search tree files (Python, two C++, Java), a matrix search that mixes a row scan with 1-D searches, and a longest-increasing-subsequence routine. The five cited sources agree on the core halving loop and on O(log n); they differ only in which equal index they return (leftmost, any, or a bool), which is recorded in Variants, so there is no conflict.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | searches/binary_search.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | searches/simple_binary_search.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | search/binary_search.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/search/BinarySearch.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
| imeplusplus/icpc-notebook | data-structures/bit_binary_search.cpp | d6db5cb0e077ed674fd16828f3c1e452a222d103 | MIT |
