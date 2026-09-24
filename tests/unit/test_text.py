"""Unit tests for text normalization."""

import pytest

from library_api.core.text import normalize_for_search


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("João", "joao"),
        ("  Saramago,   José ", "saramago, jose"),
        ("STRASSE", "strasse"),
        ("Straße", "strasse"),
        ("ﬁm", "fim"),
        ("", ""),
    ],
)
def test_normalize_for_search(raw: str, expected: str) -> None:
    """Text is case-, accent- and whitespace-folded."""
    assert normalize_for_search(raw) == expected
