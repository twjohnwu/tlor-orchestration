---
id: heap.priority_queue
name: Heap / Priority Queue
category: [heap]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: data_structures/heap/heap.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: data_structures/heap/min_heap.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: data_structures/queues/priority_queue_using_list.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: data_structures/binaryheap.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/datastructures/priorityqueue/BinaryHeap.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
---

# Heap / Priority Queue

## Problem Signals
- repeatedly take the smallest (or largest) pending item
- top k, k-th smallest or largest, running minimum or maximum
- merge several sorted streams
- schedule by priority, deadline, or cost
- items arrive online and the best one is needed after each arrival
- "extract min", "extract max", "peek at the best"

## Use When
- Items are inserted and removed interleaved, and each removal must return the current extreme.
- Only the extreme matters; a full sorted order of the pending set is not needed after each step.
- You keep a bounded set of the best k items seen so far in a stream.
- A graph or scheduling algorithm needs "cheapest frontier item next".

## Do Not Use When
- All data is known up front and you need it fully ordered once: sort the list (`sorted`).
- Items must come out in arrival order: use a FIFO queue (`collections.deque`).
- You need the newest item first: use `stack.stack`.
- You need arbitrary rank queries, range queries, or deletion of arbitrary keys in O(log n): use a balanced tree or an indexed structure.
- Priorities take only a handful of distinct small values: use one bucket queue per level.

## Preconditions
- All items are mutually comparable with a total order (for example all numbers, or all tuples with comparable fields); the class raises `ValueError` on mixed, unorderable, or NaN items before changing the heap.
- Pop and peek are issued only when the heap is non-empty; an empty pop or peek is an error.
- Items are not mutated in place while stored; to change a priority, push a new entry (lazy deletion) or use an indexed heap.
- Decide up front whether the smallest or the largest comes first; a max heap is a min heap over negated keys or a reversed comparison.

## Core Invariant
Items live in an array viewed as a complete binary tree: the children of index i sit at 2i+1 and 2i+2, its parent at (i-1)//2. Heap order holds at every node: a parent is never greater than either child (min heap). So index 0 is always the minimum. Push appends at the end and swaps upward while smaller than its parent; pop moves the last item to the root and swaps downward with the smaller child while it is greater than that child. Each repair touches one root-to-leaf path and restores heap order everywhere else.

## Algorithm
1. Store items in a list; the root (index 0) is the best item.
2. Push: append the item, then sift up: while it has a parent and is smaller than it, swap with the parent.
3. Peek: return item 0; fail if the list is empty.
4. Pop: fail if empty. Remember item 0, move the last item to index 0 (or just remove it when it was the only one), then sift down: while a child is smaller, swap with the smaller child.
5. Build from n items in O(n): sift down every internal node from the last parent back to the root.

## Canonical Implementation
```python
from __future__ import annotations

from typing import Any, Iterable, List


class BinaryMinHeap:
    """Array-backed binary min-heap supporting push, pop, and peek."""

    def __init__(self, items: Iterable[Any] = ()) -> None:
        self._a: List[Any] = list(items)
        # Validate before any reordering; a failure leaves no half-built heap.
        for item in self._a:
            self._check(item, self._a[0])
        # Heapify: repair every internal node, deepest first.
        try:
            for i in range(len(self._a) // 2 - 1, -1, -1):
                self._sift_down(i, self._a[i], len(self._a))
        except TypeError as exc:
            raise ValueError("items are not mutually comparable: %s" % exc)

    def __len__(self) -> int:
        return len(self._a)

    def peek(self) -> Any:
        if not self._a:
            raise ValueError("peek from an empty heap")
        return self._a[0]

    def push(self, item: Any) -> None:
        # Validate first so a rejected item leaves the heap untouched.
        self._check(item, self._a[0] if self._a else item)
        self._a.append(item)
        try:
            self._sift_up(len(self._a) - 1)
        except TypeError as exc:
            # The sift compares read-only before moving anything, so dropping the
            # appended item restores the heap exactly.
            self._a.pop()
            raise ValueError("%r is not comparable with the heap items: %s" % (item, exc))

    def pop(self) -> Any:
        if not self._a:
            raise ValueError("pop from an empty heap")
        if len(self._a) == 1:
            return self._a.pop()
        top = self._a[0]
        last = self._a[-1]
        try:
            # Sift `last` down from the root over the first n-1 slots; nothing is
            # written until every comparison succeeded, so a failure changes nothing.
            self._sift_down(0, last, len(self._a) - 1)
        except TypeError as exc:
            raise ValueError("heap items are not mutually comparable: %s" % exc)
        self._a.pop()
        return top

    @staticmethod
    def _check(item: Any, ref: Any) -> None:
        """Reject NaN and items not comparable with ref (one existing element)."""
        if item != item:
            raise ValueError("NaN has no consistent order: %r" % (item,))
        try:
            item < ref
            ref < item
        except TypeError:
            raise ValueError("%r is not comparable with %r" % (item, ref))

    def _sift_up(self, i: int) -> None:
        a = self._a
        item = a[i]
        path = [i]  # slots the item passes through; decided before any write
        while i > 0:
            parent = (i - 1) // 2
            if not item < a[parent]:
                break
            path.append(parent)
            i = parent
        self._shift(path, item)

    def _sift_down(self, i: int, item: Any, n: int) -> None:
        """Place item at slot i and sift it down within the first n slots."""
        a = self._a
        path = [i]
        while True:
            child = 2 * i + 1
            if child >= n:
                break
            if child + 1 < n and a[child + 1] < a[child]:
                child += 1
            if not a[child] < item:
                break
            path.append(child)
            i = child
        self._shift(path, item)

    def _shift(self, path: List[int], item: Any) -> None:
        """Pull each slot's value one step along path, then drop item at its end."""
        a = self._a
        for k in range(len(path) - 1):
            a[path[k]] = a[path[k + 1]]
        a[path[-1]] = item
```

