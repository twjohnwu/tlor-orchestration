---
id: hashing.hash_map
name: Hash Map Lookup
category: [hashing]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: data_structures/hashing/hash_map.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: hashing/chaining.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/datastructures/hashtable/HashTableLinearProbing.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
---

# Hash Map Lookup

## Problem Signals
- find whether a value was seen before, or how often
- pair or complement lookup (target minus current element)
- group items by a computed key
- need average constant-time insert, lookup and delete
- deduplicate while keeping first-seen order or original indices

## Use When
- Keys are hashable and compared by equality, and no ordering of keys is needed.
- A single pass can store what it has seen and answer later queries by key.
- Average O(1) per operation matters more than worst-case guarantees.

## Do Not Use When
- Keys must be iterated in sorted order or queried by range: use a balanced tree or sort plus `search.binary_search`.
- The input is already sorted and extra memory is not allowed: use `array.two_pointers`.
- The query is a sum over a contiguous range: use `array.prefix_sum`.
- Keys are small dense integers: use a plain array indexed by the key.
- Adversarial keys can force collisions and worst-case latency matters: use a tree-based map or a randomized hash seed.

## Preconditions
- Every key is hashable (`hash(key)` succeeds) and equal keys have equal hashes.
- A key's hash and equality do not change while it is stored.
- The load factor limit is a number strictly between 0 and 1 (open addressing needs at least one free slot to end a probe).
- The initial capacity is a positive integer.

## Core Invariant
Every stored key sits on the probe path that starts at its home slot (`hash(key)` modulo capacity) and walks forward without crossing an empty slot. A lookup can therefore stop at the first empty slot and conclude the key is absent. Deleting by writing an empty slot would break that path for later keys, so a deleted slot is marked with a tombstone, which lookups walk past and inserts may reuse. The table always keeps at least one empty slot, so probes terminate. The used-slot ratio (live plus tombstones) stays at or under the larger of the load limit and one half: a rebuild is triggered before an insert would pass the limit, but for a very small limit (for example 0.01) the rebuilt table can still sit above it, up to one half.

## Algorithm
1. Compute the home slot as `hash(key)` modulo the table size.
2. Lookup: walk forward one slot at a time; stop with a hit on an equal key, stop with a miss on an empty slot, skip tombstones.
3. Insert: if adding one entry would exceed the load limit, rebuild first (double the size if live entries are dense, otherwise rebuild at the same size to drop tombstones). Then probe; overwrite on an equal key, otherwise place the entry in the first tombstone seen, or the empty slot that ended the probe.
4. Delete: find the key as in lookup, replace its slot with a tombstone, and decrement the live count.
5. Chaining variant: each slot holds a list of entries; steps 2 to 4 operate on that list only.

## Canonical Implementation
```python
from __future__ import annotations

from typing import Any, Hashable, List, Optional

_EMPTY = object()
_TOMBSTONE = object()


class HashMap:
    """Open-addressing hash map with linear probing and tombstone deletes."""

    def __init__(self, capacity: int = 8, max_load: float = 0.75) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        if isinstance(max_load, bool) or not isinstance(max_load, (int, float)) \
                or not 0.0 < max_load < 1.0:
            raise ValueError("max_load must be strictly between 0 and 1")
        self._max_load = max_load
        self._slots: List[Any] = [_EMPTY] * capacity  # _EMPTY, _TOMBSTONE or (key, value)
        self._live = 0
        self._used = 0  # live entries plus tombstones

    def __len__(self) -> int:
        return self._live

    @staticmethod
    def _hash(key: Hashable) -> int:
        try:
            return hash(key)
        except TypeError:
            raise ValueError("key is not hashable: %r" % (key,))

    def _find(self, key: Hashable) -> int:
        """Return the slot holding key, or -1 if absent."""
        size = len(self._slots)
        i = self._hash(key) % size
        for _ in range(size):
            slot = self._slots[i]
            if slot is _EMPTY:
                return -1
            if slot is not _TOMBSTONE and slot[0] == key:
                return i
            i = (i + 1) % size
        return -1

    def _rebuild(self, size: int) -> None:
        old = self._slots
        self._slots = [_EMPTY] * size
        self._live = self._used = 0
        for slot in old:
            if slot is not _EMPTY and slot is not _TOMBSTONE:
                self._place(slot[0], slot[1])

    def _place(self, key: Hashable, value: Any) -> None:
        size = len(self._slots)
        i = self._hash(key) % size
        reusable = -1
        while self._slots[i] is not _EMPTY:
            slot = self._slots[i]
            if slot is _TOMBSTONE:
                if reusable < 0:
                    reusable = i
            elif slot[0] == key:
                self._slots[i] = (key, value)
                return
            i = (i + 1) % size
        if reusable >= 0:
            i = reusable  # reusing a tombstone adds no used slot
        else:
            self._used += 1
        self._slots[i] = (key, value)
        self._live += 1

    def put(self, key: Hashable, value: Any) -> None:
        self._hash(key)  # reject unhashable keys before touching the table
        size = len(self._slots)
        if self._used + 1 > size * self._max_load:
            dense = self._live + 1 > size * self._max_load / 2
            self._rebuild(size * 2 if dense else size)
        self._place(key, value)

    def get(self, key: Hashable, default: Optional[Any] = None) -> Any:
        i = self._find(key)
        return default if i < 0 else self._slots[i][1]

    def delete(self, key: Hashable) -> bool:
        """Remove key; return True if it was present."""
        i = self._find(key)
        if i < 0:
            return False
        self._slots[i] = _TOMBSTONE
        self._live -= 1
        return True
```

