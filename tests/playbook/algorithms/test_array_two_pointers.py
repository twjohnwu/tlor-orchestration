# -*- coding: utf-8 -*-
import random

import pytest

from ._load import load_impl

mod = load_impl("array.two_pointers")
pair_with_sum = mod.pair_with_sum


def _valid(nums, target, result):
    i, j = result
    return 0 <= i < j < len(nums) and nums[i] + nums[j] == target


def _exists(nums, target):
    return any(
        nums[i] + nums[j] == target
        for i in range(len(nums))
        for j in range(i + 1, len(nums))
    )


def test_unit_basic_pairs():
    assert pair_with_sum([2, 7, 11, 15], 9) == (0, 1)
    assert pair_with_sum([2, 7, 11, 15], 26) == (2, 3)
    assert pair_with_sum([2, 7, 11, 15], 8) is None


def test_unit_matches_brute_force():
    rng = random.Random(7)
    for _ in range(300):
        nums = sorted(rng.randint(-8, 8) for _ in range(rng.randint(0, 8)))
        target = rng.randint(-16, 16)
        got = pair_with_sum(nums, target)
        if _exists(nums, target):
            assert got is not None and _valid(nums, target, got)
        else:
            assert got is None


def test_edge_empty_single_duplicates():
    assert pair_with_sum([], 0) is None
    assert pair_with_sum([3], 6) is None
    assert pair_with_sum([3, 3], 6) == (0, 1)
    assert pair_with_sum([1, 3, 3], 6) == (1, 2)


def test_edge_negative_and_boundary():
    assert pair_with_sum([-5, -1, 0, 4], -6) == (0, 1)
    assert pair_with_sum([1, 2, 3], 6) is None


def test_known_example_sorted_target_17():
    assert pair_with_sum([2, 7, 11, 15], 17) == (0, 3)
    assert pair_with_sum([2, 7, 11, 15], 18) == (1, 2)


def test_precondition_reject_unsorted():
    with pytest.raises(ValueError):
        pair_with_sum([15, 2, 11, 7], 13)
