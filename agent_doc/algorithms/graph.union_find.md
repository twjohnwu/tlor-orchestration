---
id: graph.union_find
name: Union-Find (DSU)
category: [graph, data-structure]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: data_structures/disjoint_set/disjoint_set.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: data_structures/disjoint_set/alternate_disjoint_set.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: data_structures/dsu_union_rank.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: data_structures/dsu_path_compression.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/datastructures/unionfind/UnionFind.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
---

# Union-Find (DSU)

## Problem Signals
- "are these two items in the same group", "same component", "connected"
- groups merge over time and never split
- count the groups, or the size of a group, after a series of merges
- detect whether adding an edge closes a cycle in an undirected graph
- process edges in sorted order and keep only those joining different groups

## Use When
- Elements are known up front (or numbered 0..n-1) and the only change is merging groups.
- Many interleaved merge and same-group queries must each cost almost constant time.
- Building a spanning tree or forest by accepting an edge only if its endpoints are in different groups.
- Offline connectivity where edges are only added.

## Do Not Use When
- Edges are removed or groups must split (needs rollback DSU with union by size and no compression, or offline divide and conquer over time).
- You need the actual path between two nodes or hop distance (use graph.traversal.dfs or a BFS).
- The graph is directed and reachability matters; DSU only models undirected connectivity (use graph.traversal.dfs plus strongly connected components).
- The graph is static and you need the components once (a single graph.traversal.dfs pass is simpler).

## Preconditions
- Every element maps to an integer index in 0..n-1 (map other keys to indices first).
- The element count n is known before the first operation and is a non-negative integer.
- Only merges happen; no operation undoes a merge.
- Every element passed to find/union/connected is a valid index; otherwise reject.

## Core Invariant
The parent links form a forest in which each tree is one group and its root is the group's representative; a root points to itself. Merging links one root under the other, so two elements share a group exactly when they reach the same root. Linking the shallower or smaller tree under the other bounds tree height by O(log n), and rewriting parent links during find so they point closer to the root flattens trees without ever changing which elements share a root.

## Algorithm
1. `DisjointSet(n)` starts n singleton groups: parent[i] = i, size[i] = 1, count = n. Reject a bool or negative n.
2. `find(x)`: validate x, walk up parent links to the root, then in a second pass point every visited node directly at the root (iterative two-pass path compression, no recursion).
3. `union(a, b)`: ra = find(a), rb = find(b). If ra == rb, return False; nothing changed.
4. Otherwise attach the root of the smaller group under the root of the larger one (union by size), add the sizes, decrement `count`, and return True.
5. `connected(a, b)` is find(a) == find(b); `size(x)` is the size stored at find(x); `count` is the current number of groups.

## Canonical Implementation
```python
from __future__ import annotations

from typing import List


class DisjointSet:
    """Union-find over elements 0..n-1 with path compression and union by size."""

    def __init__(self, n: int) -> None:
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError("n must be a non-negative integer, got %r" % (n,))
        self._parent = list(range(n))  # type: List[int]
        self._size = [1] * n  # type: List[int]
        self._count = n

    @property
    def count(self) -> int:
        """Current number of groups."""
        return self._count

    def _check(self, x: int) -> None:
        if isinstance(x, bool) or not isinstance(x, int) or not 0 <= x < len(self._parent):
            raise ValueError("element %r is not an index in 0..%d" % (x, len(self._parent) - 1))

    def find(self, x: int) -> int:
        self._check(x)
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        # Second pass: point every node on the path straight at the root.
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: int, b: int) -> bool:
        """Merge the groups of a and b; False if they were already one group."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self._size[ra] < self._size[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        self._size[ra] += self._size[rb]
        self._count -= 1
        return True

    def connected(self, a: int, b: int) -> bool:
        return self.find(a) == self.find(b)

    def size(self, x: int) -> int:
        """Number of elements in x's group."""
        return self._size[self.find(x)]
```

## Complexity
Time: O(n) to build, then O(alpha(n)) amortized per find/union with both union by size/rank and path compression, where alpha is the inverse Ackermann function (at most 4 for any practical n). Space: O(n) for the parent and size arrays.

## Variants
- Union by rank — keeps an upper bound on tree height instead of exact sizes; same bounds, cannot answer group-size queries.
- Compression only or rank only — each alone gives O(log n) per operation, not O(alpha(n)); both together are needed for the near-constant bound.
- Path halving or splitting — one-pass iterative compression, no second loop and no recursion.
- Recursive find — shorter code (parent[x] = find(parent[x])) but recursion depth can reach n before the trees are flat.
- Rollback DSU — union by size without compression, with an undo stack, for offline deletion.
- Weighted DSU — stores an offset to the parent so relative differences between elements can be answered.
- Hash-keyed DSU — dictionary parents for non-integer or sparse keys.

## Common Failure Modes
- Test that union of two elements already in one group returns False and leaves the group count unchanged.
- Test that find on a long chain built by repeated unions does not recurse deeply (use the iterative form).
- Test that union compares roots, not the raw arguments, before linking (linking non-roots corrupts sizes).
- Test that the group count drops by exactly one per successful merge and never otherwise.
- Test that an out-of-range or negative index raises instead of silently wrapping (Python negative indexing hides it).
- Test that size queries use the root's size, since sizes of non-roots are stale.

## Production Considerations
- Use the iterative find; recursive versions overflow the stack on adversarial input in many languages and in CPython.
- Element keys that are not dense integers need a mapping step; a dictionary-backed DSU costs extra memory and hashing time.
- Compression mutates state during a read, so concurrent readers need a lock or a compression-free find.
- Merging cannot be undone; if deletions are needed, switch to a rollback design up front.
- Memory is two integer arrays of length n; for very large n use typed arrays.

## Related Algorithms
- graph.traversal.dfs — when you need the paths or an ordering, or the graph is processed once and is static.

## Representative Problems
- Given a stream of pairwise "same group" facts and queries, answer whether two items are in one group.
- Count the connected components of an undirected graph after adding edges one by one.
- Build a minimum spanning tree by sorting edges and keeping those that join different components.
- Decide whether an undirected edge list contains a cycle.
- Merge accounts or records that share any identifier and report the final groups.

## Sources
- TheAlgorithms/Python data_structures/disjoint_set/disjoint_set.py — node-based form with union by rank and recursive path compression; ranks bump only on equal-rank merges.
- TheAlgorithms/Python data_structures/disjoint_set/alternate_disjoint_set.py — list-backed form that tracks set counts and returns a success flag from merge (basis for union returning a bool).
- TheAlgorithms/C-Plus-Plus data_structures/dsu_union_rank.cpp — rank-only variant, documents O(log n) find without compression.
- TheAlgorithms/C-Plus-Plus data_structures/dsu_path_compression.cpp — compression-only variant. Its comments claim O(1) find for one heuristic alone; that is looser than the standard analysis (single heuristic gives O(log n) amortized), so the bound here follows the source below, not that comment.
- williamfiset/Algorithms .../unionfind/UnionFind.java — union by size plus compression, states O(alpha(n)) amortized, rejects non-positive size, offers connected, component size and component count.
- Skipped as not evidence for this entry: data_structures/disjoint_set/__init__.py (empty) and the secondary notebooks (used only for awareness of rollback/persistent variants).

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | data_structures/disjoint_set/disjoint_set.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | data_structures/disjoint_set/alternate_disjoint_set.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | data_structures/dsu_union_rank.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| TheAlgorithms/C-Plus-Plus | data_structures/dsu_path_compression.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/datastructures/unionfind/UnionFind.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
