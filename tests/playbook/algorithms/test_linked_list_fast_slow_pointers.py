# -*- coding: utf-8 -*-
import random

import pytest

from ._load import load_impl

mod = load_impl("linked_list.fast_slow_pointers")
Node = mod.Node
find_cycle_start = mod.find_cycle_start
middle_node = mod.middle_node


def build(n, cycle_to=None):
    """Chain of n nodes; the last links back to node `cycle_to` if given."""
    nodes = [Node(i) for i in range(n)]
    for a, b in zip(nodes, nodes[1:]):
        a.next = b
    if cycle_to is not None and n:
        nodes[-1].next = nodes[cycle_to]
    return nodes


def oracle_start(head):
    seen = set()
    while head is not None:
        if id(head) in seen:
            return head
        seen.add(id(head))
        head = head.next
    return None


def test_unit_cycle_with_tail():
    nodes = build(6, cycle_to=2)
    assert find_cycle_start(nodes[0]) is nodes[2]


def test_unit_no_cycle():
    assert find_cycle_start(build(5)[0]) is None


def test_unit_middle_odd_and_even():
    odd = build(5)
    even = build(6)
    assert middle_node(odd[0]) is odd[2]
    assert middle_node(even[0]) is even[3]


def test_unit_random_matches_oracle():
    rng = random.Random(11)
    for _ in range(300):
        n = rng.randint(0, 12)
        cycle_to = rng.randint(0, n - 1) if n and rng.random() < 0.6 else None
        nodes = build(n, cycle_to)
        head = nodes[0] if nodes else None
        assert find_cycle_start(head) is oracle_start(head)
        if cycle_to is None:
            assert middle_node(head) is (nodes[n // 2] if nodes else None)


def test_edge_empty_and_single():
    assert find_cycle_start(None) is None
    assert middle_node(None) is None
    one = Node(1)
    assert find_cycle_start(one) is None
    assert middle_node(one) is one


def test_edge_self_loop_and_head_cycle():
    one = Node(1)
    one.next = one
    assert find_cycle_start(one) is one
    nodes = build(4, cycle_to=0)
    assert find_cycle_start(nodes[0]) is nodes[0]


def test_edge_two_nodes_and_duplicate_values():
    two = build(2)
    assert find_cycle_start(two[0]) is None
    assert middle_node(two[0]) is two[1]
    a, b, c = Node(7), Node(7), Node(7)
    a.next, b.next = b, c
    assert find_cycle_start(a) is None


def test_known_example_cycle_at_second_node():
    # 3 -> 2 -> 0 -> -4 -> back to the node holding 2
    n3, n2, n0, n4 = Node(3), Node(2), Node(0), Node(-4)
    n3.next, n2.next, n0.next, n4.next = n2, n0, n4, n2
    assert find_cycle_start(n3) is n2


def test_precondition_reject_non_node_head():
    with pytest.raises(ValueError):
        find_cycle_start([1, 2, 3])
    with pytest.raises(ValueError):
        middle_node(5)


def test_precondition_reject_non_node_link():
    a, b = Node(1), Node(2)
    a.next, b.next = b, "oops"
    with pytest.raises(ValueError):
        find_cycle_start(a)
    with pytest.raises(ValueError):
        middle_node(a)


def _bad_link_chains():
    # a non-Node link at position 1, 2 and 3 of the chain
    yield Node(1, 5)
    yield Node(1, Node(2, "oops"))
    yield Node(1, Node(2, Node(3, "z")))


def test_precondition_reject_bad_link_at_each_position():
    for head in _bad_link_chains():
        with pytest.raises(ValueError):
            find_cycle_start(head)
    for head in _bad_link_chains():
        with pytest.raises(ValueError):
            middle_node(head)
