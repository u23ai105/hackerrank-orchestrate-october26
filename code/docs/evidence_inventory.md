# Evidence and Dataset Inventory Audit (Phase 1 — Task 1 Correction Pass)

**Project:** HackerRank Orchestrate (October 2026) — Ghost Data Still Exists  
**Audit Scope:** Repository baseline, CSV dataset integrity, deletion policy verification, per-file evidence manifest validation, evidence families membership, parsing capabilities, and preliminary investigation roadmap.  
**Report Revision:** Corrected & Audited — 2026-10-25  

---

## 1. Repository Baseline & Git Environment

The repository and working tree metadata were verified directly using native Git CLI commands:

- **Repository Root:** `/Users/muzammilmohammad/Desktop/hackerrank-orchestrate-october26`
- **Current Branch:** `feat/phase-1-evidence-inventory`
- **Active Worktree Path:** `/Users/muzammilmohammad/Desktop/hackerrank-orchestrate-october26` (commit `acb3dfc`, branch `[feat/phase-1-evidence-inventory]`)
- **Other Registered Worktrees:** None (single primary working tree)
- **Working Tree Status:** Clean working tree with respect to tracked files; untracked project additions preserved:
  - `code/docs/` (documentation and inventory reports)
  - `code/validate_inventory.py` (persistent deterministic inspection script)
  - `code/build_report_tables.py` (repeatable report table builder)
  - `log.txt` (HackerRank agent audit log beside `AGENTS.md`)
  - `transcripts/` (`transcripts/antigravity_execution_chat.md`)
  - `ANTIGRAVITY.md` (untracked instructions)
  - `log_chat.py` (untracked helper, not executed)

### Starter Code Inspection
The `code/` directory contains starter placeholders:

| File Path | Size (Bytes) | Lines | Existing Code / Dependencies | Purpose / Description |
|---|---:|---:|---|---|
| `code/main.py` | 0 | 0 | None (empty placeholder) | Target entry point for the end-to-end deletion-audit agent pipeline. Must read `dataset/deletion_requests.csv` and generate root `output.csv`. |
| `code/evaluation/main.py` | 0 | 0 | None (empty placeholder) | Target entry point for solution evaluation, accuracy reporting, and metrics generation under `evaluation/`. |

Neither file was modified or executed in this phase.

---

## 2. Core Dataset CSV Schemas, Row Counts, & Candidate Primary Key Uniqueness

All 9 CSV files under `dataset/` (including `evidence_files.csv` and the template `output.csv`) were audited using Python's `csv.reader` and `csv.DictReader` to parse quoted fields accurately rather than relying on raw line counts:

| File Name | Data Rows | Total Columns | Primary Key (PK) | Uniqueness Summary & Key Field Notes |
|---|---:|---:|---|---|
| `deletion_requests.csv` | 518 | 7 | `case_id` | **100% Unique PK** (`case_id` 518/518). Contains 517 distinct emails (1 duplicate email: `ingrid.dahl@outlook.com` appears in `case_33` and `case_52` with distinct requested timestamps). 72 unique audit cutoffs (`audit_at`). 3 reported statuses (`COMPLETE`, `PARTIALLY_COMPLETE`, `NOT_STARTED`). |
| `sample_deletion_requests.csv` | 32 | 7 | `case_id` | **100% Unique PK** (`case_id` 32/32). Public sample slice matching `sample_output.csv`. |
| `sample_output.csv` | 32 | 3 | `case_id` | **100% Unique PK** (`case_id` 32/32). Ground truth for the 32 sample cases. Deletion status breakdown: 22 `INCOMPLETE`, 10 `COMPLETE`, 0 `NOT_APPLICABLE`. |
| `user_identities.csv` | 850 | 6 | `user_id` | **100% Unique PK** (`user_id` 850/850). `email`, `phone`, `email_hash`, and `updated_at` are each 100% unique (850/850). `name` has 847 distinct values (3 realistic collisions). |
| `user_audit_log.csv` | 306 | 6 | `audit_id` | **100% Unique PK** (`audit_id` 306/306). Covers historical identifier changes across 196 users. Field distribution: `email` (107), `email_hash` (107), `phone` (92). |
| `system_activity.csv` | 4,011 | 8 | `activity_id` | **100% Unique PK** (`activity_id` 4011/4011). Unique timestamps (4011/4011). 17 distinct event types. 11 source systems, 19 target systems. Reported results: `SUCCESS` (2,914), `FAILED` (721), `PARTIAL` (376). |
| `deletion_rules.csv` | 15 | 4 | `rule_id` | **100% Unique PK** (`rule_id` 15/15). 15 distinct data categories. Required actions: `DELETE` (7), `REDACT` (3), `ANONYMIZE` (2), `RETAIN` (3). |
| `evidence_files.csv` | 94 | 4 | `file_id` | **100% Unique PK** (`file_id` 94/94). Manifest mapping each file to origin and captured timestamp. |
| `output.csv` | 0 | 3 | `case_id` | Header-only template (`case_id,deletion_status,steps_json`). Untouched blank target for 518 evaluation predictions. |

---

## 3. Deletion Policy Action Counts Verification

A direct audit of `dataset/deletion_rules.csv` resolves and corrects the required action counts. The policy contains exactly 15 rules distributed as follows:

| Required Action | Verified Count | Expected Count | Status | Notes |
|---|---:|---:|:---:|---|
| `DELETE` | 7 | 7 | **MATCH** | Rules 01, 02, 03, 04, 06, 09, 10 |
| `REDACT` | 3 | 3 | **MATCH** | Rules 05, 11, 15 |
| `ANONYMIZE` | 2 | 2 | **MATCH** | Rules 07, 08 |
| `RETAIN` | 3 | 3 | **MATCH** | Rules 12, 13, 14 |
| **Total** | **15** | **15** | **MATCH** | 100% verified against CSV source |

