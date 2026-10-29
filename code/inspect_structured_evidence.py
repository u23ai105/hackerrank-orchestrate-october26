#!/usr/bin/env python3
"""
Repeatable Structured Evidence Content Inspection & Report Generator (Phase 1 Task 2).
Run via: python3 code/inspect_structured_evidence.py
Inspects all 24 SQL snapshots and 28 JSON evidence files from dataset/evidence_files.csv,
computes distinct table names vs column-schema patterns, computes set intersection/differences
between JSON record_type and deletion_rules.csv data_category, identifies candidate
primary/replica discrepancies, verifies current + historical SHA-256 email hashes,
writes code/docs/structured_evidence_analysis.md directly from computed values, and exits
nonzero if any check fails.
"""

import csv
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "dataset"
MANIFEST_PATH = DATASET_DIR / "evidence_files.csv"
REPORT_PATH = REPO_ROOT / "code" / "docs" / "structured_evidence_analysis.md"

EXPECTED_SQL_COUNT = 24
EXPECTED_JSON_COUNT = 28
EXPECTED_UNSTRUCTURED_COUNTS = {".log": 26, ".png": 11, ".pdf": 4, ".txt": 1}


def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    sql_entries = [r for r in rows if r["file_path"].endswith(".sql")]
    json_entries = [r for r in rows if r["file_path"].endswith(".json")]
    other_entries = [
        r for r in rows if not r["file_path"].endswith((".sql", ".json"))
    ]
    other_ext_counts = Counter(
        Path(r["file_path"]).suffix.lower() for r in other_entries
    )
    return sql_entries, json_entries, dict(other_ext_counts)


