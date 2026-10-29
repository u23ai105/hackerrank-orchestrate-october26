#!/usr/bin/env python3
"""
Stage 5: Deletion Policy and Per-Obligation Assessment Tool.
Loads dataset/deletion_rules.csv, maps resources to categories/rules,
and assesses compliance of observed states.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Tuple

from tools.temporal_admissibility import parse_timestamp


class PolicySchemaError(ValueError):
    """Raised when policy schema is missing required columns or contains invalid data."""
    pass


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    data_category: str
    condition: str
    required_action: str
    source_row: int = 0


@dataclass
class PolicyAssessment:
    system_id: str
    resource_id: str
    data_category: str
    required_action: str
    state: str
    compliant: bool | None
    evidence_id: str = ""
    reason: str = ""
    blockers: list[str] = field(default_factory=list)


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold()).strip("_")


def _row_value(row: Mapping[str, Any], *names: str) -> str:
    normed = {_norm(k): v for k, v in row.items()}
    for name in names:
        value = normed.get(_norm(name))
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def load_policy_rules(path: str | Path) -> list[PolicyRule]:
    """Parse dataset/deletion_rules.csv and validate strict schema."""
    path = Path(path)
    if not path.exists():
        raise PolicySchemaError(f"Policy file does not exist: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise PolicySchemaError(f"Policy file has no header: {path}")

        normalized_cols = {_norm(c) for c in reader.fieldnames}
        required_cols = {"rule_id", "data_category", "condition", "required_action"}
        missing = required_cols - normalized_cols
        if missing:
            raise PolicySchemaError(f"Missing required policy columns: {sorted(missing)}")

        rules: list[PolicyRule] = []
        for line_no, row in enumerate(reader, start=2):
            rule_id = _row_value(row, "rule_id")
            category = _row_value(row, "data_category")
            condition = _row_value(row, "condition")
            action = _row_value(row, "required_action").upper()

            if not all((rule_id, category, condition, action)):
                raise PolicySchemaError(f"Blank required value at policy CSV line {line_no}")

            if action not in {"DELETE", "REDACT", "ANONYMIZE", "RETAIN"}:
                raise PolicySchemaError(f"Unsupported required_action {action!r} at line {line_no}")

            rules.append(
                PolicyRule(
                    rule_id=rule_id,
                    data_category=category,
                    condition=condition,
                    required_action=action,
                    source_row=line_no,
                )
            )

    if not rules:
        raise PolicySchemaError("Policy file contains no rules")
    return rules


_CATEGORY_ALIASES = {
    "account_profile": "user_profile",
    "search_index_document": "search_index_entry",
    "crm_contact": "user_profile",
    "session_token": "secondary_identifier",
}


def match_policy_rule(data_category: str, rules: Iterable[PolicyRule]) -> PolicyRule | None:
    target = _norm(data_category)
    target = _CATEGORY_ALIASES.get(target, target)
    matches = [r for r in rules if _norm(r.data_category) == target]
    if not matches:
        return None
    signatures = {(r.required_action, _norm(r.condition)) for r in matches}
    if len(signatures) != 1:
        raise PolicySchemaError(f"Conflicting policy rules for category {data_category!r}")
    return sorted(matches, key=lambda r: (r.rule_id, r.source_row))[0]


def infer_data_category(
    system_id: Any = "",
    resource_id: str = "",
    hint_category: str = "",
    *,
    record: Any = None,
    collection_name: str = "",
    record_type: str = "",
) -> str:
    """Infer canonical deletion_rules.csv category from system_id, resource_id, and hints."""
    if record is not None:
        raw = getattr(record, "raw_fields", {}) or {}
        if not raw and hasattr(record, "fields") and record.fields:
            raw = dict(record.fields)
        for k in ("data_category", "category"):
            val = raw.get(k)
            if isinstance(val, str) and val.strip():
                return val.strip().upper()
        if not resource_id:
            resource_id = getattr(record, "resource_id", "") or ""
        if not system_id:
            system_id = getattr(record, "system_id", "") or ""
        if not collection_name:
            collection_name = getattr(record, "collection_name", "") or ""
        if not record_type:
            record_type = getattr(record, "record_type", "") or ""
    elif hasattr(system_id, "resource_id"):
        # Called with record as first positional argument
        return infer_data_category(record=system_id)

    # Detect if resource_id and system_id were swapped
    s_low = str(system_id or "").strip().lower()
    if any(
        s_low.startswith(p)
        for p in (
            "account_",
            "search_",
            "export_",
            "analytics_",
            "support_",
            "data_flow_",
            "backup_",
            "tombstone_",
            "audit_record_",
            "legal_",
            "marketing_",
            "cache_",
            "email_",
            "secondary_",
            "attachment_",
            "telemetry_",
            "object_",
        )
    ):
        system_id, resource_id = resource_id, system_id

    rid = str(resource_id or "").strip().lower()
    sys_id = str(system_id or "").strip().lower()
    coll = str(collection_name or "").strip().lower()
    rtype = str(record_type or "").strip().lower()
    norm_hint = _norm(hint_category)

    if rid.startswith("support_") or rid.startswith("attachment_") or rid.startswith("object_"):
        if "attachment" in coll or "attachment" in rtype or "attachment" in norm_hint:
            return "SUPPORT_ATTACHMENT"
        if record is not None:
            raw = getattr(record, "raw_fields", {}) or (dict(record.fields) if getattr(record, "fields", None) else {})
            if "attachment" in str(raw.get("table", "")).lower() or "attachment" in str(raw.get("type", "")).lower() or "attachment" in str(raw.get("origin", "")).lower():
                return "SUPPORT_ATTACHMENT"
        if rid.startswith("attachment_") or rid.startswith("object_"):
            return "SUPPORT_ATTACHMENT"
        return "SUPPORT_MESSAGE"

    prefix_map = {
        "account_": "USER_PROFILE",
        "secondary_": "SECONDARY_IDENTIFIER",
        "session_": "SECONDARY_IDENTIFIER",
        "token_": "SECONDARY_IDENTIFIER",
        "crm_": "USER_PROFILE",
        "marketing_": "MARKETING_PROFILE",
        "analytics_": "ANALYTICS_PROFILE",
        "telemetry_": "PRODUCT_TELEMETRY",
        "search_": "SEARCH_INDEX_ENTRY",
        "cache_": "CACHE_ENTRY",
        "export_": "USER_EXPORT",
        "email_": "EMAIL_DELIVERY_LOG",
        "audit_record_": "SECURITY_AUDIT_LOG",
        "security_": "SECURITY_AUDIT_LOG",
        "legal_": "LEGAL_HOLD_RECORD",
        "hold_": "LEGAL_HOLD_RECORD",
        "backup_": "BACKUP_ARCHIVE",
        "archive_": "BACKUP_ARCHIVE",
        "tombstone_": "ACCOUNT_TOMBSTONE",
        "data_flow_": "DATA_FLOW",
        "flow_": "DATA_FLOW",
        "sync_": "DATA_FLOW",
        "pipeline_": "DATA_FLOW",
        "connector_": "DATA_FLOW",
        "webhook_": "DATA_FLOW",
    }
    for prefix, cat in prefix_map.items():
        if rid.startswith(prefix):
            return cat

    if "attachment" in coll or "attachment" in rtype:
        return "SUPPORT_ATTACHMENT"
    if "ticket" in coll or "support" in sys_id or "support" in coll:
        return "SUPPORT_MESSAGE"
    if "session" in coll or "auth" in sys_id:
        return "SECONDARY_IDENTIFIER"
    if "crm" in sys_id or "crm" in coll:
        return "USER_PROFILE"
    if "marketing" in sys_id or "marketing" in coll:
        return "MARKETING_PROFILE"
    if "telemetry" in coll or "telemetry" in sys_id:
        return "PRODUCT_TELEMETRY"
    if "analytics" in sys_id or "analytics" in coll or "warehouse" in sys_id:
        return "ANALYTICS_PROFILE"
    if "search" in sys_id or "search" in coll:
        return "SEARCH_INDEX_ENTRY"
    if "cache" in sys_id or "cache" in coll:
        return "CACHE_ENTRY"
    if "export" in sys_id or "export" in coll:
        return "USER_EXPORT"
    if "email" in sys_id or "email" in coll:
        return "EMAIL_DELIVERY_LOG"
    if "security" in sys_id or "security" in coll:
        return "SECURITY_AUDIT_LOG"
    if "legal" in sys_id or "legal" in coll or "hold" in coll:
        return "LEGAL_HOLD_RECORD"
    if "backup" in sys_id or "backup" in coll or "archive" in coll:
        return "BACKUP_ARCHIVE"
    if "account" in sys_id or "profile" in coll or "customer" in coll:
        return "USER_PROFILE"

    if norm_hint:
        return hint_category.upper()

    return "USER_PROFILE"


def fields_of(record: Any) -> dict[str, Any]:
    """Merge top-level structured fields with Stage 3's record.fields tuple/dict."""
    if isinstance(record, Mapping):
        result = dict(record)
        if isinstance(record.get("raw_fields"), Mapping):
            result.update(record["raw_fields"])
        nested = record.get("fields", {})
    else:
        result = {}
        for attr in (
            "file_id",
            "activity_id",
            "audit_id",
            "system_id",
            "resource_id",
            "source_kind",
            "observed_at",
            "captured_at",
            "event_time",
            "text",
            "locator",
            "data_category",
        ):
            value = getattr(record, attr, None)
            if value not in (None, ""):
                result[attr] = value
        nested = getattr(record, "fields", {}) or getattr(record, "raw_fields", {})
        if hasattr(record, "raw_fields") and isinstance(record.raw_fields, Mapping):
            result.update(record.raw_fields)

    if nested:
        if isinstance(nested, (list, tuple)):
            for k, v in nested:
                if v not in (None, ""):
                    result[k] = v
        elif isinstance(nested, Mapping):
            result.update(dict(nested))

    return {_norm(k): v for k, v in result.items()}


