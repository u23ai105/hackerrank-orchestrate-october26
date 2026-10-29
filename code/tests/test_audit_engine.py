#!/usr/bin/env python3
"""
Unit tests for Stage 6: Case Audit Engine and Step Builder.
"""

import unittest
from tools.audit_engine import (
    ALLOWED_PHASE_OP_STATE,
    OPERATION_RANK,
    PHASE_ORDER,
    STEP_KEYS,
    AuditEngine,
    CaseAuditResult,
    make_step,
    sort_and_number_steps,
    validate_case_result,
)
from tools.deletion_policy import PolicyRule
from tools.identity_resolution import IdentityProfile, IdentityResolution, ResolutionStatus


class MockIdentityResolver:
    def __init__(self, profiles=None):
        self.profiles = profiles or {}

    def resolve_email(self, email):
        if email in self.profiles:
            p = self.profiles[email]
            return IdentityResolution(
                status=ResolutionStatus.RESOLVED,
                queried_email=email,
                user_id=p.user_id,
                candidate_user_ids=(p.user_id,),
                matched_by=("email",),
                profile=p,
                reason="Resolved via mock",
            )
        return IdentityResolution(
            status=ResolutionStatus.UNRESOLVED,
            queried_email=email,
            user_id=None,
            candidate_user_ids=(),
            matched_by=(),
            profile=None,
            reason="Unresolved mock",
        )


class MockEvidenceIndex:
    def __init__(self, hits=None):
        self.hits = hits or {}
        self.records = []

    def retrieve(self, profile):
        class MockResult:
            def __init__(self, hits):
                self.hits = hits
        return MockResult(self.hits.get(profile.user_id if profile else "", ()))


