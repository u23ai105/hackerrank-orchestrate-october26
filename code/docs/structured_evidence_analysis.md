# Structured Evidence Content Investigation Report

**Challenge:** HackerRank Orchestrate (October 2026) — *Ghost Data Still Exists*  
**Phase:** Phase 1 — Systematic Evidence & Data Model Discovery  
**Task:** Task 2 — Structured Evidence Content Investigation (SQL & JSON Evidence)  
**Deliverable Path:** `code/docs/structured_evidence_analysis.md`  
**Repeatable Script:** `code/inspect_structured_evidence.py`  

---

## 1. Scope, Inspected Files, and Methods

This report documents the deterministic inspection of all **52 structured evidence files** (**24 SQL snapshots** and **28 JSON files**) listed in `dataset/evidence_files.csv`, alongside relationship and timestamp analysis across `user_identities.csv`, `user_audit_log.csv`, `system_activity.csv`, and `deletion_rules.csv`.

- **Remaining Unstructured Manifest Inventory:** Verified from `dataset/evidence_files.csv` as **42 unstructured files** comprising **4 PDFs**, **11 PNGs**, **26 LOGs**, and **1 TXT** file (total manifest = 94 files).
- **Execution Method:** Every SQL file was executed in an isolated `:memory:` SQLite database (`0` disk writes), and every JSON file was parsed via Python's stdlib `json` module. All table values and `PASS`/`FAIL` indicators below are generated directly from `code/inspect_structured_evidence.py`.

---

## 2. SQL Snapshot File Inventory (24 Files)

