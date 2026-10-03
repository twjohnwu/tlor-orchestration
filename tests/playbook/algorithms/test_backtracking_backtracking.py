import itertools
import random

import pytest

from ._load import load_impl

impl = load_impl("backtracking.backtracking")
unique_permutations = impl.unique_permutations


def test_unit_distinct_values():
    assert unique_permutations([1, 2, 3]) == [
        [1, 2, 3], [1, 3, 2], [2, 1, 3], [2, 3, 1], [3, 1, 2], [3, 2, 1]]


def test_unit_partial_size():
    assert unique_permutations([1, 2, 3], 2) == [
        [1, 2], [1, 3], [2, 1], [2, 3], [3, 1], [3, 2]]


def test_unit_random_matches_brute_force():
    rng = random.Random(11)
    for _ in range(30):
        n = rng.randint(0, 6)
        items = [rng.randint(0, 3) for _ in range(n)]
        k = rng.randint(0, n)
        expected = sorted(set(itertools.permutations(items, k)))
        got = unique_permutations(items, k)
        assert sorted(tuple(p) for p in got) == expected
        assert len(got) == len(expected)


def test_edge_empty_and_size_zero():
    assert unique_permutations([]) == [[]]
    assert unique_permutations([1, 2], 0) == [[]]


def test_edge_single_and_all_equal():
    assert unique_permutations([7]) == [[7]]
    assert unique_permutations([4, 4, 4]) == [[4, 4, 4]]


def test_edge_results_are_independent_lists():
    first = unique_permutations([1, 2])
    first[0].append(99)
    assert unique_permutations([1, 2]) == [[1, 2], [2, 1]]


def test_known_example_duplicates():
    assert unique_permutations([1, 1, 2]) == [[1, 1, 2], [1, 2, 1], [2, 1, 1]]


def test_known_example_string_items():
    assert unique_permutations("aab", 2) == [["a", "a"], ["a", "b"], ["b", "a"]]


@pytest.mark.parametrize("size", [-1, 1.5, "2", True, 4])
def test_precondition_reject_size(size):
    with pytest.raises(ValueError):
        unique_permutations([1, 2, 3], size)


def test_edge_shared_key_list_result_unchanged():
    assert unique_permutations([2, 1, 2, 3], 3) == [
        list(p) for p in sorted(set(itertools.permutations([2, 1, 2, 3], 3)),
                                key=lambda t: [[2, 1, 3].index(v) for v in t])]


def test_edge_equal_values_deduplicated_first_object_kept():
    got = unique_permutations([1, True, 1.0])
    assert got == [[1, 1, 1]]
    assert got[0][0] is not True and type(got[0][0]) is int
