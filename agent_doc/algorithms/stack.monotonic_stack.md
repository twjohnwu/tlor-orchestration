---
id: stack.monotonic_stack
name: Monotonic Stack
category: [stack]
confidence: medium
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: data_structures/stacks/next_greater_element.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: data_structures/stacks/largest_rectangle_histogram.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: data_structures/stacks/stock_span_problem.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: data_structures/queues/monotonic_queue.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
---

# Monotonic Stack

## Problem Signals
- next greater (or smaller) element to the right or left
- nearest larger / smaller value, per position
- how many consecutive items, the current one included, are not larger (span)
- largest rectangle under a bar profile
- replace a nested "scan forward until something bigger" loop with one pass

## Use When
- Every position needs the nearest element on one side that beats it under a fixed comparison.
- Each element can be answered at the moment a later element dominates it.
- The answer for a bar or item is bounded by its nearest dominating neighbors (rectangle width, span length).

## Do Not Use When
- The range is a bounded window of size k: use `array.sliding_window` (the monotonic deque form, with front expiry).
- Arbitrary range min/max queries arrive in any order on a static array: use a sparse table or segment tree.
- The k-th next greater, or all dominating pairs, are needed: use a nested scan or an order-statistic structure.
- Elements are inserted in the middle or the order changes online: use a balanced tree.

## Preconditions
- The input is a finite sequence (not a string) of real numbers; `bool` items are rejected.
- No item is NaN (NaN has no consistent order, so the stack invariant breaks).
- The comparison is one fixed strict or non-strict order, chosen before coding (ties decided up front).
- Only the nearest dominating element on one side is wanted, not every one.

## Core Invariant
Scanning left to right, the stack holds indices of items that have not yet met a strictly greater item. Their values never increase from bottom to top: with the pop condition "top value < current value", equal values stay stacked, so the stack is non-increasing (it is strictly decreasing only if equal values are popped too, which is the right choice for "next greater or equal" and for stock span). Every popped index gets its answer from the current index, and an index popped once is never needed again.

## Algorithm
1. Create an empty stack of indices and an answer list filled with "none".
2. For each index i from left to right:
   1. While the stack is non-empty and the top item is less than values[i], pop it and record i as its next greater index.
   2. Push i.
3. Indices left on the stack have no greater item to their right; they keep "none".
4. For a previous-greater or span, scan the same way and read the new stack top after popping (empty means none; span = i - top, or i + 1 when empty).
5. For the largest rectangle, keep the stack increasing, pop while the current bar is shorter, and compute width from the new top; append a zero-height sentinel to flush the stack.

## Canonical Implementation
```python
from __future__ import annotations

from numbers import Real
from typing import List, Sequence


def next_greater_indices(values: Sequence[float]) -> List[int]:
    """For each position, the index of the next strictly greater item, or -1."""
    if isinstance(values, (str, bytes, bytearray)):
        raise ValueError("values must be a sequence of numbers, got %s" % type(values).__name__)
    for item in values:
        if isinstance(item, bool) or not isinstance(item, Real) or (isinstance(item, float) and item != item):
            raise ValueError("values must be real numbers and not NaN, got %r" % (item,))

    answer = [-1] * len(values)
    pending = []  # type: List[int]  # indices, values non-increasing bottom to top
    for i, value in enumerate(values):
        while pending and values[pending[-1]] < value:
            answer[pending.pop()] = i
        pending.append(i)
    return answer
```

## Complexity
Time: O(n) — each index is pushed once and popped at most once, so the inner while loop does at most n pops in total. Space: O(n) — the stack can hold every index (strictly non-increasing input), plus the O(n) answer.

## Variants
- Next smaller — flip the comparison; the stack is then non-decreasing.
- Previous greater / stock span — pop while top <= current and read the surviving top; span is the distance to it (or i + 1 if empty).
- Right-to-left scan — iterate in reverse and read the top before pushing; one source returns values, not indices, and uses -1 as "none".
- Largest rectangle in a histogram — increasing stack; popping a bar fixes its height, and its width runs from the new top to the current index; a trailing zero bar flushes the rest.
- Monotonic queue (sliding window maximum) — same decreasing discipline on a deque, with an extra front pop when the index leaves the window.
- Tie handling differs by source: the sliding-window form pops on >=, the span form on <=, the next-greater form on <= when scanning in reverse; each is right for its own definition of "greater".

## Common Failure Modes
- Test equal neighbors: with strict "greater", [2, 2] must give [-1, -1], not [1, -1].
- Test strictly decreasing input: nothing pops and every answer is none.
- Test strictly increasing input: each index answers with i + 1 and the last is none.
- Test empty and single-element input return [] and [-1].
- Test that you store indices, not values, when positions or widths are needed.
- Test the histogram form with and without the zero sentinel; without it the last bars are never measured.
- Test a width computation after popping when the stack becomes empty (width is the full prefix).
- Test against a brute-force quadratic scan on small random lists.

## Production Considerations
- Streaming: the forward form works online; answers for earlier items arrive when a larger item shows up, and unresolved items stay pending.
- Use a plain list as the stack; push and pop at the end are O(1).
- Python ints do not overflow, but in fixed-width languages a rectangle area height * width needs a wider type.
- Circular next greater: scan the sequence twice (indices modulo n), pushing only on the first pass.
- Mixed or NaN values make comparisons inconsistent; validate before scanning.

## Related Algorithms
- stack.stack — when you only need last-in-first-out storage with no ordering invariant.
- array.sliding_window — when answers are limited to a window of size k (the monotonic deque).

## Representative Problems
- For every day's reading, find the number of days until a larger reading appears.
- For each element of a list, report the first larger element to its right.
- Given bar heights, find the area of the largest axis-aligned rectangle that fits under them.
- For each price in a daily series, count the consecutive earlier days with price not above it.
- Maximum of every window of fixed length over a series.

## Sources
- TheAlgorithms/Python data_structures/stacks/next_greater_element.py — brute-force versus stack comparison, the reverse-scan stack form, -1 for no answer, quadratic cost of the naive loop.
- TheAlgorithms/Python data_structures/stacks/largest_rectangle_histogram.py — increasing stack, zero sentinel, width from the new top after a pop.
- TheAlgorithms/Python data_structures/stacks/stock_span_problem.py — previous-greater-or-equal span, pop on <=, span = i - top or i + 1.
- TheAlgorithms/Python data_structures/queues/monotonic_queue.py — decreasing deque of indices, front expiry, pop on >=. Not a conflict: it differs only in tie rule and the window bound.
- All four sources are the same repository at one commit, so they count as one primary source and confidence is medium, not high; they agree on the one-pass amortized O(n) structure. Tie handling differs per definition (see Variants), not per algorithm.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | data_structures/stacks/next_greater_element.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | data_structures/stacks/largest_rectangle_histogram.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | data_structures/stacks/stock_span_problem.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | data_structures/queues/monotonic_queue.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