| `file_id` | Path | Origin | Captured At | Provenance / Scope Metadata | Tables & Row Counts | Parse Result |
|---|---|---|---|---|---|:---:|
| `evidence_05` | `evidence/databases/customer_data_read_replica_20260921.sql` | `customer_data_read_replica_capture` | `2026-09-21T10:00:00Z` | SQL header comment (`topology: read_replica`; no timestamp in SQL header) | `customer_data_primary`: 30<br>`customer_data_read_replica`: 31 | PASS |
| `evidence_10` | `evidence/databases/customer_data_read_replica_20260827.sql` | `customer_data_read_replica_capture` | `2026-08-27T12:00:00Z` | SQL header comment (`topology: read_replica`; no timestamp in SQL header) | `customer_data_primary`: 29<br>`customer_data_read_replica`: 30 | PASS |
| `evidence_15` | `evidence/databases/customer_data_read_replica_20260802.sql` | `customer_data_read_replica_capture` | `2026-08-02T07:00:00Z` | SQL header comment (`topology: read_replica`; no timestamp in SQL header) | `customer_data_primary`: 24<br>`customer_data_read_replica`: 25 | PASS |
| `evidence_20` | `evidence/databases/customer_data_read_replica_20260708.sql` | `customer_data_read_replica_capture` | `2026-07-08T09:00:00Z` | SQL header comment (`topology: read_replica`; no timestamp in SQL header) | `customer_data_primary`: 31<br>`customer_data_read_replica`: 32 | PASS |
| `evidence_24` | `evidence/databases/customer_data_read_replica_20260613.sql` | `customer_data_read_replica_capture` | `2026-06-13T11:00:00Z` | SQL header comment (`topology: read_replica`; no timestamp in SQL header) | `customer_data_primary`: 24<br>`customer_data_read_replica`: 26 | PASS |
| `evidence_29` | `evidence/databases/customer_data_regional_replicas_20260519.sql` | `customer_data_regional_replicas_capture` | `2026-05-19T06:00:00Z` | SQL header comment (`topology: regional_replicas`; no timestamp in SQL header) | `customer_data_primary`: 28<br>`customer_data_replica_ap_south`: 29<br>`customer_data_replica_eu_west`: 28 | PASS |
| `evidence_33` | `evidence/databases/customer_data_regional_replicas_20260424.sql` | `customer_data_regional_replicas_capture` | `2026-04-24T08:00:00Z` | SQL header comment (`topology: regional_replicas`; no timestamp in SQL header) | `customer_data_primary`: 29<br>`customer_data_replica_ap_south`: 29<br>`customer_data_replica_eu_west`: 31 | PASS |
| `evidence_38` | `evidence/databases/customer_data_regional_replicas_20260330.sql` | `customer_data_regional_replicas_capture` | `2026-03-30T10:00:00Z` | SQL header comment (`topology: regional_replicas`; no timestamp in SQL header) | `customer_data_primary`: 28<br>`customer_data_replica_ap_south`: 29<br>`customer_data_replica_eu_west`: 28 | PASS |
| `evidence_43` | `evidence/databases/customer_data_reporting_replica_20260305.sql` | `customer_data_reporting_replica_capture` | `2026-03-05T12:00:00Z` | SQL header comment (`topology: reporting_replica`; no timestamp in SQL header) | `customer_data_primary`: 25<br>`customer_data_reporting_replica`: 26 | PASS |
| `evidence_47` | `evidence/databases/customer_data_reporting_replica_20260208.sql` | `customer_data_reporting_replica_capture` | `2026-02-08T07:00:00Z` | SQL header comment (`topology: reporting_replica`; no timestamp in SQL header) | `customer_data_primary`: 24<br>`customer_data_reporting_replica`: 25 | PASS |
| `evidence_52` | `evidence/databases/customer_data_failover_replica_20260920.sql` | `customer_data_failover_replica_capture` | `2026-09-20T12:00:00Z` | SQL header comment (`topology: failover_replica`; no timestamp in SQL header) | `customer_data_failover_replica`: 16<br>`customer_data_primary`: 16 | PASS |
| `evidence_54` | `evidence/databases/customer_accounts_failover_replica_20260902.sql` | `customer_account_failover_replica_capture` | `2026-09-02T23:00:00Z` | SQL header comment (`topology: failover_replica`; no timestamp in SQL header) | `customer_profiles_failover_replica`: 4<br>`customer_profiles_primary`: 3 | PASS |
| `evidence_57` | `evidence/databases/customer_search_primary_20260910.sql` | `customer_search_primary_capture` | `2026-09-10T08:45:00Z` | SQL header comment (`topology: primary_only`; no timestamp in SQL header) | `search_documents_primary`: 3 | PASS |
| `evidence_63` | `evidence/databases/customer_data_inventory_20260213.sql` | `customer_data_inventory_capture` | `2026-02-13T07:43:27Z` | `snapshot_scope` table (7 systems; matches manifest `captured_at`) | `backup_restore_entries`: 1<br>`connector_subscriptions`: 1<br>`customer_analytics_profiles`: 3<br>`customer_exports`: 0<br>`customer_profiles`: 2<br>`customer_search_documents`: 4<br>`security_audit_records`: 4<br>`snapshot_scope`: 7<br>`support_records`: 2 | PASS |
| `evidence_66` | `evidence/databases/customer_data_inventory_20260310.sql` | `customer_data_inventory_capture` | `2026-03-10T05:38:48Z` | `snapshot_scope` table (8 systems; matches manifest `captured_at`) | `backup_restore_entries`: 1<br>`connector_subscriptions`: 4<br>`customer_analytics_profiles`: 5<br>`customer_exports`: 1<br>`customer_profiles`: 0<br>`customer_search_documents`: 7<br>`security_audit_records`: 2<br>`snapshot_scope`: 8<br>`support_records`: 3 | PASS |
| `evidence_69` | `evidence/databases/customer_data_inventory_20260404.sql` | `customer_data_inventory_capture` | `2026-04-04T10:04:19Z` | `snapshot_scope` table (8 systems; matches manifest `captured_at`) | `backup_restore_entries`: 1<br>`connector_subscriptions`: 2<br>`customer_analytics_profiles`: 4<br>`customer_exports`: 1<br>`customer_profiles`: 0<br>`customer_search_documents`: 5<br>`security_audit_records`: 3<br>`snapshot_scope`: 8<br>`support_records`: 2 | PASS |
| `evidence_72` | `evidence/databases/customer_data_inventory_20260504.sql` | `customer_data_inventory_capture` | `2026-05-04T09:41:47Z` | `snapshot_scope` table (7 systems; matches manifest `captured_at`) | `backup_restore_entries`: 1<br>`connector_subscriptions`: 4<br>`customer_analytics_profiles`: 3<br>`customer_exports`: 0<br>`customer_profiles`: 1<br>`customer_search_documents`: 6<br>`security_audit_records`: 3<br>`snapshot_scope`: 7<br>`support_records`: 3 | PASS |
| `evidence_75` | `evidence/databases/customer_data_inventory_20260524.sql` | `customer_data_inventory_capture` | `2026-05-24T06:39:55Z` | `snapshot_scope` table (8 systems; matches manifest `captured_at`) | `backup_restore_entries`: 1<br>`connector_subscriptions`: 4<br>`customer_analytics_profiles`: 6<br>`customer_exports`: 1<br>`customer_profiles`: 0<br>`customer_search_documents`: 5<br>`security_audit_records`: 4<br>`snapshot_scope`: 8<br>`support_records`: 3 | PASS |
| `evidence_78` | `evidence/databases/customer_data_inventory_20260618.sql` | `customer_data_inventory_capture` | `2026-06-18T11:44:03Z` | `snapshot_scope` table (7 systems; matches manifest `captured_at`) | `backup_restore_entries`: 0<br>`connector_subscriptions`: 1<br>`customer_analytics_profiles`: 4<br>`customer_exports`: 1<br>`customer_profiles`: 2<br>`customer_search_documents`: 6<br>`security_audit_records`: 2<br>`snapshot_scope`: 7<br>`support_records`: 3 | PASS |
| `evidence_81` | `evidence/databases/customer_data_inventory_20260703.sql` | `customer_data_inventory_capture` | `2026-07-03T07:43:56Z` | `snapshot_scope` table (8 systems; matches manifest `captured_at`) | `backup_restore_entries`: 1<br>`connector_subscriptions`: 2<br>`customer_analytics_profiles`: 5<br>`customer_exports`: 1<br>`customer_profiles`: 0<br>`customer_search_documents`: 5<br>`security_audit_records`: 5<br>`snapshot_scope`: 8<br>`support_records`: 5 | PASS |
| `evidence_84` | `evidence/databases/customer_data_inventory_20260723.sql` | `customer_data_inventory_capture` | `2026-07-23T11:43:30Z` | `snapshot_scope` table (8 systems; matches manifest `captured_at`) | `backup_restore_entries`: 1<br>`connector_subscriptions`: 4<br>`customer_analytics_profiles`: 5<br>`customer_exports`: 1<br>`customer_profiles`: 1<br>`customer_search_documents`: 7<br>`security_audit_records`: 2<br>`snapshot_scope`: 8<br>`support_records`: 5 | PASS |
| `evidence_87` | `evidence/databases/customer_data_inventory_20260817.sql` | `customer_data_inventory_capture` | `2026-08-17T09:42:50Z` | `snapshot_scope` table (8 systems; matches manifest `captured_at`) | `backup_restore_entries`: 1<br>`connector_subscriptions`: 1<br>`customer_analytics_profiles`: 4<br>`customer_exports`: 1<br>`customer_profiles`: 1<br>`customer_search_documents`: 5<br>`security_audit_records`: 2<br>`snapshot_scope`: 8<br>`support_records`: 4 | PASS |
| `evidence_90` | `evidence/databases/customer_data_inventory_20260905.sql` | `customer_data_inventory_capture` | `2026-09-05T07:18:01Z` | `snapshot_scope` table (1 systems; matches manifest `captured_at`) | `backup_restore_entries`: 0<br>`connector_subscriptions`: 0<br>`customer_analytics_profiles`: 0<br>`customer_exports`: 0<br>`customer_profiles`: 0<br>`customer_search_documents`: 0<br>`security_audit_records`: 0<br>`snapshot_scope`: 1<br>`support_records`: 0 | PASS |
| `evidence_93` | `evidence/databases/customer_data_inventory_20260916.sql` | `customer_data_inventory_capture` | `2026-09-16T08:37:39Z` | `snapshot_scope` table (8 systems; matches manifest `captured_at`) | `backup_restore_entries`: 2<br>`connector_subscriptions`: 2<br>`customer_analytics_profiles`: 2<br>`customer_exports`: 1<br>`customer_profiles`: 1<br>`customer_search_documents`: 3<br>`security_audit_records`: 3<br>`snapshot_scope`: 8<br>`support_records`: 3 | PASS |