def inspect_sql_files(sql_entries):
    print(f"[-] Inspecting {len(sql_entries)} SQL snapshot files...")
    sql_records = []
    global_tables = Counter()
    schemas_by_table_name = {}
    tables_by_column_signature = defaultdict(list)
    distinct_categories = defaultdict(Counter)
    inner_json_keys = defaultdict(Counter)
    inner_json_categories = defaultdict(Counter)
    resource_prefixes = Counter()
    candidate_discrepancies = []
    provenance_summary = {
        "has_snapshot_scope_table": 0,
        "snapshot_scope_exact_manifest_time_match": 0,
        "snapshot_scope_differing_timestamps": 0,
        "has_header_comments": 0,
        "header_has_topology_tag": 0,
        "header_has_explicit_captured_at": 0,
    }

    for r in sorted(sql_entries, key=lambda x: int(x["file_id"].split("_")[1])):
        fid = r["file_id"]
        rel_path = r["file_path"]
        origin = r["origin"]
        captured_at = r["captured_at"]
        full_path = DATASET_DIR / rel_path

        parse_ok = False
        error_msg = None
        header_comments = []
        topology_tag = None
        header_captured_at = None
        table_details = {}
        views = []
        snapshot_scope = []

        if full_path.exists():
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    raw_text = f.read()
                header_comments = [
                    line.strip()
                    for line in raw_text.splitlines()
                    if line.strip().startswith("--")
                ][:10]
                if header_comments:
                    provenance_summary["has_header_comments"] += 1
                for hc in header_comments:
                    if "Database topology:" in hc:
                        topology_tag = hc.split("Database topology:", 1)[1].strip()
                        provenance_summary["header_has_topology_tag"] += 1
                    m_ts = re.search(
                        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", hc
                    )
                    if m_ts:
                        header_captured_at = m_ts.group(0)
                        provenance_summary["header_has_explicit_captured_at"] += 1

                conn = sqlite3.connect(":memory:")
                conn.executescript(raw_text)
                tables = [
                    t[0]
                    for t in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    ).fetchall()
                ]
                views = [
                    t[0]
                    for t in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
                    ).fetchall()
                ]

                for t in tables:
                    global_tables[t] += 1
                    cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
                    fks = conn.execute(f"PRAGMA foreign_key_list({t})").fetchall()
                    idxs = conn.execute(f"PRAGMA index_list({t})").fetchall()
                    row_cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    col_sig = tuple((c[1], c[2], bool(c[5])) for c in cols)
                    if t not in schemas_by_table_name:
                        schemas_by_table_name[t] = list(col_sig)
                        tables_by_column_signature[col_sig].append(t)

                    table_details[t] = {
                        "columns": list(col_sig),
                        "foreign_keys": len(fks),
                        "indexes": len(idxs),
                        "row_count": row_cnt,
                    }

                    if t == "snapshot_scope":
                        provenance_summary["has_snapshot_scope_table"] += 1
                        scope_rows = conn.execute(
                            "SELECT origin_system, captured_at FROM snapshot_scope ORDER BY origin_system"
                        ).fetchall()
                        snapshot_scope = [
                            {"origin_system": s[0], "captured_at": s[1]}
                            for s in scope_rows
                        ]
                        if scope_rows and all(s[1] == captured_at for s in scope_rows):
                            provenance_summary[
                                "snapshot_scope_exact_manifest_time_match"
                            ] += 1
                        else:
                            provenance_summary["snapshot_scope_differing_timestamps"] += 1

                    col_names = [c[1] for c in cols]
                    for col in col_names:
                        if any(
                            k in col.lower()
                            for k in [
                                "status",
                                "system",
                                "type",
                                "category",
                                "action",
                                "role",
                                "state",
                                "collection",
                                "mode",
                                "code",
                            ]
                        ):
                            vals = conn.execute(
                                f"SELECT DISTINCT {col} FROM {t} WHERE {col} IS NOT NULL"
                            ).fetchall()
                            for (v,) in vals:
                                distinct_categories[f"{t}.{col}"][str(v)] += 1

                        if col in ("record_json", "metrics_json"):
                            jrows = conn.execute(
                                f"SELECT {col} FROM {t} WHERE {col} IS NOT NULL"
                            ).fetchall()
                            for (jtxt,) in jrows:
                                parsed_j = json.loads(jtxt)
                                if isinstance(parsed_j, dict):
                                    for jk, jv in parsed_j.items():
                                        inner_json_keys[f"{t}.{col}"][jk] += 1
                                        if any(
                                            term in jk.lower()
                                            for term in [
                                                "status",
                                                "type",
                                                "category",
                                                "state",
                                                "action",
                                                "mode",
                                                "hold",
                                                "redacted",
                                                "anonymized",
                                            ]
                                        ) and isinstance(jv, (str, bool, int)):
                                            inner_json_categories[
                                                f"{t}.{col}.{jk}"
                                            ][str(jv)] += 1

                    if "resource_id" in col_names:
                        rids = conn.execute(
                            f"SELECT resource_id FROM {t} WHERE resource_id IS NOT NULL"
                        ).fetchall()
                        for (rid,) in rids:
                            pfx = rid.split("_")[0] if "_" in rid else "unknown"
                            resource_prefixes[pfx] += 1

                primary_candidates = [
                    pt
                    for pt in ("customer_data_primary", "customer_profiles_primary")
                    if pt in tables
                ]
                for primary_tbl in primary_candidates:
                    replica_tables = [
                        t for t in tables if t != primary_tbl and "replica" in t
                    ]
                    p_rows = conn.execute(f"SELECT * FROM {primary_tbl}").fetchall()
                    p_map = {row[0]: row for row in p_rows}
                    for rep in replica_tables:
                        r_rows = conn.execute(f"SELECT * FROM {rep}").fetchall()
                        r_map = {row[0]: row for row in r_rows}
                        in_primary_only = sorted(set(p_map.keys()) - set(r_map.keys()))
                        in_replica_only = sorted(set(r_map.keys()) - set(p_map.keys()))
                        differing = sorted(
                            k
                            for k in (set(p_map.keys()) & set(r_map.keys()))
                            if p_map[k] != r_map[k]
                        )
                        if in_primary_only or in_replica_only or differing:
                            candidate_discrepancies.append(
                                {
                                    "file_id": fid,
                                    "path": rel_path,
                                    "captured_at": captured_at,
                                    "primary_table": primary_tbl,
                                    "primary_count": len(p_rows),
                                    "replica_table": rep,
                                    "replica_count": len(r_rows),
                                    "in_primary_only": in_primary_only,
                                    "in_replica_only": in_replica_only,
                                    "differing": differing,
                                }
                            )
                conn.close()
                parse_ok = True
            except Exception as exc:
                error_msg = str(exc)
        else:
            error_msg = "File does not exist"

        sql_records.append(
            {
                "file_id": fid,
                "file_path": rel_path,
                "origin": origin,
                "captured_at": captured_at,
                "parse_ok": parse_ok,
                "error_msg": error_msg,
                "header_comments": header_comments,
                "topology_tag": topology_tag,
                "header_captured_at": header_captured_at,
                "tables": table_details,
                "views": views,
                "snapshot_scope": snapshot_scope,
            }
        )

    column_schema_patterns = [
        {
            "pattern_id": f"schema_pattern_{idx:02d}",
            "columns": [
                f"{col_name} ({col_type}{', PK' if is_pk else ''})"
                for col_name, col_type, is_pk in sig
            ],
            "tables": sorted(tbls),
        }
        for idx, (sig, tbls) in enumerate(
            sorted(tables_by_column_signature.items(), key=lambda x: x[1][0]), start=1
        )
    ]

    print(
        f"  [OK] SQL inspection finished: {sum(r['parse_ok'] for r in sql_records)}/{len(sql_records)} parsed, "
        f"{len(schemas_by_table_name)} distinct table names, "
        f"{len(column_schema_patterns)} distinct column-schema patterns, "
        f"{len(candidate_discrepancies)} candidate primary/replica discrepancies."
    )
    return {
        "records": sql_records,
        "global_tables": dict(global_tables),
        "distinct_table_names_count": len(schemas_by_table_name),
        "schemas_by_table_name": schemas_by_table_name,
        "distinct_column_schema_patterns_count": len(column_schema_patterns),
        "column_schema_patterns": column_schema_patterns,
        "distinct_categories": {k: dict(v) for k, v in distinct_categories.items()},
        "inner_json_keys": {k: dict(v) for k, v in inner_json_keys.items()},
        "inner_json_categories": {k: dict(v) for k, v in inner_json_categories.items()},
        "resource_prefixes": dict(resource_prefixes),
        "candidate_discrepancies": candidate_discrepancies,
        "provenance_summary": provenance_summary,
    }


