# -*- coding: utf-8 -*-
import random

import pytest

from ._load import load_impl

mod = load_impl("search.binary_search")
binary_search = mod.binary_search


def _oracle(items, target):
    for i, v in enumerate(items):
        if v == target:
            return i
    return -1


def test_unit_present_and_absent():
    items = [0, 5, 7, 10, 15]
    assert binary_search(items, 0) == 0
    assert binary_search(items, 7) == 2
    assert binary_search(items, 15) == 4
    assert binary_search(items, 6) == -1


def test_unit_matches_brute_force():
    rng = random.Random(11)
    for _ in range(300):
        items = sorted(rng.randint(-6, 6) for _ in range(rng.randint(0, 10)))
        target = rng.randint(-8, 8)
        assert binary_search(items, target) == _oracle(items, target)


def test_unit_works_on_strings_and_tuples():
    assert binary_search(["a", "c", "d"], "c") == 1
    assert binary_search(("a", "c", "d"), "f") == -1


def test_edge_empty_and_single():
    assert binary_search([], 3) == -1
    assert binary_search([4], 4) == 0
    assert binary_search([4], 3) == -1
    assert binary_search([4], 5) == -1


def test_edge_duplicates_return_leftmost():
    assert binary_search([1, 2, 2, 2, 4], 2) == 1
    assert binary_search([2, 2, 2], 2) == 0
    assert binary_search([0, 5, 7, 10, 10, 10], 10) == 3


def test_edge_boundaries():
    items = [1, 3, 5, 7]
    assert binary_search(items, 0) == -1
    assert binary_search(items, 8) == -1
    assert binary_search(items, 1) == 0
    assert binary_search(items, 7) == 3


def test_known_example_sorted_run():
    items = [1, 2, 4, 4, 4, 6, 7]
    assert binary_search(items, 4) == 2
    assert binary_search(items, 5) == -1


def test_precondition_reject_unsorted():
    with pytest.raises(ValueError):
        binary_search([3, 1, 2], 1)
    with pytest.raises(ValueError):
        binary_search([1, 2, 3, 2], 2)