### Complete Deletion Policy Rule Registry
| Rule ID | Data Category | Condition / Criteria | Required Action |
|---|---|---|---|
| `rule_01` | `USER_PROFILE` | Always | `DELETE` |
| `rule_02` | `SECONDARY_IDENTIFIER` | Always | `DELETE` |
| `rule_03` | `SEARCH_INDEX_ENTRY` | Always | `DELETE` |
| `rule_04` | `CACHE_ENTRY` | Always | `DELETE` |
| `rule_05` | `SUPPORT_MESSAGE` | Conversation contains shared customer, agent, or order context that must be retained | `REDACT` |
| `rule_06` | `SUPPORT_ATTACHMENT` | Attachment belongs only to the deletion subject | `DELETE` |
| `rule_07` | `ANALYTICS_PROFILE` | Record is still attributable to a user | `ANONYMIZE` |
| `rule_08` | `PRODUCT_TELEMETRY` | Record is still attributable to a user | `ANONYMIZE` |
| `rule_09` | `USER_EXPORT` | Always | `DELETE` |
| `rule_10` | `MARKETING_PROFILE` | Always | `DELETE` |
| `rule_11` | `EMAIL_DELIVERY_LOG` | Log contains a user email address | `REDACT` |
| `rule_12` | `SECURITY_AUDIT_LOG` | Record is within the supplied retention period | `RETAIN` |
| `rule_13` | `LEGAL_HOLD_RECORD` | A supplied legal hold is active | `RETAIN` |
| `rule_14` | `BACKUP_ARCHIVE` | Restore access can be blocked | `RETAIN` |
| `rule_15` | `ACCOUNT_TOMBSTONE` | Account is deleted and only a stable internal `user_id` is needed to preserve references to retained records | `REDACT` |

*Note: In the previous draft, `rule_06` was erroneously tallied under `REDACT`. The count is now strictly verified as 7 `DELETE` and 3 `REDACT` and enforced by deterministic assertions in `code/validate_inventory.py`.*

---

## 4. Complete Per-File Evidence Manifest Audit Table

Every single entry in `dataset/evidence_files.csv` was verified on disk resolving paths relative to `dataset/`. The table below lists all 94 evidence files:

| `file_id` | `file_path` | `origin` | `captured_at` | `size_bytes` | Detected Type | Match | Exists | Parsing / Inspection Outcome |
|---|---|---|---|---:|---|:---:|:---:|---|
| `evidence_01` | `evidence/logs/service_events_ap_south_20260915.log` | `central_observability_export` | `2026-09-15T11:59:39Z` | 22,133 | Log text | PASS | PASS | Readable UTF-8 (104 lines) |
| `evidence_02` | `evidence/records/customer_data_snapshot_bundle_20260917.json` | `records_assurance_snapshot_bundle` | `2026-09-17T12:00:00Z` | 17,406 | JSON text | PASS | PASS | Valid JSON (dict, len=3) |
| `evidence_03` | `evidence/records/customer_account_handover_20261001.txt` | `customer_account_service` | `2026-10-01T12:00:00Z` | 4,488 | Plain text | PASS | PASS | Readable UTF-8 (46 lines) |
| `evidence_04` | `evidence/images/account_admin_console_20260926.png` | `account_admin_portal` | `2026-09-26T11:00:00Z` | 124,989 | PNG image (PNG) | PASS | PASS | Opened (1800x1200 PNG, OCR len=993 chars) |
| `evidence_05` | `evidence/databases/customer_data_read_replica_20260921.sql` | `customer_data_read_replica_capture` | `2026-09-21T10:00:00Z` | 24,657 | SQL script | PASS | PASS | Executable SQLite (2 tables: customer_data_primary, customer_data_read_replica) |
| `evidence_06` | `evidence/logs/structured_service_events_eu_west_20260918.log` | `central_observability_export` | `2026-09-18T11:55:24Z` | 31,199 | Log text | PASS | PASS | Readable UTF-8 (112 lines) |
| `evidence_07` | `evidence/records/customer_data_snapshot_bundle_20260913.json` | `records_assurance_snapshot_bundle` | `2026-09-13T08:00:00Z` | 12,146 | JSON text | PASS | PASS | Valid JSON (dict, len=3) |
| `evidence_08` | `evidence/logs/search_index_diagnostic_20260906.log` | `search_index_service` | `2026-09-06T07:00:00Z` | 8,013 | Log text | PASS | PASS | Readable UTF-8 (36 lines) |
| `evidence_09` | `evidence/images/search_index_inspector_20260901.png` | `search_index_admin` | `2026-09-01T06:00:00Z` | 121,101 | PNG image (PNG) | PASS | PASS | Opened (1800x1100 PNG, OCR len=952 chars) |
| `evidence_10` | `evidence/databases/customer_data_read_replica_20260827.sql` | `customer_data_read_replica_capture` | `2026-08-27T12:00:00Z` | 23,576 | SQL script | PASS | PASS | Executable SQLite (2 tables: customer_data_primary, customer_data_read_replica) |
| `evidence_11` | `evidence/logs/syslog_archive_us_east_20260824.log` | `central_observability_export` | `2026-08-24T13:56:43Z` | 26,414 | Log text | PASS | PASS | Readable UTF-8 (118 lines) |
| `evidence_12` | `evidence/records/customer_data_snapshot_bundle_20260819.json` | `records_assurance_snapshot_bundle` | `2026-08-19T10:00:00Z` | 13,064 | JSON text | PASS | PASS | Valid JSON (dict, len=3) |
| `evidence_13` | `evidence/records/connector_configurations_20260812.json` | `integration_management_service` | `2026-08-12T09:00:00Z` | 9,788 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_14` | `evidence/images/connector_management_console_20260807.png` | `integration_admin` | `2026-08-07T08:00:00Z` | 130,271 | PNG image (PNG) | PASS | PASS | Opened (1800x1150 PNG, OCR len=966 chars) |
| `evidence_15` | `evidence/databases/customer_data_read_replica_20260802.sql` | `customer_data_read_replica_capture` | `2026-08-02T07:00:00Z` | 19,312 | SQL script | PASS | PASS | Executable SQLite (2 tables: customer_data_primary, customer_data_read_replica) |
| `evidence_16` | `evidence/logs/application_trace_ap_northeast_20260730.log` | `central_observability_export` | `2026-07-30T08:53:12Z` | 18,839 | Log text | PASS | PASS | Readable UTF-8 (93 lines) |
| `evidence_17` | `evidence/records/customer_data_snapshot_bundle_20260725.json` | `records_assurance_snapshot_bundle` | `2026-07-25T15:00:00Z` | 15,328 | JSON text | PASS | PASS | Valid JSON (dict, len=3) |
| `evidence_18` | `evidence/documents/account_history_report_20260718.pdf` | `account_history_service` | `2026-07-18T11:00:00Z` | 65,704 | PDF document (%PDF) | PASS | PASS | Opened (2 pgs, 718 chars, 5 tbls detected) |
| `evidence_19` | `evidence/images/analytics_profile_view_20260713.png` | `analytics_platform` | `2026-07-13T10:00:00Z` | 129,362 | PNG image (PNG) | PASS | PASS | Opened (1800x1150 PNG, OCR len=999 chars) |
| `evidence_20` | `evidence/databases/customer_data_read_replica_20260708.sql` | `customer_data_read_replica_capture` | `2026-07-08T09:00:00Z` | 23,547 | SQL script | PASS | PASS | Executable SQLite (2 tables: customer_data_primary, customer_data_read_replica) |
| `evidence_21` | `evidence/logs/operations_stream_eu_central_20260705.log` | `central_observability_export` | `2026-07-05T07:54:27Z` | 26,198 | Log text | PASS | PASS | Readable UTF-8 (128 lines) |
| `evidence_22` | `evidence/records/customer_data_snapshot_bundle_20260630.json` | `records_assurance_snapshot_bundle` | `2026-06-30T07:00:00Z` | 23,629 | JSON text | PASS | PASS | Valid JSON (dict, len=3) |
| `evidence_23` | `evidence/images/customer_export_console_20260618.png` | `export_service` | `2026-06-18T12:00:00Z` | 134,597 | PNG image (PNG) | PASS | PASS | Opened (1800x1100 PNG, OCR len=1098 chars) |
| `evidence_24` | `evidence/databases/customer_data_read_replica_20260613.sql` | `customer_data_read_replica_capture` | `2026-06-13T11:00:00Z` | 19,611 | SQL script | PASS | PASS | Executable SQLite (2 tables: customer_data_primary, customer_data_read_replica) |
| `evidence_25` | `evidence/logs/cloud_runtime_export_us_west_20260608.log` | `central_observability_export` | `2026-06-08T09:58:28Z` | 32,266 | Log text | PASS | PASS | Readable UTF-8 (128 lines) |
| `evidence_26` | `evidence/records/customer_data_snapshot_bundle_20260605.json` | `records_assurance_snapshot_bundle` | `2026-06-05T12:00:00Z` | 13,830 | JSON text | PASS | PASS | Valid JSON (dict, len=3) |
| `evidence_27` | `evidence/documents/legal_retention_register_20260529.pdf` | `legal_retention_service` | `2026-05-29T08:00:00Z` | 65,857 | PDF document (%PDF) | PASS | PASS | Opened (2 pgs, 1002 chars, 3 tbls detected) |
| `evidence_28` | `evidence/images/support_ticket_console_20260524.png` | `support_platform` | `2026-05-24T07:00:00Z` | 135,008 | PNG image (PNG) | PASS | PASS | Opened (1800x1200 PNG, OCR len=1115 chars) |
| `evidence_29` | `evidence/databases/customer_data_regional_replicas_20260519.sql` | `customer_data_regional_replicas_capture` | `2026-05-19T06:00:00Z` | 32,168 | SQL script | PASS | PASS | Executable SQLite (3 tables: customer_data_primary, customer_data_replica_ap_south, customer_data_replica_eu_west) |
| `evidence_30` | `evidence/logs/service_events_sa_east_20260516.log` | `central_observability_export` | `2026-05-16T11:58:25Z` | 23,481 | Log text | PASS | PASS | Readable UTF-8 (110 lines) |
| `evidence_31` | `evidence/records/customer_data_snapshot_bundle_20260511.json` | `records_assurance_snapshot_bundle` | `2026-05-11T11:00:00Z` | 25,174 | JSON text | PASS | PASS | Valid JSON (dict, len=3) |
| `evidence_32` | `evidence/images/backup_restore_console_20260429.png` | `backup_service` | `2026-04-29T09:00:00Z` | 155,587 | PNG image (PNG) | PASS | PASS | Opened (1800x1150 PNG, OCR len=1263 chars) |
| `evidence_33` | `evidence/databases/customer_data_regional_replicas_20260424.sql` | `customer_data_regional_replicas_capture` | `2026-04-24T08:00:00Z` | 36,010 | SQL script | PASS | PASS | Executable SQLite (3 tables: customer_data_primary, customer_data_replica_ap_south, customer_data_replica_eu_west) |
| `evidence_34` | `evidence/logs/structured_service_events_ca_central_20260419.log` | `central_observability_export` | `2026-04-19T06:59:43Z` | 38,660 | Log text | PASS | PASS | Readable UTF-8 (136 lines) |
| `evidence_35` | `evidence/records/customer_data_snapshot_bundle_20260416.json` | `records_assurance_snapshot_bundle` | `2026-04-16T06:00:00Z` | 13,027 | JSON text | PASS | PASS | Valid JSON (dict, len=3) |
| `evidence_36` | `evidence/records/customer_export_manifest_20260409.json` | `customer_export_service` | `2026-04-09T12:00:00Z` | 11,462 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_37` | `evidence/images/security_audit_explorer_20260905.png` | `security_service` | `2026-09-05T07:00:00Z` | 147,699 | PNG image (PNG) | PASS | PASS | Opened (1800x1100 PNG, OCR len=1472 chars) |
| `evidence_38` | `evidence/databases/customer_data_regional_replicas_20260330.sql` | `customer_data_regional_replicas_capture` | `2026-03-30T10:00:00Z` | 35,506 | SQL script | PASS | PASS | Executable SQLite (3 tables: customer_data_primary, customer_data_replica_ap_south, customer_data_replica_eu_west) |
| `evidence_39` | `evidence/logs/syslog_archive_ap_southeast_20260325.log` | `central_observability_export` | `2026-03-25T08:59:44Z` | 25,968 | Log text | PASS | PASS | Readable UTF-8 (114 lines) |
| `evidence_40` | `evidence/records/customer_data_snapshot_bundle_20260322.json` | `records_assurance_snapshot_bundle` | `2026-03-22T08:00:00Z` | 13,241 | JSON text | PASS | PASS | Valid JSON (dict, len=3) |
| `evidence_41` | `evidence/logs/notification_delivery_20260315.log` | `downstream_delivery_service` | `2026-03-15T07:00:00Z` | 8,972 | Log text | PASS | PASS | Readable UTF-8 (39 lines) |
| `evidence_42` | `evidence/images/deleted_account_reference_20260310.png` | `identity_service` | `2026-03-10T06:00:00Z` | 136,696 | PNG image (PNG) | PASS | PASS | Opened (1800x1100 PNG, OCR len=1165 chars) |
| `evidence_43` | `evidence/databases/customer_data_reporting_replica_20260305.sql` | `customer_data_reporting_replica_capture` | `2026-03-05T12:00:00Z` | 20,275 | SQL script | PASS | PASS | Executable SQLite (2 tables: customer_data_primary, customer_data_reporting_replica) |
| `evidence_44` | `evidence/logs/application_trace_eu_north_20260302.log` | `central_observability_export` | `2026-03-02T10:59:23Z` | 24,885 | Log text | PASS | PASS | Readable UTF-8 (125 lines) |
| `evidence_45` | `evidence/records/customer_data_snapshot_bundle_20260223.json` | `records_assurance_snapshot_bundle` | `2026-02-23T10:00:00Z` | 24,174 | JSON text | PASS | PASS | Valid JSON (dict, len=3) |
| `evidence_46` | `evidence/images/object_storage_browser_20260213.png` | `object_storage` | `2026-02-13T08:00:00Z` | 154,193 | PNG image (PNG) | PASS | PASS | Opened (1800x1150 PNG, OCR len=1282 chars) |
| `evidence_47` | `evidence/databases/customer_data_reporting_replica_20260208.sql` | `customer_data_reporting_replica_capture` | `2026-02-08T07:00:00Z` | 19,231 | SQL script | PASS | PASS | Executable SQLite (2 tables: customer_data_primary, customer_data_reporting_replica) |
| `evidence_48` | `evidence/logs/operations_stream_me_central_20260203.log` | `central_observability_export` | `2026-02-03T05:59:42Z` | 21,199 | Log text | PASS | PASS | Readable UTF-8 (103 lines) |
| `evidence_49` | `evidence/records/customer_data_snapshot_bundle_20260131.json` | `records_assurance_snapshot_bundle` | `2026-01-31T15:00:00Z` | 14,811 | JSON text | PASS | PASS | Valid JSON (dict, len=3) |
| `evidence_50` | `evidence/records/security_audit_ledger_20261001.json` | `security_audit_service` | `2026-10-01T12:00:00Z` | 4,985 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_51` | `evidence/records/customer_data_snapshot_bundle_20260915.json` | `records_assurance_snapshot_bundle` | `2026-09-15T12:00:00Z` | 1,843 | JSON text | PASS | PASS | Valid JSON (dict, len=3) |
| `evidence_52` | `evidence/databases/customer_data_failover_replica_20260920.sql` | `customer_data_failover_replica_capture` | `2026-09-20T12:00:00Z` | 12,250 | SQL script | PASS | PASS | Executable SQLite (2 tables: customer_data_failover_replica, customer_data_primary) |
| `evidence_53` | `evidence/logs/cloud_runtime_export_af_south_20260930.log` | `central_observability_export` | `2026-09-30T11:59:44Z` | 94,518 | Log text | PASS | PASS | Readable UTF-8 (305 lines) |
| `evidence_54` | `evidence/databases/customer_accounts_failover_replica_20260902.sql` | `customer_account_failover_replica_capture` | `2026-09-02T23:00:00Z` | 2,052 | SQL script | PASS | PASS | Executable SQLite (2 tables: customer_profiles_failover_replica, customer_profiles_primary) |
| `evidence_55` | `evidence/documents/security_retention_extract.pdf` | `security_service` | `2026-09-05T06:30:00Z` | 64,847 | PDF document (%PDF) | PASS | PASS | Opened (1 pgs, 616 chars, 3 tbls detected) |
| `evidence_56` | `evidence/records/customer_analytics_report_20260907.json` | `analytics_platform` | `2026-09-07T09:45:00Z` | 1,351 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_57` | `evidence/databases/customer_search_primary_20260910.sql` | `customer_search_primary_capture` | `2026-09-10T08:45:00Z` | 826 | SQL script | PASS | PASS | Executable SQLite (1 tables: search_documents_primary) |
| `evidence_58` | `evidence/documents/delivery_correction_attachment.pdf` | `support_platform` | `2026-09-12T07:30:00Z` | 66,039 | PDF document (%PDF) | PASS | PASS | Opened (2 pgs, 837 chars, 4 tbls detected) |
| `evidence_59` | `evidence/records/customer_export_jobs_20260914.json` | `export_service` | `2026-09-14T15:40:00Z` | 817 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_60` | `evidence/images/marketing_profile_console.png` | `marketing_platform` | `2026-09-16T07:20:00Z` | 129,711 | PNG image (PNG) | PASS | PASS | Opened (1500x920 PNG, OCR len=1070 chars) |
| `evidence_61` | `evidence/logs/support_replica.log` | `support_platform` | `2026-09-17T22:00:19Z` | 1,863 | Log text | PASS | PASS | Readable UTF-8 (10 lines) |
| `evidence_62` | `evidence/records/service_resource_export_20260129_114459.json` | `service_resource_export` | `2026-01-29T11:44:59Z` | 10,387 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_63` | `evidence/databases/customer_data_inventory_20260213.sql` | `customer_data_inventory_capture` | `2026-02-13T07:43:27Z` | 5,436 | SQL script | PASS | PASS | Executable SQLite (9 tables: snapshot_scope, customer_profiles, customer_search_documents, customer_analytics_profiles, support_records, customer_exports, connector_subscriptions, backup_restore_entries, security_audit_records) |
| `evidence_64` | `evidence/logs/resource_lookup_trace_20260218_083911.log` | `service_readback_logs` | `2026-02-18T08:39:11Z` | 10,995 | Log text | PASS | PASS | Readable UTF-8 (54 lines) |
| `evidence_65` | `evidence/records/service_resource_export_20260228_103637.json` | `service_resource_export` | `2026-02-28T10:36:37Z` | 9,383 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_66` | `evidence/databases/customer_data_inventory_20260310.sql` | `customer_data_inventory_capture` | `2026-03-10T05:38:48Z` | 6,545 | SQL script | PASS | PASS | Executable SQLite (9 tables: snapshot_scope, customer_profiles, customer_search_documents, customer_analytics_profiles, support_records, customer_exports, connector_subscriptions, backup_restore_entries, security_audit_records) |
| `evidence_67` | `evidence/logs/resource_lookup_trace_20260310_061801.log` | `service_readback_logs` | `2026-03-10T06:18:01Z` | 544 | Log text | PASS | PASS | Readable UTF-8 (4 lines) |
| `evidence_68` | `evidence/records/service_resource_export_20260320_072349.json` | `service_resource_export` | `2026-03-20T07:23:49Z` | 9,000 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_69` | `evidence/databases/customer_data_inventory_20260404.sql` | `customer_data_inventory_capture` | `2026-04-04T10:04:19Z` | 5,721 | SQL script | PASS | PASS | Executable SQLite (9 tables: snapshot_scope, customer_profiles, customer_search_documents, customer_analytics_profiles, support_records, customer_exports, connector_subscriptions, backup_restore_entries, security_audit_records) |
| `evidence_70` | `evidence/logs/resource_lookup_trace_20260414_054007.log` | `service_readback_logs` | `2026-04-14T05:40:07Z` | 9,836 | Log text | PASS | PASS | Readable UTF-8 (50 lines) |
| `evidence_71` | `evidence/records/service_resource_export_20260429_083222.json` | `service_resource_export` | `2026-04-29T08:32:22Z` | 9,691 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_72` | `evidence/databases/customer_data_inventory_20260504.sql` | `customer_data_inventory_capture` | `2026-05-04T09:41:47Z` | 6,084 | SQL script | PASS | PASS | Executable SQLite (9 tables: snapshot_scope, customer_profiles, customer_search_documents, customer_analytics_profiles, support_records, customer_exports, connector_subscriptions, backup_restore_entries, security_audit_records) |
| `evidence_73` | `evidence/logs/resource_lookup_trace_20260509_104353.log` | `service_readback_logs` | `2026-05-09T10:43:53Z` | 13,602 | Log text | PASS | PASS | Readable UTF-8 (68 lines) |
| `evidence_74` | `evidence/records/service_resource_export_20260514_114454.json` | `service_resource_export` | `2026-05-14T11:44:54Z` | 8,733 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_75` | `evidence/databases/customer_data_inventory_20260524.sql` | `customer_data_inventory_capture` | `2026-05-24T06:39:55Z` | 6,601 | SQL script | PASS | PASS | Executable SQLite (9 tables: snapshot_scope, customer_profiles, customer_search_documents, customer_analytics_profiles, support_records, customer_exports, connector_subscriptions, backup_restore_entries, security_audit_records) |
| `evidence_76` | `evidence/logs/resource_lookup_trace_20260529_074313.log` | `service_readback_logs` | `2026-05-29T07:43:13Z` | 9,626 | Log text | PASS | PASS | Readable UTF-8 (48 lines) |
| `evidence_77` | `evidence/records/service_resource_export_20260603_083457.json` | `service_resource_export` | `2026-06-03T08:34:57Z` | 9,475 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_78` | `evidence/databases/customer_data_inventory_20260618.sql` | `customer_data_inventory_capture` | `2026-06-18T11:44:03Z` | 5,787 | SQL script | PASS | PASS | Executable SQLite (9 tables: snapshot_scope, customer_profiles, customer_search_documents, customer_analytics_profiles, support_records, customer_exports, connector_subscriptions, backup_restore_entries, security_audit_records) |
| `evidence_79` | `evidence/logs/resource_lookup_trace_20260623_053726.log` | `service_readback_logs` | `2026-06-23T05:37:26Z` | 12,014 | Log text | PASS | PASS | Readable UTF-8 (60 lines) |
| `evidence_80` | `evidence/records/service_resource_export_20260628_062556.json` | `service_resource_export` | `2026-06-28T06:25:56Z` | 8,742 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_81` | `evidence/databases/customer_data_inventory_20260703.sql` | `customer_data_inventory_capture` | `2026-07-03T07:43:56Z` | 6,626 | SQL script | PASS | PASS | Executable SQLite (9 tables: snapshot_scope, customer_profiles, customer_search_documents, customer_analytics_profiles, support_records, customer_exports, connector_subscriptions, backup_restore_entries, security_audit_records) |
| `evidence_82` | `evidence/logs/resource_lookup_trace_20260713_093359.log` | `service_readback_logs` | `2026-07-13T09:33:59Z` | 10,662 | Log text | PASS | PASS | Readable UTF-8 (54 lines) |
| `evidence_83` | `evidence/records/service_resource_export_20260718_104335.json` | `service_resource_export` | `2026-07-18T10:43:35Z` | 10,775 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_84` | `evidence/databases/customer_data_inventory_20260723.sql` | `customer_data_inventory_capture` | `2026-07-23T11:43:30Z` | 6,994 | SQL script | PASS | PASS | Executable SQLite (9 tables: snapshot_scope, customer_profiles, customer_search_documents, customer_analytics_profiles, support_records, customer_exports, connector_subscriptions, backup_restore_entries, security_audit_records) |
| `evidence_85` | `evidence/logs/resource_lookup_trace_20260728_054417.log` | `service_readback_logs` | `2026-07-28T05:44:17Z` | 9,052 | Log text | PASS | PASS | Readable UTF-8 (46 lines) |
| `evidence_86` | `evidence/records/service_resource_export_20260807_074104.json` | `service_resource_export` | `2026-08-07T07:41:04Z` | 8,346 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_87` | `evidence/databases/customer_data_inventory_20260817.sql` | `customer_data_inventory_capture` | `2026-08-17T09:42:50Z` | 5,922 | SQL script | PASS | PASS | Executable SQLite (9 tables: snapshot_scope, customer_profiles, customer_search_documents, customer_analytics_profiles, support_records, customer_exports, connector_subscriptions, backup_restore_entries, security_audit_records) |
| `evidence_88` | `evidence/logs/resource_lookup_trace_20260822_103910.log` | `service_readback_logs` | `2026-08-22T10:39:10Z` | 9,059 | Log text | PASS | PASS | Readable UTF-8 (46 lines) |
| `evidence_89` | `evidence/records/service_resource_export_20260901_053316.json` | `service_resource_export` | `2026-09-01T05:33:16Z` | 9,390 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_90` | `evidence/databases/customer_data_inventory_20260905.sql` | `customer_data_inventory_capture` | `2026-09-05T07:18:01Z` | 2,314 | SQL script | PASS | PASS | Executable SQLite (9 tables: snapshot_scope, customer_profiles, customer_search_documents, customer_analytics_profiles, support_records, customer_exports, connector_subscriptions, backup_restore_entries, security_audit_records) |
| `evidence_91` | `evidence/logs/resource_lookup_trace_20260911_074253.log` | `service_readback_logs` | `2026-09-11T07:42:53Z` | 12,248 | Log text | PASS | PASS | Readable UTF-8 (62 lines) |
| `evidence_92` | `evidence/records/service_resource_export_20260915_114455.json` | `service_resource_export` | `2026-09-15T11:44:55Z` | 11,804 | JSON text | PASS | PASS | Valid JSON (dict, len=4) |
| `evidence_93` | `evidence/databases/customer_data_inventory_20260916.sql` | `customer_data_inventory_capture` | `2026-09-16T08:37:39Z` | 5,550 | SQL script | PASS | PASS | Executable SQLite (9 tables: snapshot_scope, customer_profiles, customer_search_documents, customer_analytics_profiles, support_records, customer_exports, connector_subscriptions, backup_restore_entries, security_audit_records) |
| `evidence_94` | `evidence/logs/resource_lookup_trace_20260926_103856.log` | `service_readback_logs` | `2026-09-26T10:38:56Z` | 11,743 | Log text | PASS | PASS | Readable UTF-8 (58 lines) |

---

## 5. Evidence Families Grouping & Complete Membership

Manifest entries were grouped by `(origin, normalized_filename_pattern, extension)`. Including directory context (`databases/`, `documents/`, `images/`, `logs/`, `records/`) disambiguates origin roles.

### Grouping Rules & Family Count Explanation
- **Rule 1 (Consolidated Families - 40 Families):** Replaces ISO/date timestamps with `<date>` and regional identifier tokens (e.g. `_ap_south`, `_eu_west`, `_us_west`) with `_<region>`. Under this rule, the 6 regional observability log streams each consolidate into a single 2-file family, yielding **40 distinct evidence families**.
- **Rule 2 (Exact-Pattern Families - 46 Families):** Replaces dates `<date>` only, keeping region names distinct. Under this rule, the 12 observability log files form 12 single-file families, yielding **46 distinct evidence families**.

Both rules sum to exactly **94 files**. The consolidated 40-family registry is detailed below with the **complete member `file_id` list** and explicit minimum-to-maximum span:

| Origin System | Normalized Pattern | Count | Member `file_id`s | Min..Max Bound | Captured Date Range |
|---|---|---:|---|---|---|
| `account_admin_portal` | `images/account_admin_console_<date>.png` | 1 | `evidence_04` | `evidence_04` (single file) | `2026-09-26` to `2026-09-26` |
| `account_history_service` | `documents/account_history_report_<date>.pdf` | 1 | `evidence_18` | `evidence_18` (single file) | `2026-07-18` to `2026-07-18` |
| `analytics_platform` | `images/analytics_profile_view_<date>.png` | 1 | `evidence_19` | `evidence_19` (single file) | `2026-07-13` to `2026-07-13` |
| `analytics_platform` | `records/customer_analytics_report_<date>.json` | 1 | `evidence_56` | `evidence_56` (single file) | `2026-09-07` to `2026-09-07` |
| `backup_service` | `images/backup_restore_console_<date>.png` | 1 | `evidence_32` | `evidence_32` (single file) | `2026-04-29` to `2026-04-29` |
| `central_observability_export` | `logs/application_trace_<region>_<date>.log` | 2 | `evidence_16`, `evidence_44` | `evidence_16`..`evidence_44` (span) | `2026-03-02` to `2026-07-30` |
| `central_observability_export` | `logs/cloud_runtime_export_<region>_<date>.log` | 2 | `evidence_25`, `evidence_53` | `evidence_25`..`evidence_53` (span) | `2026-06-08` to `2026-09-30` |
| `central_observability_export` | `logs/operations_stream_<region>_<date>.log` | 2 | `evidence_21`, `evidence_48` | `evidence_21`..`evidence_48` (span) | `2026-02-03` to `2026-07-05` |
| `central_observability_export` | `logs/service_events_<region>_<date>.log` | 2 | `evidence_01`, `evidence_30` | `evidence_01`..`evidence_30` (span) | `2026-05-16` to `2026-09-15` |
| `central_observability_export` | `logs/structured_service_events_<region>_<date>.log` | 2 | `evidence_06`, `evidence_34` | `evidence_06`..`evidence_34` (span) | `2026-04-19` to `2026-09-18` |
| `central_observability_export` | `logs/syslog_archive_<region>_<date>.log` | 2 | `evidence_11`, `evidence_39` | `evidence_11`..`evidence_39` (span) | `2026-03-25` to `2026-08-24` |
| `customer_account_failover_replica_capture` | `databases/customer_accounts_failover_replica_<date>.sql` | 1 | `evidence_54` | `evidence_54` (single file) | `2026-09-02` to `2026-09-02` |
| `customer_account_service` | `records/customer_account_handover_<date>.txt` | 1 | `evidence_03` | `evidence_03` (single file) | `2026-10-01` to `2026-10-01` |
| `customer_data_failover_replica_capture` | `databases/customer_data_failover_replica_<date>.sql` | 1 | `evidence_52` | `evidence_52` (single file) | `2026-09-20` to `2026-09-20` |
| `customer_data_inventory_capture` | `databases/customer_data_inventory_<date>.sql` | 11 | `evidence_63`, `evidence_66`, `evidence_69`, `evidence_72`, `evidence_75`, `evidence_78`, `evidence_81`, `evidence_84`, `evidence_87`, `evidence_90`, `evidence_93` | `evidence_63`..`evidence_93` (span) | `2026-02-13` to `2026-09-16` |
| `customer_data_read_replica_capture` | `databases/customer_data_read_replica_<date>.sql` | 5 | `evidence_05`, `evidence_10`, `evidence_15`, `evidence_20`, `evidence_24` | `evidence_05`..`evidence_24` (span) | `2026-06-13` to `2026-09-21` |
| `customer_data_regional_replicas_capture` | `databases/customer_data_regional_replicas_<date>.sql` | 3 | `evidence_29`, `evidence_33`, `evidence_38` | `evidence_29`..`evidence_38` (span) | `2026-03-30` to `2026-05-19` |
| `customer_data_reporting_replica_capture` | `databases/customer_data_reporting_replica_<date>.sql` | 2 | `evidence_43`, `evidence_47` | `evidence_43`..`evidence_47` (span) | `2026-02-08` to `2026-03-05` |
| `customer_export_service` | `records/customer_export_manifest_<date>.json` | 1 | `evidence_36` | `evidence_36` (single file) | `2026-04-09` to `2026-04-09` |
| `customer_search_primary_capture` | `databases/customer_search_primary_<date>.sql` | 1 | `evidence_57` | `evidence_57` (single file) | `2026-09-10` to `2026-09-10` |
| `downstream_delivery_service` | `logs/notification_delivery_<date>.log` | 1 | `evidence_41` | `evidence_41` (single file) | `2026-03-15` to `2026-03-15` |
| `export_service` | `images/customer_export_console_<date>.png` | 1 | `evidence_23` | `evidence_23` (single file) | `2026-06-18` to `2026-06-18` |
| `export_service` | `records/customer_export_jobs_<date>.json` | 1 | `evidence_59` | `evidence_59` (single file) | `2026-09-14` to `2026-09-14` |
| `identity_service` | `images/deleted_account_reference_<date>.png` | 1 | `evidence_42` | `evidence_42` (single file) | `2026-03-10` to `2026-03-10` |
| `integration_admin` | `images/connector_management_console_<date>.png` | 1 | `evidence_14` | `evidence_14` (single file) | `2026-08-07` to `2026-08-07` |
| `integration_management_service` | `records/connector_configurations_<date>.json` | 1 | `evidence_13` | `evidence_13` (single file) | `2026-08-12` to `2026-08-12` |
| `legal_retention_service` | `documents/legal_retention_register_<date>.pdf` | 1 | `evidence_27` | `evidence_27` (single file) | `2026-05-29` to `2026-05-29` |
| `marketing_platform` | `images/marketing_profile_console.png` | 1 | `evidence_60` | `evidence_60` (single file) | `2026-09-16` to `2026-09-16` |
| `object_storage` | `images/object_storage_browser_<date>.png` | 1 | `evidence_46` | `evidence_46` (single file) | `2026-02-13` to `2026-02-13` |
| `records_assurance_snapshot_bundle` | `records/customer_data_snapshot_bundle_<date>.json` | 12 | `evidence_02`, `evidence_07`, `evidence_12`, `evidence_17`, `evidence_22`, `evidence_26`, `evidence_31`, `evidence_35`, `evidence_40`, `evidence_45`, `evidence_49`, `evidence_51` | `evidence_02`..`evidence_51` (span) | `2026-01-31` to `2026-09-17` |
| `search_index_admin` | `images/search_index_inspector_<date>.png` | 1 | `evidence_09` | `evidence_09` (single file) | `2026-09-01` to `2026-09-01` |
| `search_index_service` | `logs/search_index_diagnostic_<date>.log` | 1 | `evidence_08` | `evidence_08` (single file) | `2026-09-06` to `2026-09-06` |
| `security_audit_service` | `records/security_audit_ledger_<date>.json` | 1 | `evidence_50` | `evidence_50` (single file) | `2026-10-01` to `2026-10-01` |
| `security_service` | `documents/security_retention_extract.pdf` | 1 | `evidence_55` | `evidence_55` (single file) | `2026-09-05` to `2026-09-05` |
| `security_service` | `images/security_audit_explorer_<date>.png` | 1 | `evidence_37` | `evidence_37` (single file) | `2026-09-05` to `2026-09-05` |
| `service_readback_logs` | `logs/resource_lookup_trace_<date>.log` | 11 | `evidence_64`, `evidence_67`, `evidence_70`, `evidence_73`, `evidence_76`, `evidence_79`, `evidence_82`, `evidence_85`, `evidence_88`, `evidence_91`, `evidence_94` | `evidence_64`..`evidence_94` (span) | `2026-02-18` to `2026-09-26` |
| `service_resource_export` | `records/service_resource_export_<date>.json` | 11 | `evidence_62`, `evidence_65`, `evidence_68`, `evidence_71`, `evidence_74`, `evidence_77`, `evidence_80`, `evidence_83`, `evidence_86`, `evidence_89`, `evidence_92` | `evidence_62`..`evidence_92` (span) | `2026-01-29` to `2026-09-15` |
| `support_platform` | `documents/delivery_correction_attachment.pdf` | 1 | `evidence_58` | `evidence_58` (single file) | `2026-09-12` to `2026-09-12` |
| `support_platform` | `images/support_ticket_console_<date>.png` | 1 | `evidence_28` | `evidence_28` (single file) | `2026-05-24` to `2026-05-24` |
| `support_platform` | `logs/support_replica.log` | 1 | `evidence_61` | `evidence_61` (single file) | `2026-09-17` to `2026-09-17` |

---

## 6. Manifest vs. Filesystem Reconciliation

An exhaustive automated walk of `dataset/evidence/` reconciled against `dataset/evidence_files.csv` confirmed:
- **Files Listed in Manifest but Missing on Disk:** `0`
- **Files Present on Disk but Unlisted in Manifest:** `0`
- **Duplicate `file_id`s in Manifest:** `0` (94/94 unique)
- **Duplicate `file_path`s in Manifest:** `0` (94/94 unique)
- **Unreadable / Corrupted Files:** `0` (all 94 files opened and parsed)
- **Signature / Extension Mismatches:** `0` (magic bytes and headers align with declared extensions)
- **Invalid Timestamps:** `0` (all 94 `captured_at` values are valid ISO-8601 strings)

---

## 7. Available Python Parsing Libraries & CLI Tools

The execution environment was audited for available tools and tested against actual evidence:

### 7.1 Document & PDF Tools
- **`fitz` (PyMuPDF):** **Available & Operational** (tested on all 4 PDFs; parsed pages, fonts, and text).
- **`pdfplumber`:** **Available & Operational** (tested on all 4 PDFs; extracted layout and table bounding boxes).
- **`pdftotext` CLI:** **Available** (`/usr/local/bin/pdftotext`).
- **`pdftoppm` CLI:** **Available** (`/usr/local/bin/pdftoppm`).
- Note: `pypdf` is not installed; `fitz` and `pdfplumber` are utilized.

### 7.2 Image & OCR Tools
- **`PIL` / `Pillow`:** **Available & Operational** (tested format, mode, and dimension decoding across all 11 PNGs).
- **`pytesseract`:** **Available & Operational** (tested full OCR extraction across all 11 PNG screenshots).
- **`tesseract` CLI:** **Available** (v5.x operational on PATH).
- **`sips` CLI:** **Available** (macOS built-in image utility).

### 7.3 Structured Data, Logs, & Databases
- **`sqlite3` (Python stdlib & CLI):** **Available & Operational** (all 24 SQL files successfully executed in memory).
- **`json` (Python stdlib):** **Available & Operational** (all 28 JSON files parsed).
- **`pandas` & `numpy`:** **Available & Operational**.

---

## 8. Document & Image Extraction Verification vs. Quality Limitations

To ensure rigorous auditability, extraction claims are divided into four verification tiers:
1. **File Validation:** The file exists, has a valid header, and can be opened without error.
2. **Basic Extraction:** Non-empty text or raw data was extracted.
3. **Structured Extraction:** Expected tables, fields, or records were identified.
4. **Content-Quality Verification:** Extracted content was verified against the source for accuracy.

### 8.1 PDF Verification Details (4 files)
- **`evidence_18` (`account_history_report_20260718.pdf`):** 2 pages, 718 characters extracted via PyMuPDF. `pdfplumber` identified 5 table objects (customer statement, invoice line items).
- **`evidence_27` (`legal_retention_register_20260529.pdf`):** 2 pages, 1,002 characters extracted via PyMuPDF. `pdfplumber` identified 3 table objects (tax and disputed order register).
- **`evidence_55` (`security_retention_extract.pdf`):** 1 page, 616 characters extracted via PyMuPDF. `pdfplumber` identified 3 table objects (compliance journal signed extracts).
- **`evidence_58` (`delivery_correction_attachment.pdf`):** 2 pages, 837 characters extracted via PyMuPDF. `pdfplumber` identified 4 table objects (support ticket address correction form).
- **Observed PDF Diagnostic:** PyMuPDF noted `"CropBox missing from /Page, defaulting to MediaBox"` during layout inspection. The files opened and rendered successfully regardless.
- **Extraction Limitation:** While Tier 1, Tier 2, and preliminary Tier 3 extractions passed, full Tier 4 semantic accuracy (checking table cell coordinates and character precision against ground truth) remains to be audited in Phase 2.

### 8.2 Image & OCR Verification Details (11 PNG files)
All 11 PNG files are RGB screenshots with dimensions ranging from 1500x920 to 1800x1200:
- `evidence_04`: 1800x1200 RGB | OCR output: 993 characters (account admin console)
- `evidence_09`: 1800x1100 RGB | OCR output: 952 characters (search index inspector)
- `evidence_14`: 1800x1150 RGB | OCR output: 966 characters (connector management console)
- `evidence_19`: 1800x1150 RGB | OCR output: 999 characters (analytics profile view)
- `evidence_23`: 1800x1100 RGB | OCR output: 1,098 characters (customer export console)
- `evidence_28`: 1800x1200 RGB | OCR output: 1,115 characters (support ticket console)
- `evidence_32`: 1800x1150 RGB | OCR output: 1,263 characters (backup restore console)
- `evidence_37`: 1800x1100 RGB | OCR output: 1,472 characters (security audit explorer)
- `evidence_42`: 1800x1100 RGB | OCR output: 1,165 characters (deleted account reference)
- `evidence_46`: 1800x1150 RGB | OCR output: 1,282 characters (object storage browser)
- `evidence_60`: 1500x920 RGB | OCR output: 1,070 characters (marketing profile console)
- **Extraction Limitation:** Tier 1 and Tier 2 passed completely (all images produced non-empty text >950 chars). However, OCR output contains potential character noise (e.g. column headers, status badges, UUIDs). Ground-truth alignment of parsed IDs and status labels has not yet been audited.

### 8.3 JSON and SQL Extraction Details
- **JSON (28 files):** All 28 files parse with standard `json.load()`. Top-level structures are either dictionaries (snapshot bundles, export jobs) or arrays.
- **SQL (24 files):** All 24 files execute cleanly inside SQLite `:memory:` instances without syntax errors. They define primary tables and corresponding read, regional, reporting, or failover replicas.
- **Logs & Plain Text (27 files):** All 26 `.log` files and 1 `.txt` file decode as valid UTF-8 without replacement errors.

---

## 9. Repeatable Commands & Test Execution

The audit is 100% reproducible via the persistent script `code/validate_inventory.py`:

```bash
# Execute deterministic dataset and evidence inventory audit
python3 code/validate_inventory.py

