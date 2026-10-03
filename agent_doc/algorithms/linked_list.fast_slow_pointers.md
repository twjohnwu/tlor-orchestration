---
id: linked_list.fast_slow_pointers
name: Fast / Slow Pointers
category: [linked-list]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: data_structures/linked_list/floyds_cycle_detection.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: data_structures/linked_list/middle_element_of_linked_list.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: data_structures/linked_list/has_loop.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: search/floyd_cycle_detection_algo.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
---

# Fast / Slow Pointers

## Problem Signals
- does this linked list contain a cycle / loop
- find the node where the cycle begins
- find the middle node of a singly linked list in one pass
- no extra memory allowed, cannot mark or hash visited nodes
- repeated value in a sequence defined by `next = f(current)` (functional graph)

## Use When
- The structure is a singly linked list (or any sequence where each element has exactly one successor) and you need cycle presence, the cycle entry, or the midpoint.
- You must stay at O(1) extra space; a visited-set is not acceptable.
- You cannot index into the structure, so "length / 2" needs a first pass you want to avoid.

## Do Not Use When
- The structure is an array with indexed access and you want the midpoint: use `len(a) // 2` directly (for pair or window searches use `array.two_pointers`).
- Nodes have several successors (general graph or tree): use `graph.traversal.bfs` with a visited set.
- You also need the cycle's full node list or every visited node: a visited-set walk is simpler.
- Nodes are not identity-comparable (copies compare equal by value): the meeting test is unreliable, so fix identity first or use a visited-set.

## Preconditions
- Each node has at most one successor reachable through a `next` link (`None` ends the list).
- Node identity (`is`) is meaningful: two links to the same node are the same object.
- The list is not mutated during the walk.
- `head` is a node or `None`; `None` is a valid empty list.

## Core Invariant
Both pointers start at the head; slow advances one link and fast two per round. In a list without a cycle, fast reaches the end first, so there is no cycle. With a cycle of length L and a tail of length t, once both are inside the cycle fast closes the gap by one node per round, so they meet within L rounds. At the meeting point, the distance from the head to the cycle entry equals the distance from the meeting point forward to the entry (modulo L); so a pointer restarted at the head and one left at the meeting point, both moving one step at a time, arrive at the entry together. For the midpoint, fast covers twice the distance of slow, so when fast runs off the end slow sits at the middle.

## Algorithm
1. Validate `head` (a node or `None`); `None` returns `None`.
2. Set `slow = fast = head`.
3. While `fast` and `fast.next` exist: move `slow` one step, `fast` two steps; if they are the same node, a cycle exists, go to step 5.
4. Fast fell off the end: no cycle, return `None`.
5. Reset one pointer to `head`; keep the other at the meeting node.
6. Advance both one step at a time until they are the same node; that node is the cycle start.
7. Midpoint variant: run step 3 without the meeting test; when the loop stops, `slow` is the middle (the second of two middles for even length).

## Canonical Implementation
```python
from __future__ import annotations

from typing import Any, Optional


class Node:
    def __init__(self, value: Any = None, next: Optional["Node"] = None) -> None:
        self.value = value
        self.next = next


def _check_node(node: Any) -> None:
    if node is not None and not isinstance(node, Node):
        raise ValueError("expected a Node or None, got %r" % type(node).__name__)


def find_cycle_start(head: Optional[Node]) -> Optional[Node]:
    """Return the first node of the cycle, or None if the list ends."""
    _check_node(head)
    slow = fast = head
    while fast is not None and fast.next is not None:
        _check_node(fast.next)
        _check_node(fast.next.next)
        slow = slow.next
        fast = fast.next.next
        if slow is fast:
            # Distance head->entry equals meeting point->entry (mod cycle length).
            slow = head
            while slow is not fast:
                slow = slow.next
                fast = fast.next
            return slow
    return None


def middle_node(head: Optional[Node]) -> Optional[Node]:
    """Return the middle node (the second one for even length); None if empty.

    The list must be acyclic, otherwise the loop never ends.
    """
    _check_node(head)
    slow = fast = head
    while fast is not None and fast.next is not None:
        _check_node(fast.next)
        _check_node(fast.next.next)
        slow = slow.next
        fast = fast.next.next
    return slow
```

## Complexity
Time: O(n) — the meeting phase takes at most t + L rounds and the entry phase at most t more steps, with n = t + L. Space: O(1) — two pointers, no visited-set.

## Variants
- Cycle detection only — stop at the first `slow is fast` and return a bool.
- Middle node — drop the meeting test; stop when fast cannot advance two links.
- Functional-graph duplicate finder — treat `a[i]` as the successor of `i` in an array of values in `[1, n]` with `n + 1` entries; the repeated value is the cycle entry (the C++ source does this).
- Cycle length — after meeting, walk one pointer around until it returns and count the steps.
- Walk-until-seen baseline — the has_loop source marks nodes in a set; correct but O(n) space.

## Common Failure Modes
- Test an empty list (`None`) and a single node: both must return `None` without touching `.next` on `None`.
- Test a single node pointing to itself: the cycle start is that node.
- Test a two-node list with no cycle: guard `fast.next` before reading `fast.next.next`.
- Test that the meeting node is not returned as the cycle start when the tail is non-empty; the second phase is required.
- Test an even-length list's midpoint: expect the second middle, not the first.
- Test a cycle that returns to the head: the entry is the head, so phase two ends immediately.
- Compare nodes by identity, not by value: a list holding duplicate values has no cycle.
- Run the midpoint helper only on acyclic lists; on a cyclic one it never terminates.

## Production Considerations
- Iterative, so there is no recursion-depth limit on long lists.
- Not safe if another thread mutates the list during the walk.
- On corrupt or untrusted structures prefer a bounded step count over trusting the loop to end.
- Streaming or one-way iterators cannot be rewound for phase two; buffer the head or use a visited-set.

## Related Algorithms
- `array.two_pointers` — the structure is an indexed array and the pointers converge or both move forward by position.

## Representative Problems
- Decide whether a singly linked list loops back on itself.
- Return the node at which a loop in a linked list begins, using constant extra memory.
- Return the middle node of a linked list in a single traversal.
- Given `n + 1` integers in `[1, n]`, find the repeated value without modifying the input and with constant extra space.

## Sources
- TheAlgorithms/Python `data_structures/linked_list/floyds_cycle_detection.py` — slow/fast loop and the meet-means-cycle test; the empty-list guard (cycle presence only, no entry search).
- TheAlgorithms/Python `data_structures/linked_list/middle_element_of_linked_list.py` — midpoint by running fast off the end; second middle for even length.
- TheAlgorithms/Python `data_structures/linked_list/has_loop.py` — visited-set baseline for the same question (variant, cost comparison).
- TheAlgorithms/C-Plus-Plus `search/floyd_cycle_detection_algo.cpp` — second phase (reset one pointer, step both by one) to find the entry; functional-graph variant.
- Conflict check: no source disagrees on the core algorithm or O(n) time / O(1) space; the Python sources only detect, and the C++ source supplies the entry-finding phase.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | data_structures/linked_list/floyds_cycle_detection.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | data_structures/linked_list/middle_element_of_linked_list.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | data_structures/linked_list/has_loop.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | search/floyd_cycle_detection_algo.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
