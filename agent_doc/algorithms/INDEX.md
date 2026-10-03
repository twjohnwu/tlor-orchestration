<!-- GENERATED FILE - do not edit. Regenerate: python3 playbook/scripts/build_index.py -->
# Algorithm INDEX

Generated from `playbook/metadata/algorithms/*.yaml`; regenerate with `python3 playbook/scripts/build_index.py`.
Retrieval: Grep this table for the problem's signal words, then Read the matching entry; see README.md.

| id | name | signals | avoid_when | confidence |
|---|---|---|---|---|
| array.sliding_window | Sliding Window | contiguous subarray; window of size k; k consecutive elements; longest substring with constraint; maximum of each window; running window sum | non-contiguous subset; arbitrary subset; static range queries; negative values window; running median | high |
| array.two_pointers | Two Pointers | sorted array; pair with target sum; two sum sorted; three sum; unique triplets; converge from both ends; O(1) extra space | unsorted array; unsorted input; original indices required; running window condition; single target lookup; linked list cycle | medium |
| graph.shortest_path.dijkstra | Dijkstra's Algorithm | weighted graph; shortest path; cheapest path; non-negative edge weights; single source; minimum cost to reach; network delay | negative edge weights; negative edges; unweighted graph; equal edge costs; all-pairs paths; admissible heuristic | high |
| graph.traversal.bfs | Breadth-First Search | fewest edges; minimum number of hops; shortest path unweighted graph; level by level; reachable from source; grid maze equal step cost; nearest node | weighted graph; different edge costs; depth-first order; wide graph reachability; zero-one weights; DAG dependency ordering | high |
| search.binary_search | Binary Search | sorted array; find position of value; first or last occurrence; insertion point; lower bound upper bound; monotone predicate; search on the answer; O(log n) lookup; logarithmic time; log n; search space halving | unsorted array; unsorted data; membership lookup; pair target sum; dynamic min max; linked list; predicate not monotone | high |
