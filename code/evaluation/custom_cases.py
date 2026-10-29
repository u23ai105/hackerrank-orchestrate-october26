#!/usr/bin/env python3
"""
Custom synthetic evaluation cases for Stage 8.
Constructs 4 challenging synthetic edge-case scenarios and executes them
through the actual AuditEngine pipeline:
1. Multilingual non-deletion request (export/marketing opt-out) -> NOT_APPLICABLE, []
2. Historical email alias deletion with replica retention + active data flow -> INCOMPLETE (DISABLE_DATA_FLOW before DELETE_RECORD)
3. Account tombstone with direct PII + retained security audit log + active restore risk -> INCOMPLETE (BLOCK_RESTORE, REDACT_RECORD)
4. Post-cutoff evidence decoy (captured_at > audit_at shows deletion, but latest snapshot <= audit_at shows PRESENT) -> INCOMPLETE
"""

from __future__ import annotations

import copy
from typing import Any

from tools.request_intent import classify_request_intent
from tools.identity_resolution import IdentityProfile, IdentityResolution, IdentityResolver, ResolutionStatus
from tools.deletion_policy import PolicyRule, load_policy_rules
from tools.evidence_retrieval import EvidenceIndex, EvidenceRecord
from tools.audit_engine import AuditEngine, canonical_system, make_step, sort_and_number_steps


