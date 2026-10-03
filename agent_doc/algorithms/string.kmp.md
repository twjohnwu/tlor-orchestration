---
id: string.kmp
name: KMP String Matching
category: [string, matching]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: strings/prefix_function.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: strings/knuth_morris_pratt.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: strings/knuth_morris_pratt.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/strings/KMP.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
  - repo: ADJA/algos
    path: Strings/PrefixFunction.cpp
    commit: 244d382be168208d669db0f90ea64cc6be06e3d2
    license: MIT
  - repo: imeplusplus/icpc-notebook
    path: strings/kmp.cpp
    commit: d6db5cb0e077ed674fd16828f3c1e452a222d103
    license: MIT
  - repo: imeplusplus/icpc-notebook
    path: strings/kmp_automaton.cpp
    commit: d6db5cb0e077ed674fd16828f3c1e452a222d103
    license: MIT
---

# KMP String Matching

## Problem Signals
- find every occurrence of a pattern in a text, including overlapping ones
- exact substring search with a guaranteed linear time bound
- longest proper prefix that is also a suffix (border) of a string
- smallest period of a string, or "is the string a repetition of a block"
- text arrives as a stream and the pattern is fixed

## Use When
- One fixed, non-empty pattern is searched in a text and you need worst-case O(n + m), not average-case.
- You need all match start positions, overlaps included.
- You need the prefix function (border table) itself, e.g. for periodicity or "shortest string with this prefix and suffix" questions.
- The text is consumed one character at a time and cannot be re-read (the matcher state is a single integer).

## Do Not Use When
- Many patterns are searched in one text: use an Aho-Corasick automaton (a trie plus failure links, see `string.trie`).
- A one-off search on small inputs where the language's built-in `find` is enough: use the built-in.
- Approximate or wildcard matching (edits, mismatches): use dynamic programming or bit-parallel matching.
- Many equal-length windows must be compared, or a hash is acceptable: use Rabin-Karp rolling hash.
- Only the Z-values (match length at every position against the whole string) are needed: use the Z-algorithm.

## Preconditions
- Pattern and text are sequences of comparable symbols (the canonical code takes `str`).
- The pattern is non-empty (an empty pattern matches everywhere; reject it or define that case yourself).
- Symbol equality is exact and consistent (no case folding or normalization applied mid-run).

## Core Invariant
`fail[i]` is the length of the longest proper prefix of `pattern[:i + 1]` that is also its suffix. While scanning the text, `k` is the length of the longest prefix of the pattern that is a suffix of the text read so far. On a mismatch, the next candidate for `k` is `fail[k - 1]`, because every shorter prefix that can still match is a border of the current one. After a full match (`k == m`) the scan resets `k` to `fail[m - 1]`, not to 0, so the matched suffix is reused for overlapping matches. The text index never moves backward, and `k` drops at most as many times as it has risen, which gives the linear bound. Building `fail` is the same scan of the pattern against itself.

## Algorithm
1. Reject an empty pattern.
2. Build `fail`: set `fail[0] = 0`, `k = 0`; for each `i` from 1 to `m - 1`, while `k > 0` and `pattern[i] != pattern[k]` set `k = fail[k - 1]`; if they are equal increment `k`; store `fail[i] = k`.
3. Scan the text with `k = 0`: for each character, while `k > 0` and it differs from `pattern[k]` set `k = fail[k - 1]`; if it equals `pattern[k]` increment `k`.
4. When `k == m`, record the match start `i - m + 1`, then set `k = fail[m - 1]` so overlapping matches are found.
5. Return all recorded starts (empty list if none).

## Canonical Implementation
```python
from __future__ import annotations

from typing import List


def prefix_function(pattern: str) -> List[int]:
    """fail[i] = length of the longest proper border of pattern[:i + 1]."""
    if not isinstance(pattern, str):
        raise ValueError("pattern must be a str")
    if not pattern:
        raise ValueError("pattern must be non-empty")
    fail = [0] * len(pattern)
    k = 0
    for i in range(1, len(pattern)):
        while k > 0 and pattern[i] != pattern[k]:
            k = fail[k - 1]
        if pattern[i] == pattern[k]:
            k += 1
        fail[i] = k
    return fail


def kmp_search(text: str, pattern: str) -> List[int]:
    """Return every start index where pattern occurs in text (overlaps included)."""
    if not isinstance(text, str) or not isinstance(pattern, str):
        raise ValueError("text and pattern must both be str")
    if not pattern:
        raise ValueError("pattern must be non-empty")
    fail = prefix_function(pattern)
    starts = []
    k = 0  # length of the pattern prefix that ends at the current text index
    for i, ch in enumerate(text):
        while k > 0 and ch != pattern[k]:
            k = fail[k - 1]
        if ch == pattern[k]:
            k += 1
        if k == len(pattern):
            starts.append(i - k + 1)
            k = fail[k - 1]
    return starts
```

