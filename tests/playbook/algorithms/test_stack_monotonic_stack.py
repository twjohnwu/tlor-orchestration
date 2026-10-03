# -*- coding: utf-8 -*-
import random

import pytest

from ._load import load_impl

mod = load_impl("stack.monotonic_stack")
fn = mod.next_greater_indices


def _brute(values):
    out = []
    for i in range(len(values)):
        nxt = -1
        for j in range(i + 1, len(values)):
            if values[j] > values[i]:
                nxt = j
                break
        out.append(nxt)
    return out


def test_unit_typical():
    assert fn([1, 3, -1, -3, 5, 3, 6, 7]) == [1, 4, 4, 4, 6, 6, 7, -1]
    assert fn([2.5, 1.0, 3.5]) == [2, 2, -1]


def test_unit_random_vs_brute_force():
    rng = random.Random(11)
    for _ in range(300):
        values = [rng.randint(-6, 6) for _ in range(rng.randint(0, 20))]
        assert fn(values) == _brute(values)


def test_edge_empty_single_and_ties():
    assert fn([]) == []
    assert fn([9]) == [-1]
    assert fn([2, 2]) == [-1, -1]
    assert fn([2, 2, 3]) == [2, 2, -1]


def test_edge_monotone_inputs():
    assert fn([5, 4, 3, 2, 1]) == [-1] * 5
    assert fn([1, 2, 3, 4, 5]) == [1, 2, 3, 4, -1]


def test_known_example_daily_readings():
    values = [73, 74, 75, 71, 69, 72, 76, 73]
    assert fn(values) == [1, 2, 6, 5, 5, 6, -1, -1]


def test_precondition_reject_bad_items():
    for bad in ("abc", b"ab", [1, float("nan")], [1, None], [1, "2"], [True, 2], [1, [2]]):
        with pytest.raises(ValueError):
            fn(bad)


def test_edge_huge_int():
    assert fn([10**400]) == [-1]
    assert fn([10**400, 10**401]) == [1, -1]