def run_custom_synthetic_cases(production_engine: AuditEngine) -> list[dict[str, Any]]:
    results = []

    # =========================================================================
    # Custom Case 1: Multilingual Non-Deletion Request (Japanese export / opt-out)
    # Expected: NOT_APPLICABLE, steps_json = []
    # =========================================================================
    case_1_req = {
        "case_id": "custom_case_01",
        "email": "user_optout@example.com",
        "requested_at": "2026-09-01T10:00:00Z",
        "reported_status": "NOT_STARTED",
        "reported_at": "2026-09-01T10:00:00Z",
        "audit_at": "2026-09-05T12:00:00Z",
        "request_text": "No quiero eliminar mi cuenta; solo necesito una copia de mis datos y darme de baja del marketing.",  # Multilingual non-deletion: export + marketing opt-out
    }
    c1_res = production_engine.audit_case(case_1_req)
    c1_passed = (c1_res.deletion_status == "NOT_APPLICABLE" and len(c1_res.steps) == 0)
    results.append({
        "name": "Custom Case 1 (Multilingual Non-Deletion Request)",
        "expected_status": "NOT_APPLICABLE",
        "actual_status": c1_res.deletion_status,
        "passed": c1_passed,
        "steps_count": len(c1_res.steps),
    })

    # =========================================================================
    # Custom Case 2: Historical email alias with replica retention + active data flow
    # Expected: INCOMPLETE with DISABLE_DATA_FLOW before DELETE_RECORD
    # =========================================================================
    rules = production_engine.policy_rules
    cutoff_2 = "2026-09-15T12:00:00Z"

    # Synthetic Identity Profile with historical alias
    prof2 = IdentityProfile(
        user_id="user_synth_2",
        emails=("active.alias@example.com", "historical.alias@example.com"),
        email_hashes=(),
        phones=(),
        aliases=(),
    )
    class MockResolver2:
        def resolve_email(self, email: str) -> IdentityResolution:
            return IdentityResolution(
                status=ResolutionStatus.RESOLVED,
                queried_email=email,
                user_id=prof2.user_id,
                candidate_user_ids=(prof2.user_id,),
                matched_by=("email",),
                profile=prof2,
                reason="synthetic_alias_match",
            )

    # Synthetic evidence: replica retains account_synth_2 (evidence_syn_2a), active data flow (evidence_syn_2b)
    rec_replica = EvidenceRecord(
        evidence_id="evidence_syn_2a",
        evidence_ref_type="file_id",
        source_path="evidence/databases/replica_store.sql",
        source_kind="sql",
        locator="table:customer_replica:row:1",
        system_id="account_service",
        resource_id="account_synth_2",
        data_category="USER_PROFILE",
        observed_at="2026-09-12T10:00:00Z",
        fields=(("captured_at", "2026-09-12T10:00:00Z"), ("status", "active"), ("email", "historical.alias@example.com")),
        text="account_synth_2 active historical.alias@example.com",
        captured_at="2026-09-12T10:00:00Z",
    )
    rec_flow = EvidenceRecord(
        evidence_id="evidence_syn_2b",
        evidence_ref_type="file_id",
        source_path="evidence/records/connector_state.json",
        source_kind="json",
        locator="entry:data_flow_synth_2",
        system_id="integration_service",
        resource_id="data_flow_synth_2",
        data_category="DATA_FLOW",
        observed_at="2026-09-13T08:00:00Z",
        fields=(("captured_at", "2026-09-13T08:00:00Z"), ("status", "active"), ("enabled", "true"), ("customer_reference", "user_synth_2")),
        text="data_flow_synth_2 enabled=true",
        captured_at="2026-09-13T08:00:00Z",
    )
    manifest_2 = [
        {"file_id": "evidence_syn_2a", "captured_at": "2026-09-12T10:00:00Z"},
        {"file_id": "evidence_syn_2b", "captured_at": "2026-09-13T08:00:00Z"},
    ]
    idx2 = EvidenceIndex([rec_replica, rec_flow])
    engine_2 = AuditEngine(
        intent_classifier=classify_request_intent,
        identity_resolver=MockResolver2(),
        evidence_index=idx2,
        policy_rules=rules,
        evidence_manifest=manifest_2,
    )
    case_2_req = {
        "case_id": "custom_case_02",
        "email": "historical.alias@example.com",
        "requested_at": "2026-09-10T12:00:00Z",
        "reported_status": "COMPLETE",
        "reported_at": "2026-09-11T12:00:00Z",
        "audit_at": cutoff_2,
        "request_text": "Please delete all data associated with my account and past addresses.",
    }
    c2_res = engine_2.audit_case(case_2_req)
    remed_ops = [s["operation"] for s in c2_res.steps if s["phase"] == "REMEDIATION"]
    c2_passed = (
        c2_res.deletion_status == "INCOMPLETE"
        and "DISABLE_DATA_FLOW" in remed_ops
        and "DELETE_RECORD" in remed_ops
        and remed_ops.index("DISABLE_DATA_FLOW") < remed_ops.index("DELETE_RECORD")
    )
    results.append({
        "name": "Custom Case 2 (Historical Alias Replica Drift + Active Data Flow)",
        "expected_status": "INCOMPLETE",
        "actual_status": c2_res.deletion_status,
        "passed": c2_passed,
        "steps_count": len(c2_res.steps),
    })

    # =========================================================================
    # Custom Case 3: Tombstone with exposed PII + Retained Security Audit Log + Backup Restore Risk
    # Expected: INCOMPLETE (BLOCK_RESTORE, REDACT_RECORD; VERIFY_RECORD_PRESENT, VERIFY_RECORD_REDACTED, VERIFY_RESTORE_BLOCKED)
    # =========================================================================
    cutoff_3 = "2026-09-20T12:00:00Z"
    prof3 = IdentityProfile(
        user_id="user_synth_3",
        emails=("tombstone.pii@example.com",),
        email_hashes=(),
        phones=(),
        aliases=(),
    )
    class MockResolver3:
        def resolve_email(self, email: str) -> IdentityResolution:
            return IdentityResolution(
                status=ResolutionStatus.RESOLVED,
                queried_email=email,
                user_id=prof3.user_id,
                candidate_user_ids=(prof3.user_id,),
                matched_by=("email",),
                profile=prof3,
                reason="synthetic_tombstone_match",
            )

    rec_tombstone = EvidenceRecord(
        evidence_id="evidence_syn_3a",
        evidence_ref_type="file_id",
        source_path="evidence/databases/identity_tombstones.json",
        source_kind="json",
        locator="entry:tombstone_synth_3",
        system_id="identity_service",
        resource_id="tombstone_synth_3",
        data_category="ACCOUNT_TOMBSTONE",
        observed_at="2026-09-12T10:00:00Z",
        fields=(("captured_at", "2026-09-12T10:00:00Z"), ("user_id", "user_synth_3"), ("email", "tombstone.pii@example.com")),  # Exposed direct PII!
        text="tombstone_synth_3 user_synth_3 tombstone.pii@example.com",
        captured_at="2026-09-12T10:00:00Z",
    )
    rec_backup = EvidenceRecord(
        evidence_id="evidence_syn_3b",
        evidence_ref_type="file_id",
        source_path="evidence/records/backup_catalog.json",
        source_kind="json",
        locator="entry:backup_synth_3",
        system_id="backup_service",
        resource_id="backup_synth_3",
        data_category="BACKUP_ARCHIVE",
        observed_at="2026-09-13T10:00:00Z",
        fields=(("captured_at", "2026-09-13T10:00:00Z"), ("customer_reference", "user_synth_3"), ("restore_allowed", "true"), ("restore_status", "active")),
        text="backup_synth_3 restore_allowed=true",
        captured_at="2026-09-13T10:00:00Z",
    )
    rec_audit = EvidenceRecord(
        evidence_id="evidence_syn_3c",
        evidence_ref_type="file_id",
        source_path="evidence/logs/security_audit.log",
        source_kind="log",
        locator="line:1",
        system_id="security_service",
        resource_id="audit_record_synth_3",
        data_category="SECURITY_AUDIT_LOG",
        observed_at="2026-09-14T10:00:00Z",
        fields=(("captured_at", "2026-09-14T10:00:00Z"), ("subject_reference", "user_synth_3"), ("status", "present")),
        text="audit_record_synth_3 subject_reference=user_synth_3 present",
        captured_at="2026-09-14T10:00:00Z",
    )
    manifest_3 = [
        {"file_id": "evidence_syn_3a", "captured_at": "2026-09-12T10:00:00Z"},
        {"file_id": "evidence_syn_3b", "captured_at": "2026-09-13T10:00:00Z"},
        {"file_id": "evidence_syn_3c", "captured_at": "2026-09-14T10:00:00Z"},
    ]
    idx3 = EvidenceIndex([rec_tombstone, rec_backup, rec_audit])
    engine_3 = AuditEngine(
        intent_classifier=classify_request_intent,
        identity_resolver=MockResolver3(),
        evidence_index=idx3,
        policy_rules=rules,
        evidence_manifest=manifest_3,
    )
    case_3_req = {
        "case_id": "custom_case_03",
        "email": "tombstone.pii@example.com",
        "requested_at": "2026-09-10T12:00:00Z",
        "reported_status": "PARTIALLY_COMPLETE",
        "reported_at": "2026-09-11T12:00:00Z",
        "audit_at": cutoff_3,
        "request_text": "Please delete my account and ensure all identifiers are removed.",
    }
    c3_res = engine_3.audit_case(case_3_req)
    remed_ops_3 = [s["operation"] for s in c3_res.steps if s["phase"] == "REMEDIATION"]
    verify_ops_3 = [s["operation"] for s in c3_res.steps if s["phase"] == "VERIFICATION"]
    c3_passed = (
        c3_res.deletion_status == "INCOMPLETE"
        and "BLOCK_RESTORE" in remed_ops_3
        and "REDACT_RECORD" in remed_ops_3
        and "VERIFY_RECORD_PRESENT" in verify_ops_3
        and "VERIFY_RECORD_REDACTED" in verify_ops_3
        and "VERIFY_RESTORE_BLOCKED" in verify_ops_3
    )
    results.append({
        "name": "Custom Case 3 (Tombstone Exposed PII + Retained Audit Log + Backup Risk)",
        "expected_status": "INCOMPLETE",
        "actual_status": c3_res.deletion_status,
        "passed": c3_passed,
        "steps_count": len(c3_res.steps),
    })

    # =========================================================================
    # Custom Case 4: Post-Cutoff Evidence Decoy
    # Pre-cutoff evidence <= audit_at shows PRESENT.
    # Post-cutoff evidence > audit_at claims ABSENT.
    # Expected: INCOMPLETE (must cite admissible pre-cutoff evidence)
    # =========================================================================
    cutoff_4 = "2026-09-15T00:00:00Z"
    prof4 = IdentityProfile(
        user_id="user_synth_4",
        emails=("decoy.test@example.com",),
        email_hashes=(),
        phones=(),
        aliases=(),
    )
    class MockResolver4:
        def resolve_email(self, email: str) -> IdentityResolution:
            return IdentityResolution(
                status=ResolutionStatus.RESOLVED,
                queried_email=email,
                user_id=prof4.user_id,
                candidate_user_ids=(prof4.user_id,),
                matched_by=("email",),
                profile=prof4,
                reason="synthetic_decoy_match",
            )

    # Admissible evidence before cutoff (PRESENT)
    rec_admissible = EvidenceRecord(
        evidence_id="evidence_syn_4_pre",
        evidence_ref_type="file_id",
        source_path="evidence/databases/pre_cutoff.sql",
        source_kind="sql",
        locator="table:profiles:row:1",
        system_id="account_service",
        resource_id="account_synth_4",
        data_category="USER_PROFILE",
        observed_at="2026-09-14T12:00:00Z",
        fields=(("captured_at", "2026-09-14T12:00:00Z"), ("status", "active"), ("email", "decoy.test@example.com")),
        text="account_synth_4 active decoy.test@example.com",
        captured_at="2026-09-14T12:00:00Z",
    )
    # Post-cutoff decoy evidence after cutoff (claiming deleted)
    rec_decoy = EvidenceRecord(
        evidence_id="evidence_syn_4_post",
        evidence_ref_type="file_id",
        source_path="evidence/databases/post_cutoff.sql",
        source_kind="sql",
        locator="table:profiles:row:1",
        system_id="account_service",
        resource_id="account_synth_4",
        data_category="USER_PROFILE",
        observed_at="2026-09-18T12:00:00Z",
        fields=(("captured_at", "2026-09-18T12:00:00Z"), ("status", "deleted"), ("email", "decoy.test@example.com")),
        text="account_synth_4 deleted decoy.test@example.com",
        captured_at="2026-09-18T12:00:00Z",
    )
    manifest_4 = [
        {"file_id": "evidence_syn_4_pre", "captured_at": "2026-09-14T12:00:00Z"},
        {"file_id": "evidence_syn_4_post", "captured_at": "2026-09-18T12:00:00Z"},
    ]
    idx4 = EvidenceIndex([rec_admissible, rec_decoy])
    engine_4 = AuditEngine(
        intent_classifier=classify_request_intent,
        identity_resolver=MockResolver4(),
        evidence_index=idx4,
        policy_rules=rules,
        evidence_manifest=manifest_4,
    )
    case_4_req = {
        "case_id": "custom_case_04",
        "email": "decoy.test@example.com",
        "requested_at": "2026-09-10T12:00:00Z",
        "reported_status": "COMPLETE",
        "reported_at": "2026-09-11T12:00:00Z",
        "audit_at": cutoff_4,
        "request_text": "Please delete my account and personal data completely.",
    }
    c4_res = engine_4.audit_case(case_4_req)
    # Post-cutoff evidence must NOT be cited, pre-cutoff admissible evidence must be cited in finding
    findings_4 = [s for s in c4_res.steps if s["phase"] == "FINDING"]
    cited_ids_4 = [s["evidence_id"] for s in findings_4]
    c4_passed = (
        c4_res.deletion_status == "INCOMPLETE"
        and "evidence_syn_4_pre" in cited_ids_4
        and "evidence_syn_4_post" not in cited_ids_4
    )
    results.append({
        "name": "Custom Case 4 (Post-Cutoff Evidence Decoy Rejection)",
        "expected_status": "INCOMPLETE",
        "actual_status": c4_res.deletion_status,
        "passed": c4_passed,
        "steps_count": len(c4_res.steps),
    })

    return results