### 2.1 SQL Provenance Verification Summary
- **`snapshot_scope` Relational Metadata (11 of 24 SQL files):** Present in the 11 multi-system inventory snapshots (`evidence_63`..`evidence_93`). In **11/11** of these files, every row in `snapshot_scope.captured_at` matches the manifest `captured_at` timestamp (`0` mismatches).
- **SQL Header Comment Metadata (24 of 24 SQL files):** All 24 SQL files begin with `--` comments; **13** files declare `-- Database topology: <type>`, while **24** SQL header comments embed an ISO-8601 timestamp string. Therefore, for the 13 non-inventory SQL snapshots, authoritative capture time comes from `dataset/evidence_files.csv` (`captured_at`) and row-level timestamps (`updated_at`, `indexed_at`).

---

## 3. Cross-Snapshot SQL Schemas: 18 Distinct Table Names Across 12 Column-Schema Patterns

Across the 24 SQL snapshots, there are **18 distinct table names** that group into **12 distinct column-schema signatures** (because primary and replica tables share identical column definitions):

| Pattern ID | Column Signature `(name, type, PK)` | Tables Sharing This Exact Schema (`18` tables total) |
|---|---|---|
| `schema_pattern_01` | `resource_id (TEXT, PK)`, `customer_reference (TEXT)`, `customer_email (TEXT)`, `archive_key (TEXT)`, `restore_allowed (INTEGER)`, `updated_at (TEXT)` | `backup_restore_entries` |
| `schema_pattern_02` | `resource_id (TEXT, PK)`, `customer_reference (TEXT)`, `customer_email (TEXT)`, `connector_name (TEXT)`, `enabled (INTEGER)`, `last_delivery_status (TEXT)`, `updated_at (TEXT)` | `connector_subscriptions` |
| `schema_pattern_03` | `resource_id (TEXT, PK)`, `customer_reference (TEXT)`, `email (TEXT)`, `phone (TEXT)`, `email_hash (TEXT)`, `audience_cohort (TEXT)`, `updated_at (TEXT)` | `customer_analytics_profiles` |
| `schema_pattern_04` | `resource_id (TEXT, PK)`, `origin_system (TEXT)`, `collection_name (TEXT)`, `record_json (TEXT)`, `updated_at (TEXT)` | `customer_data_failover_replica`, `customer_data_primary`, `customer_data_read_replica`, `customer_data_replica_ap_south`, `customer_data_replica_eu_west`, `customer_data_reporting_replica` |
| `schema_pattern_05` | `resource_id (TEXT, PK)`, `customer_reference (TEXT)`, `owner_email (TEXT)`, `owner_phone (TEXT)`, `object_key (TEXT)`, `updated_at (TEXT)` | `customer_exports` |
| `schema_pattern_06` | `resource_id (TEXT, PK)`, `customer_reference (TEXT)`, `full_name (TEXT)`, `email (TEXT)`, `phone (TEXT)`, `email_hash (TEXT)`, `account_status (TEXT)`, `updated_at (TEXT)` | `customer_profiles` |
| `schema_pattern_07` | `resource_id (TEXT, PK)`, `user_id (TEXT)`, `full_name (TEXT)`, `email (TEXT)`, `phone (TEXT)`, `account_status (TEXT)`, `updated_at (TEXT)` | `customer_profiles_failover_replica`, `customer_profiles_primary` |
| `schema_pattern_08` | `resource_id (TEXT, PK)`, `customer_reference (TEXT)`, `display_name (TEXT)`, `email (TEXT)`, `phone (TEXT)`, `email_hash (TEXT)`, `index_name (TEXT)`, `updated_at (TEXT)` | `customer_search_documents` |
| `schema_pattern_09` | `resource_id (TEXT, PK)`, `display_name (TEXT)`, `email (TEXT)`, `source_resource_id (TEXT)`, `indexed_at (TEXT)` | `search_documents_primary` |
| `schema_pattern_10` | `resource_id (TEXT, PK)`, `subject_reference (TEXT)`, `event_code (TEXT)`, `retention_until (TEXT)`, `updated_at (TEXT)` | `security_audit_records` |
| `schema_pattern_11` | `origin_system (TEXT, PK)`, `captured_at (TEXT)` | `snapshot_scope` |
| `schema_pattern_12` | `resource_id (TEXT, PK)`, `customer_reference (TEXT)`, `requester_name (TEXT)`, `requester_email (TEXT)`, `requester_phone (TEXT)`, `message_excerpt (TEXT)`, `updated_at (TEXT)` | `support_records` |

