---
id: dp.one_dimensional
name: 1-D Dynamic Programming
category: [dynamic-programming]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: dynamic_programming/climbing_stairs.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: dynamic_programming/max_subarray_sum.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: dynamic_programming/coin_change.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: dynamic_programming/house_robber.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/dp/CoinChange.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/dp/examples/houserobber/HouseRobber.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/dp/LongestIncreasingSubsequence.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
  - repo: ADJA/algos
    path: DP/LIS.cpp
    commit: 244d382be168208d669db0f90ea64cc6be06e3d2
    license: MIT
---

# 1-D Dynamic Programming

## Problem Signals
- minimum number of items to reach a total, or "impossible"
- count the ways to reach step n using fixed moves
- best total when no two adjacent items may both be taken
- longest increasing subsequence of a sequence
- best contiguous subarray sum
- answer for size i depends only on answers for smaller sizes

## Use When
- The state is a single integer index or amount, and each answer is a fixed function of a few earlier answers.
- Subproblems overlap, so plain recursion would recompute them exponentially often.
- You need the optimum (min, max) or a count over choices, not the list of all choices.
- Only the last k states are read, so the table can shrink to k variables (stairs, house robber, Kadane).

## Do Not Use When
- The state needs two indices (two strings, item plus capacity): use `dp.two_dimensional`.
- You must list every valid combination, not count or optimize: use `backtracking.backtracking`.
- A locally best choice is provably safe, as with interval scheduling: use `greedy.interval_scheduling`.
- The amount or index range is huge (1e12) while the item count is tiny: the table does not fit; look for a closed form or a different model.
- Subproblems depend on a graph with cycles or on arbitrary neighbors: use `graph.shortest_path.dijkstra` or a graph search.

## Preconditions
- Every state is an integer index or amount `0..n`, and the transition for state `i` reads only states `< i`.
- Inputs that must be integers are real `int`, never `bool`.
- Coin-style problems: each denomination is a positive integer (a zero or negative value breaks the order of evaluation) and the target is non-negative.
- Sub-structure is optimal: the best answer for `i` is built from best answers for smaller states.
- The table size (target or length plus one) fits in memory.
- `coins` is any iterable of ints; the canonical code copies it with `list(coins)` before validating, so a generator is safe.

## Core Invariant
After processing state `i`, `dp[i]` holds the exact optimum (or count) for the subproblem of size `i`, using only choices already evaluated. Unreachable states carry an explicit sentinel (infinity, or `amount + 1` here) that is larger than any real answer, so `sentinel + 1` can never win the min comparison and a bad state cannot look like a cheap one.

## Algorithm
1. Define the state `dp[i]` in one sentence and its meaning at `i = 0`.
2. Seed the base cases (`dp[0]`, and `dp[1]` if two steps back are read).
3. Choose an evaluation order in which every dependency is computed first (ascending `i`).
4. For each `i`, combine the allowed earlier states with min, max or sum; skip any dependency that is out of range or unreachable.
5. Return `dp[n]`, or for subsequence and subarray problems the best over all `dp[i]`.
6. If only the last few entries are read, replace the table by rolling variables.

## Canonical Implementation
```python
from __future__ import annotations

from typing import Iterable


def min_coins(coins: Iterable[int], amount: int) -> int:
    """Fewest coins (each denomination reusable) summing to amount, or -1."""
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise ValueError("amount must be a non-negative int")
    coins = list(coins)  # materialise: a generator would be consumed by the check below
    for coin in coins:
        if isinstance(coin, bool) or not isinstance(coin, int) or coin <= 0:
            raise ValueError("every coin must be a positive int")

    unreachable = amount + 1  # larger than any real answer (all-ones needs amount coins)
    best = [0] + [unreachable] * amount
    for total in range(1, amount + 1):
        for coin in coins:
            if coin <= total and best[total - coin] + 1 < best[total]:
                best[total] = best[total - coin] + 1
    return best[amount] if best[amount] != unreachable else -1
```

## Complexity
Time: O(n * m) for target n and m denominations — n states, each tries m transitions. Space: O(n) for the table. Rolling forms (stairs, house robber, Kadane) run in O(n) time and O(1) space; the binary-search LIS runs in O(n log n) time and O(n) space.

