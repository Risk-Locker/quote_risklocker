"""Unit tests for the safe AST formula evaluator in road_tax_engine."""

from __future__ import annotations

import pytest
from app.services.road_tax_engine import _eval_formula


def test_ast_evaluator_valid_arithmetic():
    # Standard linear formula: 380 + (cc - 2000) * 1.0
    res = _eval_formula("380 + (cc - 2000) * 1.0", 2500)
    assert res == 880.0

    # Negative numbers and unary operators
    res_unary = _eval_formula("+100 - -50", 1500)
    assert res_unary == 150.0

    # Multiplication and float division
    res_div = _eval_formula("(cc / 2) + 10.5", 2000)
    assert res_div == 1010.5


def test_ast_evaluator_rejects_unsafe_operations():
    # Exponentiation
    assert _eval_formula("2 ** 10", 1800) is None
    assert _eval_formula("cc ** 2", 1800) is None

    # Division by zero
    assert _eval_formula("100 / 0", 1800) is None
    assert _eval_formula("cc / (2000 - 2000)", 2000) is None

    # Code execution / Built-ins / Arbitrary variables
    assert _eval_formula("__import__('os').system('dir')", 1800) is None
    assert _eval_formula("open('/etc/passwd')", 1800) is None
    assert _eval_formula("x + y", 1800) is None

    # Bitwise and shift operations
    assert _eval_formula("1 << 4", 1800) is None
    assert _eval_formula("100 & 50", 1800) is None


def test_ast_evaluator_handles_empty_or_malformed():
    assert _eval_formula("", 1800) is None
    assert _eval_formula(None, 1800) is None  # type: ignore
    assert _eval_formula("   ", 1800) is None
    assert _eval_formula("++--**", 1800) is None
    assert _eval_formula("380 + (cc -", 1800) is None