## Complexity
Time: O(n + m) — the text index only advances, and `k` can fall only as often as it has risen, so the inner `while` loops cost O(n) and O(m) amortized in total. Space: O(m) for the failure table, plus the output list.

## Variants
- First-match only — return at the first `k == m` instead of collecting (the Python and C++ sources do this).
- KMP automaton — precompute a full transition table `next[state][symbol]`; O(m * alphabet) preprocessing, then exactly one step per text character with no inner loop (icpc-notebook `kmp_automaton.cpp`).
- Off-by-one table — store `fail` with a leading `-1` and length `m + 1` (C++ and icpc-notebook sources); same algorithm, different indexing.
- Z-algorithm — compute match lengths against the whole string; search by running it on `pattern + sep + text` with a separator absent from both.
- Prefix function alone — periods and borders: `m - fail[m - 1]` is the shortest period candidate.

## Common Failure Modes
- Test that overlapping occurrences are all reported (`"aaaa"` with `"aa"` gives `[0, 1, 2]`): after a full match, fall back to `fail[m - 1]`, not to 0.
- Test that an empty pattern raises instead of reading `pattern[0]` out of range.
- Test a pattern longer than the text returns `[]`.
- Test periodic patterns such as `"aabaabaaa"`, whose table is `[0, 1, 0, 1, 2, 3, 4, 5, 2]`; a table built with a single `if` instead of the fallback `while` gets this wrong.
- Test that the result equals a brute-force scan on random small-alphabet strings.
- Test the text-equals-pattern and pattern-at-the-very-end cases (off-by-one on the start index `i - m + 1`).

## Production Considerations
- Sources disagree on empty-pattern behavior (the C++ source returns 0, the Python source would index out of range, the Java source would read `charAt(0)` on an empty string); the canonical code rejects it explicitly.
- Python's `str.find` and `re` are implemented in C and usually beat a pure-Python KMP; use KMP for the prefix table, for streaming, or when a guaranteed worst case matters.
- Streaming: keep only `k` between chunks; no text is buffered.
- The failure table is reusable across many texts for the same pattern; build it once.
- The automaton variant trades O(m * alphabet) memory for branch-free scanning; avoid it for large alphabets.

## Related Algorithms
- `string.trie` — when matching a set of patterns; extending a trie with failure links gives Aho-Corasick.

## Representative Problems
- Report every position where a short word occurs inside a long document.
- Find the shortest string whose repetition builds a given string.
- Find the longest prefix of a string that is also its suffix.
- Decide whether one string is a rotation of another.
- Count how many times a pattern occurs in a character stream, overlaps allowed.

## Sources
- TheAlgorithms/Python `strings/prefix_function.py` — the prefix-function recurrence and its O(n) bound (primary).
- TheAlgorithms/Python `strings/knuth_morris_pratt.py` — search loop with fallback via the table; test table `[0, 1, 0, 1, 2, 3, 4, 5, 2]` for `"aabaabaaa"` (primary; first-match only).
- TheAlgorithms/C-Plus-Plus `strings/knuth_morris_pratt.cpp` — the `-1`-offset table variant and the empty-pattern-returns-0 choice (primary).
- williamfiset/Algorithms `.../strings/KMP.java` — returns all matches including overlaps via `j = arr[j - 1]` after a match (primary).
- ADJA/algos `Strings/PrefixFunction.cpp` — the 1-indexed prefix function agrees with the other builders (primary).
- imeplusplus/icpc-notebook `strings/kmp.cpp` — compact find-all form (secondary, variant only).
- imeplusplus/icpc-notebook `strings/kmp_automaton.cpp` — automaton variant (secondary, variant only).
- No conflict on the core algorithm or complexity; the only divergence is empty-pattern handling (see Production Considerations).

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | strings/prefix_function.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | strings/knuth_morris_pratt.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | strings/knuth_morris_pratt.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/strings/KMP.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
| ADJA/algos | Strings/PrefixFunction.cpp | 244d382be168208d669db0f90ea64cc6be06e3d2 | MIT |
| imeplusplus/icpc-notebook | strings/kmp.cpp | d6db5cb0e077ed674fd16828f3c1e452a222d103 | MIT |
| imeplusplus/icpc-notebook | strings/kmp_automaton.cpp | d6db5cb0e077ed674fd16828f3c1e452a222d103 | MIT |
