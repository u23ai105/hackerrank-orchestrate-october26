# HackerRank Orchestrate (October 2026) — Ghost Data Still Exists

Comprehensive, production-ready AI-powered deletion-audit agent built for the HackerRank Orchestrate Challenge: **Ghost Data Still Exists**.

- **Challenge & Submission URL**: [https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists](https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists)
- **Repository**: `hackerrank-orchestrate-october26`
- **Output Submission**: Root [`output.csv`](output.csv) (518 evaluation cases)
- **Code Submission**: Root [`code.zip`](code.zip) (Clean allowlist archive)

---

## 1. Executive Summary & Problem Overview

In modern distributed commerce architectures, deletion workflows frequently report **Complete** while personal customer data remains hidden in:
- Regional and failover read replicas subject to replication lag
- Search index directories and operational caches
- Centralized observability streams, service logs, and crash reports
- Customer support ticket attachments and message excerpts
- User data exports and batch inventory bundles
- Active asynchronous data pipelines and scheduled synchronization flows
- Unblocked backup archives that can resurrect deleted data upon restoration

Reported workflow statuses and activity events are merely claims. This deletion-audit agent independently determines the true evidentiary state of every request at its exact `audit_at` cutoff, identifying policy violations, active recreation risks, and orphaned records. For incomplete deletions, it produces a safe, canonically ordered remediation plan and specifies post-remediation verification checks. For compliant deletions, it provides grounded verification steps proving required states.

---

## 2. System Architecture

The deletion-audit solution is structured into an 8-stage modular pipeline:

```text
               ┌───────────────────────┐             ┌─────────────────────────┐
               │     Request Text      │             │     Requested Email     │
               └───────────┬───────────┘             └────────────┬────────────┘
                           │                                      │
                           ▼                                      ▼
               ┌───────────────────────┐             ┌─────────────────────────┐
               │ Stage 1: Intent       │             │ Stage 2: Identity       │
               │ Classifier            │             │ Resolution Engine       │
               │ request_intent.py     │             │ identity_resolution.py  │
               └───────────┬───────────┘             └────────────┬────────────┘
                           │                                      │
                           │   (Profile & Historical Identifiers) │
                           │                                      ▼
                           │                         ┌─────────────────────────┐
                           │                         │ Stage 3: Evidence       │
                           │                         │ Retrieval & Indexing    │
                           │                         │ evidence_retrieval.py   │
                           │                         └────────────┬────────────┘
                           │                                      │
                           │                                      │ (Candidate Hits)
                           ▼                                      ▼
               ┌───────────────────────────────────────────────────────────────┐
               │ Stage 4: Temporal Admissibility Filter                        │
               │ temporal_admissibility.py                                     │
               │ (Strict cutoff: file_captured_at / event_time <= audit_at)   │
               └───────────────────────────────┬───────────────────────────────┘
                                               │
                                               ▼
               ┌───────────────────────────────────────────────────────────────┐
               │ Stage 5: Dynamic Policy Compliance Assessment                 │
               │ deletion_policy.py                                            │
               │ (Maps deletion_rules.csv, handles tombstones & retention)     │
               └───────────────────────────────┬───────────────────────────────┘
                                               │
                                               ▼
               ┌───────────────────────────────────────────────────────────────┐
               │ Stage 6: Case Audit Engine                                    │
               │ audit_engine.py                                               │
               │ (Findings, ordered remediation, post-remediation verification)│
               └───────────────────────────────┬───────────────────────────────┘
                                               │
                                               ▼
               ┌───────────────────────────────────────────────────────────────┐
               │ Stage 7: Deterministic Output Builder & Contract Validator    │
               │ build_output.py / validate_output.py / main.py                │
               │ (Builds root output.csv for 518 cases with strict validation) │
               └───────────────────────────────┬───────────────────────────────┘
                                               │
                                               ▼
               ┌───────────────────────────────────────────────────────────────┐
               │ Stage 8: Evaluation Framework & Synthetic Benchmarks          │
               │ code/evaluation/main.py & custom_cases.py                     │
               │ (Accuracy metrics, 4 edge cases, usage & evaluation reports)  │
               └───────────────────────────────────────────────────────────────┘
```