class AuditEngineTests(unittest.TestCase):
    def test_step_schema_and_keys(self):
        step = make_step("FINDING", "account_service", "account_001", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_54")
        self.assertEqual(set(step.keys()), set(STEP_KEYS))
        self.assertEqual(step["step_no"], 0)
        self.assertEqual(step["phase"], "FINDING")
        self.assertEqual(step["operation"], "REPORT_REMAINING_RECORD")
        self.assertEqual(step["state"], "PRESENT")
        self.assertEqual(step["evidence_id"], "evidence_54")

    def test_invalid_phase_op_state_combination_raises(self):
        with self.assertRaises(ValueError):
            make_step("FINDING", "account_service", "account_001", "DELETE_RECORD", "ABSENT", "evidence_54")
        with self.assertRaises(ValueError):
            make_step("REMEDIATION", "account_service", "account_001", "REPORT_REMAINING_RECORD", "PRESENT", "")
        with self.assertRaises(ValueError):
            make_step("VERIFICATION", "account_service", "account_001", "VERIFY_RECORD_ABSENT", "PRESENT", "evidence_54")

    def test_step_sorting_and_numbering(self):
        steps = [
            make_step("VERIFICATION", "account_service", "account_001", "VERIFY_RECORD_ABSENT", "ABSENT", ""),
            make_step("FINDING", "search_service", "search_001", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_57"),
            make_step("REMEDIATION", "search_service", "search_001", "DELETE_RECORD", "ABSENT", ""),
            make_step("FINDING", "account_service", "account_001", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_54"),
        ]
        sorted_steps = sort_and_number_steps(steps)
        self.assertEqual([s["step_no"] for s in sorted_steps], [1, 2, 3, 4])
        self.assertEqual(sorted_steps[0]["phase"], "FINDING")
        self.assertEqual(sorted_steps[0]["resource_id"], "account_001")
        self.assertEqual(sorted_steps[1]["phase"], "FINDING")
        self.assertEqual(sorted_steps[1]["resource_id"], "search_001")
        self.assertEqual(sorted_steps[2]["phase"], "REMEDIATION")
        self.assertEqual(sorted_steps[3]["phase"], "VERIFICATION")

    def test_validate_case_result_not_applicable(self):
        # Valid
        validate_case_result("NOT_APPLICABLE", [])
        # Invalid with steps
        with self.assertRaises(ValueError):
            validate_case_result("NOT_APPLICABLE", [make_step("VERIFICATION", "acc", "res", "VERIFY_RECORD_ABSENT", "ABSENT", "ev_1")])

    def test_validate_case_result_complete(self):
        valid_steps = [
            make_step("VERIFICATION", "account_service", "account_001", "VERIFY_RECORD_ABSENT", "ABSENT", "evidence_54")
        ]
        validate_case_result("COMPLETE", valid_steps)

        # Empty steps invalid
        with self.assertRaises(ValueError):
            validate_case_result("COMPLETE", [])

        # Step without evidence_id invalid
        with self.assertRaises(ValueError):
            invalid_step = [make_step("VERIFICATION", "account_service", "account_001", "VERIFY_RECORD_ABSENT", "ABSENT", "")]
            validate_case_result("COMPLETE", invalid_step)

        # Non-verification phase invalid
        with self.assertRaises(ValueError):
            invalid_phase = [make_step("FINDING", "account_service", "account_001", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_54")]
            validate_case_result("COMPLETE", invalid_phase)

    def test_validate_case_result_incomplete(self):
        valid_steps = [
            make_step("FINDING", "account_service", "account_001", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_54"),
            make_step("REMEDIATION", "account_service", "account_001", "DELETE_RECORD", "ABSENT", ""),
            make_step("VERIFICATION", "account_service", "account_001", "VERIFY_RECORD_ABSENT", "ABSENT", ""),
        ]
        validate_case_result("INCOMPLETE", valid_steps)

        # Missing finding invalid
        with self.assertRaises(ValueError):
            validate_case_result("INCOMPLETE", valid_steps[1:])

        # Finding with empty evidence invalid
        with self.assertRaises(ValueError):
            bad_finding = [
                make_step("FINDING", "account_service", "account_001", "REPORT_REMAINING_RECORD", "PRESENT", ""),
                valid_steps[1],
                valid_steps[2],
            ]
            validate_case_result("INCOMPLETE", bad_finding)

        # Remediation with non-empty evidence invalid
        with self.assertRaises(ValueError):
            bad_remedy = [
                valid_steps[0],
                make_step("REMEDIATION", "account_service", "account_001", "DELETE_RECORD", "ABSENT", "evidence_54"),
                valid_steps[2],
            ]
            validate_case_result("INCOMPLETE", bad_remedy)

    def test_non_deletion_intent_returns_not_applicable(self):
        engine = AuditEngine(
            intent_classifier=lambda txt: "NOT_A_DELETION_REQUEST",
            identity_resolver=MockIdentityResolver(),
            evidence_index=MockEvidenceIndex(),
            policy_rules=[],
        )
        res = engine.audit_case({
            "case_id": "case_999",
            "request_text": "Please export my invoices and do not delete my account.",
            "email": "test@example.com",
            "audit_at": "2026-09-15T12:00:00Z",
        })
        self.assertEqual(res.deletion_status, "NOT_APPLICABLE")
        self.assertEqual(res.steps, [])

    def test_unresolved_identity_returns_incomplete_with_blocker(self):
        engine = AuditEngine(
            intent_classifier=lambda txt: "DELETION_REQUESTED",
            identity_resolver=MockIdentityResolver(),  # Empty
            evidence_index=MockEvidenceIndex(),
            policy_rules=[],
        )
        res = engine.audit_case({
            "case_id": "case_101",
            "request_text": "Please delete my account immediately.",
            "email": "unknown@example.com",
            "audit_at": "2026-09-15T12:00:00Z",
        })
        self.assertEqual(res.deletion_status, "INCOMPLETE")
        self.assertIn("IDENTITY_NOT_RESOLVED", res.blockers)

    def test_empty_evidence_index_fails_closed(self):
        from tools.evidence_retrieval import EvidenceIndex
        engine = AuditEngine(evidence_index=EvidenceIndex(records=[]))
        req = {
            "case_id": "case_01",
            "request_text": "Please delete all my data immediately and completely.",
            "email": "user_01@example.com",
            "audit_at": "2026-09-15T12:00:00Z",
        }
        identity = IdentityProfile(
            user_id="user_001",
            emails=("user_01@example.com",),
            email_hashes=(),
            phones=(),
            aliases=(),
        )
        res = engine.evaluate_case(req, identity)
        self.assertEqual(res.deletion_status, "INCOMPLETE")
        self.assertEqual(res.steps, [])

    def test_activity_cannot_override_policy_rule(self):
        from tools.evidence_retrieval import EvidenceIndex, EvidenceRecord
        rule_security = PolicyRule("rule_12", "SECURITY_AUDIT_LOG", "Always", "RETAIN", 1)
        rec = EvidenceRecord(
            evidence_id="evidence_99",
            evidence_ref_type="file_id",
            source_path="dataset/evidence/logs/security.log",
            source_kind="log",
            locator="line:1",
            system_id="security_service",
            resource_id="security_001",
            data_category="SECURITY_AUDIT_LOG",
            observed_at="2026-09-01T00:00:00Z",
            fields=(("status", "present"), ("event_code", "AUTH_LOGIN"), ("integrity_seal", "valid")),
            text="audit record present",
        )
        del_act = {
            "activity_id": "act_999",
            "timestamp": "2026-09-02T00:00:00Z",
            "source_system": "deletion_worker",
            "activity_type": "DELETE_RECORD",
            "resource_id": "security_001",
            "status": "COMPLETED",
        }
        engine = AuditEngine(
            evidence_index=EvidenceIndex(records=[rec]),
            policy_rules=[rule_security],
            system_activities=[del_act],
        )
        req = {
            "case_id": "case_test",
            "request_text": "Please delete my account",
            "email": "user@example.com",
            "audit_at": "2026-09-15T12:00:00Z",
        }
        identity = IdentityProfile(
            user_id="user_999",
            emails=("user@example.com",),
            email_hashes=(),
            phones=(),
            aliases=(),
        )
        res = engine.evaluate_case(req, identity)
        for step in res.steps:
            if step.get("resource_id") == "security_001":
                self.assertNotEqual(step.get("operation"), "DELETE_RECORD")

    def test_validator_fails_closed_on_missing_timestamp(self):
        import json
        from validate_output import validate_output_rows
        # 1. Missing audit_at
        req_bad = [{"case_id": "case_1", "audit_at": ""}]
        out = [{"case_id": "case_1", "deletion_status": "NOT_APPLICABLE", "steps_json": "[]"}]
        errs = validate_output_rows(req_bad, out, {})
        self.assertTrue(any("Missing or invalid audit_at" in e for e in errs))

        # 2. Missing source timestamp for evidence
        req_good = [{"case_id": "case_1", "audit_at": "2026-09-15T12:00:00Z"}]
        step = [{"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "acc_1", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_99"}]
        out_ev = [{"case_id": "case_1", "deletion_status": "COMPLETE", "steps_json": json.dumps(step)}]
        errs2 = validate_output_rows(req_good, out_ev, {})
        self.assertTrue(any("Unknown evidence_id" in e for e in errs2))

        # 3. Malformed timestamp
        errs3 = validate_output_rows(req_good, out_ev, {"evidence_99": "not-a-timestamp"})
        self.assertTrue(any("Malformed or timezone-naive" in e for e in errs3))


if __name__ == "__main__":
    unittest.main()
