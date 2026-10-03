---
id: dp.two_dimensional
name: 2-D Dynamic Programming
category: [dynamic-programming]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: dynamic_programming/knapsack.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: dynamic_programming/edit_distance.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: knapsack/knapsack.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: dynamic_programming/longest_common_subsequence.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: dynamic_programming/edit_distance.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/dp/LongestCommonSubsequence.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/dp/Knapsack_01.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
---

# 2-D Dynamic Programming

## Problem Signals
- longest common subsequence of two sequences
- minimum edit distance, insert / delete / substitute
- 0/1 knapsack, each item taken at most once, capacity limit
- state is a pair (prefix of A, prefix of B) or (items considered, budget used)
- optimal choice over two sequences or over items and a capacity

## Use When
- the answer for prefixes (i, j) depends only on a constant number of neighbouring cells such as (i-1, j-1), (i-1, j), (i, j-1)
- both dimensions are small enough to hold n*m cells (or a rolling row of them)
- variant — not covered by the canonical code or its tests: for knapsack, capacities and weights are non-negative integers, so capacity is a usable table index

## Do Not Use When
- the state needs one index only -> dp.one_dimensional
- capacity is huge or real-valued and items are few -> meet-in-the-middle or branch and bound
- items may be taken fractionally -> greedy by value/weight ratio
- the state is a subset of items -> bitmask DP

## Preconditions
- the inputs are indexable sequences (str, list, tuple) with a defined length; generators and numbers are rejected
- elements of the two sequences are comparable with `==` (LCS)
- n*m cells fit in memory; otherwise use the rolling-row form
- Only the LCS preconditions above are enforced by the canonical code and its tests. Knapsack and edit-distance inputs (non-negative int capacity, equal-length weights and values) are variant territory: validate them yourself; no code here checks them.

## Core Invariant
`dp[i][j]` is the LCS length of the first `i` elements of the first input against the first `j` elements of the second. (Variant — not covered by the canonical code or its tests: for knapsack, `dp[i][j]` is the best value of the first `i` items under budget `j`.) Row 0 and column 0 are base cases. Every cell is computed from already finished cells, so the final cell is the answer.

## Algorithm
1. Allocate a table of (n+1) x (m+1) cells; fill row 0 and column 0 with 0 (the LCS base case). Variant — not covered by the canonical code or its tests: knapsack also uses 0; edit distance uses the index.
2. Iterate i from 1..n, j from 1..m in an order that visits dependencies first.
3. LCS: if `a[i-1] == b[j-1]` take `dp[i-1][j-1] + 1`, else `max(dp[i-1][j], dp[i][j-1])`.
4. Variant — not covered by the canonical code or its tests. Edit distance: on equal elements copy `dp[i-1][j-1]`, else `1 + min(insert, delete, substitute)` over the three neighbours.
5. Variant — not covered by the canonical code or its tests. 0/1 knapsack: `dp[i][w] = dp[i-1][w]`, or if item i fits, the max with `dp[i-1][w - wt] + val`.
6. Return `dp[n][m]` (knapsack variant: `dp[n][W]`). To recover the choice, walk back from the last cell comparing with the neighbour it came from.

## Canonical Implementation
```python
from __future__ import annotations

from typing import Sequence


def lcs_length(a: Sequence, b: Sequence) -> int:
    """Length of the longest common subsequence of two sequences."""
    for name, seq in (("a", a), ("b", b)):
        if not isinstance(seq, (str, list, tuple)):
            raise ValueError("%s must be a str, list or tuple, got %s" % (name, type(seq).__name__))
    n, m = len(a), len(b)
    # dp[i][j] = LCS length of a[:i] and b[:j]; row 0 / column 0 stay 0.
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[n][m]
```

## Complexity
Time: O(n*m) — each of the (n+1)(m+1) cells is filled once from O(1) neighbours. Space: O(n*m) for the full table; O(m) if only the previous row is kept (the row length comes from `b`; to get O(min(n, m)) call with the shorter sequence as `b`), at the price of losing the walk-back reconstruction. The knapsack variant is O(n*W) time and space, the pseudo-polynomial form.

## Variants
Everything in this section is a variant — not covered by the canonical code or its tests.
- Edit distance — base row/column are `j` and `i`; the mismatch cell is `1 + min` of three neighbours; same O(n*m).
- 0/1 knapsack — rows are items, columns are capacities; one row of size W+1 suffices if capacity is scanned downwards.
- Unbounded knapsack (repetition allowed) — scan capacity upwards in the one-row form so an item can be reused.
- Memoised top-down — same recurrence with a cache; one source uses it, but it risks deep recursion on long inputs.
- Matrix chain multiplication — interval DP over (i, j) with a split point, O(n^3); listed as an alias but no cited source covers it, so verify before relying on it.

## Common Failure Modes
- test that empty input on either side returns 0 (LCS; edit distance would return the other length, a variant)
- test that a single shared element gives LCS 1
- test that an off-by-one between table index `i` and element `a[i-1]` does not shift the result
- test that a non-sequence input (generator, number, None) is rejected with ValueError
- if you port the knapsack or edit-distance variants, write their own tests (capacity 0, item heavier than capacity, one-row upward scan allowing reuse, bool or negative capacity); none exist for the canonical code

## Production Considerations
- memory is the limit before time: keep two rows when only the value is needed
- variant: knapsack time depends on the numeric value of W, not its bit length; huge W is a different problem
- the tie-break in reconstruction decides which of several optimal answers is returned
- avoid recursion for long inputs; Python's default recursion limit is about 1000

## Related Algorithms
- dp.one_dimensional — when one index suffices, for example coin change or a rolling row of one sequence

## Representative Problems
- longest sequence of elements appearing in order in two given sequences
- fewest single-element edits that turn one string into another
- most valuable subset of items whose total weight fits a limit
- cheapest way to fully parenthesise a chain of products

## Sources
- TheAlgorithms/Python dynamic_programming/knapsack.py — 0/1 recurrence, input validation, walk-back reconstruction
- TheAlgorithms/Python dynamic_programming/edit_distance.py — top-down and bottom-up edit distance, base cases
- TheAlgorithms/Python knapsack/knapsack.py — repetition (unbounded) knapsack variant in its test file
- TheAlgorithms/C-Plus-Plus dynamic_programming/longest_common_subsequence.cpp — LCS table with a direction trace
- TheAlgorithms/C-Plus-Plus dynamic_programming/edit_distance.cpp — O(m*n) bottom-up table
- williamfiset/Algorithms LongestCommonSubsequence.java — LCS O(nm) recurrence
- williamfiset/Algorithms Knapsack_01.java — O(n*W) time and space for 0/1 knapsack
- Skipped as a false match: TheAlgorithms/C-Plus-Plus greedy_algorithms/knapsack.cpp (fractional greedy). Matrix chain has no source; the sources agree on the core table-fill and complexity.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | dynamic_programming/knapsack.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | dynamic_programming/edit_distance.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | knapsack/knapsack.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | dynamic_programming/longest_common_subsequence.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| TheAlgorithms/C-Plus-Plus | dynamic_programming/edit_distance.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/dp/LongestCommonSubsequence.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/dp/Knapsack_01.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
