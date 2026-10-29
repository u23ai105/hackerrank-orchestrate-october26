#!/usr/bin/env python3
"""
Stage 4: Temporal Admissibility Tool.
Evaluates EvidenceRecord / EvidenceHit instances against a case's audit_at cutoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Optional


class TemporalDisposition(str, Enum):
    ADMISSIBLE = "ADMISSIBLE"
    POST_CUTOFF = "POST_CUTOFF"
    UNDATED = "UNDATED"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    CONFLICTING_TIMESTAMPS = "CONFLICTING_TIMESTAMPS"


@dataclass(frozen=True)
class TemporalAssessment:
    disposition: TemporalDisposition
    state_usable: bool
    linkage_usable: bool
    basis_timestamp: str
    basis_kind: str
    reason_code: str


def parse_timestamp(value: Any) -> Optional[datetime]:
    """Return UTC-aware datetime; missing -> None; malformed/naive -> ValueError."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("TIMEZONE_NAIVE")
    return dt.astimezone(timezone.utc)


def _field(record: Any, name: str) -> Any:
    if isinstance(record, dict):
        if name in record and record[name] not in (None, ""):
            return record[name]
        fields_val = record.get("fields")
    else:
        val = getattr(record, name, None)
        if val not in (None, ""):
            return val
        fields_val = getattr(record, "fields", None)

    if fields_val:
        fdict = dict(fields_val) if not isinstance(fields_val, dict) else fields_val
        if name in fdict and fdict[name] not in (None, ""):
            return fdict[name]
    return None


def assess_evidence(record: Any, audit_at: Any, source_kind: str = "") -> TemporalAssessment:
    try:
        cutoff = parse_timestamp(audit_at)
    except ValueError:
        return TemporalAssessment(
            TemporalDisposition.INVALID_TIMESTAMP,
            False,
            True,
            str(audit_at or ""),
            "audit_at",
            "INVALID_AUDIT_CUTOFF",
        )
    if cutoff is None:
        return TemporalAssessment(
            TemporalDisposition.UNDATED,
            False,
            True,
            "",
            "audit_at",
            "MISSING_AUDIT_CUTOFF",
        )

    captured_raw = _field(record, "captured_at")
    event_raw = _field(record, "event_time")
    updated_raw = _field(record, "record_updated_at") or _field(record, "updated_at")
    created_raw = _field(record, "record_created_at") or _field(record, "created_at")
    observed_raw = _field(record, "observed_at")
    ref_type = str(_field(record, "evidence_ref_type") or "").lower()
    kind_lower = (source_kind or str(_field(record, "source_kind") or "")).lower()

    # Check capture timestamp first if present
    captured: Optional[datetime] = None
    if captured_raw:
        try:
            captured = parse_timestamp(captured_raw)
        except ValueError:
            return TemporalAssessment(
                TemporalDisposition.INVALID_TIMESTAMP,
                False,
                True,
                str(captured_raw or ""),
                "captured_at",
                "INVALID_CAPTURE_TIMESTAMP",
            )
        if captured is not None and captured > cutoff:
            return TemporalAssessment(
                TemporalDisposition.POST_CUTOFF,
                False,
                True,
                captured.isoformat(),
                "captured_at",
                "CAPTURE_AFTER_CUTOFF",
            )

    is_event = (
        bool(event_raw)
        or kind_lower in {"activity", "event", "audit", "audit_event"}
        or ref_type in {"activity_id", "audit_id"}
    )
    primary_raw = event_raw if is_event else captured_raw
    primary_kind = "event_time" if is_event else "captured_at"

    # In Stage 3 EvidenceRecord, observed_at stores the manifest captured_at for file_id
    # or event_time for activity_id / audit_id when captured_at/event_time isn't separate.
    if not primary_raw and observed_raw:
        if is_event or captured_raw is None:
            primary_raw = observed_raw
            primary_kind = "event_time" if is_event else "observed_at"

    if not primary_raw:
        return TemporalAssessment(
            TemporalDisposition.UNDATED,
            False,
            True,
            "",
            primary_kind,
            "NO_AUTHORITATIVE_TIMESTAMP",
        )

    try:
        primary = parse_timestamp(primary_raw)
    except ValueError:
        return TemporalAssessment(
            TemporalDisposition.INVALID_TIMESTAMP,
            False,
            True,
            str(primary_raw),
            primary_kind,
            "INVALID_EVIDENCE_TIMESTAMP",
        )
    if primary is None:
        return TemporalAssessment(
            TemporalDisposition.UNDATED,
            False,
            True,
            "",
            primary_kind,
            "MISSING_EVIDENCE_TIMESTAMP",
        )

    try:
        updated = parse_timestamp(updated_raw) if updated_raw else None
        created = parse_timestamp(created_raw) if created_raw else None
    except ValueError:
        return TemporalAssessment(
            TemporalDisposition.INVALID_TIMESTAMP,
            False,
            True,
            "",
            "metadata",
            "INVALID_METADATA_TIMESTAMP",
        )
    if created is not None and updated is not None and created > updated:
        return TemporalAssessment(
            TemporalDisposition.CONFLICTING_TIMESTAMPS,
            False,
            True,
            f"created={created.isoformat()};updated={updated.isoformat()}",
            "record_created_at+record_updated_at",
            "CREATED_AFTER_UPDATED",
        )

    if primary > cutoff:
        return TemporalAssessment(
            TemporalDisposition.POST_CUTOFF,
            False,
            True,
            primary.isoformat(),
            primary_kind,
            "EVIDENCE_AFTER_CUTOFF",
        )
    return TemporalAssessment(
        TemporalDisposition.ADMISSIBLE,
        True,
        True,
        primary.isoformat(),
        primary_kind,
        "AT_OR_BEFORE_CUTOFF",
    )


def assess_hits(
    hits: Iterable[Any], audit_at: Any
) -> list[tuple[Any, TemporalAssessment]]:
    """Return (original_hit, assessment) pairs without mutating either object."""
    result = []
    for hit in hits:
        record = _field(hit, "record")
        if record is None:
            record = hit
        kind = _field(record, "source_kind") or _field(hit, "source_kind") or ""
        result.append((hit, assess_evidence(record, audit_at, str(kind))))
    return result