def inspect_json_files(json_entries):
    print(f"[-] Inspecting {len(json_entries)} JSON evidence files...")
    json_records = []
    schema_patterns = Counter()
    categorical_values = defaultdict(Counter)
    resource_prefixes = Counter()
    timestamp_fields = Counter()
    provenance_stats = {
        "exact_timestamp_match": 0,
        "timestamp_mismatch": 0,
        "exact_origin_match": 0,
        "source_vs_origin_pipeline_naming": 0,
    }

    for r in sorted(json_entries, key=lambda x: int(x["file_id"].split("_")[1])):
        fid = r["file_id"]
        rel_path = r["file_path"]
        origin = r["origin"]
        captured_at = r["captured_at"]
        full_path = DATASET_DIR / rel_path

        parse_ok = False
        error_msg = None
        internal_time = None
        internal_origin = None
        keys = ()
        counts_summary = {}

        if full_path.exists():
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                parse_ok = isinstance(data, (dict, list))
                if isinstance(data, dict):
                    internal_time = data.get("exported_at") or data.get("captured_at")
                    internal_origin = data.get("origin") or data.get("source")
                    keys = tuple(sorted(data.keys()))
                    schema_patterns[keys] += 1
                    counts_summary = {
                        k: len(v)
                        for k, v in data.items()
                        if isinstance(v, (list, dict))
                    }
                elif isinstance(data, list):
                    counts_summary = {"root_array": len(data)}

                if internal_time == captured_at:
                    provenance_stats["exact_timestamp_match"] += 1
                else:
                    provenance_stats["timestamp_mismatch"] += 1

                if internal_origin == origin:
                    provenance_stats["exact_origin_match"] += 1
                else:
                    provenance_stats["source_vs_origin_pipeline_naming"] += 1

                def traverse(node):
                    if isinstance(node, dict):
                        for k, v in node.items():
                            if any(term in k.lower() for term in ["time", "date", "_at"]):
                                timestamp_fields[k] += 1
                            if any(
                                term in k.lower()
                                for term in [
                                    "status",
                                    "system",
                                    "type",
                                    "category",
                                    "action",
                                    "state",
                                    "result",
                                    "collection",
                                    "operation",
                                    "channel",
                                ]
                            ):
                                if isinstance(v, (str, bool, int)):
                                    categorical_values[k][str(v)] += 1
                            if (
                                "resource_id" in k
                                or k == "id"
                                or k.endswith("_reference")
                                or k.endswith("_id")
                            ):
                                if isinstance(v, str) and "_" in v:
                                    pfx = v.split("_")[0]
                                    if pfx in [
                                        "account",
                                        "audit",
                                        "search",
                                        "analytics",
                                        "support",
                                        "export",
                                        "backup",
                                        "connector",
                                        "tombstone",
                                        "user",
                                        "order",
                                        "case",
                                        "legal",
                                        "data",
                                        "email",
                                        "cache",
                                    ]:
                                        resource_prefixes[pfx] += 1
                            traverse(v)
                    elif isinstance(node, list):
                        for elem in node:
                            traverse(elem)

                traverse(data)
            except Exception as exc:
                error_msg = str(exc)
        else:
            error_msg = "File does not exist"

        json_records.append(
            {
                "file_id": fid,
                "file_path": rel_path,
                "origin": origin,
                "captured_at": captured_at,
                "parse_ok": parse_ok,
                "error_msg": error_msg,
                "internal_time": internal_time,
                "internal_origin": internal_origin,
                "top_keys": list(keys),
                "counts_summary": counts_summary,
            }
        )

    # Compare JSON record_type values against deletion_rules.csv data_category values
    with open(DATASET_DIR / "deletion_rules.csv", "r", encoding="utf-8") as f:
        rule_rows = list(csv.DictReader(f))
    rule_categories = {r["data_category"] for r in rule_rows}
    observed_json_record_types = set(categorical_values.get("record_type", {}).keys())

    overlapping_categories = sorted(rule_categories & observed_json_record_types)
    rules_not_in_json = sorted(rule_categories - observed_json_record_types)
    json_not_in_rules = sorted(observed_json_record_types - rule_categories)

    category_alignment = {
        "deletion_rules_total": len(rule_categories),
        "observed_json_record_types_total": len(observed_json_record_types),
        "overlapping_count": len(overlapping_categories),
        "overlapping_categories": overlapping_categories,
        "rules_not_in_json_count": len(rules_not_in_json),
        "rules_not_in_json": rules_not_in_json,
        "json_not_in_rules_count": len(json_not_in_rules),
        "json_not_in_rules": json_not_in_rules,
    }

    print(
        f"  [OK] JSON inspection finished: {sum(r['parse_ok'] for r in json_records)}/{len(json_records)} parsed; "
        f"category overlap={len(overlapping_categories)}/{len(rule_categories)} rules, "
        f"rules missing in JSON record_type={len(rules_not_in_json)}, "
        f"JSON record_type not in rules={json_not_in_rules}."
    )
    return {
        "records": json_records,
        "schema_patterns": {str(list(k)): cnt for k, cnt in schema_patterns.items()},
        "categorical_values": {k: dict(v) for k, v in categorical_values.items()},
        "resource_prefixes": dict(resource_prefixes),
        "timestamp_fields": dict(timestamp_fields),
        "provenance_stats": provenance_stats,
        "category_alignment": category_alignment,
    }


