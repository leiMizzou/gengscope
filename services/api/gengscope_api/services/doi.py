from __future__ import annotations

import re
from urllib.parse import unquote


DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def normalize_doi(value: str) -> str:
    if value is None:
        raise ValueError("DOI is required")
    doi = unquote(str(value)).strip()
    doi = re.sub(r"\s+", "", doi)
    doi = doi.removeprefix("doi:")
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = doi.strip(" .")
    doi = doi.lower()
    if not DOI_RE.match(doi):
        raise ValueError(f"Invalid DOI: {value}")
    return doi


def doi_url(doi: str) -> str:
    return f"https://doi.org/{normalize_doi(doi)}"
