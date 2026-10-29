# Unstructured Evidence Content Investigation & Cross-Source Index

**Challenge:** HackerRank Orchestrate (October 2026) — *Ghost Data Still Exists*  
**Phase:** Phase 1 — Task 3: Unstructured Evidence Inspection & Grounded Index  
**Deliverable Path:** `code/docs/unstructured_evidence_analysis.md`  
**Repeatable Script:** `code/inspect_unstructured_evidence.py`  

---

## 1. Scope, Verified Manifest Counts, and Three-Tier Grounding Methodology

This report indexes all **42 participant-facing unstructured evidence files** discovered dynamically from `dataset/evidence_files.csv`:
- **PDF Documents (`.pdf`):** `4` files
- **PNG Application Screenshots (`.png`):** `11` files
- **Operational & Readback Logs (`.log`):** `26` files
- **Plain-Text Handover Records (`.txt`):** `1` file
- **Total Unstructured Files Inspected:** `42` files

### 1.1 Three-Tier Identifier Distinction
To prevent false attribution from OCR noise or uncorroborated strings, `code/inspect_unstructured_evidence.py` enforces three distinct levels of identifier validation:
1. **Extracted ID (`extracted_resource_ids`):** Any token in the document, OCR output, or log line matching the canonical resource-ID regex (`<prefix>_<digits>`). Across all 42 files, **1125** per-file deduplicated ID appearances were extracted.
2. **Grounded Resource ID (`grounded_resource_ids`):** An extracted resource ID that is independently corroborated in a trusted structured source (`system_activity.csv`, one of the 24 SQL snapshots, or one of the 28 JSON files). Across all 42 files, **663** per-file deduplicated ID appearances are grounded in structured/activity sources, while **462** per-file deduplicated ID appearances are IDs not found in the trusted structured/activity universe and require direct document-level identity corroboration.
3. **Resolved Identity Link (`resolved_identity_links`):** An explicit, provenance-backed connection to a specific `user_id` established via `user_identities.csv`, `user_audit_log.csv` (`audit_id`), `LINK_RESOURCE_IDENTITY` in `system_activity.csv` (`activity_id`), or a structured SQL/JSON record linking that `resource_id` to `user_id`. Raw customer emails, phone numbers, and hashes are redacted (`<EMAIL_REDACTED>`, `<PHONE_REDACTED>`, `<HASH_REDACTED>`) in report snippets.

---

## 2. PDF Evidence Inventory (4 Files)

All 4 PDF files were inspected page-by-page using PyMuPDF (`fitz`) and `pdfplumber`. Every status value below is derived dynamically from `r["parse_ok"]`:

| `file_id` | Path | Origin | Captured At | Pages | Chars | Tables | Extracted Resource IDs | Grounded Resource IDs | Resolved `user_id` Links | Status |
|---|---|---|---|---:|---:|---:|---|---|---|:---:|
| `evidence_18` | `evidence/documents/account_history_report_20260718.pdf` | `account_history_service` | `2026-07-18T11:00:00Z` | 2 | 718 | 5 | None | None | `user_18` | PASS |
| `evidence_27` | `evidence/documents/legal_retention_register_20260529.pdf` | `legal_retention_service` | `2026-05-29T08:00:00Z` | 2 | 1,002 | 3 | None | None | `user_08`, `user_12`, `user_17`, `user_21`, `user_24`, `user_29` | PASS |
| `evidence_55` | `evidence/documents/security_retention_extract.pdf` | `security_service` | `2026-09-05T06:30:00Z` | 1 | 616 | 3 | `audit_record_003` | `audit_record_003` | `user_03` | PASS |
| `evidence_58` | `evidence/documents/delivery_correction_attachment.pdf` | `support_platform` | `2026-09-12T07:30:00Z` | 2 | 837 | 4 | `support_001` | None | `user_07` | PASS |

---

## 3. PNG Screenshot OCR Inventory (11 Files)

All 11 PNG files were inspected using `PIL.Image` and `pytesseract` OCR. Extracted tokens were cross-checked against the trusted identity and resource universe:

| `file_id` | Path | Origin | Captured At | Dimensions | OCR Chars | Extracted Resource IDs | Grounded Resource IDs | Resolved `user_id` Links | Ungrounded OCR Emails | Status |
|---|---|---|---|---|---:|---|---|---|---:|:---:|
| `evidence_04` | `evidence/images/account_admin_console_20260926.png` | `account_admin_portal` | `2026-09-26T11:00:00Z` | 1800x1200 (RGB) | 993 | `account_5762`, `support_9538`, `support_9638` | `account_5762`, `support_9538` | `user_11` | 0 | PASS |
| `evidence_09` | `evidence/images/search_index_inspector_20260901.png` | `search_index_admin` | `2026-09-01T06:00:00Z` | 1800x1100 (RGB) | 952 | `search_428` | `search_428` | `user_13` | 2 | PASS |
| `evidence_14` | `evidence/images/connector_management_console_20260807.png` | `integration_admin` | `2026-08-07T08:00:00Z` | 1800x1150 (RGB) | 966 | `data_flow_1121` | `data_flow_1121` | `user_14`, `user_15` | 0 | PASS |
| `evidence_19` | `evidence/images/analytics_profile_view_20260713.png` | `analytics_platform` | `2026-07-13T10:00:00Z` | 1800x1150 (RGB) | 999 | `analytics_7438` | `analytics_7438` | `user_20` | 0 | PASS |
| `evidence_23` | `evidence/images/customer_export_console_20260618.png` | `export_service` | `2026-06-18T12:00:00Z` | 1800x1100 (RGB) | 1,098 | `export_1259`, `export_1260` | `export_1260` | `user_18` | 3 | PASS |
| `evidence_28` | `evidence/images/support_ticket_console_20260524.png` | `support_platform` | `2026-05-24T07:00:00Z` | 1800x1200 (RGB) | 1,115 | `support_1034` | `support_1034` | `user_22` | 0 | PASS |
| `evidence_32` | `evidence/images/backup_restore_console_20260429.png` | `backup_service` | `2026-04-29T09:00:00Z` | 1800x1150 (RGB) | 1,263 | `backup_9281`, `backup_9286`, `backup_9287`, `backup_9288`, `backup_9291` | `backup_9287` | `user_16` | 5 | PASS |
| `evidence_37` | `evidence/images/security_audit_explorer_20260905.png` | `security_service` | `2026-09-05T07:00:00Z` | 1800x1100 (RGB) | 1,472 | `audit_record_001`, `audit_record_003`, `audit_record_004`, `audit_record_005`, `audit_record_006` | `audit_record_003` | `user_03` | 0 | PASS |
| `evidence_42` | `evidence/images/deleted_account_reference_20260310.png` | `identity_service` | `2026-03-10T06:00:00Z` | 1800x1100 (RGB) | 1,165 | None | None | `user_17` | 0 | PASS |
| `evidence_46` | `evidence/images/object_storage_browser_20260213.png` | `object_storage` | `2026-02-13T08:00:00Z` | 1800x1150 (RGB) | 1,282 | None | None | None | 0 | PASS |
| `evidence_60` | `evidence/images/marketing_profile_console.png` | `marketing_platform` | `2026-09-16T07:20:00Z` | 1500x920 (RGB) | 1,070 | None | None | None | 1 | PASS |

---

## 4. LOG and TXT Evidence Inventory (26 LOG + 1 TXT = 27 Files)

All 26 `.log` files and 1 `.txt` file (`evidence_03`) were parsed line-by-line with 1-based line numbers preserved:

| `file_id` | Path | Origin | Captured At | Lines | Chars | Extracted IDs (Count) | Grounded IDs (Count) | Resolved `user_id`s (Count) | Status |
|---|---|---|---|---:|---:|---:|---:|---:|:---:|
| `evidence_01` | `evidence/logs/service_events_ap_south_20260915.log` | `central_observability_export` | `2026-09-15T11:59:39Z` | 104 | 22,133 | 36 | 25 | 10 | PASS |
| `evidence_03` | `evidence/records/customer_account_handover_20261001.txt` | `customer_account_service` | `2026-10-01T12:00:00Z` | 46 | 4,488 | 41 | 31 | 10 | PASS |
| `evidence_06` | `evidence/logs/structured_service_events_eu_west_20260918.log` | `central_observability_export` | `2026-09-18T11:55:24Z` | 112 | 31,199 | 36 | 26 | 10 | PASS |
| `evidence_08` | `evidence/logs/search_index_diagnostic_20260906.log` | `search_index_service` | `2026-09-06T07:00:00Z` | 36 | 8,013 | 35 | 25 | 10 | PASS |
| `evidence_11` | `evidence/logs/syslog_archive_us_east_20260824.log` | `central_observability_export` | `2026-08-24T13:56:43Z` | 118 | 26,414 | 36 | 25 | 10 | PASS |
| `evidence_16` | `evidence/logs/application_trace_ap_northeast_20260730.log` | `central_observability_export` | `2026-07-30T08:53:12Z` | 93 | 18,839 | 35 | 24 | 10 | PASS |
| `evidence_21` | `evidence/logs/operations_stream_eu_central_20260705.log` | `central_observability_export` | `2026-07-05T07:54:27Z` | 128 | 26,198 | 39 | 34 | 10 | PASS |
| `evidence_25` | `evidence/logs/cloud_runtime_export_us_west_20260608.log` | `central_observability_export` | `2026-06-08T09:58:28Z` | 128 | 32,266 | 43 | 32 | 10 | PASS |
| `evidence_30` | `evidence/logs/service_events_sa_east_20260516.log` | `central_observability_export` | `2026-05-16T11:58:25Z` | 110 | 23,481 | 37 | 31 | 10 | PASS |
| `evidence_34` | `evidence/logs/structured_service_events_ca_central_20260419.log` | `central_observability_export` | `2026-04-19T06:59:43Z` | 136 | 38,660 | 44 | 34 | 10 | PASS |
| `evidence_39` | `evidence/logs/syslog_archive_ap_southeast_20260325.log` | `central_observability_export` | `2026-03-25T08:59:44Z` | 114 | 25,968 | 40 | 30 | 10 | PASS |
| `evidence_41` | `evidence/logs/notification_delivery_20260315.log` | `downstream_delivery_service` | `2026-03-15T07:00:00Z` | 39 | 8,972 | 39 | 29 | 10 | PASS |
| `evidence_44` | `evidence/logs/application_trace_eu_north_20260302.log` | `central_observability_export` | `2026-03-02T10:59:23Z` | 125 | 24,885 | 39 | 32 | 10 | PASS |
| `evidence_48` | `evidence/logs/operations_stream_me_central_20260203.log` | `central_observability_export` | `2026-02-03T05:59:42Z` | 103 | 21,199 | 36 | 26 | 10 | PASS |
| `evidence_53` | `evidence/logs/cloud_runtime_export_af_south_20260930.log` | `central_observability_export` | `2026-09-30T11:59:44Z` | 305 | 94,518 | 300 | 0 | 300 | PASS |
| `evidence_61` | `evidence/logs/support_replica.log` | `support_platform` | `2026-09-17T22:00:19Z` | 10 | 1,863 | 4 | 1 | 1 | PASS |
| `evidence_64` | `evidence/logs/resource_lookup_trace_20260218_083911.log` | `service_readback_logs` | `2026-02-18T08:39:11Z` | 54 | 10,995 | 26 | 26 | 10 | PASS |
| `evidence_67` | `evidence/logs/resource_lookup_trace_20260310_061801.log` | `service_readback_logs` | `2026-03-10T06:18:01Z` | 4 | 544 | 1 | 1 | 1 | PASS |
| `evidence_70` | `evidence/logs/resource_lookup_trace_20260414_054007.log` | `service_readback_logs` | `2026-04-14T05:40:07Z` | 50 | 9,836 | 24 | 24 | 10 | PASS |
| `evidence_73` | `evidence/logs/resource_lookup_trace_20260509_104353.log` | `service_readback_logs` | `2026-05-09T10:43:53Z` | 68 | 13,602 | 33 | 33 | 10 | PASS |
| `evidence_76` | `evidence/logs/resource_lookup_trace_20260529_074313.log` | `service_readback_logs` | `2026-05-29T07:43:13Z` | 48 | 9,626 | 23 | 20 | 10 | PASS |
| `evidence_79` | `evidence/logs/resource_lookup_trace_20260623_053726.log` | `service_readback_logs` | `2026-06-23T05:37:26Z` | 60 | 12,014 | 29 | 29 | 10 | PASS |
| `evidence_82` | `evidence/logs/resource_lookup_trace_20260713_093359.log` | `service_readback_logs` | `2026-07-13T09:33:59Z` | 54 | 10,662 | 26 | 22 | 10 | PASS |
| `evidence_85` | `evidence/logs/resource_lookup_trace_20260728_054417.log` | `service_readback_logs` | `2026-07-28T05:44:17Z` | 46 | 9,052 | 22 | 19 | 10 | PASS |
| `evidence_88` | `evidence/logs/resource_lookup_trace_20260822_103910.log` | `service_readback_logs` | `2026-08-22T10:39:10Z` | 46 | 9,059 | 22 | 19 | 10 | PASS |
| `evidence_91` | `evidence/logs/resource_lookup_trace_20260911_074253.log` | `service_readback_logs` | `2026-09-11T07:42:53Z` | 62 | 12,248 | 30 | 30 | 10 | PASS |
| `evidence_94` | `evidence/logs/resource_lookup_trace_20260926_103856.log` | `service_readback_logs` | `2026-09-26T10:38:56Z` | 58 | 11,743 | 28 | 25 | 9 | PASS |