# Rebuild Markdown summary tables
python3 code/build_report_tables.py
```

### Script Assertions Enforced
1. Asserts row counts of all 9 CSV files against baseline expectations.
2. Asserts candidate primary key uniqueness across all primary datasets.
3. Asserts exact deletion action counts (7 DELETE, 3 REDACT, 3 RETAIN, 2 ANONYMIZE).
4. Asserts 94/94 manifest existence, path uniqueness, and file size match (2,934,541 bytes).
5. Asserts 0 missing and 0 unlisted files in `dataset/evidence/`.
6. Asserts ISO-8601 validity for all timestamps.
7. Executes SQLite scripts, loads JSON, checks UTF-8 logs, opens PDFs with PyMuPDF, and runs OCR with Pillow/Tesseract.
8. Asserts evidence family file count sums to 94.

---

## 10. Explicitly Unresolved Questions for Phase 2

1. **Request Intent Classification:** How to deterministically differentiate genuine deletion authorizations from access, export, rectification, and marketing opt-out requests across multilingual requests (English, German, French, Spanish, Italian, Portuguese, Japanese, Korean, etc.)?
2. **Subject Identity Stitching:** What deterministic join graph should link `user_identities.csv` snapshots with historical mutations in `user_audit_log.csv` (email changes, email hashes, phone numbers) to ensure full trace coverage across legacy logs and SQL replicas?
3. **Temporal Cutoff Alignment:** How to guarantee that evidence evaluation strictly excludes events or files captured after each case's `audit_at` cutoff timestamp?
4. **Replication Drift & Ground-Truth State:** How to reliably identify cases where workflow reported status (`COMPLETE` in `deletion_requests.csv` or `SUCCESS` in `system_activity.csv`) conflicts with the actual physical presence of customer PII in secondary database replicas or search index dumps?
5. **Remediation Dependency DAG:** What exact topological sort must be enforced so that `DISABLE_DATA_FLOW` and `BLOCK_RESTORE` operations are always sequenced prior to dependent `DELETE_RECORD` and `REDACT_RECORD` actions?
6. **Account Tombstones (Rule 15):** What exact fields must be redacted vs retained for account tombstones where legal retention requirements mandate preserving internal `user_id` while purging direct identifiers?
