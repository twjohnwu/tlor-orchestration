# -*- coding: utf-8 -*-
import random

import pytest

from ._load import load_impl

mod = load_impl("hashing.hash_map")
HashMap = mod.HashMap


class Collider:
    """Every instance hashes alike, forcing probe chains."""

    def __init__(self, tag):
        self.tag = tag

    def __hash__(self):
        return 7

    def __eq__(self, other):
        return isinstance(other, Collider) and self.tag == other.tag


def two_sum(nums, target):
    seen = HashMap()
    for i, x in enumerate(nums):
        j = seen.get(target - x)
        if j is not None:
            return (j, i)
        seen.put(x, i)
    return None


def test_unit_put_get_overwrite_delete():
    m = HashMap()
    m.put("a", 1)
    m.put("b", 2)
    assert m.get("a") == 1 and m.get("b") == 2
    m.put("a", 10)
    assert m.get("a") == 10 and len(m) == 2
    assert m.delete("a") is True
    assert m.get("a") is None and m.get("a", "dflt") == "dflt"
    assert len(m) == 1
    assert m.delete("a") is False


def test_unit_collisions_survive_delete():
    m = HashMap()
    keys = [Collider(i) for i in range(5)]
    for i, k in enumerate(keys):
        m.put(k, i)
    assert m.delete(keys[1]) is True
    for i, k in enumerate(keys):
        assert m.get(k, "gone") == ("gone" if i == 1 else i)
    m.put(keys[1], 99)  # reuses the tombstone
    assert m.get(keys[1]) == 99 and len(m) == 5


def test_edge_empty_single_and_growth():
    m = HashMap(capacity=1)
    assert len(m) == 0 and m.get(1) is None and m.delete(1) is False
    m.put(1, "x")
    assert m.get(1) == "x"
    for i in range(200):
        m.put(i, i * i)
    assert len(m) == 200
    assert all(m.get(i) == i * i for i in range(200))


def test_edge_delete_reinsert_churn_terminates():
    m = HashMap(capacity=4)
    for round_ in range(500):
        m.put(round_, round_)
        assert m.delete(round_) is True
    assert len(m) == 0
    m.put("end", 1)
    assert m.get("end") == 1 and m.get("missing") is None


def test_edge_equal_keys_across_types_and_none_value():
    m = HashMap()
    m.put(1, "int")
    m.put(1.0, "float")  # 1 == 1.0 and equal hashes: same key
    assert len(m) == 1 and m.get(1) == "float"
    m.put("k", None)
    assert len(m) == 2 and m.get("k", "dflt") is None


def test_known_example_two_sum():
    assert two_sum([2, 7, 11, 15], 9) == (0, 1)
    assert two_sum([3, 2, 4], 6) == (1, 2)
    assert two_sum([3, 3], 6) == (0, 1)
    assert two_sum([1, 2, 3], 100) is None


def test_known_example_random_vs_dict_oracle():
    rng = random.Random(12345)
    m, oracle = HashMap(capacity=2), {}
    for _ in range(3000):
        k = rng.randrange(60)
        op = rng.randrange(3)
        if op == 0:
            v = rng.randrange(1000)
            m.put(k, v)
            oracle[k] = v
        elif op == 1:
            assert m.delete(k) == (oracle.pop(k, _MISSING) is not _MISSING)
        else:
            assert m.get(k, _MISSING) == oracle.get(k, _MISSING)
        assert len(m) == len(oracle)


_MISSING = object()


@pytest.mark.parametrize("key", [[1], {}, {1, 2}])
def test_precondition_reject_unhashable_key(key):
    m = HashMap()
    with pytest.raises(ValueError):
        m.put(key, 1)
    with pytest.raises(ValueError):
        m.get(key)
    with pytest.raises(ValueError):
        m.delete(key)
    assert len(m) == 0


@pytest.mark.parametrize("load", [0, 0.0, 1, 1.0, 1.5, -0.2, True, "0.5", None])
def test_precondition_reject_max_load(load):
    with pytest.raises(ValueError):
        HashMap(max_load=load)


@pytest.mark.parametrize("cap", [0, -3, True, 2.5, "8", None])
def test_precondition_reject_capacity(cap):
    with pytest.raises(ValueError):
        HashMap(capacity=cap)