### 4.1 Observed Key-Value Operations and Statuses in Logs
- **Observed Event/Operation Attributes:** `{'event=export_started': 13, 'event=index_query_started': 72, 'event=connection_acquired': 65, 'event=dependency_retry': 31, 'event=dependency_recovered': 31, 'event=index_query_completed': 80, 'event=consumer_lag': 3, 'event=cache_refresh': 4, 'event=lease_extended': 2, 'event=delivery_abandoned': 2, 'event=message_scan_started': 7, 'event=message_pii_scan': 9, 'event=profile_lookup_started': 81, 'event=profile_lookup_completed': 91, 'event=attachment_scan_started': 3, 'event=audit_record_query_started': 32, 'event=attachment_pii_scan': 3, 'event=audit_record_read_completed': 77, 'event=cache_lookup': 34, 'event=analytics_profile_scan_started': 8, 'event=restore_policy_check_started': 2, 'event=connector_config_read_started': 42, 'event=analytics_identity_scan': 4, 'event=restore_candidate_evaluated': 3, 'event=connector_heartbeat': 10, 'event=export_download_check_started': 2, 'event=export_download_check_completed': 3, 'event=contact_lookup_completed': 1, 'event=export_completed': 13, 'event=record_lookup': 75, 'record_type=USER_PROFILE': 21, 'record_type=ANALYTICS_PROFILE': 7, 'record_type=BACKUP_ARCHIVE': 2, 'record_type=DATA_FLOW': 7, 'record_type=SEARCH_INDEX_ENTRY': 11, 'record_type=SECURITY_AUDIT_LOG': 20, 'record_type=SUPPORT_MESSAGE': 7, 'event=analytics_profile_read': 6, 'event=timer_tick': 2, 'event=certificate_checked': 2, 'event=disk_latency': 2, 'event=\\"export_started\\': 2, 'event=\\"index_query_completed\\': 8, 'event=\\"cache_refresh\\': 2, 'event=\\"lease_extended\\': 2, 'event=\\"delivery_abandoned\\': 2, 'event=\\"telemetry_flushed\\': 2, 'event=\\"message_scan_started\\': 4, 'event=\\"connection_acquired\\': 16, 'event=\\"message_pii_scan\\': 4, 'event=\\"connector_config_read_started\\': 3, 'event=\\"cache_lookup\\': 11, 'event=\\"connector_heartbeat\\': 3, 'event=\\"profile_lookup_started\\': 10, 'event=\\"dependency_retry\\': 10, 'event=\\"dependency_recovered\\': 10, 'event=\\"profile_lookup_completed\\': 310, 'event=\\"message_read\\': 1, 'event=\\"audit_record_query_started\\': 7, 'event=\\"index_query_started\\': 5, 'event=\\"audit_record_read_completed\\': 10, 'event=\\"analytics_profile_scan_started\\': 2, 'event=\\"analytics_identity_scan\\': 2, 'event=\\"attachment_scan_started\\': 1, 'event=\\"attachment_pii_scan\\': 1, 'event=\\"restore_policy_check_started\\': 1, 'event=\\"restore_authorization_completed\\': 1, 'event=\\"connector_config_loaded\\': 1, 'event=\\"analytics_profile_read\\': 2, 'event=batch_started': 1, 'event=contact_query_started': 2, 'event=contact_query_completed': 3, 'event=deletion_marker_check': 1, 'event=thumbnail_failed': 1, 'event=checkpoint_saved': 1, 'event=connector_config_read_completed': 34, 'event=analytics_profile_read_started': 39, 'event=analytics_profile_read_completed': 39, 'event=export_metadata_read_started': 5, 'event=export_metadata_read_completed': 5, 'event=support_ticket_read_started': 34, 'event=support_ticket_read_completed': 34, 'event=audit_record_read_started': 37, 'event=restore_policy_read_started': 15, 'event=restore_policy_read_completed': 15}`
- **Observed Status/Result Attributes:** `{'result=hit': 102, 'result=miss': 62, 'result=FOUND': 35, 'result=NOT_FOUND': 17, 'result=IDENTIFIABLE': 13, 'result=ANONYMIZED': 1, 'result=ACTIVE': 9, 'result=\\"hit\\': 8, 'result=\\"miss\\': 11}`

