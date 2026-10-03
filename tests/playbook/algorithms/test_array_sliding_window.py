# -*- coding: utf-8 -*-
import random

import pytest

from ._load import load_impl

mod = load_impl("array.sliding_window")
fn = mod.sliding_window_maximum


def _brute(values, k):
    return [max(values[i:i + k]) for i in range(len(values) - k + 1)]


def test_unit_typical():
    assert fn([1, 3, -1, -3, 5, 3, 6, 7], 3) == [3, 3, 5, 5, 6, 7]
    assert fn([4, 2, 12, 3], 1) == [4, 2, 12, 3]


def test_unit_random_vs_brute_force():
    rng = random.Random(7)
    for _ in range(200):
        n = rng.randint(0, 25)
        values = [rng.randint(-10, 10) for _ in range(n)]
        k = rng.randint(1, 8)
        assert fn(values, k) == _brute(values, k)


def test_edge_empty_single_and_boundaries():
    assert fn([], 3) == []
    assert fn([5], 1) == [5]
    assert fn([1, 2, 3], 3) == [3]
    assert fn([1, 2], 5) == []


def test_edge_duplicates_and_monotone():
    assert fn([2, 2, 2, 2], 2) == [2, 2, 2]
    assert fn([5, 4, 3, 2, 1], 3) == [5, 4, 3]
    assert fn([1, 2, 3, 4, 5], 3) == [3, 4, 5]
    assert fn([-3, -1, -2], 2) == [-1, -1]


def test_known_example_classic():
    assert fn([1, 3, -1, -3, 5, 3, 6, 7], 3) == [3, 3, 5, 5, 6, 7]
    assert fn([9, 11], 2) == [11]


def test_precondition_reject_window_size():
    for bad in (0, -1, 1.5, "2", None, True):
        with pytest.raises(ValueError):
            fn([1, 2, 3], bad)


def test_unit_duplicates_keep_front_max():
    assert fn([5, 5, 1], 3) == [5]
    assert fn([5, 5, 1], 2) == [5, 5]