### 3.1 Inner Serialized JSON Attributes in SQL (`record_json` & `metrics_json`)
- **`record_json` (in `customer_data_primary` and 5 replica tables):** Contains 37 distinct JSON keys (`resource_id`, `user_id`, `customer_reference`, `full_name`, `name`, `email`, `phone`, `email_hash`, `account_status`, `ticket_id`, `channel`, `message_text`, `index_name`, `connector_name`, `destination`, `enabled`, `mode`, `archive_path`, `restore_allowed`, `retention_reason`, `retained_until`, etc.).
- **Observed Inner Status Values:**
  - `customer_data_primary.record_json.account_status`: `{'DELETED': 8}`
  - `customer_data_read_replica.record_json.account_status`: `{'ACTIVE': 6}`
  - `customer_data_failover_replica.record_json.account_status`: `{'DELETED': 8}`
- **Outer Relational Categorical Values:**
  - `customer_profiles.account_status`: `{'DELETION_PENDING': 6}`
  - `customer_profiles_primary.account_status`: `{'ACTIVE': 1}`
  - `customer_profiles_failover_replica.account_status`: `{'ACTIVE': 1}`
  - `connector_subscriptions.last_delivery_status`: `{'delivered': 10, 'stopped': 5}`
  - `backup_restore_entries.restore_status`: `{}`

