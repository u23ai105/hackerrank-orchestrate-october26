#!/usr/bin/env python3
"""
Stage 7: Output Validator for output.csv.
Validates exact contract requirements, schema, step ordering,
evidence ID existence, and temporal admissibility against audit_at.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset"
OUTPUT = ROOT / "output.csv"

HEADERS = ["case_id", "deletion_status", "steps_json"]
STATUSES = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}
STEP_KEYS = {"step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"}

PHASE_ORDER = {"FINDING": 0, "REMEDIATION": 1, "VERIFICATION": 2}
OPERATION_RANK = {
    "REPORT_REMAINING_RECORD": 0,
    "REPORT_EXPOSED_PII": 1,
    "REPORT_ACTIVE_DATA_FLOW": 2,
    "REPORT_RESTORE_RISK": 3,
    "DISABLE_DATA_FLOW": 4,
    "BLOCK_RESTORE": 5,
    "DELETE_RECORD": 6,
    "REDACT_RECORD": 7,
    "ANONYMIZE_RECORD": 8,
    "VERIFY_RECORD_ABSENT": 9,
    "VERIFY_RECORD_PRESENT": 10,
    "VERIFY_RECORD_REDACTED": 11,
    "VERIFY_RECORD_ANONYMIZED": 12,
    "VERIFY_DATA_FLOW_DISABLED": 13,
    "VERIFY_RESTORE_BLOCKED": 14,
}

ALLOWED_PHASE_OP_STATE = {
    ("FINDING", "REPORT_REMAINING_RECORD", "PRESENT"),
    ("FINDING", "REPORT_EXPOSED_PII", "PRESENT"),
    ("FINDING", "REPORT_ACTIVE_DATA_FLOW", "ACTIVE"),
    ("FINDING", "REPORT_RESTORE_RISK", "ACTIVE"),
    ("REMEDIATION", "DISABLE_DATA_FLOW", "DISABLED"),
    ("REMEDIATION", "BLOCK_RESTORE", "BLOCKED"),
    ("REMEDIATION", "DELETE_RECORD", "ABSENT"),
    ("REMEDIATION", "REDACT_RECORD", "REDACTED"),
    ("REMEDIATION", "ANONYMIZE_RECORD", "ANONYMIZED"),
    ("VERIFICATION", "VERIFY_RECORD_ABSENT", "ABSENT"),
    ("VERIFICATION", "VERIFY_RECORD_PRESENT", "PRESENT"),
    ("VERIFICATION", "VERIFY_RECORD_REDACTED", "REDACTED"),
    ("VERIFICATION", "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"),
    ("VERIFICATION", "VERIFY_DATA_FLOW_DISABLED", "DISABLED"),
    ("VERIFICATION", "VERIFY_RESTORE_BLOCKED", "BLOCKED"),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def case_key(x: str) -> tuple[int, Any]:
    m = re.fullmatch(r"case_(\d+)", x)
    return (0, int(m.group(1))) if m else (1, x)


def step_sort_key(step: dict[str, Any]) -> tuple:
    return (
        PHASE_ORDER.get(step["phase"], 99),
        OPERATION_RANK.get(step["operation"], 10**6),
        str(step.get("system_id", "")),
        str(step.get("resource_id", "")),
        str(step.get("evidence_id", "")),
    )


def validate_output_rows(
    req_rows: list[dict[str, str]],
    out_rows: list[dict[str, str]],
    source_timestamps: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    req_by_id = {str(r.get("case_id", "")).strip(): r for r in req_rows}
    valid_evidence_ids = set(source_timestamps.keys())

    # Helper to check timestamp cutoff
    from datetime import datetime, timezone

    def parse_ts(ts_str: str) -> datetime | None:
        if not ts_str:
            return None
        raw = ts_str.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                return None
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    for row in out_rows:
        cid = row.get("case_id", "").strip()
        status = row.get("deletion_status", "").strip()
        req = req_by_id.get(cid, {})
        audit_at_str = req.get("audit_at", "").strip()
        audit_dt = parse_ts(audit_at_str)
        if audit_dt is None:
            errors.append(f"{cid}: Missing or invalid audit_at timestamp {audit_at_str!r}")

        if status not in STATUSES:
            errors.append(f"{cid}: Invalid status {status!r}")

        try:
            steps = json.loads(row.get("steps_json", ""))
        except Exception as e:
            errors.append(f"{cid}: Invalid JSON in steps_json: {e}")
            continue

        if not isinstance(steps, list):
            errors.append(f"{cid}: steps_json is not an array")
            continue

        if status == "NOT_APPLICABLE":
            if steps:
                errors.append(f"{cid}: NOT_APPLICABLE steps must be []")
            continue

        if status == "COMPLETE":
            if not steps:
                errors.append(f"{cid}: COMPLETE steps must be non-empty")
        elif status == "INCOMPLETE":
            if not steps:
                errors.append(f"{cid}: INCOMPLETE steps must be non-empty")

        # Check step sorting
        expected_sorted = sorted(steps, key=step_sort_key)
        # Check that steps are sorted canonically
        sig_actual = [
            (
                PHASE_ORDER.get(s.get("phase", ""), 99),
                OPERATION_RANK.get(s.get("operation", ""), 10**6),
                str(s.get("system_id", "")),
                str(s.get("resource_id", "")),
                str(s.get("evidence_id", "")),
            )
            for s in steps
        ]
        sig_sorted = [
            (
                PHASE_ORDER.get(s.get("phase", ""), 99),
                OPERATION_RANK.get(s.get("operation", ""), 10**6),
                str(s.get("system_id", "")),
                str(s.get("resource_id", "")),
                str(s.get("evidence_id", "")),
            )
            for s in expected_sorted
        ]
        if sig_actual != sig_sorted:
            errors.append(f"{cid}: Steps not canonically sorted")

        for idx, step in enumerate(steps, 1):
            if not isinstance(step, dict) or set(step) != STEP_KEYS:
                errors.append(f"{cid}: Step {idx} schema mismatch")
                continue
            if step["step_no"] != idx:
                errors.append(f"{cid}: Step {idx} sequence number is {step['step_no']}")

            tup = (step["phase"], step["operation"], step["state"])
            if tup not in ALLOWED_PHASE_OP_STATE:
                errors.append(f"{cid}: Step {idx} has invalid combination: {tup!r}")

            ev = str(step.get("evidence_id", "") or "").strip()
            if ev:
                if ev not in valid_evidence_ids:
                    errors.append(f"{cid} step {idx}: Unknown evidence_id {ev!r}")
                elif ev not in source_timestamps:
                    errors.append(f"{cid} step {idx}: Missing timestamp entry for evidence_id {ev!r}")
                else:
                    ev_ts = parse_ts(source_timestamps[ev])
                    if ev_ts is None:
                        errors.append(f"{cid} step {idx}: Malformed or timezone-naive timestamp for {ev!r}: {source_timestamps[ev]!r}")
                    elif audit_dt is None or ev_ts > audit_dt:
                        errors.append(
                            f"{cid} step {idx}: Post-cutoff evidence {ev} ({source_timestamps[ev]} > {audit_at_str})"
                        )

            if status == "COMPLETE":
                if step["phase"] != "VERIFICATION" or not ev:
                    errors.append(
                        f"{cid}: COMPLETE requires only cited VERIFICATION steps (step {idx} has phase={step['phase']}, evidence_id={ev!r})"
                    )
            elif status == "INCOMPLETE":
                if step["phase"] in {"REMEDIATION", "VERIFICATION"} and ev:
                    errors.append(
                        f"{cid}: INCOMPLETE post-remediation/planned step {idx} must have empty evidence_id, got {ev!r}"
                    )
                if step["phase"] == "FINDING" and not ev:
                    errors.append(f"{cid}: INCOMPLETE FINDING step {idx} must have non-empty evidence_id")

        if status == "INCOMPLETE":
            if not any(s.get("phase") == "FINDING" and s.get("evidence_id") for s in steps):
                errors.append(f"{cid}: INCOMPLETE missing grounded FINDING")
            if not any(s.get("phase") == "REMEDIATION" and not s.get("evidence_id") for s in steps):
                errors.append(f"{cid}: INCOMPLETE missing planned REMEDIATION")
            if not any(s.get("phase") == "VERIFICATION" and not s.get("evidence_id") for s in steps):
                errors.append(f"{cid}: INCOMPLETE missing planned VERIFICATION")

    return errors


def main() -> None:
    errors = []
    if not OUTPUT.exists():
        print(f"VALIDATION FAILED: {OUTPUT} does not exist")
        sys.exit(1)

    req_rows = read_csv(DATASET / "deletion_requests.csv")
    out_rows = read_csv(OUTPUT)

    with OUTPUT.open("r", encoding="utf-8-sig", newline="") as f:
        header = next(csv.reader(f), [])
    if header != HEADERS:
        errors.append(f"Bad header: got {header!r}, expected {HEADERS!r}")

    req_ids = [str(r.get("case_id", "")).strip() for r in req_rows]
    out_ids = [str(r.get("case_id", "")).strip() for r in out_rows]

    if len(req_ids) != len(out_ids):
        errors.append(f"Row count mismatch: input has {len(req_ids)}, output has {len(out_ids)}")
    if len(set(out_ids)) != len(out_ids):
        errors.append("Duplicate case_id in output.csv")
    if set(req_ids) != set(out_ids):
        errors.append("Input and output case_id sets differ")
    if out_ids != sorted(out_ids, key=case_key):
        errors.append("Output case_ids not sorted by numeric case_key")

    # Load participant evidence universe and their authoritative timestamps
    source_timestamps: dict[str, str] = {}

    manifest_path = DATASET / "evidence_files.csv"
    if not manifest_path.exists():
        errors.append("Missing dataset/evidence_files.csv")
    else:
        for r in read_csv(manifest_path):
            fid = r.get("file_id", "").strip()
            if fid:
                source_timestamps[fid] = r.get("captured_at", "").strip()

    act_path = DATASET / "system_activity.csv"
    if act_path.exists():
        for r in read_csv(act_path):
            aid = r.get("activity_id", "").strip()
            if aid:
                source_timestamps[aid] = r.get("event_time", "").strip()

    audit_path = DATASET / "user_audit_log.csv"
    if audit_path.exists():
        for r in read_csv(audit_path):
            auid = r.get("audit_id", "").strip()
            if auid:
                source_timestamps[auid] = r.get("event_time", "").strip()

    errors.extend(validate_output_rows(req_rows, out_rows, source_timestamps))

    if errors:
        print("VALIDATION FAILED")
        for err in errors[:50]:
            print(f" - {err}")
        if len(errors) > 50:
            print(f" ... and {len(errors) - 50} more errors")
        print(f"Total errors: {len(errors)}")
        sys.exit(1)

    print(
        f"VALIDATION PASSED: rows={len(out_rows)} cases_validated={len(req_rows)} source_ids={len(source_timestamps)}"
    )


if __name__ == "__main__":
    main()