## Variants
- Climbing stairs / Fibonacci — `ways[i] = ways[i-1] + ways[i-2]`; keep two variables, O(1) space.
- House robber — `best[i] = max(best[i-1], best[i-2] + value[i])`; a backward walk over the table recovers which items were taken.
- Kadane (max subarray) — `cur = max(x, cur + x)`; one pass, O(1) space; decide up front whether the empty subarray is allowed, since it changes the all-negative answer.
- LIS, quadratic — `dp[j] = max(dp[i] + 1)` over earlier `i` with `a[i] < a[j]`; O(n^2).
- LIS, O(n log n) — keep `tails[k]`, the smallest tail of an increasing subsequence of length `k+1`; binary-search each element into it (`bisect_left` for strict, `bisect_right` for non-decreasing).
- Coin change top-down — memoized recursion; visits only reachable amounts but is bounded by recursion depth.
- Coin count of ways — same loop shape, but `+=` and coins in the outer loop to count combinations rather than orderings.

## Common Failure Modes
- Test that an amount no coin set can form returns the sentinel, not a huge number or a crash.
- Test amount 0 returns 0 and an empty coin list with amount 0 returns 0.
- Test that a stale value is never carried across coins: one source reuses a temporary `res` between inner iterations without resetting it, which is only safe because it is re-read before use; prefer reading the table directly.
- Test an unreachable state never beats a real value; in fixed-width languages a sentinel of INT_MAX overflows when `+ 1` is applied, so use a bounded sentinel like `amount + 1`.
- Test Kadane on an all-negative array: the answer is the largest element, not 0 (unless empty subarrays are allowed).
- Test LIS on equal elements to confirm strict versus non-decreasing handling.
- Test a single-element and an empty input for stairs, robber and LIS.
- Test that a zero or negative coin is rejected instead of looping forever or reading a negative index.

## Production Considerations
- Memoized recursion in Python hits the recursion limit near depth 1000; prefer the bottom-up loop.
- Fixed-width integers overflow for count-the-ways problems (Fibonacci-like growth); Python ints do not, other languages need a modulus or big integers.
- A table of size `amount + 1` is O(amount) memory even if few denominations exist; check the magnitude first.
- Streaming input only suits the rolling forms (Kadane, robber, stairs); LIS needs the `tails` array.
- To return the actual choice (coins used, houses robbed, subsequence), store a parent index per state alongside `dp`.

## Related Algorithms
- `dp.two_dimensional` — when the state needs two indices or a capacity dimension.
- `backtracking.backtracking` — when all solutions must be enumerated, not just the best value.

## Representative Problems
- Fewest coins that sum to a target, or report impossible.
- Number of distinct ways to climb n stairs taking one or two at a time.
- Largest total from a row of values with no two neighbors chosen.
- Length of the longest strictly increasing subsequence of a sequence.
- Largest sum over all contiguous subarrays of a numeric array.

## Sources
- TheAlgorithms/Python dynamic_programming/climbing_stairs.py — two-variable rolling recurrence and the positive-integer input check.
- TheAlgorithms/Python dynamic_programming/max_subarray_sum.py — Kadane in O(1) space, and the empty-subarray option.
- TheAlgorithms/C-Plus-Plus dynamic_programming/coin_change.cpp — min-coins table with an INT_MAX sentinel guarded before adding one; the shared `res` temporary is the stale-value risk noted above.
- TheAlgorithms/C-Plus-Plus dynamic_programming/house_robber.cpp — O(n) time, O(1) space rolling form.
- williamfiset/Algorithms dp/CoinChange.java — states the unbounded-reuse assumption, a 1-D O(n) space version, and memoized top-down skipping unreachable states.
- williamfiset/Algorithms dp/examples/houserobber/HouseRobber.java — table padded by two cells, plus backward reconstruction of chosen houses.
- williamfiset/Algorithms dp/LongestIncreasingSubsequence.java — O(n^2) LIS, `dp[i]` initialized to 1, empty input returns 0.
- ADJA/algos DP/LIS.cpp — O(n log n) LIS with a tails array and binary search, plus parent links to rebuild the sequence.
- No conflict on core algorithm or complexity across the four repositories; the sources differ only in reuse of space (table versus rolling) and strictness of LIS.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | dynamic_programming/climbing_stairs.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | dynamic_programming/max_subarray_sum.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | dynamic_programming/coin_change.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| TheAlgorithms/C-Plus-Plus | dynamic_programming/house_robber.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/dp/CoinChange.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/dp/examples/houserobber/HouseRobber.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/dp/LongestIncreasingSubsequence.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
| ADJA/algos | DP/LIS.cpp | 244d382be168208d669db0f90ea64cc6be06e3d2 | MIT |