---

## 4. JSON Evidence File Inventory (28 Files)

| `file_id` | Path | Origin | Captured At | Internal Timestamp & Source/Origin | Top-Level Counts | Parse Result |
|---|---|---|---|---|---|:---:|
| `evidence_02` | `evidence/records/customer_data_snapshot_bundle_20260917.json` | `records_assurance_snapshot_bundle` | `2026-09-17T12:00:00Z` | time: `2026-09-17T12:00:00Z`<br>src: `records_assurance_service` | `snapshots`: 11 | PASS |
| `evidence_07` | `evidence/records/customer_data_snapshot_bundle_20260913.json` | `records_assurance_snapshot_bundle` | `2026-09-13T08:00:00Z` | time: `2026-09-13T08:00:00Z`<br>src: `records_assurance_service` | `snapshots`: 9 | PASS |
| `evidence_12` | `evidence/records/customer_data_snapshot_bundle_20260819.json` | `records_assurance_snapshot_bundle` | `2026-08-19T10:00:00Z` | time: `2026-08-19T10:00:00Z`<br>src: `records_assurance_service` | `snapshots`: 11 | PASS |
| `evidence_13` | `evidence/records/connector_configurations_20260812.json` | `integration_management_service` | `2026-08-12T09:00:00Z` | time: `2026-08-12T09:00:00Z`<br>src: `integration_management_service` | `records`: 39 | PASS |
| `evidence_17` | `evidence/records/customer_data_snapshot_bundle_20260725.json` | `records_assurance_snapshot_bundle` | `2026-07-25T15:00:00Z` | time: `2026-07-25T15:00:00Z`<br>src: `records_assurance_service` | `snapshots`: 11 | PASS |
| `evidence_22` | `evidence/records/customer_data_snapshot_bundle_20260630.json` | `records_assurance_snapshot_bundle` | `2026-06-30T07:00:00Z` | time: `2026-06-30T07:00:00Z`<br>src: `records_assurance_service` | `snapshots`: 11 | PASS |
| `evidence_26` | `evidence/records/customer_data_snapshot_bundle_20260605.json` | `records_assurance_snapshot_bundle` | `2026-06-05T12:00:00Z` | time: `2026-06-05T12:00:00Z`<br>src: `records_assurance_service` | `snapshots`: 9 | PASS |
| `evidence_31` | `evidence/records/customer_data_snapshot_bundle_20260511.json` | `records_assurance_snapshot_bundle` | `2026-05-11T11:00:00Z` | time: `2026-05-11T11:00:00Z`<br>src: `records_assurance_service` | `snapshots`: 10 | PASS |
| `evidence_35` | `evidence/records/customer_data_snapshot_bundle_20260416.json` | `records_assurance_snapshot_bundle` | `2026-04-16T06:00:00Z` | time: `2026-04-16T06:00:00Z`<br>src: `records_assurance_service` | `snapshots`: 8 | PASS |
| `evidence_36` | `evidence/records/customer_export_manifest_20260409.json` | `customer_export_service` | `2026-04-09T12:00:00Z` | time: `2026-04-09T12:00:00Z`<br>src: `customer_export_service` | `records`: 46 | PASS |
| `evidence_40` | `evidence/records/customer_data_snapshot_bundle_20260322.json` | `records_assurance_snapshot_bundle` | `2026-03-22T08:00:00Z` | time: `2026-03-22T08:00:00Z`<br>src: `records_assurance_service` | `snapshots`: 12 | PASS |
| `evidence_45` | `evidence/records/customer_data_snapshot_bundle_20260223.json` | `records_assurance_snapshot_bundle` | `2026-02-23T10:00:00Z` | time: `2026-02-23T10:00:00Z`<br>src: `records_assurance_service` | `snapshots`: 11 | PASS |
| `evidence_49` | `evidence/records/customer_data_snapshot_bundle_20260131.json` | `records_assurance_snapshot_bundle` | `2026-01-31T15:00:00Z` | time: `2026-01-31T15:00:00Z`<br>src: `records_assurance_service` | `snapshots`: 10 | PASS |
| `evidence_50` | `evidence/records/security_audit_ledger_20261001.json` | `security_audit_service` | `2026-10-01T12:00:00Z` | time: `2026-10-01T12:00:00Z`<br>src: `security_audit_service` | `records`: 20 | PASS |
| `evidence_51` | `evidence/records/customer_data_snapshot_bundle_20260915.json` | `records_assurance_snapshot_bundle` | `2026-09-15T12:00:00Z` | time: `2026-09-15T12:00:00Z`<br>src: `records_assurance_service` | `snapshots`: 3 | PASS |
| `evidence_56` | `evidence/records/customer_analytics_report_20260907.json` | `analytics_platform` | `2026-09-07T09:45:00Z` | time: `2026-09-07T09:45:00Z`<br>src: `analytics_identity_store` | `records`: 2 | PASS |
| `evidence_59` | `evidence/records/customer_export_jobs_20260914.json` | `export_service` | `2026-09-14T15:40:00Z` | time: `2026-09-14T15:40:00Z`<br>src: `user_export_store` | `records`: 2 | PASS |
| `evidence_62` | `evidence/records/service_resource_export_20260129_114459.json` | `service_resource_export` | `2026-01-29T11:44:59Z` | time: `2026-01-29T11:44:59Z`<br>src: `records_assurance_gateway` | `service_exports`: 8 | PASS |
| `evidence_65` | `evidence/records/service_resource_export_20260228_103637.json` | `service_resource_export` | `2026-02-28T10:36:37Z` | time: `2026-02-28T10:36:37Z`<br>src: `records_assurance_gateway` | `service_exports`: 8 | PASS |
| `evidence_68` | `evidence/records/service_resource_export_20260320_072349.json` | `service_resource_export` | `2026-03-20T07:23:49Z` | time: `2026-03-20T07:23:49Z`<br>src: `records_assurance_gateway` | `service_exports`: 7 | PASS |
| `evidence_71` | `evidence/records/service_resource_export_20260429_083222.json` | `service_resource_export` | `2026-04-29T08:32:22Z` | time: `2026-04-29T08:32:22Z`<br>src: `records_assurance_gateway` | `service_exports`: 8 | PASS |
| `evidence_74` | `evidence/records/service_resource_export_20260514_114454.json` | `service_resource_export` | `2026-05-14T11:44:54Z` | time: `2026-05-14T11:44:54Z`<br>src: `records_assurance_gateway` | `service_exports`: 7 | PASS |
| `evidence_77` | `evidence/records/service_resource_export_20260603_083457.json` | `service_resource_export` | `2026-06-03T08:34:57Z` | time: `2026-06-03T08:34:57Z`<br>src: `records_assurance_gateway` | `service_exports`: 7 | PASS |
| `evidence_80` | `evidence/records/service_resource_export_20260628_062556.json` | `service_resource_export` | `2026-06-28T06:25:56Z` | time: `2026-06-28T06:25:56Z`<br>src: `records_assurance_gateway` | `service_exports`: 8 | PASS |
| `evidence_83` | `evidence/records/service_resource_export_20260718_104335.json` | `service_resource_export` | `2026-07-18T10:43:35Z` | time: `2026-07-18T10:43:35Z`<br>src: `records_assurance_gateway` | `service_exports`: 8 | PASS |
| `evidence_86` | `evidence/records/service_resource_export_20260807_074104.json` | `service_resource_export` | `2026-08-07T07:41:04Z` | time: `2026-08-07T07:41:04Z`<br>src: `records_assurance_gateway` | `service_exports`: 8 | PASS |
| `evidence_89` | `evidence/records/service_resource_export_20260901_053316.json` | `service_resource_export` | `2026-09-01T05:33:16Z` | time: `2026-09-01T05:33:16Z`<br>src: `records_assurance_gateway` | `service_exports`: 8 | PASS |
| `evidence_92` | `evidence/records/service_resource_export_20260915_114455.json` | `service_resource_export` | `2026-09-15T11:44:55Z` | time: `2026-09-15T11:44:55Z`<br>src: `records_assurance_gateway` | `service_exports`: 8 | PASS |