### Module Responsibilities:

1. **Stage 1 — Intent Classification ([`code/tools/request_intent.py`](code/tools/request_intent.py))**:
   - Parses multilingual natural language request text (English, Spanish, French, German, Japanese, Portuguese, Korean).
   - Discerns explicit deletion requests from inquiries, profile updates, phone changes, address updates, marketing opt-outs, and standalone data export requests.
   - Emits `NOT_APPLICABLE` with `steps_json = []` when deletion is unauthorized.

2. **Stage 2 — Identity Resolution ([`code/tools/identity_resolution.py`](code/tools/identity_resolution.py))**:
   - Queries `dataset/user_identities.csv` and `dataset/user_audit_log.csv`.
   - Resolves current and historical aliases, recovering stable internal `user_id`, prior email addresses, SHA-256 email hashes, and phone numbers.

3. **Stage 3 — Evidence Retrieval & Normalization ([`code/tools/evidence_retrieval.py`](code/tools/evidence_retrieval.py))**:
   - Ingests 24 SQL database snapshots, 28 JSON records/exports, 26 log files, 14 document PDFs, application screenshots, and global `system_activity.csv`.
   - Implements two-pass trace correlation (`tr-XXXXXXX`) across asynchronous observability logs, associating lookup keys and resource actions.

4. **Stage 4 — Temporal Admissibility ([`code/tools/temporal_admissibility.py`](code/tools/temporal_admissibility.py))**:
   - Evaluates timestamps against the case's specific `audit_at` cutoff.
   - Strictly enforces file manifest capture timestamps (`captured_at <= audit_at`) and internal event times, marking post-cutoff records as inadmissible for proving historical compliance.

5. **Stage 5 — Policy Obligation Assessment ([`code/tools/deletion_policy.py`](code/tools/deletion_policy.py))**:
   - Dynamically parses `dataset/deletion_rules.csv` into typed policy rules.
   - Enforces specific treatments: `DELETE`, `REDACT`, `ANONYMIZE`, and `RETAIN`.
   - Handles `ACCOUNT_TOMBSTONE` preservation (retaining stable `user_id` while stripping direct PII).
   - Validates legal holds and security audit retention periods.

6. **Stage 6 — Case Audit Engine ([`code/tools/audit_engine.py`](code/tools/audit_engine.py))**:
   - Synthesizes findings, remediation plans, and verification checks into `CaseAuditResult`.
   - Orders remediation safely: disabling active data flows and blocking restore paths prior to changing dependent data records.
   - Assigns participant-visible evidence IDs exclusively to historical findings and complete verifications; remediation and future verification steps use empty `evidence_id = ""`.

7. **Stage 7 — Output Builder & Validator ([`code/build_output.py`](code/build_output.py) & [`code/validate_output.py`](code/validate_output.py))**:
   - Generates the root [`output.csv`](output.csv) across all 518 cases (`case_33` through `case_550`).
   - Validates JSON structure, consecutive 1-indexed numbering, canonical phase ordering (`FINDING` -> `REMEDIATION` -> `VERIFICATION`), operation rankings, and non-empty step guarantees.

8. **Stage 8 — Evaluation & Reporting ([`code/evaluation/main.py`](code/evaluation/main.py))**:
   - Evaluates performance against the 32 public sample cases in `dataset/sample_output.csv`.
   - Executes 4 custom synthetic evaluation edge cases covering complex scenarios.
   - Generates [`evaluation/evaluation_report.md`](evaluation/evaluation_report.md) and [`evaluation/usage_report.md`](evaluation/usage_report.md).

---

## 3. Repository Directory Structure

