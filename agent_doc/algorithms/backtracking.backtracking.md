---
id: backtracking.backtracking
name: Backtracking
category: [backtracking]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: backtracking/n_queens.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: backtracking/sudoku.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: backtracking/combination_sum.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: backtracking/all_combinations.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: backtracking/n_queens.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: backtracking/subset_sum.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
---

# Backtracking

## Problem Signals
- enumerate all subsets, permutations or combinations
- place items so that no two conflict (queens, digits)
- find every combination that reaches a target sum
- fill a partial grid under row, column and box rules
- count or list solutions, not just one optimum
- constraint can be checked on a partial assignment

## Use When
- The answer is a sequence of choices and a partially built choice list can be tested for validity at every step.
- You need all solutions, or the first solution, of a constraint problem with no closed form.
- Invalid prefixes can be rejected early, so whole subtrees are cut without being visited.
- The input is small enough that an exponential worst case is acceptable (roughly n up to 10-20, depending on pruning).

## Do Not Use When
- Only the best value or a count is needed and subproblems overlap: use `dp.one_dimensional` (memoise instead of enumerating).
- The search is over a graph with explicit edges and you need reachability or shortest paths: use `graph.traversal.dfs` or BFS.
- A greedy or sorted-scan rule is provably optimal: use that rule, no search needed.
- Pruning is impossible (every prefix is valid) and only a fixed-size family is wanted: a library generator such as `itertools` is simpler.

## Preconditions
- Every size or count argument is an `int` (not `bool`) and non-negative.
- The candidate set is finite and known up front.
- A validity test exists that can be applied to a partial solution, not only a complete one.
- The caller accepts exponential worst-case time and recursion depth equal to the solution length.

## Core Invariant
At every call the partial solution built so far satisfies all constraints. A choice is appended only after it passes the validity test, and is removed again after the recursive call returns, so the shared state at the top of each loop iteration equals the state when the call started. Every complete solution is reached exactly once because each level fixes one position and tries candidates in a fixed order.

## Algorithm
1. If the partial solution is complete, record a copy of it and return.
2. For each candidate for the next position, in a fixed order:
   1. Skip it if adding it would violate a constraint (prune), or if it repeats an already-tried equal value at this position (duplicate guard).
   2. Add it to the partial solution and update the bookkeeping.
   3. Recurse.
   4. Undo the addition (choose, explore, un-choose).
3. When the loop ends, return to the caller, which continues with its next candidate.

## Canonical Implementation
```python
from __future__ import annotations

from collections import OrderedDict
from typing import Hashable, List, Optional, Sequence


def unique_permutations(items: Sequence[Hashable], size: Optional[int] = None) -> List[List[Hashable]]:
    """All distinct arrangements of `size` elements drawn from the multiset `items`.

    Equal values are interchangeable, so each distinct arrangement appears once.
    Values that compare equal and hash alike (1, True, 1.0) count as one value;
    the first object seen is the one kept in the output.
    Arrangements come out in order of first appearance of the values in `items`.
    `size` defaults to len(items).
    """
    n = len(items)
    if size is None:
        size = n
    if isinstance(size, bool) or not isinstance(size, int):
        raise ValueError("size must be an int, got %r" % (size,))
    if size < 0:
        raise ValueError("size must not be negative, got %d" % size)
    if size > n:
        raise ValueError("size %d exceeds number of items %d" % (size, n))

    remaining = OrderedDict()  # value -> copies still unused
    for x in items:
        remaining[x] = remaining.get(x, 0) + 1
    keys = list(remaining)  # distinct values in first-appearance order, built once

    result = []  # type: List[List[Hashable]]
    path = []  # type: List[Hashable]

    def extend() -> None:
        if len(path) == size:
            result.append(list(path))
            return
        # Looping over distinct values (not positions) is the duplicate guard.
        for value in keys:
            if remaining[value] == 0:
                continue  # prune: no copy left, partial solution stays valid
            remaining[value] -= 1
            path.append(value)
            extend()
            path.pop()
            remaining[value] += 1

    extend()
    return result
```

## Complexity
Time: O(P * size) where P is the number of distinct arrangements (up to n!/(n-size)! when all values differ) — each output is built and copied once, and pruning keeps dead branches from adding more. Space: O(size + distinct values) beyond the output — the path, the counts and one shared key list (no per-frame copy); recursion depth is size.

