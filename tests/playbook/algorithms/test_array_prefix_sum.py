import random

import pytest

from ._load import load_impl

impl = load_impl("array.prefix_sum")
range_sums = impl.range_sums


def test_unit_basic_ranges():
    assert range_sums([1, 2, 3], [(0, 2), (1, 2), (2, 2)]) == [6, 5, 3]


def test_unit_negative_elements_and_generator_queries():
    assert range_sums([4, -2, 7, -1], ((i, j) for i, j in [(0, 3), (1, 1)])) == [8, -2]


def test_unit_random_matches_brute_force():
    rng = random.Random(7)
    values = [rng.randint(-50, 50) for _ in range(40)]
    queries = []
    for _ in range(200):
        a = rng.randrange(40)
        b = rng.randrange(a, 40)
        queries.append((a, b))
    assert range_sums(values, queries) == [sum(values[a:b + 1]) for a, b in queries]


def test_edge_empty_queries_and_empty_array():
    assert range_sums([], []) == []
    assert range_sums([5], []) == []


def test_edge_single_element_and_boundaries():
    assert range_sums([9], [(0, 0)]) == [9]
    assert range_sums([2, 2, 2], [(0, 0), (2, 2), (0, 2)]) == [2, 2, 6]


def test_known_example_mixed_array():
    # worked example in the style of the C++ source's self-test, shifted to 0-based
    values = [123, 0, 2, -2, 5, 24, 0, 23, -1, -1]
    assert range_sums(values, [(0, 9), (3, 5), (4, 8)]) == [173, 27, 51]


@pytest.mark.parametrize("query", [(-1, 2), (2, 3), (2, 1), (0, 3)])
def test_precondition_reject_bad_range(query):
    with pytest.raises(ValueError):
        range_sums([1, 2, 3], [query])


@pytest.mark.parametrize("query", [5, (1,), (0, 1, 2), None])
def test_precondition_reject_non_pair_query(query):
    with pytest.raises(ValueError):
        range_sums([1, 2, 3], [query])


def test_precondition_reject_empty_array_query():
    with pytest.raises(ValueError):
        range_sums([], [(0, 0)])


def test_precondition_reject_bool_and_non_int():
    with pytest.raises(ValueError):
        range_sums([1, True, 3], [(0, 1)])
    with pytest.raises(ValueError):
        range_sums([1, 2, 3], [(False, 1)])
    with pytest.raises(ValueError):
        range_sums([1, 2, 3], [(0, True)])
    with pytest.raises(ValueError):
        range_sums([1, 2.5, 3], [(0, 1)])
