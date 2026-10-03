import random

import pytest

from ._load import load_impl

mod = load_impl("string.kmp")


def brute(text, pattern):
    return [i for i in range(len(text) - len(pattern) + 1) if text.startswith(pattern, i)]


def test_unit_basic_matches():
    assert mod.kmp_search("abcabcabc", "abc") == [0, 3, 6]
    assert mod.kmp_search("hello world", "world") == [6]
    assert mod.kmp_search("abc", "xyz") == []


def test_unit_overlapping_matches():
    assert mod.kmp_search("aaaa", "aa") == [0, 1, 2]
    assert mod.kmp_search("abababa", "aba") == [0, 2, 4]


def test_unit_random_vs_brute_force():
    rng = random.Random(7)
    for _ in range(300):
        text = "".join(rng.choice("ab") for _ in range(rng.randint(0, 20)))
        pattern = "".join(rng.choice("ab") for _ in range(rng.randint(1, 5)))
        assert mod.kmp_search(text, pattern) == brute(text, pattern)


def test_edge_empty_text_and_long_pattern():
    assert mod.kmp_search("", "a") == []
    assert mod.kmp_search("ab", "abc") == []


def test_edge_pattern_equals_text_and_at_end():
    assert mod.kmp_search("abc", "abc") == [0]
    assert mod.kmp_search("xxabc", "abc") == [2]
    assert mod.kmp_search("a", "a") == [0]


def test_known_example_prefix_function():
    assert mod.prefix_function("aabaabaaa") == [0, 1, 0, 1, 2, 3, 4, 5, 2]
    assert mod.prefix_function("abcabcd") == [0, 0, 0, 1, 2, 3, 0]


def test_known_example_search_with_fallback():
    text = "P@TTerNabcdefP@TTerNP@TTerNabcdefabcdefabcdefabcdefP@TTerN"
    assert mod.kmp_search(text, "P@TTerN") == [0, 13, 20, 51]
    assert mod.kmp_search("ABABZABABYABABX", "ABABX") == [10]


def test_precondition_reject_empty_pattern():
    with pytest.raises(ValueError):
        mod.kmp_search("abc", "")


def test_precondition_reject_non_str():
    with pytest.raises(ValueError):
        mod.kmp_search(None, "a")
    with pytest.raises(ValueError):
        mod.kmp_search("abc", 5)


@pytest.mark.parametrize("bad", [None, 5, ["a", "b"], "", b"ab"])
def test_precondition_prefix_function_rejects_bad_pattern(bad):
    with pytest.raises(ValueError):
        mod.prefix_function(bad)
