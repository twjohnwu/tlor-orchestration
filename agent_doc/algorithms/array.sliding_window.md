---
id: array.sliding_window
name: Sliding Window
category: [array, window]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: other/sliding_window_maximum.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: maths/max_sum_sliding_window.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: greedy_methods/sliding_window.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/other/SlidingWindowMaximum.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
---

# Sliding Window

## Problem Signals
- contiguous subarray or substring
- every window of size k
- maximum / minimum / sum of k consecutive elements
- longest substring or subarray satisfying a constraint
- replace a nested loop over (start, end) with one pass

## Use When
- The answer concerns a contiguous range whose ends only move forward.
- The window statistic can be updated in O(1) amortized time when one element enters or leaves.
- The window has a fixed size k, or a variable size whose validity is monotone in the left end (shrinking a bad window never makes it worse).

## Do Not Use When
- The range is not contiguous (subsequences, subsets): use dynamic programming.
- Arbitrary range queries come in any order on a static array: use `array.prefix_sum` (sums) or a sparse table (min/max).
- Elements can be negative and the task is "shortest/longest window with sum at least or exactly T" with a variable window: validity is not monotone, so use `array.prefix_sum` with a hash map or deque.
- The statistic cannot be maintained by adding and removing one element (e.g. median): use two heaps or an order-statistic structure.

## Preconditions
- The window is a contiguous range of the input sequence.
- Fixed-size form: window size k is an integer (any `numbers.Integral` except bool) with k >= 1 (k <= 0 is rejected).
- Variable-size form: the window predicate is monotone, i.e. if a window is valid every sub-window is valid (or the reverse), so the left end never needs to move backward.
- The window statistic supports add-one and remove-one updates (sum, count, max/min via a monotonic deque).

## Core Invariant
At every step the window `[left, right]` covers exactly the elements the current answer depends on, and both ends only move forward. For the fixed-size maximum, the deque holds indices inside the window whose values are non-increasing from front to back (indices increasing; equal values stay), so the front always names the window maximum; anything strictly smaller that arrived earlier than a larger value can never be a maximum again and is discarded.

## Algorithm
1. Reject an invalid window size.
2. Keep an empty deque of indices (monotonic: values non-increasing front to back).
3. For each index i from left to right:
   1. Pop the front index if it has fallen out of the window (index <= i - k).
   2. Pop back indices whose value is less than values[i], then push i.
   3. Once i >= k - 1, the front index is the maximum of the window ending at i; record it.
4. For a sum or count statistic, replace the deque by a running total: add the entering element, subtract the leaving one.
5. For a variable window, advance the right end each step and move the left end forward while the window is invalid, recording the best size.

## Canonical Implementation
```python
from __future__ import annotations

from collections import deque
from numbers import Integral
from typing import Deque, List, Sequence


def sliding_window_maximum(values: Sequence[float], k: int) -> List[float]:
    """Return the maximum of every length-k window of values, left to right."""
    if not isinstance(k, Integral) or isinstance(k, bool) or k < 1:
        raise ValueError("window size k must be an integer >= 1, got %r" % (k,))

    best = []  # type: List[float]
    window = deque()  # type: Deque[int]  # indices, values non-increasing
    for i, value in enumerate(values):
        if window and window[0] <= i - k:
            window.popleft()
        while window and values[window[-1]] < value:
            window.pop()
        window.append(i)
        if i >= k - 1:
            best.append(values[window[0]])
    return best
```

## Complexity
Time: O(n) — each index is pushed once and popped at most once, so the total deque work is at most 2n. Space: O(k) — the deque holds at most k indices (plus O(n - k + 1) for the output).

## Variants
- Window sum — keep a running total, add the entering element and subtract the leaving one; O(n) time, O(1) extra space.
- Window minimum — flip the comparison in the back-pop step.
- Variable window (longest substring without repeats) — a map from item to last index; on a repeat inside the window, jump `left` to one past that index.
- Two-ended API (advance/shrink) — a stateful object where the caller moves each end; same deque, pops front when the left end passes it.
- Short input convention — one source returns an empty list when k exceeds the length, another raises an error for the sum form; the canonical form returns an empty list. Pick one and test it.

## Common Failure Modes
- Test that k == 1 returns the input unchanged.
- Test that k == len(values) returns a single element.
- Test that k > len(values) and empty input return an empty list (or whatever convention you chose).
- Test duplicates: equal values must not break the window maximum when the older equal index expires.
- Test all-decreasing and all-increasing inputs (deque grows to k, or stays at 1).
- Test negative numbers: never seed a running maximum with 0.
- Test that k <= 0 raises instead of looping forever or returning garbage.
- Test the variable-window form where the repeated item lies before `left` (stale map entry must not move `left` backward).

## Production Considerations
- Streaming: the deque form works online, emitting one result per arriving element after the first k - 1.
- Floating-point running sums drift; recompute periodically or use exact integers.
- Integer overflow in fixed-width languages when adding the entering element before subtracting the leaving one.
- Store indices, not values, in the deque; otherwise you cannot tell when the front expires.
- Use `collections.deque`; a list with `pop(0)` is O(k) per step.

## Related Algorithms
- array.two_pointers — when the two ends move by a sortedness argument rather than a window statistic.
- array.prefix_sum — when queries are arbitrary ranges or the variable window involves negatives.
- stack.monotonic_stack — when you need next-greater element rather than a bounded window.

## Representative Problems
- Maximum of each group of k consecutive readings in a stream.
- Largest sum of k consecutive elements in an array.
- Longest substring with no repeated characters.
- Longest subarray that contains at most m distinct values.
- Smallest contiguous block whose sum reaches a target, given non-negative numbers.

## Sources
- TheAlgorithms/Python other/sliding_window_maximum.py — monotonic deque of indices, front expiry, O(n) claim, window size must be positive, empty input gives empty output.
- TheAlgorithms/Python maths/max_sum_sliding_window.py — running-sum form; raises on k larger than the array (differs from the empty-result convention above).
- TheAlgorithms/Python greedy_methods/sliding_window.py — variable-size window via last-index map; the stale-entry guard `index >= left`.
- williamfiset/Algorithms SlidingWindowMaximum.java — stateful advance/shrink variant, same deque invariant, flip the comparison for the minimum.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | other/sliding_window_maximum.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | maths/max_sum_sliding_window.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | greedy_methods/sliding_window.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/other/SlidingWindowMaximum.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