def is_tombstone(record: Any) -> bool:
    f = fields_of(record)
    rid = str(f.get("resource_id") or "").lower()
    cat = str(f.get("data_category") or "").lower()
    return rid.startswith("tombstone_") or "tombstone" in cat or "tombstone" in rid


def classify_resource_state(
    record: Any,
    required_action: str = "",
    identity: Any = None,
    data_category: str = "",
) -> tuple[str, str]:
    """
    Return (state, reason) from structured fields.
    Valid states:
      - 'PRESENT'
      - 'ABSENT'
      - 'REDACTED'
      - 'ANONYMIZED'
      - 'ACTIVE_FLOW'
      - 'FLOW_DISABLED'
      - 'RESTORE_RISK'
      - 'RESTORE_BLOCKED'
      - 'UNKNOWN'
    """
    f = fields_of(record)

    def val(*keys: str) -> str:
        for key in keys:
            v = f.get(_norm(key))
            if v is not None and str(v).strip():
                return str(v).strip()
        return ""

    action = (required_action or "").upper()
    res_id = _norm(val("resource_id"))
    sys_id = _norm(val("system_id", "system"))
    status = _norm(val("result", "status", "account_status", "profile_status", "state"))
    status_code = val("status_code", "http_status")
    delivery = _norm(val("last_delivery_status", "delivery_status"))
    restore_allowed = _norm(val("restore_allowed"))
    restore_status = _norm(val("restore_status"))
    enabled = _norm(val("enabled", "is_enabled"))
    email_val = val("email", "requester_email", "owner_email", "customer_email")
    matched_val = val("matched_value")
    if matched_val and "@" in str(matched_val):
        email_val = matched_val
    phone_val = val("phone", "requester_phone", "owner_phone")
    name_val = val("name", "requester_name", "full_name")
    hash_val = val("email_hash", "correlation_key")
    text = str(val("text", "raw_text", "message", "message_excerpt")).casefold()
    source_kind = (getattr(record, "source_kind", "") or val("source_kind")).lower()

    # 1. Integration Service / Data Flow
    if "data_flow" in res_id or "flow_" in res_id or sys_id in {"integration_service", "data_pipeline"}:
        if status in {"disabled", "stopped", "inactive"} or delivery in {"stopped", "disabled"} or enabled in {"false", "0", "no"} or "data flow disabled" in text or "connector disabled" in text:
            return "FLOW_DISABLED", "Data flow is explicitly disabled/stopped"
        return "ACTIVE_FLOW", "Data flow is active recreation risk"

    # 2. Backup Service / Restore Risk
    if "backup" in res_id or "archive" in res_id or sys_id == "backup_service":
        del_block = _norm(val("deletion_block"))
        if del_block in {"true", "1", "yes"}:
            return "RESTORE_BLOCKED", "Backup restore access is explicitly blocked"
        if del_block in {"false", "0", "no"}:
            return "RESTORE_RISK", "Backup deletion block is false"
        if restore_allowed in {"false", "0", "no"} or restore_status in {"blocked", "disabled"} or status in {"blocked", "disabled", "restore_blocked"} or "restore blocked" in text or "restore_allowed=false" in text:
            return "RESTORE_BLOCKED", "Backup restore access is explicitly blocked"
        return "RESTORE_RISK", "Backup restore access is active risk"

    # 3. Check PII Presence (Takes precedence over generic deleted status on tombstones/records)
    has_pii = bool(email_val or phone_val or name_val or hash_val)
    if has_pii:
        return "PRESENT", "Record contains exposed identifying PII"

    # 4. Explicit Absence Markers
    rows_val = val("rows", "total", "hits_total", "total_hits")
    if rows_val is not None and str(rows_val).strip() != "":
        try:
            if int(str(rows_val).strip()) == 0:
                return "ABSENT", f"Query returned 0 rows/hits (rows={rows_val})"
            elif int(str(rows_val).strip()) > 0 and not action:
                return "PRESENT", f"Query returned {rows_val} hit(s)"
        except ValueError:
            pass

    res_val = _norm(val("result", "query_result"))
    if res_val in {"hit", "found"} or "result=hit" in text:
        return "PRESENT", f"Query returned hit (result={res_val})"

    if str(status_code) in {"404", "404.0"} or status in {"not_found", "absent", "deleted", "purged", "removed"}:
        return "ABSENT", f"Record absent (status={status or status_code})"
    if "not found" in text or "status=deleted" in text or "absent" in text:
        return "ABSENT", "Text indicates record absent"

    # 5. Verified Structured Schema & Explicit De-identification Markers
    has_structured_schema = source_kind in {"sql", "json"} or any(
        k in f
        for k in (
            "customer_reference",
            "message_excerpt",
            "metrics_json",
            "profile_status",
            "record_json",
            "anonymized_id",
            "redacted_at",
            "subject_reference",
            "audience_cohort",
            "cohort",
            "user_id",
        )
    )
    explicit_deid_marker = any(
        tok in text or tok in status
        for tok in (
            "redacted",
            "anonymized",
            "scrubbed",
            "deidentified",
            "masked",
            "pii_removed",
            "anon_",
            "[redacted]",
        )
    )

    # 6. Tombstones
    if is_tombstone(record) or "tombstone" in res_id or sys_id in {"identity_service"}:
        if explicit_deid_marker or has_structured_schema:
            if "anonym" in status or "anonym" in text:
                return "ANONYMIZED", "Tombstone record anonymized"
            return "REDACTED", "Tombstone retains only stable internal identifier"
        return "UNKNOWN", "Tombstone state unresolved on unstructured record"

    # 7. Support Messages / Attachments
    if "support" in res_id or "attachment" in res_id or sys_id in {"support_platform", "support_service"}:
        if action == "DELETE":
            if status_code == "404" or status in {"not_found", "absent", "deleted"}:
                return "ABSENT", "Support attachment deleted"
            return "PRESENT", "Support attachment remains present"
        else:  # REDACT
            if explicit_deid_marker or (has_structured_schema and status not in ("identifiable", "active_unredacted")):
                return "REDACTED", "Support message direct PII is redacted"
            return "UNKNOWN", "Support message state unresolved"

    # 8. Analytics Platform / Product Telemetry
    if "analytics" in res_id or "telemetry" in res_id or sys_id in {"analytics_platform", "analytics_service"}:
        if action == "DELETE":
            return "PRESENT", "Analytics profile remains present"
        else:  # ANONYMIZE
            if explicit_deid_marker or (has_structured_schema and status not in ("identifiable", "active_identifiable")):
                return "ANONYMIZED", "Analytics profile unlinked from direct identifiers"
            return "UNKNOWN", "Analytics profile state unresolved"

    # 9. Retained records (Security Audit Log, Legal Hold)
    if "audit_record" in res_id or "legal" in res_id or sys_id in {"security_service", "legal_service", "legal_hold_service"}:
        if status in {"absent", "deleted"} or status_code == "404":
            return "ABSENT", "Retained record is absent"
        if status in {"present", "active", "retained", "found", "held"} or has_structured_schema:
            return "PRESENT", "Retained record is present and available"
        if source_kind in {"sql", "json", "log", "pdf", "txt", "image"}:
            return "PRESENT", "Retained record observed"

    # 10. General status
    if status in {"present", "active", "found", "retained", "held"} or status_code == "200":
        return "PRESENT", f"Record present (status={status or status_code})"

    return "UNKNOWN", "Resource state could not be conclusively determined"


