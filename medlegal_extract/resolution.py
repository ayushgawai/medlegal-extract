from __future__ import annotations
import re
from .schema import CaseExtraction


def normalize_provider(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", "", name.lower())
    n = re.sub(r"\b(hospital|clinic|medical center|inc|llc|md|do)\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def resolve(case: CaseExtraction) -> CaseExtraction:
    """Merge providers that are the same entity under spelling variants,
    and point visits at the canonical name. Visits were already de-duped
    on (provider, DOS) during extraction."""
    canon: dict[str, str] = {}
    for p in case.providers:
        p.normalized = normalize_provider(p.name)
        canon.setdefault(p.normalized, p.name)
    seen, providers = set(), []
    for p in case.providers:
        if p.normalized not in seen:
            seen.add(p.normalized); providers.append(p)
    case.providers = providers
    for v in case.visits:
        v.provider = canon.get(normalize_provider(v.provider), v.provider)
    return case
