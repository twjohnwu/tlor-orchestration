import heapq
import random

import pytest

from ._load import load_impl

mod = load_impl("heap.priority_queue")
Heap = mod.BinaryMinHeap


def _drain(h):
    out = []
    while len(h):
        out.append(h.pop())
    return out


def test_unit_push_pop_peek_order():
    h = Heap()
    for x in [5, 3, 8, 1, 9, 2]:
        h.push(x)
    assert h.peek() == 1
    assert len(h) == 6
    assert _drain(h) == [1, 2, 3, 5, 8, 9]


def test_unit_heapify_from_iterable():
    assert _drain(Heap([9, 4, 7, 1, 8, 2, 6])) == [1, 2, 4, 6, 7, 8, 9]


def test_edge_sizes_and_duplicates():
    assert len(Heap()) == 0
    assert _drain(Heap([])) == []
    assert _drain(Heap([4])) == [4]
    assert _drain(Heap([2, 1])) == [1, 2]
    assert _drain(Heap([3, 1, 3, 1, 2, 2])) == [1, 1, 2, 2, 3, 3]
    h = Heap()
    h.push(1)
    assert h.pop() == 1
    assert len(h) == 0
    h.push(7)
    assert h.peek() == 7


def test_edge_interleaved_and_right_child():
    h = Heap([10, 20, 30, 40, 50])
    h.push(5)
    assert h.pop() == 5
    assert h.pop() == 10
    # right child smaller than left must be chosen on sift down
    assert _drain(Heap([1, 9, 2, 10, 11, 3, 4])) == [1, 2, 3, 4, 9, 10, 11]
    assert _drain(Heap([(2, "b"), (1, "z"), (2, "a")])) == [(1, "z"), (2, "a"), (2, "b")]


def test_known_example_sorted_and_matches_heapq():
    data = [103, 9, 1, 7, 11, 15, 25, 201, 209, 107, 5]
    assert _drain(Heap(data)) == sorted(data)
    rng = random.Random(11)
    for _ in range(200):
        items = [rng.randint(-20, 20) for _ in range(rng.randint(0, 25))]
        h = Heap()
        ref = []
        for x in items:
            h.push(x)
            heapq.heappush(ref, x)
            if ref and rng.random() < 0.3:
                assert h.pop() == heapq.heappop(ref)
            if ref:
                assert h.peek() == ref[0]
        assert _drain(h) == sorted(ref)


def test_precondition_reject_empty_pop_and_peek():
    with pytest.raises(ValueError):
        Heap().pop()
    with pytest.raises(ValueError):
        Heap().peek()
    h = Heap([1])
    h.pop()
    with pytest.raises(ValueError):
        h.pop()
    with pytest.raises(ValueError):
        h.peek()


def test_precondition_reject_mixed_type_push_keeps_heap_intact():
    h = Heap([3, 1, 2])
    with pytest.raises(ValueError):
        h.push("a")
    assert len(h) == 3
    assert _drain(h) == [1, 2, 3]


def test_precondition_reject_nan():
    h = Heap([1, 2])
    with pytest.raises(ValueError):
        h.push(float("nan"))
    assert len(h) == 2
    with pytest.raises(ValueError):
        Heap([float("nan")])
    with pytest.raises(ValueError):
        Heap().push(float("nan"))


def test_precondition_reject_mixed_constructor():
    with pytest.raises(ValueError):
        Heap([1, "a"])
    with pytest.raises(ValueError):
        Heap([1, None])