def is_retention_supported(
    record: Any,
    rule: Optional[PolicyRule],
    audit_at: str = "",
) -> bool:
    """Evaluate whether evidence supports the RETAIN condition for rule at audit_at."""
    if record is None or rule is None:
        return False
    f = fields_of(record)
    status = str(f.get("status") or f.get("result") or "").strip().lower()
    text = str(f.get("text") or "").lower()

    # Check retention_until / expires_at against audit_at if present
    for ts_key in ("retention_until", "retained_until", "expires_at", "hold_until"):
        val = f.get(ts_key)
        if isinstance(val, str) and val.strip() and audit_at:
            try:
                r_dt = parse_timestamp(val.strip())
                a_dt = parse_timestamp(audit_at.strip())
                if r_dt and a_dt:
                    if r_dt < a_dt:
                        return False
                    return True
            except Exception:
                return False

    cat = rule.data_category.upper()
    if cat == "SECURITY_AUDIT_LOG":
        if "expired" in status or "expired" in text:
            return False
        if any(k in f for k in ("retention_until", "event_code", "integrity_seal", "retention_reason", "integrity_check")):
            return True
        if status in ("present", "retained", "active", "found") or "security_service" in str(f.get("system_id") or "") or "security_service" in text or "security" in text:
            return True
        return False

    if cat == "LEGAL_HOLD_RECORD":
        if status in ("released", "expired", "inactive", "closed"):
            return False
        if status in ("active", "present", "retained", "found", "held") or "hold" in text or "legal" in text:
            return True
        return False

    if cat == "BACKUP_ARCHIVE":
        restore_allowed = f.get("restore_allowed")
        restore_status = str(f.get("restore_status") or "").strip().lower()
        if restore_allowed in (False, "false", "0", "no") or restore_status in ("blocked", "disabled") or status in ("blocked", "restore_blocked"):
            return True
        return False

    return False