---

## 5. Cross-Source Evidence Index (Representative Grounded Findings)

Below are representative line- and page-level findings across all four unstructured modalities (`PDF`, `PNG_OCR`, `TXT`, `LOG`), showing extracted IDs, grounded resource IDs, resolved `user_id` provenance, and PII-redacted summaries:

| `file_id` | Modality | Captured At | Location | Extracted IDs | Grounded Resource IDs | Resolved `user_id` & Provenance | Reliability | Redacted Finding Summary |
|---|---|---|---|---|---|---|---|---|
| `evidence_18` | `PDF` | `2026-07-18T11:00:00Z` | `page 1, line 7` | None | None | `user_18` (direct_user_id_token) | HIGH (digital PDF text stream) | `user_18` |
| `evidence_18` | `PDF` | `2026-07-18T11:00:00Z` | `page 1, line 9` | None | None | `user_18` (email_match(user_identities.csv)) | HIGH (digital PDF text stream) | `<EMAIL_REDACTED>` |
| `evidence_27` | `PDF` | `2026-05-29T08:00:00Z` | `page 2, line 5` | None | None | `user_08` (direct_user_id_token) | HIGH (digital PDF text stream) | `ORD-20264118 \| user_08 \| Card dispute \| 04 May 2026 \| USD 184.20 \| Retain until 04 May 2033 \| AR` |
| `evidence_27` | `PDF` | `2026-05-29T08:00:00Z` | `page 2, line 7` | None | None | `user_12` (direct_user_id_token) | HIGH (digital PDF text stream) | `ORD-20264207 \| user_12 \| Tax correction \| 09 May 2026 \| EUR 72.40 \| Retain until 09 May 2033 \| ML` |
| `evidence_27` | `PDF` | `2026-05-29T08:00:00Z` | `page 2, line 9` | None | None | `user_17` (direct_user_id_token) | HIGH (digital PDF text stream) | `ORD-20264319 \| user_17 \| Chargeback \| 14 May 2026 \| GBP 219.00 \| Retain until 14 May 2033 \| SK` |
| `evidence_27` | `PDF` | `2026-05-29T08:00:00Z` | `page 2, line 11` | None | None | `user_21` (direct_user_id_token) | HIGH (digital PDF text stream) | `ORD-20264402 \| user_21 \| Invoice inquiry \| 18 May 2026 \| CAD 96.55 \| Retain until 18 May 2033 \| AR` |
| `evidence_27` | `PDF` | `2026-05-29T08:00:00Z` | `page 2, line 13` | None | None | `user_24` (direct_user_id_token) | HIGH (digital PDF text stream) | `ORD-20264511 \| user_24 \| Card dispute \| 23 May 2026 \| AUD 311.80 \| Retain until 23 May 2033 \| ML` |
| `evidence_27` | `PDF` | `2026-05-29T08:00:00Z` | `page 2, line 15` | None | None | `user_29` (direct_user_id_token) | HIGH (digital PDF text stream) | `ORD-20264600 \| user_29 \| Tax record \| 28 May 2026 \| USD 48.75 \| Retain until 28 May 2033 \| SK` |
| `evidence_04` | `PNG_OCR` | `2026-09-26T11:00:00Z` | `ocr_line 21` | `account_5762` | `account_5762` | `user_11` (direct_user_id_token, resource_link(account_5762 via system_activity:activity_4000)) | HIGH (OCR token corroborated in trusted universe) | `user_11 - account_5762` |
| `evidence_04` | `PNG_OCR` | `2026-09-26T11:00:00Z` | `ocr_line 27` | None | None | `user_11` (email_match(user_audit_log:audit_277), email_match(user_identities.csv)) | HIGH (OCR token corroborated in trusted universe) | `<EMAIL_REDACTED>` |
| `evidence_04` | `PNG_OCR` | `2026-09-26T11:00:00Z` | `ocr_line 98` | `support_9538` | `support_9538` | None | HIGH (OCR token corroborated in trusted universe) | `Support S-8538 - support_9538` |
| `evidence_09` | `PNG_OCR` | `2026-09-01T06:00:00Z` | `ocr_line 39` | None | None | `user_13` (email_match(user_identities.csv)) | HIGH (OCR token corroborated in trusted universe) | `2 email:<EMAIL_REDACTED>` |
| `evidence_09` | `PNG_OCR` | `2026-09-01T06:00:00Z` | `ocr_line 47` | None | None | `user_13` (email_match(user_identities.csv)) | HIGH (OCR token corroborated in trusted universe) | `<EMAIL_REDACTED>` |
| `evidence_09` | `PNG_OCR` | `2026-09-01T06:00:00Z` | `ocr_line 75` | `search_428` | `search_428` | `user_13` (resource_link(search_428 via system_activity:activity_4001)) | HIGH (OCR token corroborated in trusted universe) | `Raw document - search_428` |
| `evidence_09` | `PNG_OCR` | `2026-09-01T06:00:00Z` | `ocr_line 82` | None | None | `user_13` (email_match(user_identities.csv)) | HIGH (OCR token corroborated in trusted universe) | `email <EMAIL_REDACTED>` |
| `evidence_09` | `PNG_OCR` | `2026-09-01T06:00:00Z` | `ocr_line 84` | None | None | `user_13` (direct_user_id_token) | HIGH (OCR token corroborated in trusted universe) | `customer_reference user_13` |
| `evidence_03` | `TXT` | `2026-10-01T12:00:00Z` | `line 6` | `account_146` | `account_146` | `user_31` (email_match(user_identities.csv)) | HIGH (UTF-8 structured log/text line) | `- 2026-10-01T12:00:00Z \| account_service \| account_146 \| USER_PROFILE \| NOT_FOUND \| <EMAIL_REDACTED>` |
| `evidence_03` | `TXT` | `2026-10-01T12:00:00Z` | `line 7` | `account_1810` | `account_1810` | `user_38` (email_match(user_audit_log:audit_303)) | HIGH (UTF-8 structured log/text line) | `- 2026-10-01T12:00:00Z \| account_service \| account_1810 \| USER_PROFILE \| NOT_FOUND \| <EMAIL_REDACTED>` |
| `evidence_03` | `TXT` | `2026-10-01T12:00:00Z` | `line 8` | `account_2381` | `account_2381` | `user_36` (email_match(user_identities.csv)) | HIGH (UTF-8 structured log/text line) | `- 2026-10-01T12:00:00Z \| account_service \| account_2381 \| USER_PROFILE \| NOT_FOUND \| <EMAIL_REDACTED>` |
| `evidence_03` | `TXT` | `2026-10-01T12:00:00Z` | `line 9` | `account_3677` | `account_3677` | `user_37` (email_match(user_identities.csv)) | HIGH (UTF-8 structured log/text line) | `- 2026-10-01T12:00:00Z \| account_service \| account_3677 \| USER_PROFILE \| NOT_FOUND \| <EMAIL_REDACTED>` |
| `evidence_03` | `TXT` | `2026-10-01T12:00:00Z` | `line 10` | `account_4051` | `account_4051` | `user_39` (email_match(user_audit_log:audit_301)) | HIGH (UTF-8 structured log/text line) | `- 2026-10-01T12:00:00Z \| account_service \| account_4051 \| USER_PROFILE \| NOT_FOUND \| <EMAIL_REDACTED>` |
| `evidence_03` | `TXT` | `2026-10-01T12:00:00Z` | `line 11` | `account_4248` | `account_4248` | `user_32` (email_match(user_identities.csv)) | HIGH (UTF-8 structured log/text line) | `- 2026-10-01T12:00:00Z \| account_service \| account_4248 \| USER_PROFILE \| NOT_FOUND \| <EMAIL_REDACTED>` |
| `evidence_03` | `TXT` | `2026-10-01T12:00:00Z` | `line 12` | `account_4337` | `account_4337` | `user_40` (email_match(user_identities.csv)) | HIGH (UTF-8 structured log/text line) | `- 2026-10-01T12:00:00Z \| account_service \| account_4337 \| USER_PROFILE \| NOT_FOUND \| <EMAIL_REDACTED>` |
| `evidence_03` | `TXT` | `2026-10-01T12:00:00Z` | `line 13` | `account_5193` | `account_5193` | `user_35` (email_match(user_audit_log:audit_179)) | HIGH (UTF-8 structured log/text line) | `- 2026-10-01T12:00:00Z \| account_service \| account_5193 \| USER_PROFILE \| NOT_FOUND \| <EMAIL_REDACTED>` |
| `evidence_01` | `LOG` | `2026-09-15T11:59:39Z` | `line 11` | None | None | `user_19` (email_match(user_identities.csv)) | HIGH (UTF-8 structured log/text line) | `2026-09-15T11:50:57Z level=DEBUG service=support_platform instance=support-2 pod=support-70f0 region=ap-south-1 trace_id=tr-8896806 event=message_scan_started s` |
| `evidence_01` | `LOG` | `2026-09-15T11:59:39Z` | `line 15` | `support_9553` | `support_9553` | `user_19` (email_match(user_identities.csv)) | HIGH (UTF-8 structured log/text line) | `2026-09-15T11:51:08Z level=WARN service=support_platform instance=support-2 pod=support-70f0 region=ap-south-1 trace_id=tr-8896806 resource_id=support_9553 even` |
| `evidence_01` | `LOG` | `2026-09-15T11:59:39Z` | `line 16` | None | None | `user_17` (email_match(user_identities.csv)) | HIGH (UTF-8 structured log/text line) | `2026-09-15T11:51:09Z level=DEBUG service=account_service instance=account-6 pod=account-581a region=us-east-2 trace_id=tr-4708586 event=profile_lookup_started l` |
| `evidence_01` | `LOG` | `2026-09-15T11:59:39Z` | `line 18` | `search_4639` | `search_4639` | `user_20` (email_match(user_identities.csv)) | HIGH (UTF-8 structured log/text line) | `2026-09-15T11:51:16Z level=INFO service=search_service instance=search-7 pod=search-acaf region=eu-central-1 trace_id=tr-0506485 resource_id=search_4639 event=i` |
| `evidence_01` | `LOG` | `2026-09-15T11:59:39Z` | `line 21` | `account_4092` | `account_4092` | None | HIGH (UTF-8 structured log/text line) | `2026-09-15T11:51:19Z level=INFO service=account_service instance=account-6 pod=account-581a region=us-east-2 trace_id=tr-4708586 resource_id=account_4092 event=` |
| `evidence_01` | `LOG` | `2026-09-15T11:59:39Z` | `line 22` | `account_4745` | `account_4745` | `user_15` (email_match(user_identities.csv)) | HIGH (UTF-8 structured log/text line) | `2026-09-15T11:51:20Z level=INFO service=account_service instance=account-1 pod=account-b3b8 region=ap-south-1 trace_id=tr-9146590 resource_id=account_4745 event` |
| `evidence_01` | `LOG` | `2026-09-15T11:59:39Z` | `line 24` | None | None | `user_16` (direct_user_id_token) | HIGH (UTF-8 structured log/text line) | `2026-09-15T11:51:40Z level=DEBUG service=security_service instance=security-7 pod=security-a46c region=ap-south-1 trace_id=tr-4614434 event=audit_record_query_s` |
| `evidence_01` | `LOG` | `2026-09-15T11:59:39Z` | `line 25` | `support_9538` | `support_9538` | None | HIGH (UTF-8 structured log/text line) | `2026-09-15T11:51:46Z level=WARN service=support_platform instance=support-1 pod=support-63b9 region=eu-west-1 trace_id=tr-5845609 resource_id=support_9538 event` |

