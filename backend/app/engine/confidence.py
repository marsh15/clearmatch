"""Composite confidence — weighted blend of extraction quality, match quality
and document quality. Surfaced with every decision; never a black box."""
from __future__ import annotations

from .. import config
from ..schemas import ExtractionSource, ExtractedInvoice, MatchMethod, MatchResult

_DOC_PRIORS = {
    ExtractionSource.TEXT: config.CONF_DIGITAL,
    ExtractionSource.OCR: config.CONF_OCR,
    ExtractionSource.FALLBACK: config.CONF_FALLBACK,
}

_MATCH_QUALITY = {
    MatchMethod.NONE: 0.30,
    MatchMethod.HEURISTIC: 0.70,
}


def extraction_confidence(extraction: ExtractedInvoice) -> float:
    if extraction.field_confidence:
        return sum(extraction.field_confidence.values()) / len(extraction.field_confidence)
    return _DOC_PRIORS[extraction.source]


def match_quality(match: MatchResult) -> float:
    if match.method == MatchMethod.NONE:
        return _MATCH_QUALITY[MatchMethod.NONE]
    if match.method == MatchMethod.HEURISTIC:
        return _MATCH_QUALITY[MatchMethod.HEURISTIC]
    # explicit ref: exact beats within-tolerance
    if match.delta_abs is not None and abs(match.delta_abs) < 0.005:
        return 1.0
    if match.within_soft_tolerance:
        return 0.90
    return 0.60


def composite(extraction: ExtractedInvoice, match: MatchResult) -> float:
    doc = _DOC_PRIORS[extraction.source]
    value = (config.W_EXTRACTION * extraction_confidence(extraction)
             + config.W_MATCH * match_quality(match)
             + config.W_DOC_QUALITY * doc)
    return round(min(1.0, max(0.0, value)), 3)