def assess_policy_state(
    rule: PolicyRule | None,
    state: str,
    *,
    is_tombstone_record: bool = False,
    has_pii: bool = False,
    retention_supported: bool = False,
    coverage_complete: bool = True,
) -> tuple[bool | None, str]:
    """
    Evaluate compliance of resource state against rule.
    Returns (is_compliant, explanation).
    compliant=None represents unresolved/ambiguous state.
    """
    if not coverage_complete:
        return None, "Coverage is incomplete"

    if state in {"ACTIVE_FLOW", "RESTORE_RISK"}:
        return False, f"Active recreation risk ({state}) violates required safe deletion state"

    if state == "FLOW_DISABLED":
        return True, "Data flow is verified disabled"

    if state == "RESTORE_BLOCKED":
        return True, "Backup restore is verified blocked"

    if rule is None:
        return None, f"No policy rule defined for state {state}"

    st = (state or "UNKNOWN").upper()
    action = rule.required_action.upper()

    if st == "UNKNOWN":
        return None, f"Resource state is UNKNOWN for required action {action}"

    if action == "DELETE":
        if st == "ABSENT":
            return True, "Record is absent as required by DELETE policy"
        if is_tombstone_record:
            if not has_pii and st in ("REDACTED", "ANONYMIZED"):
                return True, "Non-identifying tombstone is permissible under DELETE"
            return False, "Tombstone still contains identifying PII or is unredacted"
        return False, f"Record is {st} but rule {rule.rule_id} requires DELETE"

    if action == "REDACT":
        if st in ("REDACTED", "ABSENT"):
            return True, f"Record is {st}, satisfying REDACT"
        return False, f"Record is {st} but rule {rule.rule_id} requires REDACT"

    if action == "ANONYMIZE":
        if st in ("ANONYMIZED", "ABSENT"):
            return True, f"Record is {st}, satisfying ANONYMIZE"
        return False, f"Record is {st} but rule {rule.rule_id} requires ANONYMIZE"

    if action == "RETAIN":
        if rule.data_category == "BACKUP_ARCHIVE":
            if st in ("RESTORE_BLOCKED", "ABSENT"):
                return True, f"Backup archive is {st}"
            return False, f"Backup archive is {st} (restore not blocked)"
        if st == "PRESENT" and retention_supported:
            return True, f"Resource is PRESENT and retention is supported under {rule.rule_id}"
        if st != "PRESENT":
            return False, f"Resource is {st} but rule {rule.rule_id} requires RETAIN"
        return False, f"Retention condition not supported for rule {rule.rule_id}"

    return None, f"Unsupported required action {action}"
