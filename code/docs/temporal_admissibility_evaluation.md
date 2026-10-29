# Temporal Admissibility Evaluation Report

This report evaluates Stage 4 temporal admissibility across all candidate evidence hits.
It distinguishes evidence admissible for proving state at `audit_at` from post-cutoff linkage-only evidence.

- **Evaluation Duration**: 9.39 seconds
- **Sample Requests Evaluated**: 32
- **Evaluation Requests Evaluated**: 518

## 1. Full Evaluation Dataset (518 Requests)

- **Total Assessed Candidate Hits**: 4054
- **State Usable (Admissible <= audit_at)**: 3410 (84.11%)
- **Linkage Only (Post-Cutoff / Non-State)**: 644 (15.89%)
- **Cases with Admissible Evidence**: 508
- **Cases with Post-Cutoff Evidence**: 110
- **Cases with Only Post-Cutoff Hits**: 0

### Disposition Breakdown (Evaluation Requests)

| Disposition | Count | Share | Semantics |
|---|---:|---:|---|
| `ADMISSIBLE` | 3410 | 84.11% | Admissible for proving resource state at or before audit_at cutoff |
| `POST_CUTOFF` | 644 | 15.89% | Captured or occurred after audit_at; usable for entity/resource linkage only |

### Basis Kind Breakdown

| Basis Kind | Count | Share | Description |
|---|---:|---:|---|
| `captured_at` | 1953 | 48.17% | File or snapshot manifest capture timestamp |
| `event_time` | 2101 | 51.83% | Individual event or activity record timestamp |

## 2. Sample Dataset (32 Requests)

- **Total Assessed Hits**: 307
- **State Usable**: 302
- **Linkage Only**: 5
- **Cases with Admissible Hits**: 29
- **Cases with Post-Cutoff Hits**: 2

## 3. Core Safety Rules Verified

1. **No Post-Cutoff State Evidence**: Evidence captured or occurring after a case's `audit_at` is strictly marked `state_usable=False`. Downstream logic cannot cite post-cutoff evidence in verification or finding steps.
2. **Snapshot Precedence**: A database snapshot captured after `audit_at` cannot prove state at `audit_at` even if individual row `updated_at` timestamps are earlier.
3. **Conservative Missing/Invalid Handling**: Unparseable or missing cutoff timestamps result in `state_usable=False` rather than permissive default admission.
4. **Zero PII Exposure**: All timestamps and diagnostic fields are completely free of raw email addresses, phone numbers, and full hashes.
