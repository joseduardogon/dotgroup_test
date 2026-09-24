"""Text normalization helpers used to make searches forgiving and deterministic."""

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def normalize_for_search(value: str) -> str:
    """Fold a string into its canonical searchable form.

    SQLite's ``LIKE`` is only case-insensitive for ASCII and knows nothing about
    diacritics, which would make ``"joao"`` miss ``"João"``. Instead of relying on
    database collations we persist a normalized shadow column and normalize the
    user's query the same way.

    The pipeline is: Unicode NFKD decomposition, removal of combining marks,
    ``casefold`` (the aggressive, Unicode-aware lower-casing) and collapsing of
    whitespace runs.

    Args:
        value: Arbitrary user supplied text.

    Returns:
        The normalized text, e.g. ``"  Saramago,  José "`` -> ``"saramago, jose"``.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _WHITESPACE.sub(" ", stripped.casefold()).strip()
