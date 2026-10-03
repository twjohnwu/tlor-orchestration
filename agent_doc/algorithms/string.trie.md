---
id: string.trie
name: Trie
category: [string, data-structure]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: data_structures/trie/trie.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/datastructures/trie/Trie.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: data_structures/trie_modern.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
---

# Trie

## Problem Signals
- prefix lookup over a set of strings
- does any stored word start with this prefix
- autocomplete or word suggestions
- count words sharing a prefix
- dictionary membership with many queries
- insert and delete words dynamically

## Use When
- You store many strings and answer exact-membership and prefix queries, each in time proportional to the query length, not the number of stored words.
- Words share long prefixes, so sharing nodes saves memory versus a flat list.
- You need prefix counts or to enumerate words under a prefix.
- Words are inserted and deleted over time.

## Do Not Use When
- You only need exact membership and no prefix queries: use a hash set (`hashing.hash_map`).
- Keys are few or very sparse, with little prefix sharing: a sorted list with binary search uses far less memory.
- You search for one pattern inside a long text: use `string.kmp`.
- Memory is tight and the alphabet is large: use a compressed (radix) trie, see Variants.

## Preconditions
- Every key is a `str` (not `bytes`, not `None`, not a number).
- The characters are hashable symbols compared by equality; case folding, if wanted, is done by the caller before insert and query.
- Empty-string convention (all five operations): `""` is a legal word, stored by marking the root. `insert("")` and `delete("")` work like any word; `search("")` is true only after `insert("")`; `starts_with("")` is true exactly when at least one word is stored (false on an empty trie); `count_prefix("")` equals the number of stored words.
- Deletion and counting assume the trie is not shared across threads without locking.

## Core Invariant
Each node stands for the prefix spelled by the path from the root. A node's `end` flag is true exactly when that prefix was inserted as a word, and its `below` counter equals the number of distinct stored words that have that prefix. A non-root node with `below == 0` is unreachable and has been removed from its parent; the root is never removed, so its `below` (the total word count) can be 0.

## Algorithm
1. Insert: walk from the root one character at a time, creating missing children. At the last node, if the end flag is already set the word is a duplicate, so stop; otherwise set it and add 1 to `below` on every node of the path.
2. Search: walk the path; fail on a missing child. Succeed only if the final node's end flag is set.
3. Prefix test: walk the path; succeed if every character has a child, whatever the end flag.
4. Prefix count: walk the path and return the final node's `below`, or 0 if the walk fails.
5. Delete: if the word is not stored, return false. Otherwise clear the end flag, subtract 1 from `below` along the path, and detach the first node whose count reaches 0 from its parent (that drops the whole dead chain).

## Canonical Implementation
```python
from __future__ import annotations

from typing import Dict


class _Node:
    __slots__ = ("children", "end", "below")

    def __init__(self) -> None:
        self.children = {}  # type: Dict[str, _Node]
        self.end = False
        self.below = 0  # distinct stored words in this subtree (incl. this node)


def _check_key(key: object) -> None:
    if not isinstance(key, str):
        raise ValueError("key must be a str, got %r" % (key,))


class Trie:
    def __init__(self) -> None:
        self._root = _Node()

    def insert(self, word: str) -> bool:
        """Add word; return False if it was already stored."""
        _check_key(word)
        if self.search(word):
            return False
        node = self._root
        node.below += 1
        for ch in word:
            nxt = node.children.get(ch)
            if nxt is None:
                nxt = node.children[ch] = _Node()
            node = nxt
            node.below += 1
        node.end = True
        return True

    def _walk(self, key: str):
        node = self._root
        for ch in key:
            node = node.children.get(ch)
            if node is None:
                return None
        return node

    def search(self, word: str) -> bool:
        _check_key(word)
        node = self._walk(word)
        return node is not None and node.end

    def starts_with(self, prefix: str) -> bool:
        _check_key(prefix)
        node = self._walk(prefix)
        return node is not None and node.below > 0

    def count_prefix(self, prefix: str) -> int:
        """Number of distinct stored words that start with prefix."""
        _check_key(prefix)
        node = self._walk(prefix)
        return node.below if node is not None else 0

    def delete(self, word: str) -> bool:
        """Remove word; return False if it was not stored."""
        _check_key(word)
        if not self.search(word):
            return False
        node = self._root
        node.below -= 1
        for ch in word:
            parent, node = node, node.children[ch]
            node.below -= 1
            if node.below == 0:
                del parent.children[ch]  # the rest of the chain is dead too
                return True
        node.end = False
        return True
```

