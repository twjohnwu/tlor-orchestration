import random

import pytest

from ._load import load_impl

mod = load_impl("stack.stack")
is_balanced = mod.is_balanced


def _oracle(text):
    # Brute force: repeatedly delete adjacent matched pairs.
    s = [c for c in text if c in "()[]{}"]
    s = "".join(s)
    prev = None
    while prev != s:
        prev = s
        for pair in ("()", "[]", "{}"):
            s = s.replace(pair, "")
    return s == ""


def test_unit_typical():
    assert is_balanced("([]{})") is True
    assert is_balanced("[()]{}{[()()]()}") is True
    assert is_balanced("[(])") is False
    assert is_balanced("1+2*(3-4)") is True


def test_edge_boundaries():
    assert is_balanced("") is True
    assert is_balanced("abc") is True
    assert is_balanced(")") is False
    assert is_balanced("((") is False
    assert is_balanced("))((") is False
    assert is_balanced("(" * 50 + ")" * 50) is True


def test_known_example_crossed_and_deep():
    assert is_balanced("{[()]}") is True
    assert is_balanced("{[(])}") is False
    assert is_balanced("((())") is False


def test_randomized_matches_oracle():
    rng = random.Random(7)
    for _ in range(300):
        text = "".join(rng.choice("()[]{}a") for _ in range(rng.randint(0, 12)))
        assert is_balanced(text) == _oracle(text), text


@pytest.mark.parametrize("bad", [None, 5, True, b"()", ["("], ("(",)])
def test_precondition_reject_non_string(bad):
    with pytest.raises(ValueError):
        is_balanced(bad)