---

## 6. Case-Specific `audit_at` Temporal Cutoff Rules

- **Preserve File-Level `captured_at` During Indexing:** `deletion_requests.csv` contains **518 cases** spanning **72 distinct `audit_at` cutoff timestamps** (ranging from `2026-01-29T12:00:00Z` to `2026-10-01T12:00:00Z`). These 72 distinct `audit_at` values are indexed cutoffs recorded for Phase 2—not proof that case-specific time filtering has already been executed or that all 518 cases have been resolved.
- **Per-Case Filtering at Audit Time:** An unstructured evidence file with capture timestamp `captured_at` (or an internal log line with timestamp `event_time`) is admissible for a given `case_id` **if and only if `captured_at <= case.audit_at`**. No file is globally excluded during indexing because a file captured after one case's `audit_at` is valid evidence for a later case's `audit_at`.

---

## 7. Extraction Limitations and Uncertainties

1. **PDF Table Layout vs. Text Stream:** PyMuPDF (`fitz`) emits `"CropBox missing from /Page, defaulting to MediaBox"` on the 4 PDFs, but extracts 100% of the underlying digital text streams cleanly. Line-by-line text stream parsing combined with `pdfplumber` table extraction recovers all `resource_id` and `user_id` tokens.
2. **PNG OCR Fidelity:** `pytesseract` recovers 950–1,472 characters per console screenshot. Because OCR can introduce minor punctuation noise on UI badges or borders, downstream audit logic must match extracted `resource_id` and `user_id` tokens against the grounded identity/resource universe rather than relying on unvalidated free-text substrings.
3. **IDs Not Found in Trusted Universe (462 per-file deduplicated appearances):** Resource IDs that appear in PDFs, screenshots, or logs without appearing in the 52 SQL/JSON snapshots or `system_activity.csv` must be linked to a subject only when the same unstructured entry or `system_activity.csv` explicitly links that `resource_id` to a verified `user_id`, current/historical email, phone, or SHA-256 email hash.