```text
.
├── AGENTS.md                          # Mandatory agent specification and logging contract
├── README.md                          # Comprehensive project documentation (this file)
├── output.csv                         # Final prediction output (518 evaluation rows)
├── code.zip                           # Packaged submission archive (45 clean entries)
├── log.txt                            # Full per-turn audit log trace (Antigravity harness)
├── .gitignore                         # Standard gitignore (caches, virtualenvs, OS files)
│
├── dataset/                           # Challenge input data (100% immutable and pristine)
│   ├── deletion_requests.csv          # 518 production evaluation requests
│   ├── sample_deletion_requests.csv   # 32 public sample requests
│   ├── sample_output.csv              # 32 public sample ground-truth answers
│   ├── user_identities.csv            # User identity snapshots
│   ├── user_audit_log.csv             # Identity change history
│   ├── system_activity.csv            # Global activity events stream
│   ├── deletion_rules.csv             # 15 domain deletion rules
│   ├── evidence_files.csv             # Manifest mapping 98 evidence files
│   └── evidence/                      # Multi-modal evidence files
│       ├── databases/                 # 24 SQLite SQL snapshot exports
│       ├── documents/                 # 14 PDF invoices and support documents
│       ├── images/                    # 6 application screenshots (PNG)
│       ├── logs/                      # 26 service and observability logs
│       └── records/                   # 28 JSON exports and inventory records
│
├── code/                              # Core implementation package
│   ├── main.py                        # Primary command-line entry point
│   ├── build_output.py                # Deterministic prediction generator
│   ├── validate_output.py             # Strict output contract validator
│   ├── package_submission.py          # Deterministic code.zip archive packager
│   ├── validate_inventory.py          # Manifest and evidence integrity validator
│   ├── inspect_structured_evidence.py   # SQL and JSON evidence analyzer
│   ├── inspect_unstructured_evidence.py # PDF, log, and OCR image analyzer
│   │
│   ├── tools/                         # Modular tool layer
│   │   ├── request_intent.py          # Stage 1: Multilingual intent classifier
│   │   ├── identity_resolution.py     # Stage 2: Historical identity resolver
│   │   ├── evidence_retrieval.py      # Stage 3: Multi-modal evidence retrieval
│   │   ├── temporal_admissibility.py  # Stage 4: Strict audit cutoff assessor
│   │   ├── deletion_policy.py         # Stage 5: Policy rules and state classifier
│   │   └── audit_engine.py            # Stage 6: Case audit & remediation planner
│   │
│   ├── tests/                         # Comprehensive unit test suite (131 tests)
│   │   ├── test_request_intent.py
│   │   ├── test_identity_resolution.py
│   │   ├── test_evidence_retrieval.py
│   │   ├── test_temporal_admissibility.py
│   │   ├── test_deletion_policy.py
│   │   └── test_audit_engine.py
│   │
│   ├── evaluation/                    # Stage 8 evaluation framework
│   │   ├── main.py                    # Evaluation runner
│   │   ├── custom_cases.py            # 4 synthetic edge-case tests
│   │   └── evaluate_*.py              # Per-stage deep evaluators
│   │
│   └── docs/                          # Detailed technical documentation & audit reports
│       ├── evidence_inventory.md
│       ├── structured_evidence_analysis.md
│       └── unstructured_evidence_analysis.md
│
├── evaluation/                        # Evaluation reports required for submission
│   ├── evaluation_report.md           # Benchmark metrics, edge cases & accuracy
│   └── usage_report.md                # Token usage, API calls ($0.00) & model details
│
└── transcripts/                       # Human-readable agent chat transcripts
    └── antigravity_execution_chat.md
```

---

## 4. Setup & Environment

### Prerequisites:
- Python 3.10+
- Recommended virtual environment:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### Dependencies:
The solution is built using Python standard library components along with lightweight document and image parsing libraries:
```bash
pip install pypdf pdfplumber pymupdf pillow pytesseract
```

Set your `PYTHONPATH` to include `code/`:
```bash
export PYTHONPATH=code
```

