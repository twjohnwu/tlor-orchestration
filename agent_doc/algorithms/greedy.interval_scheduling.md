---
id: greedy.interval_scheduling
name: Greedy Interval Scheduling
category: [greedy, intervals]
confidence: medium
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: greedy_methods/activity_selection.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: other/activity_selection.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: data_structures/arrays/merge_intervals.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: greedy_methods/minimum_waiting_time.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
---

# Greedy Interval Scheduling

## Problem Signals
- maximum number of non-overlapping intervals / activities / meetings
- one resource, each task has a start and an end time
- remove the fewest intervals so the rest do not overlap
- merge overlapping ranges into disjoint ones
- order jobs to minimize total waiting time

## Use When
- You must pick the largest subset of intervals that are pairwise compatible on a single resource.
- Sorting by one key (end time) and one linear scan is acceptable.
- Touching endpoints (one ends exactly where the next starts) count as compatible, or you can adapt the comparison.
- Variant: you need disjoint merged ranges (sort by start) or the order of jobs that minimizes summed waiting (sort by duration).

## Do Not Use When
- Intervals carry weights and you want maximum total weight: use dynamic programming over end-sorted intervals with binary search.
- You need the number of resources (rooms) to serve every interval: use `heap.priority_queue` over end times (or a sweep over sorted endpoints).
- A task needs several resources or has precedence constraints: this is not a one-resource problem; use a general scheduling or flow model.
- Intervals are not known up front and must be decided online: the end-time order is unavailable; the greedy guarantee does not hold.

## Preconditions
- Every interval is a `tuple` or `list` of exactly two integers (not `bool`) with `start <= end`; an interval with `end < start` is rejected.
- A single resource: at most one chosen interval is active at any time.
- Compatibility is "`end_a <= start_b`" (half-open intervals); for closed intervals where touching conflicts, change the scan test to `>`.
- The whole input is available before selection starts.

## Core Invariant
After processing intervals in non-decreasing end time, the chosen set is a largest compatible set among the intervals seen so far, and its last end is the smallest possible among all such largest sets. Exchange argument: in any optimal solution, swap its first interval for the interval with the globally earliest end; that one ends no later, so it still fits before the rest and the count does not drop. Repeat on the remaining suffix of intervals that start at or after the chosen end.

## Algorithm
1. Validate every interval: two integers, `start <= end`.
2. Sort by end time (break ties by start) without mutating the input.
3. Set `last_end` to `None` (nothing chosen yet; the first interval is always taken).
4. For each interval in order: if its start is `>= last_end`, choose it and set `last_end` to its end; otherwise skip it.
5. Return the chosen intervals (their count is the answer).

## Canonical Implementation
```python
from __future__ import annotations

from typing import Iterable, List, Tuple


def select_max_intervals(intervals: Iterable[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Return a largest set of pairwise non-overlapping (start, end) intervals.

    Intervals that merely touch (end == next start) are compatible.
    Raises ValueError if an interval is malformed or has end < start.
    """
    checked = []
    for item in intervals:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError("interval must be a (start, end) pair, got %r" % (item,))
        start, end = item
        if isinstance(start, bool) or isinstance(end, bool):
            raise ValueError("interval bounds must be integers, got %r" % (item,))
        if not isinstance(start, int) or not isinstance(end, int):
            raise ValueError("interval bounds must be integers, got %r" % (item,))
        if end < start:
            raise ValueError("interval end %r is before start %r" % (end, start))
        checked.append((start, end))

    chosen = []  # type: List[Tuple[int, int]]
    last_end = None
    # Earliest end first: it leaves the most room for what follows.
    for start, end in sorted(checked, key=lambda iv: (iv[1], iv[0])):
        if last_end is None or start >= last_end:
            chosen.append((start, end))
            last_end = end
    return chosen
```

## Complexity
Time: O(n log n) — the sort dominates; the scan is O(n). Space: O(n) — the sorted copy and the result.

## Variants
- Merge intervals — sort by start; extend the last merged interval while `start <= last_end` (using `max` of ends), otherwise open a new one. Output is disjoint ranges, not a selection.
- Minimum rooms / maximum overlap — sort by start and keep a min-heap of end times (`heap.priority_queue`); the peak heap size is the room count.
- Minimum waiting time — sort job durations ascending; job at sorted position i is waited on by the (n - i - 1) jobs after it, so total wait is the sum of duration * (n - i - 1).
- Pre-sorted input — if ends are already sorted, skip step 2 and the scan is O(n); one source assumes this and takes parallel start and finish arrays.
- Minimum removals — n minus the size of the selected set.

## Common Failure Modes
- Test sorting by start time instead of end time: `[(0, 10), (1, 2), (3, 4)]` must give 2, not 1.
- Test sorting by shortest duration: `[(0, 5), (4, 7), (6, 10)]` needs the two outer intervals, not the short middle one.
- Test touching intervals: `[(1, 2), (2, 3)]` both chosen under half-open semantics; decide and state it.
- Test the empty list returns an empty list.
- Test that an interval with `end < start` raises `ValueError`.
- Test that the input list is not reordered or mutated.
- Test duplicates: two identical positive-length intervals yield one.
- Merge variant: test that touching ranges merge (`[1, 4], [4, 5]` becomes `[1, 5]`) and that a fully contained range does not shrink the end (use `max`).

## Production Considerations
- Python ints do not overflow; in fixed-width languages compare without subtracting (`start >= last_end`), and widen timestamps if needed.
- Sorting is stable, but ties by end only change which equal-size solution you return, not its size; sort by (end, start) for deterministic output.
- Streaming input cannot be sorted; if arrival is already end-ordered, the scan works online in O(1) memory.
- One source accepted falsy non-list inputs such as `None`; here, validate types explicitly and reject bad shapes instead of treating them as empty.
- Return indices rather than tuples when callers need to map the choice back to original records.

## Related Algorithms
- heap.priority_queue — switch when the question is how many resources are needed, not how many intervals fit on one.

## Representative Problems
- Given meetings with start and end times and one room, schedule the largest number of meetings.
- Given a list of ranges, return the fewest to delete so that no two overlap.
- Given a list of ranges, return the merged disjoint ranges that cover the same points.
- Given queries with processing times served one at a time, order them to minimize the total waiting time.
- Given arrival and departure times, find the minimum number of rooms so nobody waits.

## Sources
- TheAlgorithms/Python greedy_methods/activity_selection.py — sort by end time, take the first, then take each interval whose start is at or after the last chosen end (core algorithm, touching allowed).
- TheAlgorithms/Python other/activity_selection.py — same earliest-finish scan over parallel start/finish arrays assuming pre-sorted finish times; confirms the O(n) scan once sorted.
- TheAlgorithms/Python data_structures/arrays/merge_intervals.py — merge variant: sort by start, extend with max of ends, reject non-pair intervals.
- TheAlgorithms/Python greedy_methods/minimum_waiting_time.py — shortest-first ordering variant for waiting time (a related greedy, not an interval selection).
- Confidence is medium: all sources come from one repository, so they count as one primary source. Minimum meeting rooms is not in the evidence; it is stated here from general knowledge and flagged as such.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | greedy_methods/activity_selection.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | other/activity_selection.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | data_structures/arrays/merge_intervals.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | greedy_methods/minimum_waiting_time.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
