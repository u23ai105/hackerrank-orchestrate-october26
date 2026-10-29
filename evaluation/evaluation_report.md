# Evaluation Report: HackerRank Orchestrate (Ghost Data Still Exists)

## 1. Case-Level Deletion-Status Accuracy
- **Public Ground-Truth Cases Evaluated**: 32
- **Status Correct**: 28 / 32
- **Exact Status Accuracy**: 87.50%
- **Production Evaluation Dataset Cases**: 518 (from `dataset/deletion_requests.csv`)
- **Production Status Distribution**: `{"COMPLETE": 129, "INCOMPLETE": 379, "NOT_APPLICABLE": 10}`

## 2. Step-Level and Field-Level Accuracy
- **Step Precision**: 70.81%
- **Step Recall**: 67.88%
- **Step F1 Score**: 69.31%
- **Step Counts (TP / FP / FN)**: 131 / 54 / 62
- **Positional Field Accuracy**: 58.29% (738 / 1266 matched)
- **Step Fields Measured**: `phase`, `system_id`, `resource_id`, `operation`, `state`, `evidence_id`

## 3. Sequence Accuracy
- **Exact Full-Sequence Matches**: 9 / 32 (28.12%)
- **Mean Normalized Sequence Similarity**: 69.82% (computed via `difflib.SequenceMatcher`)

## 4. Custom Synthetic Evaluations
- **Passed**: 4 / 4 (100.0%)

- **Custom Case 1 (Multilingual Non-Deletion Request)**: `PASS` (expected: `NOT_APPLICABLE`, actual: `NOT_APPLICABLE`, steps: 0)
- **Custom Case 2 (Historical Alias Replica Drift + Active Data Flow)**: `PASS` (expected: `INCOMPLETE`, actual: `INCOMPLETE`, steps: 6)
- **Custom Case 3 (Tombstone Exposed PII + Retained Audit Log + Backup Risk)**: `PASS` (expected: `INCOMPLETE`, actual: `INCOMPLETE`, steps: 7)
- **Custom Case 4 (Post-Cutoff Evidence Decoy Rejection)**: `PASS` (expected: `INCOMPLETE`, actual: `INCOMPLETE`, steps: 3)

### Detailed Breakdown of Custom Scenarios:
1. **Multilingual Non-Deletion Request**: Evaluates non-English requests (e.g., Spanish `"No quiero eliminar mi cuenta; solo necesito una copia de mis datos y darme de baja del marketing."`) requesting data export and marketing opt-out while explicitly negating account deletion. Correctly returns `NOT_APPLICABLE` with `steps_json = []`.
2. **Historical Email Alias Replica Drift + Active Data Flow**: Tests identity resolution of historical alias (`historical.alias@example.com`) where an un-replicated replica retains the record (`account_service`) alongside an active data flow (`integration_service`). Verifies that remediation plans order `DISABLE_DATA_FLOW` before `DELETE_RECORD`.
3. **Account Tombstone with Exposed PII + Retained Security Audit Log + Backup Risk**: Verifies policy rule 15 (tombstone redaction), rule 12 (security audit retention), and rule 14 (backup restore risk blocking). Verifies remediation ordering `BLOCK_RESTORE` then `REDACT_RECORD`, followed by post-remediation verification checks `VERIFY_RECORD_PRESENT`, `VERIFY_RECORD_REDACTED`, and `VERIFY_RESTORE_BLOCKED`.
4. **Post-Cutoff Evidence Decoy Rejection**: Evaluates temporal admissibility when a decoy snapshot captured after `audit_at` claims a resource was deleted, while the latest admissible snapshot prior to `audit_at` shows the resource was `PRESENT`. Verifies that post-cutoff evidence is rejected (`state_usable=False`) and only admissible pre-cutoff evidence is cited.

## 5. Failures Found and Improvements Made
1. **Two-Pass Trace ID Context Linking in Logs**: In `service_events_*.log` and `resource_lookup_trace_*.log`, lookup keys (`email`) and outcome rows (`resource_id`, `status_code=404`) frequently appear on separate log lines sharing a `trace_id`. Implemented a two-pass context linking pass in `evidence_retrieval._parse_log_or_txt()` to associate discrete log lines by `trace_id`.
2. **Manifest Captured-At Cutoff Enforcement**: Discovered that snapshots such as `evidence_02` had older internal record timestamps (`2026-09-09`) while the manifest file capture was `2026-09-17`. Enforced file manifest-level filtering (`manifest_captured_at <= audit_at`) so that entire post-cutoff files are excluded from proving state at `audit_at`.
3. **Data Flows and Backups Compliance Mapping**: `DATA_FLOW` does not have a separate row in `deletion_rules.csv`, and `BACKUP_ARCHIVE` requires blocking restore access. Updated `assess_policy_state()` to classify `FLOW_DISABLED` and `RESTORE_BLOCKED` as compliant (`True`), and `ACTIVE_FLOW` and `RESTORE_RISK` as non-compliant violations (`False`).
4. **Deletion Worker Operational Alignment in `system_activity.csv`**: Grounded resource operations against deletion worker claims in `system_activity.csv` (`DELETE_RECORD` for support attachments and failed analytics profile deletes vs `REDACT_RECORD` for support messages).
5. **PDF Document-Level Resource ID Inheritance**: Resolved PDF attachment extraction where header support references (`support_001` in `evidence_58`) were not inherited by customer detail rows. Inheriting document-level resource IDs grounded customer attachments directly to `support_platform`.

## Execution Metadata
- **Evaluation Runtime**: 9.363 seconds
- **Deterministic Local Runtime**: Local Python execution with 0 external LLM API calls.
- **Contract Adherence**: Zero hardcoded case IDs or sample label lookups in production decision logic.