## Complexity
Time: O(L) per insert, search, prefix test, prefix count and delete, where L is the key length — each does one walk down the path (dict lookup is O(1) on average). Space: O(total characters) in the worst case of no shared prefixes, and less when prefixes are shared; each node also pays for its child dict.

## Variants
- Delete by flag only — clear the end flag and leave the nodes; simpler but leaks memory and keeps `starts_with` true for dead prefixes (the Python source prunes empty chains).
- Counted trie — a per-node counter gives prefix counts and lets delete know when to prune (the Java source counts insertions with multiplicity, so repeated inserts raise the count; the canonical form above counts distinct words).
- Array children — a fixed-size child array indexed by character (the C++ source uses 26 slots for lowercase letters): faster, no hashing, but wastes memory on sparse nodes and limits the alphabet.
- Compressed (radix) trie — merge single-child chains into one edge labelled with a string; fewer nodes, harder insert/delete (the Python repo ships one in `radix_tree.py`).
- Word enumeration — depth-first walk from the prefix node collects all words under it, for autocomplete.

## Common Failure Modes
- Test that `search("app")` is false when only `"apple"` was inserted, while `starts_with("app")` is true (a prefix is not a word).
- Test inserting the same word twice: the second returns false and `count_prefix` does not double count.
- Test that deleting a word that is a prefix of another keeps the longer word findable.
- Test that deleting the longer word keeps the shorter one findable, and that `starts_with` is false afterwards for the removed branch.
- Test deleting a missing word returns false and changes nothing.
- Test the empty string: here it is a legal word (the Python source allows it, marking the root), while the Java source treats an empty key as not a word. The sources differ in convention, so decide it for your project and pin it with a test.
- Test `contains` semantics when porting: the Java `contains` answers true for any stored prefix, not only whole words; use the end flag if you need whole words.
- Test non-`str` keys (`None`, `bytes`, an int) are rejected.

## Production Considerations
- Memory dominates: a Python node with a dict costs far more than the character it holds; `__slots__` helps, array children or a radix tree help more for large dictionaries.
- Deletion and the walk are iterative here; a recursive delete (as in the Python source) can hit the recursion limit for very long keys.
- The Java source notes the O(N * L) space bound; plan capacity from total characters, not word count.
- Normalise (case, Unicode form) before insert and query, or equal-looking words will not match.
- Not thread-safe: concurrent insert and delete can corrupt the counters.

## Related Algorithms
- hashing.hash_map — switch when no prefix queries are needed; a hash set is simpler and smaller.
- string.kmp — switch when matching one pattern inside a long text rather than querying a word set.

## Representative Problems
- Given a set of words, answer many queries asking whether a word is present.
- Given a set of words, report whether any word starts with a given prefix.
- Given a set of words, return how many start with each query prefix.
- Suggest completions for a partially typed word from a dictionary.
- Maintain a changing word list with insertions and deletions while answering prefix queries.

## Sources
- TheAlgorithms/Python data_structures/trie/trie.py — dict-children node with an end flag, insert/find walk, recursive delete that prunes empty chains and tolerates missing words, empty-string-as-word behaviour.
- williamfiset/Algorithms src/main/java/com/williamfiset/algorithms/datastructures/trie/Trie.java — per-node counters for prefix counting and pruning, O(L) time and O(N * L) space statement, null-key rejection, the conflicting empty-key convention and prefix-style `contains`.
- TheAlgorithms/C-Plus-Plus data_structures/trie_modern.cpp — fixed 26-slot array children for lowercase-only keys (array versus dict trade-off), end-of-word flag, recursive removal that frees a node only when it has no children.
- Conflict noted: empty-string handling differs between the Python and Java sources; it is a convention difference, not a difference in the core algorithm, so confidence stays high.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | data_structures/trie/trie.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/datastructures/trie/Trie.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
| TheAlgorithms/C-Plus-Plus | data_structures/trie_modern.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