### 4.1 JSON Provenance & Categorical Summary
- **Timestamp Alignment:** **28/28** JSON files have an internal `exported_at` or `captured_at` field that exactly matches the manifest `captured_at` (`0` mismatches).
- **Origin vs. Internal Source Naming:** **3/28** JSON files use the exact same string in internal `origin` as the manifest `origin`, while **25/28** files record the internal service name in `source` (e.g., `records_assurance_service`, `records_assurance_gateway`, `analytics_identity_store`, `user_export_store`).
- **JSON `record_type` vs. `deletion_rules.csv` `data_category` Set Comparison:**
  - `deletion_rules.csv` defines **15** distinct `data_category` values; JSON `record_type` contains **9** distinct values.
  - **Overlapping Categories (8):** `ANALYTICS_PROFILE`, `BACKUP_ARCHIVE`, `LEGAL_HOLD_RECORD`, `SEARCH_INDEX_ENTRY`, `SECURITY_AUDIT_LOG`, `SUPPORT_MESSAGE`, `USER_EXPORT`, `USER_PROFILE`
  - **Rule Categories Not Present in JSON `record_type` (7):** `ACCOUNT_TOMBSTONE`, `CACHE_ENTRY`, `EMAIL_DELIVERY_LOG`, `MARKETING_PROFILE`, `PRODUCT_TELEMETRY`, `SECONDARY_IDENTIFIER`, `SUPPORT_ATTACHMENT` *(these categories appear instead via SQL tables, inner `collection_name` payloads, or unstructured logs/PDFs/screenshots)*.
  - **Observed JSON `record_type` Values With No Direct `data_category` Name in `deletion_rules.csv` (1):** `DATA_FLOW` *(corresponds to active sync/data-flow processes evaluated for recreation risk)*.

