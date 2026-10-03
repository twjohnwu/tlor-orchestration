---
id: array.two_pointers
name: Two Pointers
category: [array]
confidence: medium
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: maths/two_pointer.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: maths/three_sum.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: maths/two_sum.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
---

# Two Pointers

## Problem Signals
- sorted array, find a pair (or triple) with a given sum
- pair with target sum, two sum on sorted input
- find all unique triplets summing to a value
- squeeze or shrink from both ends
- no extra memory allowed for the lookup

## Use When
- The array is sorted (or can be sorted cheaply) and the condition on a pair is monotone in each pointer: moving the left pointer right increases the pair sum, moving the right pointer left decreases it.
- You need O(1) extra space for a pair search.
- A triple search can be reduced to "fix one element, run a pair search on the rest".

## Do Not Use When
- The input is unsorted and must keep its original indices, and sorting would lose them: use a hash map of seen values (one pass, O(n) space; the `two_sum` source does this).
- The target is a contiguous subarray with a running condition: use `array.sliding_window`.
- The data is a linked list and you need a midpoint or cycle: use `linked_list.fast_slow_pointers`.
- You need a single value in sorted data, not a pair: use `search.binary_search`.

## Preconditions
- The input is sorted in non-decreasing order (checkable in one O(n) scan).
- Elements support addition and comparison with the target (numbers).
- The two chosen positions must be distinct indices (`left < right`); equal values at different indices are allowed.

## Core Invariant
Every pair `(a, b)` with `a < left` or `b > right` has already been proven not to sum to the target, so any remaining solution lies inside `[left, right]`. When `nums[left] + nums[right]` is too small, no pair using `left` and any index `<= right` can reach the target, since `nums[right]` is already the largest remaining partner, so `left` is safely discarded. The symmetric argument discards `right` when the sum is too large.

## Algorithm
1. Check preconditions (sorted).
2. Set `left = 0`, `right = len - 1`.
3. While `left < right`: compute the sum of the two ends.
4. If it equals the target, report the pair.
5. If it is smaller, advance `left`; if larger, retreat `right`.
6. When the pointers meet, no pair exists.

## Canonical Implementation
```python
from __future__ import annotations

from typing import List, Optional, Tuple


def pair_with_sum(nums: List[int], target: int) -> Optional[Tuple[int, int]]:
    """Return indices (i, j), i < j, with nums[i] + nums[j] == target, else None.

    nums must be sorted in non-decreasing order.
    """
    for k in range(1, len(nums)):
        if nums[k - 1] > nums[k]:
            raise ValueError("nums must be sorted in non-decreasing order")

    left, right = 0, len(nums) - 1
    while left < right:
        total = nums[left] + nums[right]
        if total == target:
            return left, right
        if total < target:
            left += 1
        else:
            right -= 1
    return None
```

## Complexity
Time: O(n) — each step moves one pointer inward, so at most n - 1 iterations (the sortedness check is also O(n)); O(n log n) if a sort is needed first. Space: O(1) — only two indices.

## Variants
- Three sum — sort, fix index `i` (skipping repeated values), then run the pair search on `i + 1..end` for target `-nums[i]`; O(n^2). This variant assumes the target sum is 0; for another target `T` use `T - nums[i]`.
- Unique results — after a hit, skip over repeated values on both sides before moving both pointers, so duplicate pairs are not reported.
- Hash-map two sum — one pass over unsorted data storing value to index; O(n) time and space, preserves original indices, does not need sorting.

## Common Failure Modes
- Test that unsorted input raises instead of silently returning a wrong answer.
- Test that `[3]` with target 6 returns nothing (an element must not pair with itself).
- Test that `[3, 3]` with target 6 returns `(0, 1)` (equal values at distinct indices are valid).
- Test that an empty array returns nothing without indexing error.
- Test that all-unique enumeration (three sum) does not repeat triplets when the input has runs of equal values.
- Test that sorting a copy still maps results back to original indices when indices are required.

## Production Considerations
- Sorting in place mutates the caller's list (the three-sum source sorts its argument); copy first if the caller must keep the order.
- Python integers do not overflow, but fixed-width languages can: compute the sum in a wider type.
- Floating-point targets need a tolerance instead of exact equality.
- Works on streams only if they are already ordered and random access is available.

## Related Algorithms
- array.sliding_window — contiguous range with a running condition instead of a pair at both ends.
- search.binary_search — one target value in sorted data; also an alternative per-element lookup for a pair search at O(n log n).
- linked_list.fast_slow_pointers — pointers moving in the same direction at different speeds.

## Representative Problems
- Given a sorted list of numbers and a target, find two positions whose values add up to the target.
- Given an unsorted list, find all distinct triples that sum to zero.
- Given a sorted list, decide whether any two values differ by exactly a given amount (same-direction variant: both pointers move forward, unlike the converging form taught here).
- Reverse or test a sequence for symmetry by comparing the two ends moving inward.

## Sources
- TheAlgorithms/Python maths/two_pointer.py — the core opposite-ends pair search on sorted input; its docstring examples show the empty result and the duplicate-values case.
- TheAlgorithms/Python maths/three_sum.py — reduction of a triple search to a pair search, with duplicate skipping; it sorts its argument in place despite documenting a sorted input.
- TheAlgorithms/Python maths/two_sum.py — the hash-map alternative for unsorted input; used for the Do Not Use When and Variants entries only. All three sources are in one repository, so confidence is medium; they do not conflict.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | maths/two_pointer.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | maths/three_sum.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | maths/two_sum.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