---

## 5. Execution Guide

### 1. Generate Full Predictions (`output.csv`):
Run the primary production pipeline from the repository root:
```bash
python3 code/main.py
```
*Output*: Generates [`output.csv`](output.csv) with exactly 518 evaluation rows (`case_33` through `case_550`).

### 2. Validate Output Contract:
Run the strict contract validation suite:
```bash
python3 code/validate_output.py
```
*Verification checks*:
- Validates 518 data rows sorted by numerical case index.
- Validates JSON step syntax, keys, and 1-indexed numbering.
- Validates canonical phase progression: `FINDING` -> `REMEDIATION` -> `VERIFICATION`.
- Validates operation and state validity against challenge taxonomy.
- Enforces temporal admissibility (no post-cutoff evidence cited).
- Enforces non-empty step requirements for all `INCOMPLETE` and `COMPLETE` cases.

### 3. Run the Unit Test Suite (131 Tests):
Execute the complete test suite across all stages:
```bash
PYTHONPATH=code python3 -m unittest discover -s code/tests -p 'test_*.py' -v
```
*Result*: 131 tests passing in ~0.05s.

### 4. Run the Evaluation Suite:
Execute the full benchmark evaluator:
```bash
python3 code/evaluation/main.py
```
*Output*: Evaluates public sample accuracy, tests 4 custom synthetic cases, and updates [`evaluation/evaluation_report.md`](evaluation/evaluation_report.md) and [`evaluation/usage_report.md`](evaluation/usage_report.md).

### 5. Package the Submission (`code.zip`):
Build the submission archive using the strict allowlist:
```bash
python3 code/package_submission.py
```
*Output*: Creates clean [`code.zip`](code.zip) (45 files, strictly excluding `dataset/`, `.venv/`, credentials, and caches).

---

## 6. Evaluation & Benchmark Results

### Performance Summary:

| Metric | Measured Result | Notes |
|---|---|---|
| **Public Ground Truth Status Accuracy** | **87.50%** (28 / 32 correct) | Evaluated against `dataset/sample_output.csv` |
| **Step F1 Score** | **69.31%** | Precision: 70.81%, Recall: 67.88% |
| **Positional Field Accuracy** | **58.29%** | 738 / 1,266 fields exactly matched |
| **Mean Sequence Similarity** | **69.82%** | Sequence alignment via `difflib.SequenceMatcher` |
| **Custom Synthetic Scenarios** | **100.0%** (4 / 4 passed) | Multilingual, replica drift, tombstone/hold, decoy rejection |
| **Unit Test Suite** | **131 / 131 passed** | 0 failures, 0 regressions |
| **Production Evaluation Output** | **518 cases validated** | 0 validation errors, 100% contract compliance |
| **Runtime & Cost** | **$0.00 / 0 tokens** | 100% deterministic local execution, 0 external API calls |

### Production Status Distribution (518 Cases):
- **`INCOMPLETE`**: 379 cases (73.17%) — Remaining records, active data flows, or restore risks identified with safe remediation plans.
- **`COMPLETE`**: 129 cases (24.90%) — All records verified deleted, redacted, anonymized, or retained per policy with grounded verification steps.
- **`NOT_APPLICABLE`**: 10 cases (1.93%) — Inquiries, updates, or non-deletion requests with empty step arrays `[]`.

---

## 7. Custom Synthetic Evaluation Scenarios

The test framework in [`code/evaluation/custom_cases.py`](code/evaluation/custom_cases.py) evaluates 4 synthetic edge-case scenarios:

1. **Multilingual Non-Deletion Request**:
   - *Scenario*: Spanish request (`"No quiero eliminar mi cuenta; solo necesito una copia de mis datos..."`) seeking data export and marketing opt-out while explicitly negating deletion.
   - *Outcome*: Correctly classified as `NOT_APPLICABLE` with `steps_json = []`.

