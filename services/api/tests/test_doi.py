from __future__ import annotations

import pytest

from gengscope_api.services.doi import doi_url, normalize_doi


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10.1234/ABC.Def", "10.1234/abc.def"),
        ("https://doi.org/10.1234/ABC.Def", "10.1234/abc.def"),
        ("doi:10.1234/ABC.Def", "10.1234/abc.def"),
        ("  https://dx.doi.org/10.1234/ABC.Def  ", "10.1234/abc.def"),
    ],
)
def test_normalize_doi(raw: str, expected: str) -> None:
    assert normalize_doi(raw) == expected
    assert doi_url(raw) == f"https://doi.org/{expected}"


def test_normalize_doi_rejects_invalid_value() -> None:
    with pytest.raises(ValueError):
        normalize_doi("not-a-doi")
