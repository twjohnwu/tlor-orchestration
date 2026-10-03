import itertools
import random

import pytest

from ._load import load_impl

impl = load_impl("dp.two_dimensional")
lcs_length = impl.lcs_length


def _brute(a, b):
    best = 0
    for r in range(len(a) + 1):
        for idx in itertools.combinations(range(len(a)), r):
            sub = [a[i] for i in idx]
            it = iter(b)
            if all(x in it for x in sub):
                best = max(best, r)
    return best


def test_unit_basic_strings():
    assert lcs_length("ABCBDAB", "BDCABA") == 4
    assert lcs_length("abc", "abc") == 3
    assert lcs_length("abc", "xyz") == 0


def test_unit_lists_and_tuples():
    assert lcs_length([1, 2, 3, 4], (2, 4, 6)) == 2


def test_unit_random_matches_brute_force():
    rng = random.Random(3)
    for _ in range(60):
        a = [rng.randint(0, 3) for _ in range(rng.randint(0, 8))]
        b = [rng.randint(0, 3) for _ in range(rng.randint(0, 8))]
        assert lcs_length(a, b) == _brute(a, b)
        assert lcs_length(a, b) == lcs_length(b, a)


def test_edge_empty_and_single():
    assert lcs_length("", "") == 0
    assert lcs_length("", "abc") == 0
    assert lcs_length("a", "a") == 1
    assert lcs_length("a", "b") == 0


def test_edge_duplicates():
    assert lcs_length("aaaa", "aa") == 2
    assert lcs_length("abab", "baba") == 3


def test_known_example_clrs():
    assert lcs_length("AGGTAB", "GXTXAYB") == 4


def test_precondition_reject_non_sequence():
    with pytest.raises(ValueError):
        lcs_length(123, "abc")
    with pytest.raises(ValueError):
        lcs_length("abc", (c for c in "abc"))
    with pytest.raises(ValueError):
        lcs_length(None, [])