2. **Historical Alias Replica Drift + Active Data Flow**:
   - *Scenario*: Request submitted with historical email alias (`historical.alias@example.com`). Secondary read replica retains outdated customer records alongside an active synchronization pipeline.
   - *Outcome*: Correctly classified as `INCOMPLETE`, ordering `DISABLE_DATA_FLOW` before `DELETE_RECORD`, followed by post-remediation verification checks.

3. **Account Tombstone with Exposed PII + Retained Security Audit Log + Backup Risk**:
   - *Scenario*: Tombstone record still contains exposed email and phone identifiers (violating Rule 15), while security audit log is within retention (Rule 12), and unblocked backup archive allows restoration (Rule 14).
   - *Outcome*: Generates findings for exposed PII and restore risk, orders `BLOCK_RESTORE` then `REDACT_RECORD`, and verifies tombstone redaction, audit log retention, and restore blocking.

4. **Post-Cutoff Evidence Decoy Rejection**:
   - *Scenario*: Decoy snapshot captured after `audit_at` claims a resource was deleted, while the newest admissible pre-cutoff snapshot shows it was `PRESENT`.
   - *Outcome*: Strictly rejects post-cutoff evidence, citing admissible historical evidence and maintaining fail-closed audit integrity.

---

## 8. Key Implementation Innovations & Hardening

1. **Two-Pass Multi-Line Trace Correlation**:
   - Centralized observability streams often separate lookup queries (`email`), trace identifiers (`tr-XXXXXXX`), and query outcomes (`rows=0`, `http_status=404`) across discrete lines.
   - Implemented a two-pass parser in [`evidence_retrieval.py`](code/tools/evidence_retrieval.py) that propagates trace-level context across all related lines, resolving resources that would otherwise lack direct identifier linkages.

2. **Strict Manifest-Level Temporal Enforcement**:
   - Evaluates evidence file manifest capture timestamps (`evidence_files.csv:captured_at`) in addition to internal line timestamps.
   - Excludes entire files captured after `audit_at` from serving as historical proof of state at cutoff.

3. **Grounded SQL Snapshot Verification**:
   - Verifies resource absence against loaded SQLite account snapshots (`customer_accounts_failover_replica_*.sql`) only when grounded by identity and activity history.
   - Eliminates ungrounded fallback citations.

4. **Canonical System and Resource Normalization**:
   - Maps prefixes (`marketing_`, `object_`, `cache_`, `email_`, `support_`) directly to canonical system authorities (`marketing_platform`, `backup_service`, `cache_service`, `email_service`, `support_platform`).
   - Prevents activity log overrides from bypassing formal policy actions defined in `deletion_rules.csv`.

5. **Fail-Closed Retention & Legal Hold Auditing**:
   - Requires explicit evidence of active legal holds or valid retention dates (`retention_until >= audit_at`) before permitting records to be retained under `RETAIN` rules.

---

## 9. Submission Artifacts & Verification

| Item | Location | Verification Status |
|---|---|---|
| **Predictions** | [`output.csv`](output.csv) | `7d77366dd6889c27a0af551ce5f872c23c3a486af72a6b92e9e07bdfea9a2a84` |
| **Code Package** | [`code.zip`](code.zip) | Verified allowlist archive (45 entries, strictly compliant) |
| **Chat Log** | [`log.txt`](log.txt) | Appended and verified per AGENTS.md §5.2 (`tool=Antigravity`) |
| **Evaluation Report** | [`evaluation/evaluation_report.md`](evaluation/evaluation_report.md) | Verified and included in `code.zip` |
| **Usage Report** | [`evaluation/usage_report.md`](evaluation/usage_report.md) | Verified and included in `code.zip` |
| **Dataset Immutability** | `dataset/` | `git diff -- dataset` returns 0 changes (pristine) |

---

## 10. Authors & Acknowledgements

Developed with **Antigravity IDE** using **Gemini 3.8 Flash High** for the **HackerRank Orchestrate (October 2026)** competition.
