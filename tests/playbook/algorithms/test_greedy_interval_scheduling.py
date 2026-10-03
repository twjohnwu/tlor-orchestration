import itertools
import random

import pytest

from ._load import load_impl

impl = load_impl("greedy.interval_scheduling")
select = impl.select_max_intervals


def test_unit_earliest_end_beats_earliest_start():
    assert select([(0, 10), (1, 2), (3, 4)]) == [(1, 2), (3, 4)]


def test_unit_earliest_end_beats_shortest():
    assert select([(0, 5), (4, 7), (6, 10)]) == [(0, 5), (6, 10)]


def test_unit_touching_intervals_compatible_and_input_untouched():
    data = [(2, 3), (1, 2)]
    assert select(data) == [(1, 2), (2, 3)]
    assert data == [(2, 3), (1, 2)]


def test_unit_random_matches_brute_force():
    rng = random.Random(11)
    for _ in range(150):
        n = rng.randint(0, 7)
        ivs = []
        for _ in range(n):
            s = rng.randint(0, 10)
            ivs.append((s, s + rng.randint(0, 4)))
        got = select(ivs)
        assert len(got) == _oracle(ivs)
        for a, b in itertools.combinations(sorted(got, key=lambda iv: iv[1]), 2):
            assert a[1] <= b[0]


def _oracle(ivs):
    best = 0
    for mask in range(1 << len(ivs)):
        pick = [ivs[i] for i in range(len(ivs)) if mask >> i & 1]
        if all(a[1] <= b[0] or b[1] <= a[0] for a, b in itertools.combinations(pick, 2)):
            best = max(best, len(pick))
    return best


def test_edge_empty_and_single():
    assert select([]) == []
    assert select([(3, 5)]) == [(3, 5)]


def test_edge_duplicates_and_zero_length():
    assert select([(1, 4), (1, 4)]) == [(1, 4)]
    assert select([(3, 3), (1, 5)]) == [(3, 3)]


def test_known_example_classic_activities():
    acts = [(0, 6), (1, 4), (3, 5), (5, 7), (5, 9), (8, 9)]
    assert select(acts) == [(1, 4), (5, 7), (8, 9)]


def test_precondition_reject_end_before_start():
    with pytest.raises(ValueError):
        select([(1, 2), (5, 3)])


def test_precondition_reject_bad_shape_and_types():
    with pytest.raises(ValueError):
        select([(1, 2, 3)])
    with pytest.raises(ValueError):
        select([(True, 2)])
    with pytest.raises(ValueError):
        select([(1.5, 2)])


@pytest.mark.parametrize("bad", [5, None, {1, 2}, "ab", (1,), (1, 2, 3)])
def test_precondition_reject_malformed_shapes(bad):
    with pytest.raises(ValueError):
        select([bad])