## Complexity
Time: O(1) average per put, get and delete under a good hash and a bounded load factor; O(n) worst case when many keys collide. A rebuild costs O(n) but is amortized O(1) per insert because the table doubles. Space: O(peak n), not O(current n), because the table never shrinks after deletes; the constant factor is set by the load limit.

## Variants
- Separate chaining — each slot holds a list of entries; lookup scans one list, and the load factor may exceed 1 (the chaining source scans a list per slot by hash).
- Linear versus other probing — step by 1 (the Python source), by a constant coprime to the capacity (the Java source adjusts capacity until the gcd is 1), quadratic, or double hashing; non-unit steps spread clusters but must still visit every slot.
- Shrink on sparse — the Python source halves the table when it gets sparse; the canonical form only grows.
- Counting or grouping dictionary — value is a counter or a list, built in one pass.
- Two-sum pattern — store each seen value with its index; for each new element look up `target - value` before inserting it.

## Common Failure Modes
- Test that deleting a key does not hide other keys that collided with it (tombstone, not empty slot).
- Test that overwriting an existing key keeps the length unchanged.
- Test that a delete-then-reinsert cycle many times does not fill the table with tombstones or loop forever.
- Test that a missing key returns the default and does not raise.
- Test that an unhashable key (list, dict) is rejected with a clear error.
- Test that a load limit of 0 or 1 or more is rejected, as is a boolean passed for a numeric argument.
- Test that keys with equal hashes but different values (forced collisions) both stay retrievable.
- Test that mutating a key object after insertion is flagged as forbidden in the caller, since its slot no longer matches its hash.

## Production Considerations
- In real Python code use the built-in `dict` or `collections.Counter`; this form is for understanding or for porting to a language without one.
- Python's string hashing is randomized per process, so iteration order of a hand-built table can differ between runs; do not assert on slot order.
- A rebuild pauses one insert for O(n); preallocate capacity when the final size is known.
- Hash flooding: attacker-chosen keys can turn every operation into O(n); use a keyed or randomized hash for untrusted input.
- Floats that are NaN never compare equal to themselves, so such a key can be stored but never found.

## Related Algorithms
- array.prefix_sum — combine with a map of prefix values to count subarrays with a target sum.
- array.two_pointers — pair search on sorted input with O(1) extra space instead of a map.

## Representative Problems
- Given a list of numbers and a target, return the positions of two numbers that add up to the target (store each value with its index, look up the complement before inserting the current value).
- Count how many times each distinct item occurs in a sequence.
- Find the first element of a sequence that appears twice.
- Group strings that are rearrangements of each other by a canonical key.
- Detect whether any two entries in a list share the same identifier.

## Sources
- TheAlgorithms/Python data_structures/hashing/hash_map.py — open addressing with linear probing, a deleted-slot marker, load-factor-triggered doubling and sparse shrinking; basis of the Core Invariant and Algorithm.
- TheAlgorithms/C-Plus-Plus hashing/chaining.cpp — separate chaining by modulus with a list per slot; the chaining variant and the note that the hash function is replaceable.
- williamfiset/Algorithms HashTableLinearProbing.java — probing step that must be coprime to the capacity, load-factor and null-key rejection tests, and tombstone behaviour under forced collisions; used for Variants and Preconditions. The three sources agree on slot-by-hash storage and average O(1) cost; they differ only in collision strategy and probe step, which are recorded as variants, not conflicts.
- Evidence files for MD5, SHA-1, SHA-256 and string polynomial hashing were skipped as false matches (cryptographic and rolling hashes, not a key-value lookup).

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | data_structures/hashing/hash_map.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | hashing/chaining.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/datastructures/hashtable/HashTableLinearProbing.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
