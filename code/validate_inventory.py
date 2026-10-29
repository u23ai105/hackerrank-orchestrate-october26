#!/usr/bin/env python3
"""
Repeatable Deterministic Validation Script for Phase 1 Task 1:
Evidence Inventory and Dataset Integrity Audit
"""

import csv
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "dataset"

EXPECTED_CSV_COUNTS = {
    "deletion_requests.csv": 518,
    "sample_deletion_requests.csv": 32,
    "sample_output.csv": 32,
    "user_identities.csv": 850,
    "user_audit_log.csv": 306,
    "system_activity.csv": 4011,
    "deletion_rules.csv": 15,
    "evidence_files.csv": 94,
    "output.csv": 0,
}

EXPECTED_RULE_ACTIONS = {
    "DELETE": 7,
    "REDACT": 3,
    "RETAIN": 3,
    "ANONYMIZE": 2,
}

EXPECTED_TOTAL_EVIDENCE_FILES = 94
EXPECTED_TOTAL_EVIDENCE_BYTES = 2934541


def validate_csv_datasets():
    print("[-] Validating 9 CSV datasets...")
    csv_summaries = {}
    
    for filename, expected_rows in EXPECTED_CSV_COUNTS.items():
        file_path = DATASET_DIR / filename
        assert file_path.exists(), f"Missing expected dataset CSV: {file_path}"
        
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            data_rows = list(reader)
            
        actual_rows = len(data_rows)
        assert actual_rows == expected_rows, (
            f"Row count mismatch in {filename}: expected {expected_rows}, got {actual_rows}"
        )
        
        # Primary key candidate check
        pk_col = header[0] if header else None
        pk_unique = False
        distinct_pk = 0
        if header and actual_rows > 0:
            pk_values = [row[0] for row in data_rows]
            distinct_pk = len(set(pk_values))
            pk_unique = (distinct_pk == actual_rows)
            # All primary tables must have unique first column
            if filename != "output.csv":
                assert pk_unique, f"Candidate primary key {pk_col} not unique in {filename}"
                
        csv_summaries[filename] = {
            "header": header,
            "row_count": actual_rows,
            "pk_col": pk_col,
            "pk_unique": pk_unique,
            "distinct_pk": distinct_pk,
        }
        print(f"  [OK] {filename}: {actual_rows} rows, PK '{pk_col}' unique={pk_unique}")
        
    return csv_summaries


