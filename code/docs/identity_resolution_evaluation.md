# Identity Resolution & Hash Verification Evaluation

This report evaluates identifier matching, alias profile reconstruction, and
underlying hash data consistency. It does not determine deletion status or prove resource absence.

## 1. Verified CSV Schemas & Header Adaptations

Inspected actual dataset CSV headers:
- `dataset/user_identities.csv`: `user_id`, `name`, `email`, `phone`, `email_hash`, `updated_at`
- `dataset/user_audit_log.csv`: `audit_id`, `user_id`, `event_time`, `field_name`, `old_value`, `new_value`
- `dataset/deletion_requests.csv`: `case_id`, `email`, `requested_at`, `reported_status`, `reported_at`, `audit_at`, `request_text`

### Header Adaptations in `_FIELD_ALIASES`
- `observed_at` was extended to include `updatedat` (mapping `updated_at` in current identities) and `eventtime` (mapping `event_time` in audit logs).
- Existing normalized aliases handle `user_id` (`userid`), `email` (`email`), `email_hash` (`emailhash`), `phone` (`phone`), `audit_id` (`auditid`), `field_name` (`fieldname`), `old_value` (`oldvalue`), and `new_value` (`newvalue`) seamlessly.
- No modifications or renames were made to dataset files.

## 2. Dataset Sizes

- Evaluation requests: 518
- Sample requests: 32
- Current identity rows: 850
- Identity audit rows: 306

## 3. Evaluation Requests Resolution Outcomes (518 Cases)

| Outcome | Count | Percentage |
|---|---:|---:|
| RESOLVED | 518 | 100.0% |
| AMBIGUOUS | 0 | 0.0% |
| UNRESOLVED | 0 | 0.0% |

### Current vs. Historical Resolution Split

- **Direct Current Snapshot Matches**: 418 cases (80.7%) matched current identity snapshot emails directly.
- **Historical Audit Matches Only**: 100 cases (19.3%) matched an outdated email that was subsequently updated in audit history.
- *Critical finding*: Without historical audit log indexing, exactly 100 out of 518 cases would have been completely UNRESOLVED.

## 4. Match Pathways & Resolution Hardening

| Match pathway | Count | Meaning & Grounding |
|---|---:|---|
| `email+email_hash` | 518 | Exact email matched; independent explicitly stored SHA-256 hash also matched |

### Architectural Separation of Stored vs. Derived Hashes
- **Explicit Stored Hashes**: Indexed for resolution with `index_for_resolution=True`. These come exclusively from `user_identities.csv` (`email_hash` column) and `user_audit_log.csv` (`field_name='email_hash'` events).
- **Derived Hashes**: Ingested with `index_for_resolution=False`. They are retained in `IdentityProfile.email_hashes` and `aliases` for downstream evidence queries across databases and logs, but are NOT indexed as independent resolution evidence.
- **Integrity Guarantee**: A direct email match will never claim independent hash verification unless an explicitly stored hash was present in the dataset (verified by isolated unit tests).

## 5. Stored-Hash Consistency Verification (Real Dataset)

### A. Current Identity Snapshots (`dataset/user_identities.csv`)

- **Total Rows Examined**: 850
- **Comparable Rows** (valid email + valid hash): 850 (100.0%)
- **Matching Hashes** (`stored_hash == sha256(email)`): 850 (100.0% of comparable)
- **Mismatched Hashes**: 0 (0.0%)
- **Missing / Invalid Emails**: 0
- **Missing / Invalid Hashes**: 0

### B. Identity Audit Log Events (`dataset/user_audit_log.csv`)

- **Total Audit Rows**: 306
  - `email` events: 107
  - `email_hash` events: 107
  - `phone` events: 92
- **Pairing Rule**: Paired email audit rows and email_hash audit rows by matching `(user_id, event_time)`.
- **Paired Events**: 107 of 107 distinct keys (100.0% paired)
- **Unpaired Email Events**: 0
- **Unpaired Hash Events**: 0
- **Duplicated or Ambiguous Keys**: 0
- **Malformed or Invalid Values**: 0
- **Paired Old-Value Hashes Matching** (`old_hash == sha256(old_email)`): 107 / 107 (100.0%)
- **Paired New-Value Hashes Matching** (`new_hash == sha256(new_email)`): 107 / 107 (100.0%)
- **Hash Mismatches in Paired Events**: 0 (0.0%)

## 6. Sample Dataset Offline Benchmark (32 Cases)

| Outcome | Count | Percentage |
|---|---:|---:|
| RESOLVED | 32 | 100.0% |
| AMBIGUOUS | 0 | 0.0% |
| UNRESOLVED | 0 | 0.0% |

- Current snapshot matches: 29
- Historical audit-only matches: 3

## 7. Unresolved & Ambiguous Tracking

- Unresolved Cases in 518 Requests: 0 *(None)*
- Ambiguous Cases in 518 Requests: 0 *(None)*

## 8. Provenance & Diagnostics

Provenance tracking details:
- Current identity aliases record `source='current_identity'`, `source_id=''`, and `observed_at=updated_at` (no fabricated audit IDs).
- Audit log aliases record `source='audit_log'`, `source_id=audit_id`, and `observed_at=event_time`.

- `audit_log_aliases_added`: 826
- `audit_rows_seen`: 306
- `current_identity_aliases_added`: 2550
- `identity_rows_seen`: 850

## 9. Safety & Contract Rules Verified

1. **No Case-ID Heuristics**: Resolution is 100% semantic and deterministic based on normalized exact matches.
2. **Ambiguity Preservation**: Shared identifiers across distinct `user_id`s strictly return `AMBIGUOUS` with candidate user IDs (verified by unit tests).
3. **Tombstone Neutrality**: Stable `user_id` preservation does not imply data leakage; tombstone rules are left to subsequent policy evaluation.
4. **Temporal Independence**: Aliases observed after `audit_at` are indexed for identifier correlation only; deletion state is evaluated independently.
5. **Zero External Dependencies**: Standard library only; no external network requests or LLM calls.
