"""Small helpers for building AuditFindings."""
from __future__ import annotations

from typing import Any

from ..resolver.confidence import classify_confidence
from ..schemas import (
    AuditFinding,
    CanonicalField,
    Confidence,
    ConflictClass,
    EvidenceClaim,
    FindingType,
    Severity,
)


def build_finding(
    *,
    entry_key: str,
    finding_type: FindingType,
    severity: Severity,
    field: str | None,
    current_value: Any,
    suggested_value: Any,
    explanation: str,
    evidence: list[EvidenceClaim],
    conflict: ConflictClass | None = None,
    confidence: Confidence | None = None,
) -> AuditFinding:
    if confidence is None:
        confidence = classify_confidence(evidence, conflict_resolved=conflict is not None)
    return AuditFinding(
        entry_key=entry_key,
        finding_type=finding_type,
        severity=severity,
        confidence=confidence,
        field=field,
        current_value=current_value,
        suggested_value=suggested_value,
        explanation=explanation,
        evidence=evidence,
        conflict=conflict,
    )


def finding_from_canonical_field(
    *,
    entry_key: str,
    field: str,
    current_value: Any,
    canon: CanonicalField,
    finding_type: FindingType,
    severity: Severity,
    explanation: str,
) -> AuditFinding | None:
    """Emit a finding only if canonical evidence disagrees with the current value.

    Never returns a finding without evidence (§0 invariant).
    """
    if canon.value is None or not canon.evidence:
        return None
    if _values_match(current_value, canon.value):
        return None
    return build_finding(
        entry_key=entry_key,
        finding_type=finding_type,
        severity=severity,
        field=field,
        current_value=current_value,
        suggested_value=canon.value,
        explanation=explanation,
        evidence=canon.evidence,
        conflict=canon.conflict,
    )


def _values_match(a: Any, b: Any) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().lower().rstrip(".") == b.strip().lower().rstrip(".")
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    return a == b
