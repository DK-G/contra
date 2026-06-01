"""Tests for the numeric grounding guard in generate.py."""

from src.pipeline.generate import _unsupported_numbers


def test_no_numbers_returns_empty():
    assert _unsupported_numbers("no numbers here", "abstract") == set()


def test_number_in_abstract_is_supported():
    assert _unsupported_numbers("improvement of 85%", "result was 85% in the study") == set()


def test_number_not_in_abstract_is_unsupported():
    result = _unsupported_numbers("improvement of 85%", "abstract with no numbers")
    assert "85" in result


def test_comma_decimal_normalised_to_dot():
    # "6,0" in hypothesis should match "6.0" in abstract
    assert _unsupported_numbers("value of 6,0 was found", "value of 6.0") == set()


def test_multiple_numbers_partial_support():
    result = _unsupported_numbers("85% and 0.7", "the number 0.7 is here")
    assert "85" in result
    assert "0.7" not in result


def test_empty_inputs_return_empty():
    assert _unsupported_numbers("", "") == set()
    assert _unsupported_numbers("", "some text") == set()


def test_hypothesis_subset_of_abstract_numbers():
    assert _unsupported_numbers("effect of 0.5 and 1.2", "0.5 and 1.2 were measured") == set()


def test_float_with_leading_zero():
    result = _unsupported_numbers("accuracy 0.92", "no numbers in abstract")
    assert "0.92" in result