---

## 5. Canonical Entity and Resource Schema

Resource IDs across SQL, JSON, and `system_activity.csv` use consistent prefixes:
- **SQL Resource Prefixes:** `{'analytics': 134, 'audit': 276, 'backup': 34, 'data': 79, 'search': 190, 'support': 109, 'account': 27, 'export': 18, 'legal': 8, 'tombstone': 16}`
- **JSON Resource Prefixes:** `{'account': 139, 'user': 375, 'search': 214, 'analytics': 118, 'backup': 41, 'export': 20, 'data': 90, 'audit': 209, 'support': 112, 'legal': 3, 'tombstone': 2}`

---

## 6. Identity-to-Resource Relationship Patterns & Provenance

1. **Deterministic SHA-256 Email Hashing (Current & Historical):**
   - Verified `SHA-256(lowercase(email.strip()))` across **850/850** rows in `user_identities.csv` and **107/107** historical `(old_value, new_value)` email mutation pairs in `user_audit_log.csv`.
2. **`system_activity.csv` Linkage Mechanics:**
   - Across **4011** rows in `system_activity.csv`, exactly **12** rows (`event_type == 'LINK_RESOURCE_IDENTITY'`) contain `user_id` or email strings in `details` (`0` non-link rows contain user/email strings). All other **3,999** rows reference only `resource_id`.