## Variants
- All subsets — decide include or exclude per element; 2^n leaves, or iterate candidates from an increasing start index.
- Combinations of k out of n — pass a start index so each set is built in increasing order and no set repeats (Python all_combinations; time O(C(n,k))).
- Combination sum with reuse — recurse with the same start index so an element can repeat, and prune when the remaining target drops below the candidate (Python combination_sum; it states O(n!) average and assumes non-negative distinct candidates, see failure modes).
- N-queens — one queen per row, try each column, prune on column and both diagonals (Python and C++ n_queens); using sets or boolean arrays for columns and diagonals makes the safety test O(1) instead of a scan.
- Sudoku — pick the next empty cell, try digits 1-9 that are safe in row, column and box, undo on failure; returns on the first solution (Python sudoku).
- Subset-sum counting — the C++ subset_sum enumerates all 2^n bitmasks and sums each (O(2^n * n)) with no pruning; it is brute force, so add a prefix-sum bound if you want true backtracking.
- First-solution search — return a boolean from the recursive call and stop the loops as soon as it is true.

## Common Failure Modes
- Test that the shared path is copied when a solution is recorded; appending the live list yields a result full of identical, emptied lists.
- Test that every addition is undone on every exit path, including after a successful recursive call when collecting all solutions.
- Test duplicates in the input: with items [1, 1, 2] the answer must have 3 distinct arrangements, not 6.
- Test size 0: exactly one solution, the empty arrangement (not zero solutions).
- Test negative and non-int sizes, and `True`, are rejected with ValueError.
- Test that results do not leak between calls; the Python n_queens source appends to a module-level list, so a second call keeps the first call's boards.
- Test negative candidates in combination sum: with a "target >= candidate" prune and negative or zero values the recursion may never terminate; the Python source rejects negatives but does not reject zero.
- Test that the validity check covers the whole constraint (all three: column and both diagonals for queens), or invalid solutions slip through.

## Production Considerations
- Recursion depth equals solution length; Python's default limit (about 1000) is hit for long sequences, so convert to an explicit stack if depth can be large.
- Output size is the real cost: the number of solutions can be factorial or exponential, so prefer a generator (yield) when callers may stop early.
- Order candidates to fail fast (most constrained cell first for sudoku); this changes running time, not correctness.
- Do not mutate caller input; the Python sudoku source edits its grid in place, so copy first if the original is needed.
- Memoising works only when subproblems repeat; if they do, switch to dynamic programming.

## Related Algorithms
- graph.traversal.dfs — switch when the state space is an explicit graph and you need reachability or a path rather than every constrained assignment.
- dp.one_dimensional — switch when only the count or best value is needed and the same partial states recur.

## Representative Problems
- List every distinct ordering of a collection that may contain repeated values.
- Place n pieces on an n by n board so none attack another and report each arrangement.
- Find all combinations of numbers from a list that sum to a target, where numbers may be reused.
- Complete a partially filled grid so that each row, column and block holds each digit once.
- Count the subsets of an array whose sum equals a given value.

## Sources
- TheAlgorithms/Python backtracking/n_queens.py — row-by-row placement, safety check on column and diagonals, undo after recursion; the global result list is a failure mode.
- TheAlgorithms/Python backtracking/sudoku.py — find-empty-cell, try digits, undo; first-solution return; in-place mutation. It uses the walrus operator, so the canonical code here avoids it.
- TheAlgorithms/Python backtracking/combination_sum.py — start-index recursion with reuse, prune when target is smaller than the candidate, input validation, stated O(n!) average.
- TheAlgorithms/Python backtracking/all_combinations.py — start-index combinations, k and n non-negative checks, O(C(n,k)) time, empty combination for k = 0.
- TheAlgorithms/C-Plus-Plus backtracking/n_queens.cpp — same queen placement scheme in C++; confirms the algorithm across languages.
- TheAlgorithms/C-Plus-Plus backtracking/subset_sum.cpp — subset-sum counting via bitmask brute force; used only for the exponential-cost caveat and test examples. The sources agree on the core scheme (choose, check, recurse, undo); no conflicts found. The permutation-with-duplicates canonical form is a rewrite not present in any source.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | backtracking/n_queens.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | backtracking/sudoku.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | backtracking/combination_sum.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | backtracking/all_combinations.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | backtracking/n_queens.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| TheAlgorithms/C-Plus-Plus | backtracking/subset_sum.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