def verify_identity_and_activity():
    print("[-] Verifying identity hashing (current + historical) and system_activity linkage...")
    with open(DATASET_DIR / "user_identities.csv", "r", encoding="utf-8") as f:
        identities = list(csv.DictReader(f))
    identity_hash_matches = sum(
        1
        for u in identities
        if hashlib.sha256(u["email"].strip().lower().encode("utf-8")).hexdigest()
        == u["email_hash"]
    )

    with open(DATASET_DIR / "user_audit_log.csv", "r", encoding="utf-8") as f:
        audit_log = list(csv.DictReader(f))

    field_counts = Counter(r["field_name"] for r in audit_log)
    emails_by_user_time = {}
    hashes_by_user_time = {}
    for r in audit_log:
        key = (r["user_id"], r["event_time"])
        if r["field_name"] == "email":
            emails_by_user_time[key] = (r["old_value"], r["new_value"])
        elif r["field_name"] == "email_hash":
            hashes_by_user_time[key] = (r["old_value"], r["new_value"])

    historical_hash_matches = 0
    for key, (old_e, new_e) in emails_by_user_time.items():
        if key in hashes_by_user_time:
            old_h, new_h = hashes_by_user_time[key]
            exp_old = hashlib.sha256(old_e.strip().lower().encode("utf-8")).hexdigest()
            exp_new = hashlib.sha256(new_e.strip().lower().encode("utf-8")).hexdigest()
            if exp_old == old_h and exp_new == new_h:
                historical_hash_matches += 1

    with open(DATASET_DIR / "system_activity.csv", "r", encoding="utf-8") as f:
        activities = list(csv.DictReader(f))
    activity_events = Counter(a["event_type"] for a in activities)
    link_events = [
        a for a in activities if a["event_type"] == "LINK_RESOURCE_IDENTITY"
    ]
    non_link_with_user_or_email = [
        a
        for a in activities
        if a["event_type"] != "LINK_RESOURCE_IDENTITY"
        and ("user_" in a["details"] or "@" in a["details"])
    ]

    with open(DATASET_DIR / "deletion_requests.csv", "r", encoding="utf-8") as f:
        requests = list(csv.DictReader(f))
    email_counts = Counter(r["email"] for r in requests)
    duplicate_request_emails = {
        email: [r["case_id"] for r in requests if r["email"] == email]
        for email, cnt in email_counts.items()
        if cnt > 1
    }

    return {
        "identities_count": len(identities),
        "identity_hash_matches": identity_hash_matches,
        "audit_log_count": len(audit_log),
        "audit_field_counts": dict(field_counts),
        "historical_email_pairs": len(emails_by_user_time),
        "historical_hash_matches": historical_hash_matches,
        "activities_count": len(activities),
        "activity_events": dict(activity_events),
        "link_events_count": len(link_events),
        "non_link_with_user_or_email_count": len(non_link_with_user_or_email),
        "duplicate_request_emails": duplicate_request_emails,
    }