3. **Duplicate Request Emails With Distinct Audit Cutoffs:**
   - In `deletion_requests.csv`, `{'ingrid.dahl@outlook.com': ['case_33', 'case_52']}` shares the same email across two cases with distinct `requested_at` and `audit_at` timestamps.

---

## 7. Candidate Primary/Replica Discrepancies, Tombstones, Retention, and Recreation Indicators

### 7.1 Observed Primary/Replica Discrepancies (11 Candidate Pairs)
Across the 24 SQL snapshots, comparing primary tables (`customer_data_primary` and `customer_profiles_primary`) against replica tables in the same snapshot identifies **11 observed primary/replica discrepancies, candidates for replication drift** (whether a discrepancy constitutes a deletion failure for a specific case depends on resolving the subject's identity and comparing against the case's `audit_at` cutoff):

| Evidence ID | Path | Captured At | Primary Table (`count`) | Replica Table (`count`) | Candidate Resource IDs Present in Replica Only |
|---|---|---|---|---|---|
| `evidence_05` | `evidence/databases/customer_data_read_replica_20260921.sql` | `2026-09-21T10:00:00Z` | `customer_data_primary` (30) | `customer_data_read_replica` (31) | `account_994` |
| `evidence_10` | `evidence/databases/customer_data_read_replica_20260827.sql` | `2026-08-27T12:00:00Z` | `customer_data_primary` (29) | `customer_data_read_replica` (30) | `account_6345` |
| `evidence_15` | `evidence/databases/customer_data_read_replica_20260802.sql` | `2026-08-02T07:00:00Z` | `customer_data_primary` (24) | `customer_data_read_replica` (25) | `account_8023` |
| `evidence_20` | `evidence/databases/customer_data_read_replica_20260708.sql` | `2026-07-08T09:00:00Z` | `customer_data_primary` (31) | `customer_data_read_replica` (32) | `account_4348` |
| `evidence_24` | `evidence/databases/customer_data_read_replica_20260613.sql` | `2026-06-13T11:00:00Z` | `customer_data_primary` (24) | `customer_data_read_replica` (26) | `account_3150`, `account_9608` |
| `evidence_29` | `evidence/databases/customer_data_regional_replicas_20260519.sql` | `2026-05-19T06:00:00Z` | `customer_data_primary` (28) | `customer_data_replica_ap_south` (29) | `account_585` |
| `evidence_33` | `evidence/databases/customer_data_regional_replicas_20260424.sql` | `2026-04-24T08:00:00Z` | `customer_data_primary` (29) | `customer_data_replica_eu_west` (31) | `account_6539`, `account_8105` |
| `evidence_38` | `evidence/databases/customer_data_regional_replicas_20260330.sql` | `2026-03-30T10:00:00Z` | `customer_data_primary` (28) | `customer_data_replica_ap_south` (29) | `account_5389` |
| `evidence_43` | `evidence/databases/customer_data_reporting_replica_20260305.sql` | `2026-03-05T12:00:00Z` | `customer_data_primary` (25) | `customer_data_reporting_replica` (26) | `account_3183` |
| `evidence_47` | `evidence/databases/customer_data_reporting_replica_20260208.sql` | `2026-02-08T07:00:00Z` | `customer_data_primary` (24) | `customer_data_reporting_replica` (25) | `account_1035` |
| `evidence_54` | `evidence/databases/customer_accounts_failover_replica_20260902.sql` | `2026-09-02T23:00:00Z` | `customer_profiles_primary` (3) | `customer_profiles_failover_replica` (4) | `account_005` |

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
