#!/usr/bin/env python3
"""
Stage 7: Build output.csv for HackerRank Orchestrate Challenge.
Audits all 518 evaluation deletion requests in dataset/deletion_requests.csv
and outputs root output.csv with exact contract schema.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

DATASET = ROOT / "dataset"
OUTPUT = ROOT / "output.csv"
FIELDS = ["case_id", "deletion_status", "steps_json"]
ALLOWED = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def case_sort_key(case_id: str) -> tuple[int, Any]:
    m = re.fullmatch(r"case_(\d+)", case_id)
    return (0, int(m.group(1))) if m else (1, case_id)


def main() -> None:
    req_file = DATASET / "deletion_requests.csv"
    if not req_file.exists():
        raise SystemExit(f"Missing {req_file}")

    requests = read_csv(req_file)
    if not requests:
        raise SystemExit(f"{req_file} is empty")

    ids = [str(r.get("case_id", "")).strip() for r in requests]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        raise SystemExit("Input has empty or duplicate case_id")

    from tools.audit_engine import build_audit_engine

    print("Building AuditEngine and indexing evidence...")
    engine = build_audit_engine(dataset_root=DATASET)
    print(f"Auditing {len(requests)} evaluation requests...")

    out_rows = []
    for idx, request in enumerate(requests, 1):
        cid = str(request.get("case_id", "")).strip()
        result = engine.audit_case(request)
        status = str(result.deletion_status).strip()
        steps = result.steps
        if status not in ALLOWED:
            raise SystemExit(f"Invalid status for {cid}: {status}")

        out_rows.append(
            {
                "case_id": cid,
                "deletion_status": status,
                "steps_json": json.dumps(steps, ensure_ascii=False, separators=(",", ":")),
            }
        )

    out_rows.sort(key=lambda r: case_sort_key(r["case_id"]))

    temp = OUTPUT.with_suffix(".csv.tmp")
    with temp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)
    temp.replace(OUTPUT)

    counts = dict(Counter(r["deletion_status"] for r in out_rows))
    print(
        json.dumps(
            {"rows": len(out_rows), "status_counts": counts, "output": str(OUTPUT)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
