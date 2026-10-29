#!/usr/bin/env python3
"""
Report Table Generator for Phase 1 Task 1:
Consumes validated manifest records from code/validate_inventory.py
and updates code/docs/evidence_inventory.md directly in-place without
creating temporary intermediate files or hardcoding success values.
"""

import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "code"))
from validate_inventory import run_full_validation

REPORT_FILE = REPO_ROOT / "code/docs/evidence_inventory.md"


def generate_per_file_table(records):
    lines = [
        "| `file_id` | `file_path` | `origin` | `captured_at` | `size_bytes` | Detected Type | Match | Exists | Parsing / Inspection Outcome |",
        "|---|---|---|---|---:|---|:---:|:---:|---|",
    ]
    
    for r in records:
        # Validate that required keys exist and are boolean where appropriate
        assert "ext_match" in r and isinstance(r["ext_match"], bool), (
            f"Missing or non-boolean 'ext_match' in record for {r.get('file_id')}"
        )
        assert "exists" in r and isinstance(r["exists"], bool), (
            f"Missing or non-boolean 'exists' in record for {r.get('file_id')}"
        )
        assert "file_id" in r and r["file_id"], "Missing 'file_id' in record"
        assert "file_path" in r and r["file_path"], "Missing 'file_path' in record"
        assert "origin" in r and r["origin"], "Missing 'origin' in record"
        assert "captured_at" in r and r["captured_at"], "Missing 'captured_at' in record"
        assert "size_bytes" in r, "Missing 'size_bytes' in record"
        assert "detected_type" in r and r["detected_type"], "Missing 'detected_type' in record"
        assert "summary_str" in r and r["summary_str"], "Missing 'summary_str' in record"
        
        fid = r["file_id"]
        fpath = r["file_path"]
        orig = r["origin"]
        cat = r["captured_at"]
        sz = f"{r['size_bytes']:,}"
        dtype = r["detected_type"]
        
        # Derive dynamically from validation results — NEVER hardcoded
        match_status = "PASS" if r["ext_match"] else "FAIL"
        exists_status = "PASS" if r["exists"] else "FAIL"
        outcome = r["summary_str"]
        
        lines.append(
            f"| `{fid}` | `{fpath}` | `{orig}` | `{cat}` | {sz} | {dtype} | {match_status} | {exists_status} | {outcome} |"
        )
        
    return "\n".join(lines)


def generate_families_table(cons_families):
    lines = [
        "| Origin System | Normalized Pattern | Count | Member `file_id`s | Min..Max Bound | Captured Date Range |",
        "|---|---|---:|---|---|---|",
    ]
    
    for (orig, pat), items in sorted(cons_families.items()):
        fids = [i["file_id"] for i in items]
        fids_sorted = sorted(fids, key=lambda x: int(x.split("_")[1]))
        dates = sorted(i["captured_at"] for i in items)
        member_list = ", ".join(f"`{x}`" for x in fids_sorted)
        if len(fids_sorted) == 1:
            bound = f"`{fids_sorted[0]}` (single file)"
        else:
            bound = f"`{fids_sorted[0]}`..`{fids_sorted[-1]}` (span)"
        d_start = dates[0][:10]
        d_end = dates[-1][:10]
        lines.append(
            f"| `{orig}` | `{pat}` | {len(items)} | {member_list} | {bound} | `{d_start}` to `{d_end}` |"
        )
        
    return "\n".join(lines)


def update_report_in_place():
    print("[-] Running full deterministic validation to obtain validated records...")
    validation_results = run_full_validation()
    records = validation_results["evidence_records"]
    cons_families = validation_results["cons_families"]
    
    assert len(records) == 94, f"Expected 94 records, got {len(records)}"
    
    per_file_table_md = generate_per_file_table(records)
    families_table_md = generate_families_table(cons_families)
    
    assert REPORT_FILE.exists(), f"Report file not found: {REPORT_FILE}"
    with open(REPORT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Replace Section 4 table in-place
    s4_marker = "## 4. Complete Per-File Evidence Manifest Audit Table\n\nEvery single entry in `dataset/evidence_files.csv` was verified on disk resolving paths relative to `dataset/`. The table below lists all 94 evidence files:\n\n"
    s5_marker = "\n\n---\n\n## 5. Evidence Families Grouping & Complete Membership"
    
    assert s4_marker in content, "Section 4 marker not found in evidence_inventory.md"
    assert s5_marker in content, "Section 5 marker not found in evidence_inventory.md"
    
    part1 = content[: content.find(s4_marker) + len(s4_marker)]
    after_s4 = content[content.find(s5_marker):]
    
    # Replace Section 5 table in-place
    s5_table_marker = "Both rules sum to exactly **94 files**. The consolidated 40-family registry is detailed below with the **complete member `file_id` list** and explicit minimum-to-maximum span:\n\n"
    s6_marker = "\n\n---\n\n## 6. Manifest vs. Filesystem Reconciliation"
    
    assert s5_table_marker in after_s4, "Section 5 table marker not found"
    assert s6_marker in after_s4, "Section 6 marker not found"
    
    part2 = after_s4[: after_s4.find(s5_table_marker) + len(s5_table_marker)]
    part3 = after_s4[after_s4.find(s6_marker):]
    
    updated_content = part1 + per_file_table_md + part2 + families_table_md + part3
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(updated_content)
        
    print(f"[OK] Report {REPORT_FILE} successfully updated in-place with dynamic validation tables.")


if __name__ == "__main__":
    update_report_in_place()