## Complexity
Time: push and pop are O(log n) — each walks one root-to-leaf path of a tree with height log2 n; peek is O(1); building from n items is O(n) because most nodes sit near the leaves and sift only a short way. Space: O(n) — one array slot per item, no pointers.

## Variants
- Max heap — flip the comparison, or store negated keys; the max-heap source (`heap.py`) also adds an in-place heap sort by repeatedly moving the root to the end.
- Decrease-key heap — keeps a map from item to array index so a priority can be lowered and sifted up in O(log n) (`min_heap.py`).
- Lazy deletion — push a new entry instead of editing; skip stale entries on pop. Simpler than an index map.
- Removal at an index — swap with the last item, shrink, then sift down and, if the item did not move, sift up (Java `BinaryHeap`); removal by value costs O(n) to find the item.
- Fixed-capacity heap — rejects a push when full (the C++ source prints an overflow message and drops the key).
- Bucket / fixed-level queue — one FIFO list per priority level; stable within a level but only for a small closed set of priorities (`priority_queue_using_list.py`).
- d-ary heap — more than two children per node; shallower tree, cheaper decrease-key, costlier pop.

## Common Failure Modes
- Test pop and peek on an empty heap raise your chosen error, not `IndexError` from the list or a silent `None`.
- Test a heap built from an unsorted list pops items in sorted order (checks heapify bounds, especially lists of length 0, 1, 2).
- Test duplicate keys all come out, each once.
- Test interleaved push and pop: pushing an item smaller than the current root makes it the next pop.
- Test popping the last remaining item leaves a valid empty heap (the root and the last item are the same slot).
- Test child selection: when the right child is smaller than the left, sift down must pick the right one.
- Test the heap does not order stably: equal keys with different payloads may come out in any order; add a counter to the key if arrival order matters.
- Test that tuples with a non-comparable second field are not compared when the first fields differ, and add a tiebreaker if they can tie.

## Production Considerations
- In Python prefer `heapq` (`heappush`, `heappop`, `heapify`, `nlargest`, `nsmallest`): it is a C-accelerated min heap on a plain list. The class here is for understanding or for when a custom ordering or index map is needed. For a max heap with `heapq`, push negated keys.
- `queue.PriorityQueue` wraps `heapq` with locking for threads; use it only when threads share the queue.
- Comparability is checked against one existing element only (the root, or the first item at build time); this is a guard against common mixed-type mistakes, not a proof of a total order over all items (for example NaN nested inside a tuple passes).
- Push `(priority, seq, payload)` tuples with a monotonically increasing `seq` so payloads are never compared and arrival order breaks ties (the dijkstra entry does this).
- A tuple pair that compares fine at the root can still fail deeper (for example `(1, 2)`, then `(2, 'a')`, then `(2, 3)`); the class turns that into `ValueError` and leaves the heap unchanged, but the fix is the `seq` tiebreaker, not catching the error.
- Peek and pop on empty differ between sources (Java returns null, the Python max heap raises a bare exception, the C++ min read is unchecked); pick one explicit behaviour and test it.
- To track the k largest of a stream, keep a min heap of size k and replace the root when a bigger item arrives: O(n log k) time, O(k) space.
- Sorting with a heap is O(n log n) but not stable and usually slower than the built-in sort in Python.

## Related Algorithms
- `graph.shortest_path.dijkstra` — uses the heap as its frontier; switch to it for weighted shortest paths.
- `greedy.interval_scheduling` — often needs a heap of end times or deadlines to pick the next item.

## Representative Problems
- Find the k-th largest element in an unsorted collection.
- Merge several sorted lists into one sorted list.
- Maintain the median of a stream of numbers using two heaps.
- Schedule tasks so the highest-priority ready task runs next.
- Return the k most frequent items in a sequence.
- Repeatedly combine the two smallest items until one remains.

## Sources
- TheAlgorithms/Python data_structures/heap/heap.py — max-heap with index arithmetic, build by sifting down internal nodes, extract and insert, heap sort; empty extract raises a bare exception (failure mode).
- TheAlgorithms/Python data_structures/heap/min_heap.py — min-heap sift up and sift down, decrease-key via an index map (variant).
- TheAlgorithms/Python data_structures/queues/priority_queue_using_list.py — fixed levels of FIFO lists and an element-priority list queue; overflow and underflow errors (variant; not a binary heap).
- TheAlgorithms/C-Plus-Plus data_structures/binaryheap.cpp — array min-heap with fixed capacity, extract-min, decrease-key, delete-key; same 2i+1 / 2i+2 layout (variant).
- williamfiset/Algorithms .../priorityqueue/BinaryHeap.java — min heap with swim/sink, O(n) heapify from a collection, removeAt with sink-then-swim, O(n) removal by value, null return on empty (variant, edge cases).
- The sources agree on the array layout, sift-up on insert, sift-down on extract, O(log n) push/pop and O(n) build; they differ only in empty-pop behaviour and capacity policy (noted above), not in the core algorithm. The binary-heap-adjacent sorting files, the Fibonacci heap, the d-ary heap, and the two Dijkstra files were not used: they repeat the same sift logic or belong to other entries.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | data_structures/heap/heap.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | data_structures/heap/min_heap.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | data_structures/queues/priority_queue_using_list.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | data_structures/binaryheap.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/datastructures/priorityqueue/BinaryHeap.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