def validate_deletion_rules():
    print("[-] Validating deletion rules actions...")
    rules_path = DATASET_DIR / "deletion_rules.csv"
    with open(rules_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        
    assert len(rows) == 15, f"Expected 15 rules, found {len(rows)}"
    action_counts = Counter(r["required_action"] for r in rows)
    
    for action, expected_count in EXPECTED_RULE_ACTIONS.items():
        actual_count = action_counts.get(action, 0)
        assert actual_count == expected_count, (
            f"Action count mismatch for {action}: expected {expected_count}, got {actual_count}"
        )
        
    assert sum(action_counts.values()) == 15, "Rule counts do not sum to 15"
    print(f"  [OK] Deletion rules action counts: {dict(action_counts)}")
    return action_counts


def check_magic_bytes(full_path: Path):
    with open(full_path, "rb") as f:
        head = f.read(1024)
    if head.startswith(b"%PDF"):
        return "PDF document (%PDF)"
    elif head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG image (\x89PNG)"
    elif head.startswith(b"SQLite format 3\x00"):
        return "SQLite3 binary"
    else:
        # Check text content
        try:
            sample = head.decode("utf-8", errors="replace").strip()
            if sample.startswith(("{", "[")):
                return "JSON text"
            elif sample.startswith("--") or any(k in sample.upper() for k in ["CREATE TABLE", "INSERT INTO", "BEGIN TRANSACTION"]):
                return "SQL script"
            elif any(k in sample for k in ["INFO", "DEBUG", "WARN", "ERROR", "timestamp", "latency", "requestId"]):
                return "Log text"
            return "Plain text"
        except Exception:
            return "Binary"


def validate_evidence_manifest():
    print("[-] Validating evidence manifest and filesystem...")
    manifest_path = DATASET_DIR / "evidence_files.csv"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_rows = list(csv.DictReader(f))
        
    assert len(manifest_rows) == EXPECTED_TOTAL_EVIDENCE_FILES, (
        f"Expected {EXPECTED_TOTAL_EVIDENCE_FILES} manifest entries, got {len(manifest_rows)}"
    )
    
    file_ids = [r["file_id"] for r in manifest_rows]
    file_paths = [r["file_path"] for r in manifest_rows]
    
    assert len(file_ids) == len(set(file_ids)), "Duplicate file_id detected in manifest"
    assert len(file_paths) == len(set(file_paths)), "Duplicate file_path detected in manifest"
    
    # Check filesystem under dataset/evidence
    evidence_root = DATASET_DIR / "evidence"
    fs_relative_paths = set()
    for root, _, files in os.walk(evidence_root):
        for fname in files:
            p = Path(root) / fname
            rel_p = str(p.relative_to(DATASET_DIR))
            fs_relative_paths.add(rel_p)
            
    manifest_path_set = set(file_paths)
    missing_files = manifest_path_set - fs_relative_paths
    unlisted_files = fs_relative_paths - manifest_path_set
    
    assert len(missing_files) == 0, f"Files listed in manifest but missing on disk: {missing_files}"
    assert len(unlisted_files) == 0, f"Files present on disk but unlisted in manifest: {unlisted_files}"
    
    total_size = 0
    records = []
    
    # Pre-import test tools
    try:
        import fitz
    except ImportError:
        fitz = None
    try:
        import pdfplumber
    except ImportError:
        pdfplumber = None
    try:
        from PIL import Image
    except ImportError:
        Image = None
    try:
        import pytesseract
    except ImportError:
        pytesseract = None

    for r in manifest_rows:
        fid = r["file_id"]
        rel_path = r["file_path"]
        origin = r["origin"]
        captured_at = r["captured_at"]
        full_path = DATASET_DIR / rel_path
        
        # Verify existence & size
        file_exists = full_path.exists()
        st_size = full_path.stat().st_size if file_exists else 0
        total_size += st_size
        
        # Validate ISO-8601 timestamp
        try:
            datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            iso_valid = True
        except ValueError:
            iso_valid = False
        assert iso_valid, f"Invalid ISO-8601 captured_at: {captured_at} in {fid}"
        
        # Check signature & extension match
        ext = full_path.suffix.lstrip(".").lower()
        detected_sig = check_magic_bytes(full_path) if file_exists else "MISSING"
        
        ext_match = False
        if file_exists:
            if ext == "pdf" and "PDF" in detected_sig:
                ext_match = True
            elif ext == "png" and "PNG" in detected_sig:
                ext_match = True
            elif ext == "json" and "JSON" in detected_sig:
                ext_match = True
            elif ext == "sql" and "SQL" in detected_sig:
                ext_match = True
            elif ext == "log" and ("Log" in detected_sig or "Plain" in detected_sig):
                ext_match = True
            elif ext == "txt" and "Plain" in detected_sig:
                ext_match = True
            
        assert file_exists, f"File does not exist: {full_path}"
        assert ext_match, f"Extension mismatch for {fid}: ext={ext}, detected={detected_sig}"
        
        # Inspection / basic extraction
        outcome = "UNKNOWN"
        summary_str = ""
        
        if ext == "json":
            with open(full_path, "r", encoding="utf-8") as jf:
                data = json.load(jf)
            outcome = "VALID_JSON"
            summary_str = f"Valid JSON ({type(data).__name__}, len={len(data)})"
            
        elif ext == "sql":
            with open(full_path, "r", encoding="utf-8") as sf:
                sql_content = sf.read()
            conn = sqlite3.connect(":memory:")
            conn.executescript(sql_content)
            tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            conn.close()
            outcome = "EXECUTABLE_SQLITE"
            summary_str = f"Executable SQLite ({len(tables)} tables: {', '.join(tables)})"
            
        elif ext in ("log", "txt"):
            with open(full_path, "r", encoding="utf-8") as lf:
                lines = lf.readlines()
            assert len(lines) > 0, f"Empty log/txt file: {fid}"
            outcome = "READABLE_UTF8"
            summary_str = f"Readable UTF-8 ({len(lines)} lines)"
            
        elif ext == "pdf":
            assert fitz is not None, "fitz (PyMuPDF) required for PDF verification"
            doc = fitz.open(full_path)
            pages = len(doc)
            text = "".join(page.get_text() for page in doc)
            assert pages > 0, f"PDF has 0 pages: {fid}"
            assert len(text.strip()) > 0, f"PDF extracted 0 text: {fid}"
            tables_count = 0
            if pdfplumber is not None:
                with pdfplumber.open(full_path) as pdf:
                    for p in pdf.pages:
                        t = p.extract_tables()
                        if t:
                            tables_count += len(t)
            outcome = "VERIFIED_PDF"
            summary_str = f"Opened ({pages} pgs, {len(text)} chars, {tables_count} tbls detected)"
            
        elif ext == "png":
            assert Image is not None, "PIL required for image verification"
            with Image.open(full_path) as img:
                w, h = img.size
                fmt = img.format
                mode = img.mode
            assert w > 0 and h > 0, f"Invalid dimensions for {fid}"
            ocr_len = 0
            if pytesseract is not None:
                with Image.open(full_path) as img:
                    ocr_text = pytesseract.image_to_string(img)
                ocr_len = len(ocr_text)
                assert ocr_len > 0, f"OCR returned empty string for {fid}"
            outcome = "VERIFIED_PNG"
            summary_str = f"Opened ({w}x{h} {fmt}, OCR len={ocr_len} chars)"
            
        records.append({
            "file_id": fid,
            "file_path": rel_path,
            "origin": origin,
            "captured_at": captured_at,
            "size_bytes": st_size,
            "detected_type": detected_sig,
            "ext_match": ext_match,
            "exists": True,
            "outcome": outcome,
            "summary_str": summary_str,
        })
        
    assert total_size == EXPECTED_TOTAL_EVIDENCE_BYTES, (
        f"Total size mismatch: expected {EXPECTED_TOTAL_EVIDENCE_BYTES}, got {total_size}"
    )
    print(f"  [OK] Manifest verification passed for all 94 files ({total_size:,} bytes).")
    return records


def compute_evidence_families(records):
    print("[-] Computing evidence families...")
    # Rule 1: Consolidated rule: normalize dates <date> and regional tokens <region>
    consolidated_families = defaultdict(list)
    # Rule 2: Raw pattern rule: normalize dates <date> only
    raw_pattern_families = defaultdict(list)
    
    for r in records:
        p = Path(r["file_path"])
        ext = p.suffix.lstrip(".")
        dir_name = p.parent.name
        
        # Pattern with date normalized
        pat_raw = re.sub(r"\d{8}(?:_\d{6})?", "<date>", p.stem) + "." + ext
        # Pattern with date and region normalized
        pat_cons = re.sub(r"_(?:ap|eu|af|us|me|sa|ca)_[a-z]+", "_<region>", pat_raw)
        
        consolidated_families[(r["origin"], dir_name + "/" + pat_cons)].append(r)
        raw_pattern_families[(r["origin"], dir_name + "/" + pat_raw)].append(r)
        
    total_cons_files = sum(len(v) for v in consolidated_families.values())
    total_raw_files = sum(len(v) for v in raw_pattern_families.values())
    assert total_cons_files == EXPECTED_TOTAL_EVIDENCE_FILES, "Consolidated families count mismatch"
    assert total_raw_files == EXPECTED_TOTAL_EVIDENCE_FILES, "Raw pattern families count mismatch"
    
    print(f"  [OK] Found {len(consolidated_families)} consolidated families and {len(raw_pattern_families)} exact-pattern families.")
    return consolidated_families, raw_pattern_families


def run_full_validation():
    print("================================================================================")
    print("STARTING DETERMINISTIC INVENTORY AND EVIDENCE AUDIT VALIDATION")
    print("================================================================================")
    csv_data = validate_csv_datasets()
    rules_data = validate_deletion_rules()
    evidence_records = validate_evidence_manifest()
    cons_families, raw_families = compute_evidence_families(evidence_records)
    print("================================================================================")
    print("ALL DETERMINISTIC AUDIT ASSERTIONS PASSED SUCCESSFULLY!")
    print("================================================================================")
    return {
        "csv_data": csv_data,
        "rules_data": rules_data,
        "evidence_records": evidence_records,
        "cons_families": cons_families,
        "raw_families": raw_families,
    }


if __name__ == "__main__":
    run_full_validation()
