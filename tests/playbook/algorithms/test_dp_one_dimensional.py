import random

import pytest

from ._load import load_impl

mod = load_impl("dp.one_dimensional")
min_coins = mod.min_coins


def _brute(coins, amount):
    best = {0: 0}
    frontier = [0]
    while frontier:
        nxt = []
        for s in frontier:
            for c in coins:
                t = s + c
                if t <= amount and t not in best:
                    best[t] = best[s] + 1
                    nxt.append(t)
        frontier = nxt
    return best.get(amount, -1)


def test_unit_basic_amounts():
    assert min_coins([1, 2, 5], 11) == 3
    assert min_coins([2], 3) == -1
    assert min_coins([1, 3, 4], 6) == 2


def test_edge_zero_empty_and_duplicates():
    assert min_coins([1, 2], 0) == 0
    assert min_coins([], 0) == 0
    assert min_coins([], 5) == -1
    assert min_coins([5], 5) == 1
    assert min_coins([2, 2, 2], 4) == 2


def test_known_example_greedy_fails():
    # greedy would take 4+1+1 (3 coins); optimum is 3+3 (2 coins)
    assert min_coins([1, 3, 4], 6) == 2
    assert min_coins([186, 419, 83, 408], 6249) == 20


def test_unit_matches_brute_force_oracle():
    rng = random.Random(7)
    for _ in range(150):
        coins = [rng.randint(1, 9) for _ in range(rng.randint(0, 4))]
        amount = rng.randint(0, 30)
        assert min_coins(coins, amount) == _brute(coins, amount)


@pytest.mark.parametrize(
    "coins, amount",
    [([0, 1], 3), ([-1, 2], 3), ([1], -1), ([True], 3), ([1], True), ([1.5], 3), ([1], 2.0)],
)
def test_precondition_reject_invalid_inputs(coins, amount):
    with pytest.raises(ValueError):
        min_coins(coins, amount)


def test_edge_generator_coins_are_materialised():
    assert min_coins((c for c in [1, 2, 5]), 11) == 3
