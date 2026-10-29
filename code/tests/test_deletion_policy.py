#!/usr/bin/env python3
"""
Unit tests for Stage 5: Deletion Policy and Per-Obligation Assessment.
"""

import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "code"))

from tools.deletion_policy import (
    PolicyRule,
    PolicySchemaError,
    assess_policy_state,
    classify_resource_state,
    infer_data_category,
    is_retention_supported,
    load_policy_rules,
    match_policy_rule,
)
from tools.evidence_retrieval import EvidenceRecord


class DeletionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.rules_path = REPO_ROOT / "dataset" / "deletion_rules.csv"
        self.rules = load_policy_rules(self.rules_path)

    def test_load_policy_rules_count_and_columns(self):
        self.assertEqual(len(self.rules), 15)
        categories = {r.data_category for r in self.rules}
        self.assertIn("USER_PROFILE", categories)
        self.assertIn("SEARCH_INDEX_ENTRY", categories)
        self.assertIn("ACCOUNT_TOMBSTONE", categories)
        self.assertIn("BACKUP_ARCHIVE", categories)
        self.assertIn("SECURITY_AUDIT_LOG", categories)

    def test_missing_policy_file_raises_schema_error(self):
        with self.assertRaises(PolicySchemaError):
            load_policy_rules("/nonexistent/path/rules.csv")

    def test_corrupt_header_raises_schema_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_csv = Path(tmpdir) / "bad_rules.csv"
            bad_csv.write_text("rule_id,data_category,wrong_column\nr1,CAT,val\n")
            with self.assertRaises(PolicySchemaError):
                load_policy_rules(bad_csv)

    def test_unsupported_action_raises_schema_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_csv = Path(tmpdir) / "bad_rules.csv"
            bad_csv.write_text(
                "rule_id,data_category,condition,required_action\n"
                "r1,CAT,Always,INVALID_ACTION\n"
            )
            with self.assertRaises(PolicySchemaError):
                load_policy_rules(bad_csv)

    def test_conflicting_rules_detected(self):
        r1 = PolicyRule("r1", "USER_PROFILE", "Always", "DELETE", 1)
        r2 = PolicyRule("r2", "USER_PROFILE", "Always", "RETAIN", 2)
        with self.assertRaises(PolicySchemaError):
            match_policy_rule("USER_PROFILE", [r1, r2])

    def test_match_policy_rule_case_insensitive(self):
        rule = match_policy_rule("user_profile", self.rules)
        self.assertIsNotNone(rule)
        self.assertEqual(rule.data_category, "USER_PROFILE")
        self.assertEqual(rule.required_action, "DELETE")

    def test_infer_data_category(self):
        self.assertEqual(infer_data_category("account_service", "account_100"), "USER_PROFILE")
        self.assertEqual(infer_data_category("search_service", "search_200"), "SEARCH_INDEX_ENTRY")
        self.assertEqual(infer_data_category("integration_service", "data_flow_300"), "DATA_FLOW")
        self.assertEqual(infer_data_category("backup_service", "backup_400"), "BACKUP_ARCHIVE")
        self.assertEqual(infer_data_category("identity_service", "tombstone_500"), "ACCOUNT_TOMBSTONE")
        self.assertEqual(infer_data_category("security_service", "audit_record_600"), "SECURITY_AUDIT_LOG")

    def test_classify_and_assess_delete_rule(self):
        rule = match_policy_rule("USER_PROFILE", self.rules)

        # 1. 404 absent -> Compliant
        rec_absent = {"resource_id": "account_1", "status_code": "404", "system_id": "account_service"}
        state, _ = classify_resource_state(rec_absent, "DELETE")
        self.assertEqual(state, "ABSENT")
        comp, _ = assess_policy_state(rule, state)
        self.assertTrue(comp)

        # 2. 200 present -> Non-compliant
        rec_present = {"resource_id": "account_1", "status_code": "200", "system_id": "account_service"}
        state, _ = classify_resource_state(rec_present, "DELETE")
        self.assertEqual(state, "PRESENT")
        comp, _ = assess_policy_state(rule, state)
        self.assertFalse(comp)

    def test_classify_and_assess_data_flow(self):
        rule = PolicyRule("rf", "DATA_FLOW", "Disabled", "DELETE", 0)

        # Active flow -> Non-compliant
        rec_active = {
            "resource_id": "data_flow_1",
            "system_id": "integration_service",
            "enabled": True,
            "last_delivery_status": "delivered",
        }
        state, _ = classify_resource_state(rec_active, "DELETE")
        self.assertEqual(state, "ACTIVE_FLOW")
        comp, _ = assess_policy_state(rule, state)
        self.assertFalse(comp)

        # Disabled flow -> Compliant
        rec_disabled = {
            "resource_id": "data_flow_1",
            "system_id": "integration_service",
            "enabled": False,
            "last_delivery_status": "stopped",
        }
        state, _ = classify_resource_state(rec_disabled, "DELETE")
        self.assertEqual(state, "FLOW_DISABLED")
        comp, _ = assess_policy_state(rule, state)
        self.assertTrue(comp)

    def test_classify_and_assess_backup_restore(self):
        rule = match_policy_rule("BACKUP_ARCHIVE", self.rules)

        # Restore allowed -> Risk / Non-compliant
        rec_risk = {
            "resource_id": "backup_1",
            "system_id": "backup_service",
            "restore_allowed": True,
        }
        state, _ = classify_resource_state(rec_risk, "RETAIN")
        self.assertEqual(state, "RESTORE_RISK")
        comp, _ = assess_policy_state(rule, state)
        self.assertFalse(comp)

        # Restore blocked -> Compliant
        rec_blocked = {
            "resource_id": "backup_1",
            "system_id": "backup_service",
            "restore_allowed": False,
        }
        state, _ = classify_resource_state(rec_blocked, "RETAIN")
        self.assertEqual(state, "RESTORE_BLOCKED")
        comp, _ = assess_policy_state(rule, state)
        self.assertTrue(comp)

    def test_classify_and_assess_tombstone(self):
        rule = match_policy_rule("ACCOUNT_TOMBSTONE", self.rules)

        # Direct PII exposed -> Non-compliant
        rec_exposed = {
            "resource_id": "tombstone_1",
            "system_id": "identity_service",
            "subject_reference": "user_100",
            "email": "user@example.com",
            "phone": "+1234567890",
        }
        state, _ = classify_resource_state(rec_exposed, "REDACT")
        self.assertEqual(state, "PRESENT")
        comp, _ = assess_policy_state(rule, state)
        self.assertFalse(comp)

        # Direct PII redacted, only user_id kept -> Compliant
        rec_redacted = {
            "resource_id": "tombstone_1",
            "system_id": "identity_service",
            "subject_reference": "user_100",
            "email": None,
            "phone": None,
        }
        state, _ = classify_resource_state(rec_redacted, "REDACT")
        self.assertEqual(state, "REDACTED")
        comp, _ = assess_policy_state(rule, state)
        self.assertTrue(comp)

    def test_classify_and_assess_analytics_anonymization(self):
        rule = match_policy_rule("ANALYTICS_PROFILE", self.rules)

        # PII exposed -> Non-compliant
        rec_exposed = {
            "resource_id": "analytics_1",
            "system_id": "analytics_platform",
            "email": "user@example.com",
        }
        state, _ = classify_resource_state(rec_exposed, "ANONYMIZE")
        self.assertEqual(state, "PRESENT")
        comp, _ = assess_policy_state(rule, state)
        self.assertFalse(comp)

        # Unlinked -> Compliant
        rec_anon = {
            "resource_id": "analytics_1",
            "system_id": "analytics_platform",
            "email": None,
            "phone": None,
            "audience_cohort": "lifestyle",
        }
        state, _ = classify_resource_state(rec_anon, "ANONYMIZE")
        self.assertEqual(state, "ANONYMIZED")
        comp, _ = assess_policy_state(rule, state)
        self.assertTrue(comp)

    def test_retain_rule_compliance(self):
        rule = match_policy_rule("SECURITY_AUDIT_LOG", self.rules)

        # Present under supported retention -> Compliant
        comp, _ = assess_policy_state(rule, "PRESENT", retention_supported=True)
        self.assertTrue(comp)

        # Absent when required to retain -> Non-compliant
        comp_absent, _ = assess_policy_state(rule, "ABSENT")
        self.assertFalse(comp_absent)

    def test_absent_pii_without_marker_is_unknown(self):
        rec = {
            "resource_id": "support_999",
            "system_id": "support_platform",
            "source_kind": "txt",
            "raw_fields": {"note": "partial"},
            "text": "fragment without pii",
        }
        st, _ = classify_resource_state(rec, "REDACT")
        self.assertEqual(st, "UNKNOWN")
        rule = match_policy_rule("SUPPORT_MESSAGE", self.rules)
        comp, _ = assess_policy_state(rule, st)
        self.assertIsNone(comp)

    def test_retain_requires_retention_supported(self):
        rule_12 = match_policy_rule("SECURITY_AUDIT_LOG", self.rules)
        comp, msg = assess_policy_state(rule_12, "PRESENT")
        self.assertFalse(comp)
        self.assertIn("Retention condition not supported", msg)

        # Record with expired retention_until < audit_at
        rec_expired = {
            "raw_fields": {"retention_until": "2026-08-01T00:00:00Z"},
            "status": "present",
        }
        self.assertFalse(is_retention_supported(rec_expired, rule_12, audit_at="2026-09-01T00:00:00Z"))


if __name__ == "__main__":
    unittest.main()