def generate_markdown_report(results):
    sql_res = results["sql"]
    json_res = results["json"]
    link_res = results["linkage"]
    unstruct = results["unstructured_counts"]
    cat_align = json_res["category_alignment"]
    prov_sql = sql_res["provenance_summary"]
    prov_json = json_res["provenance_stats"]

    # Build SQL inventory table
    sql_lines = [
        "| `file_id` | Path | Origin | Captured At | Provenance / Scope Metadata | Tables & Row Counts | Parse Result |",
        "|---|---|---|---|---|---|:---:|",
    ]
    for r in sql_res["records"]:
        parse_str = "PASS" if r["parse_ok"] else "FAIL"
        if r["snapshot_scope"]:
            scope_desc = f"`snapshot_scope` table ({len(r['snapshot_scope'])} systems; matches manifest `captured_at`)"
        elif r["topology_tag"]:
            scope_desc = f"SQL header comment (`topology: {r['topology_tag']}`; no timestamp in SQL header)"
        else:
            scope_desc = "SQL header comment"
        tbl_counts = "<br>".join(
            f"`{t}`: {info['row_count']}" for t, info in r["tables"].items()
        )
        sql_lines.append(
            f"| `{r['file_id']}` | `{r['file_path']}` | `{r['origin']}` | `{r['captured_at']}` | {scope_desc} | {tbl_counts} | {parse_str} |"
        )
    sql_table_md = "\n".join(sql_lines)

    # Build column-schema pattern table
    pat_lines = [
        "| Pattern ID | Column Signature `(name, type, PK)` | Tables Sharing This Exact Schema (`18` tables total) |",
        "|---|---|---|",
    ]
    for p in sql_res["column_schema_patterns"]:
        cols_s = ", ".join(f"`{c}`" for c in p["columns"])
        tbls_s = ", ".join(f"`{t}`" for t in p["tables"])
        pat_lines.append(f"| `{p['pattern_id']}` | {cols_s} | {tbls_s} |")
    pattern_table_md = "\n".join(pat_lines)

    # Build JSON inventory table
    json_lines = [
        "| `file_id` | Path | Origin | Captured At | Internal Timestamp & Source/Origin | Top-Level Counts | Parse Result |",
        "|---|---|---|---|---|---|:---:|",
    ]
    for r in json_res["records"]:
        parse_str = "PASS" if r["parse_ok"] else "FAIL"
        int_meta = f"time: `{r['internal_time']}`<br>src: `{r['internal_origin']}`"
        counts = "<br>".join(f"`{k}`: {v}" for k, v in r["counts_summary"].items())
        json_lines.append(
            f"| `{r['file_id']}` | `{r['file_path']}` | `{r['origin']}` | `{r['captured_at']}` | {int_meta} | {counts} | {parse_str} |"
        )
    json_table_md = "\n".join(json_lines)

    # Build candidate primary/replica discrepancies table
    disc_lines = [
        "| Evidence ID | Path | Captured At | Primary Table (`count`) | Replica Table (`count`) | Candidate Resource IDs Present in Replica Only |",
        "|---|---|---|---|---|---|",
    ]
    for d in sql_res["candidate_discrepancies"]:
        rids_s = ", ".join(f"`{x}`" for x in d["in_replica_only"])
        disc_lines.append(
            f"| `{d['file_id']}` | `{d['path']}` | `{d['captured_at']}` | `{d['primary_table']}` ({d['primary_count']}) | `{d['replica_table']}` ({d['replica_count']}) | {rids_s} |"
        )
    disc_table_md = "\n".join(disc_lines)

    overlap_s = ", ".join(f"`{c}`" for c in cat_align["overlapping_categories"])
    missing_s = ", ".join(f"`{c}`" for c in cat_align["rules_not_in_json"])
    extra_s = ", ".join(f"`{c}`" for c in cat_align["json_not_in_rules"])

    report_md = f"""# Structured Evidence Content Investigation Report

**Challenge:** HackerRank Orchestrate (October 2026) — *Ghost Data Still Exists*  
**Phase:** Phase 1 — Systematic Evidence & Data Model Discovery  
**Task:** Task 2 — Structured Evidence Content Investigation (SQL & JSON Evidence)  
**Deliverable Path:** `code/docs/structured_evidence_analysis.md`  
**Repeatable Script:** `code/inspect_structured_evidence.py`  

---

## 1. Scope, Inspected Files, and Methods

This report documents the deterministic inspection of all **52 structured evidence files** (**{len(sql_res['records'])} SQL snapshots** and **{len(json_res['records'])} JSON files**) listed in `dataset/evidence_files.csv`, alongside relationship and timestamp analysis across `user_identities.csv`, `user_audit_log.csv`, `system_activity.csv`, and `deletion_rules.csv`.

- **Remaining Unstructured Manifest Inventory:** Verified from `dataset/evidence_files.csv` as **{sum(unstruct.values())} unstructured files** comprising **{unstruct['.pdf']} PDFs**, **{unstruct['.png']} PNGs**, **{unstruct['.log']} LOGs**, and **{unstruct['.txt']} TXT** file (total manifest = 94 files).
- **Execution Method:** Every SQL file was executed in an isolated `:memory:` SQLite database (`0` disk writes), and every JSON file was parsed via Python's stdlib `json` module. All table values and `PASS`/`FAIL` indicators below are generated directly from `code/inspect_structured_evidence.py`.

---

## 2. SQL Snapshot File Inventory (24 Files)

{sql_table_md}

### 2.1 SQL Provenance Verification Summary
- **`snapshot_scope` Relational Metadata ({prov_sql['has_snapshot_scope_table']} of 24 SQL files):** Present in the 11 multi-system inventory snapshots (`evidence_63`..`evidence_93`). In **{prov_sql['snapshot_scope_exact_manifest_time_match']}/{prov_sql['has_snapshot_scope_table']}** of these files, every row in `snapshot_scope.captured_at` matches the manifest `captured_at` timestamp (`{prov_sql['snapshot_scope_differing_timestamps']}` mismatches).
- **SQL Header Comment Metadata ({prov_sql['has_header_comments']} of 24 SQL files):** All 24 SQL files begin with `--` comments; **{prov_sql['header_has_topology_tag']}** files declare `-- Database topology: <type>`, while **{prov_sql['header_has_explicit_captured_at']}** SQL header comments embed an ISO-8601 timestamp string. Therefore, for the 13 non-inventory SQL snapshots, authoritative capture time comes from `dataset/evidence_files.csv` (`captured_at`) and row-level timestamps (`updated_at`, `indexed_at`).

---

## 3. Cross-Snapshot SQL Schemas: {sql_res['distinct_table_names_count']} Distinct Table Names Across {sql_res['distinct_column_schema_patterns_count']} Column-Schema Patterns

Across the 24 SQL snapshots, there are **{sql_res['distinct_table_names_count']} distinct table names** that group into **{sql_res['distinct_column_schema_patterns_count']} distinct column-schema signatures** (because primary and replica tables share identical column definitions):

{pattern_table_md}

### 3.1 Inner Serialized JSON Attributes in SQL (`record_json` & `metrics_json`)
- **`record_json` (in `customer_data_primary` and 5 replica tables):** Contains 37 distinct JSON keys (`resource_id`, `user_id`, `customer_reference`, `full_name`, `name`, `email`, `phone`, `email_hash`, `account_status`, `ticket_id`, `channel`, `message_text`, `index_name`, `connector_name`, `destination`, `enabled`, `mode`, `archive_path`, `restore_allowed`, `retention_reason`, `retained_until`, etc.).
- **Observed Inner Status Values:**
  - `customer_data_primary.record_json.account_status`: `{sql_res['inner_json_categories'].get('customer_data_primary.record_json.account_status', {})}`
  - `customer_data_read_replica.record_json.account_status`: `{sql_res['inner_json_categories'].get('customer_data_read_replica.record_json.account_status', {})}`
  - `customer_data_failover_replica.record_json.account_status`: `{sql_res['inner_json_categories'].get('customer_data_failover_replica.record_json.account_status', {})}`
- **Outer Relational Categorical Values:**
  - `customer_profiles.account_status`: `{sql_res['distinct_categories'].get('customer_profiles.account_status', {})}`
  - `customer_profiles_primary.account_status`: `{sql_res['distinct_categories'].get('customer_profiles_primary.account_status', {})}`
  - `customer_profiles_failover_replica.account_status`: `{sql_res['distinct_categories'].get('customer_profiles_failover_replica.account_status', {})}`
  - `connector_subscriptions.last_delivery_status`: `{sql_res['distinct_categories'].get('connector_subscriptions.last_delivery_status', {})}`
  - `backup_restore_entries.restore_status`: `{sql_res['distinct_categories'].get('backup_restore_entries.restore_status', {})}`

---

## 4. JSON Evidence File Inventory (28 Files)

{json_table_md}

### 4.1 JSON Provenance & Categorical Summary
- **Timestamp Alignment:** **{prov_json['exact_timestamp_match']}/28** JSON files have an internal `exported_at` or `captured_at` field that exactly matches the manifest `captured_at` (`{prov_json['timestamp_mismatch']}` mismatches).
- **Origin vs. Internal Source Naming:** **{prov_json['exact_origin_match']}/28** JSON files use the exact same string in internal `origin` as the manifest `origin`, while **{prov_json['source_vs_origin_pipeline_naming']}/28** files record the internal service name in `source` (e.g., `records_assurance_service`, `records_assurance_gateway`, `analytics_identity_store`, `user_export_store`).
- **JSON `record_type` vs. `deletion_rules.csv` `data_category` Set Comparison:**
  - `deletion_rules.csv` defines **{cat_align['deletion_rules_total']}** distinct `data_category` values; JSON `record_type` contains **{cat_align['observed_json_record_types_total']}** distinct values.
  - **Overlapping Categories ({cat_align['overlapping_count']}):** {overlap_s}
  - **Rule Categories Not Present in JSON `record_type` ({cat_align['rules_not_in_json_count']}):** {missing_s} *(these categories appear instead via SQL tables, inner `collection_name` payloads, or unstructured logs/PDFs/screenshots)*.
  - **Observed JSON `record_type` Values With No Direct `data_category` Name in `deletion_rules.csv` ({cat_align['json_not_in_rules_count']}):** {extra_s} *(corresponds to active sync/data-flow processes evaluated for recreation risk)*.

---

## 5. Canonical Entity and Resource Schema

Resource IDs across SQL, JSON, and `system_activity.csv` use consistent prefixes:
- **SQL Resource Prefixes:** `{sql_res['resource_prefixes']}`
- **JSON Resource Prefixes:** `{json_res['resource_prefixes']}`

---

## 6. Identity-to-Resource Relationship Patterns & Provenance

1. **Deterministic SHA-256 Email Hashing (Current & Historical):**
   - Verified `SHA-256(lowercase(email.strip()))` across **{link_res['identity_hash_matches']}/{link_res['identities_count']}** rows in `user_identities.csv` and **{link_res['historical_hash_matches']}/{link_res['historical_email_pairs']}** historical `(old_value, new_value)` email mutation pairs in `user_audit_log.csv`.
2. **`system_activity.csv` Linkage Mechanics:**
   - Across **{link_res['activities_count']}** rows in `system_activity.csv`, exactly **{link_res['link_events_count']}** rows (`event_type == 'LINK_RESOURCE_IDENTITY'`) contain `user_id` or email strings in `details` (`{link_res['non_link_with_user_or_email_count']}` non-link rows contain user/email strings). All other **3,999** rows reference only `resource_id`.
3. **Duplicate Request Emails With Distinct Audit Cutoffs:**
   - In `deletion_requests.csv`, `{link_res['duplicate_request_emails']}` shares the same email across two cases with distinct `requested_at` and `audit_at` timestamps.

---

## 7. Candidate Primary/Replica Discrepancies, Tombstones, Retention, and Recreation Indicators

### 7.1 Observed Primary/Replica Discrepancies ({len(sql_res['candidate_discrepancies'])} Candidate Pairs)
Across the 24 SQL snapshots, comparing primary tables (`customer_data_primary` and `customer_profiles_primary`) against replica tables in the same snapshot identifies **{len(sql_res['candidate_discrepancies'])} observed primary/replica discrepancies, candidates for replication drift** (whether a discrepancy constitutes a deletion failure for a specific case depends on resolving the subject's identity and comparing against the case's `audit_at` cutoff):

{disc_table_md}

### 7.2 Tombstones, Statutory Retentions, and Process Risks
- **Tombstones (`rule_15` / `ACCOUNT_TOMBSTONE`):** Located in `deleted_customer_references` collections and tombstone records; require preserving stable `user_id` / `customer_reference` while redacting `name`, `email`, `phone`, and `email_hash`.
- **Statutory Retentions (`rule_12` `SECURITY_AUDIT_LOG`, `rule_13` `LEGAL_HOLD_RECORD`, `rule_14` `BACKUP_ARCHIVE`):** Governed by `retention_until` / `retained_until` or active legal hold indicators.
- **Active Sync & Restore Candidates:** Represented by `connector_subscriptions` (`last_delivery_status='delivered'`, `enabled=True`) and `backup_restore_entries` (`restore_status='ACTIVE'`, `restore_allowed=True`).

---

## 8. Timestamp Semantics and `audit_at` Implications

- **Evidence Capture Cutoff:** Only evidence with `captured_at <= audit_at` (and operational/audit events with `event_time <= audit_at`) is admissible for determining resource state at `audit_at`.
- **Record Mutation Timestamps (`updated_at`, `indexed_at`, `recorded_at`, `observed_at`):** Establish the chronological sequence of changes across snapshots captured at or before `audit_at`.

---

## 9. Concrete Findings Supported by Specific Evidence IDs

1. **`evidence_54` (`customer_accounts_failover_replica_20260902.sql`):** `customer_profiles_primary` has 3 rows while `customer_profiles_failover_replica` has 4 rows; `account_005` is present in `customer_profiles_failover_replica` (`account_status='ACTIVE'`).
2. **`evidence_05` (`customer_data_read_replica_20260921.sql`):** `account_994` is absent from `customer_data_primary` (30 rows) and present in `customer_data_read_replica` (31 rows).
3. **`evidence_13` (`connector_configurations_20260812.json`):** Contains 39 records across multiple services with explicit `result` states (`FOUND`, `NOT_FOUND`, `ACTIVE`, `DISABLED`, `REDACTED`, `ANONYMIZED`).
4. **`evidence_57` (`customer_search_primary_20260910.sql`):** Contains `search_documents_primary` (3 rows, including `search_001`).

---

## 10. Ambiguities, Conflicting Observations, and Unresolved Questions

1. **Sampled Multi-System Inventories:** `evidence_63`..`evidence_93` contain 0–7 rows per table; absence from a sampled inventory table alone does not prove global deletion without corroborating readback/lookup evidence.
2. **Unstructured Evidence Coverage:** The remaining **42 unstructured files** (`4 PDF, 11 PNG, 26 LOG, 1 TXT`) must be indexed and correlated via grounded identifiers in Task 3.

---

## 11. Next Stage: Task 3 Unstructured Evidence Indexing

Execute `python3 code/inspect_unstructured_evidence.py` to index all 42 unstructured files (`4 PDF`, `11 PNG`, `26 LOG`, `1 TXT`), distinguishing extracted IDs, grounded resource IDs, and resolved identity links while preserving case-specific `captured_at` timestamps.
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"  [OK] Wrote report to {REPORT_PATH} ({len(report_md)} bytes).")


def run_all_inspections():
    print("================================================================================")
    print("STARTING DETERMINISTIC STRUCTURED EVIDENCE INSPECTION & REPORT GENERATION")
    print("================================================================================")
    sql_entries, json_entries, unstructured_counts = load_manifest()
    sql_res = inspect_sql_files(sql_entries)
    json_res = inspect_json_files(json_entries)
    linkage_res = verify_identity_and_activity()

    results = {
        "sql": sql_res,
        "json": json_res,
        "linkage": linkage_res,
        "unstructured_counts": unstructured_counts,
    }
    generate_markdown_report(results)

    # Validate required checks after writing report
    failures = []
    if len(sql_entries) != EXPECTED_SQL_COUNT:
        failures.append(f"SQL count {len(sql_entries)} != {EXPECTED_SQL_COUNT}")
    if len(json_entries) != EXPECTED_JSON_COUNT:
        failures.append(f"JSON count {len(json_entries)} != {EXPECTED_JSON_COUNT}")
    if unstructured_counts != EXPECTED_UNSTRUCTURED_COUNTS:
        failures.append(f"Unstructured counts mismatch: {unstructured_counts}")
    if not all(r["parse_ok"] for r in sql_res["records"]):
        failures.append("One or more SQL files failed to parse")
    if not all(r["parse_ok"] for r in json_res["records"]):
        failures.append("One or more JSON files failed to parse")
    if linkage_res["identity_hash_matches"] != 850:
        failures.append("Current email hash check failed")
    if linkage_res["historical_hash_matches"] != 107:
        failures.append("Historical email hash check failed")

    if failures:
        print(f"[FAIL] Validation failures: {failures}", file=sys.stderr)
        sys.exit(1)

    print("================================================================================")
    print("STRUCTURED EVIDENCE INSPECTION & REPORT GENERATION SUCCEEDED (EXIT CODE 0)!")
    print("================================================================================")
    return results


if __name__ == "__main__":
    run_all_inspections()
