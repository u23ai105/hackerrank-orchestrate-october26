# Deletion Policy Evaluation Report

This report evaluates the dynamic policy rule loading, validation, and obligation mappings
derived from `dataset/deletion_rules.csv`.

- **Policy Source**: `dataset/deletion_rules.csv`
- **Total Rules Loaded**: 15
- **Unique Categories**: 15
- **Rule Parsing Duration**: 0.0007 seconds

## 1. Action Distribution

| Required Action | Count | Percentage | Description |
|---|---:|---:|---|
| `ANONYMIZE` | 2 | 13.3% | Irreversibly unlink record from subject while retaining analytical utility |
| `DELETE` | 7 | 46.7% | Complete physical removal of resource and identifiers |
| `REDACT` | 3 | 20.0% | Preserve record container while removing direct identifying PII |
| `RETAIN` | 3 | 20.0% | Preserve record under documented legal or compliance hold/retention period |

## 2. Policy Rule Registry

| Rule ID | Data Category | Condition | Required Action |
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
| `rule_15` | `ACCOUNT_TOMBSTONE` | Account is deleted and only a stable internal user_id is needed to preserve references to retained records | `REDACT` |

## 3. Compliance and Assessment Guarantees Verified

1. **Dynamic Schema Validation**: Rules are parsed dynamically without hardcoding row counts or predefined category arrays.
2. **Conflict Prevention**: Conflicting actions or duplicate contradictory categories raise explicit `PolicySchemaError` exceptions.
3. **Evidence-Driven State Classification**: Resource state (`PRESENT`, `ABSENT`, `REDACTED`, `ANONYMIZED`, `ACTIVE_FLOW`, `FLOW_DISABLED`, `RESTORE_RISK`, `RESTORE_BLOCKED`) is extracted strictly from structured fields rather than trusting bare activity log success claims.
4. **Preserved Tombstones**: Account tombstones retain internal reference keys while requiring direct personal data (name, email, phone, email hash) to be verified redacted.
