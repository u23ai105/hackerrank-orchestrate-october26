#!/usr/bin/env python3
"""
Unit tests for Stage 4: Temporal Admissibility.
"""

import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "code"))

from tools.temporal_admissibility import (
    TemporalAssessment,
    TemporalDisposition,
    assess_evidence,
    assess_hits,
    parse_timestamp,
)
from tools.evidence_retrieval import EvidenceRecord


class TemporalAdmissibilityTests(unittest.TestCase):
    def test_parse_timestamp_valid_z(self):
        dt = parse_timestamp("2026-08-01T12:00:00Z")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.tzinfo, timezone.utc)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 8)
        self.assertEqual(dt.day, 1)

    def test_parse_timestamp_explicit_offset(self):
        dt = parse_timestamp("2026-08-01T14:00:00+02:00")
        self.assertIsNotNone(dt)
        # In UTC, 14:00+02:00 is 12:00 UTC
        self.assertEqual(dt.hour, 12)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_parse_timestamp_equivalent_instants(self):
        dt1 = parse_timestamp("2026-08-01T12:00:00Z")
        dt2 = parse_timestamp("2026-08-01T17:30:00+05:30")
        self.assertEqual(dt1, dt2)

    def test_parse_timestamp_missing_and_none(self):
        self.assertIsNone(parse_timestamp(None))
        self.assertIsNone(parse_timestamp(""))
        self.assertIsNone(parse_timestamp("   "))

    def test_parse_timestamp_naive_rejected(self):
        with self.assertRaises(ValueError):
            parse_timestamp("2026-08-01T12:00:00")

    def test_parse_timestamp_malformed_rejected(self):
        with self.assertRaises(ValueError):
            parse_timestamp("not-a-timestamp")

    def test_exact_cutoff_equality_is_admissible(self):
        cutoff = "2026-08-01T12:00:00Z"
        rec = EvidenceRecord(
            evidence_id="ev_1",
            evidence_ref_type="file_id",
            source_path="db.sql",
            source_kind="sql",
            locator="t=1",
            system_id="sys",
            resource_id="res_1",
            data_category="CAT",
            observed_at=cutoff,
            fields=(),
            text="",
            captured_at=cutoff,
        )
        ass = assess_evidence(rec, cutoff)
        self.assertEqual(ass.disposition, TemporalDisposition.ADMISSIBLE)
        self.assertTrue(ass.state_usable)
        self.assertTrue(ass.linkage_usable)
        self.assertEqual(ass.reason_code, "AT_OR_BEFORE_CUTOFF")

    def test_strictly_earlier_is_admissible(self):
        cutoff = "2026-08-01T12:00:00Z"
        rec = EvidenceRecord(
            evidence_id="ev_1",
            evidence_ref_type="file_id",
            source_path="db.sql",
            source_kind="sql",
            locator="t=1",
            system_id="sys",
            resource_id="res_1",
            data_category="CAT",
            observed_at="2026-07-01T00:00:00Z",
            fields=(),
            text="",
            captured_at="2026-07-01T00:00:00Z",
        )
        ass = assess_evidence(rec, cutoff)
        self.assertEqual(ass.disposition, TemporalDisposition.ADMISSIBLE)
        self.assertTrue(ass.state_usable)
        self.assertTrue(ass.linkage_usable)

    def test_strictly_later_is_post_cutoff(self):
        cutoff = "2026-08-01T12:00:00Z"
        rec = EvidenceRecord(
            evidence_id="ev_1",
            evidence_ref_type="file_id",
            source_path="db.sql",
            source_kind="sql",
            locator="t=1",
            system_id="sys",
            resource_id="res_1",
            data_category="CAT",
            observed_at="2026-09-01T00:00:00Z",
            fields=(),
            text="",
            captured_at="2026-09-01T00:00:00Z",
        )
        ass = assess_evidence(rec, cutoff)
        self.assertEqual(ass.disposition, TemporalDisposition.POST_CUTOFF)
        self.assertFalse(ass.state_usable)
        self.assertTrue(ass.linkage_usable)
        self.assertEqual(ass.reason_code, "CAPTURE_AFTER_CUTOFF")

    def test_snapshot_captured_after_cutoff_with_earlier_row_updated_at(self):
        """A snapshot captured after cutoff is POST_CUTOFF even if row updated_at is earlier."""
        cutoff = "2026-08-01T00:00:00Z"
        rec = EvidenceRecord(
            evidence_id="ev_snapshot",
            evidence_ref_type="file_id",
            source_path="accounts_20260905.sql",
            source_kind="sql",
            locator="table=accounts:row=1",
            system_id="account_service",
            resource_id="account_100",
            data_category="USER_PROFILE",
            observed_at="2026-07-15T00:00:00Z",
            fields=(("updated_at", "2026-07-15T00:00:00Z"),),
            text="",
            captured_at="2026-09-05T00:00:00Z",
            record_updated_at="2026-07-15T00:00:00Z",
        )
        ass = assess_evidence(rec, cutoff)
        self.assertEqual(ass.disposition, TemporalDisposition.POST_CUTOFF)
        self.assertFalse(ass.state_usable)
        self.assertTrue(ass.linkage_usable)
        self.assertEqual(ass.basis_kind, "captured_at")
        self.assertEqual(ass.reason_code, "CAPTURE_AFTER_CUTOFF")

    def test_event_time_semantics(self):
        cutoff = "2026-08-01T00:00:00Z"
        rec = EvidenceRecord(
            evidence_id="act_123",
            evidence_ref_type="activity_id",
            source_path="system_activity.csv",
            source_kind="activity",
            locator="row=1",
            system_id="audit_service",
            resource_id="account_100",
            data_category="AUDIT",
            observed_at="2026-07-20T10:00:00Z",
            fields=(("event_time", "2026-07-20T10:00:00Z"),),
            text="",
            event_time="2026-07-20T10:00:00Z",
        )
        ass = assess_evidence(rec, cutoff)
        self.assertEqual(ass.disposition, TemporalDisposition.ADMISSIBLE)
        self.assertTrue(ass.state_usable)
        self.assertEqual(ass.basis_kind, "event_time")

    def test_event_after_cutoff_is_post_cutoff(self):
        cutoff = "2026-08-01T00:00:00Z"
        rec = EvidenceRecord(
            evidence_id="act_999",
            evidence_ref_type="activity_id",
            source_path="system_activity.csv",
            source_kind="activity",
            locator="row=99",
            system_id="audit_service",
            resource_id="account_100",
            data_category="AUDIT",
            observed_at="2026-08-15T10:00:00Z",
            fields=(("event_time", "2026-08-15T10:00:00Z"),),
            text="",
            event_time="2026-08-15T10:00:00Z",
        )
        ass = assess_evidence(rec, cutoff)
        self.assertEqual(ass.disposition, TemporalDisposition.POST_CUTOFF)
        self.assertFalse(ass.state_usable)
        self.assertEqual(ass.basis_kind, "event_time")

    def test_missing_audit_at_handled_conservatively(self):
        rec = EvidenceRecord(
            evidence_id="ev_1",
            evidence_ref_type="file_id",
            source_path="a.sql",
            source_kind="sql",
            locator="t=1",
            system_id="sys",
            resource_id="res_1",
            data_category="CAT",
            observed_at="2026-01-01T00:00:00Z",
            fields=(),
            text="",
            captured_at="2026-01-01T00:00:00Z",
        )
        ass1 = assess_evidence(rec, None)
        self.assertEqual(ass1.disposition, TemporalDisposition.UNDATED)
        self.assertFalse(ass1.state_usable)
        self.assertEqual(ass1.reason_code, "MISSING_AUDIT_CUTOFF")

        ass2 = assess_evidence(rec, "invalid-cutoff")
        self.assertEqual(ass2.disposition, TemporalDisposition.INVALID_TIMESTAMP)
        self.assertFalse(ass2.state_usable)
        self.assertEqual(ass2.reason_code, "INVALID_AUDIT_CUTOFF")

    def test_missing_evidence_timestamp_is_undated(self):
        cutoff = "2026-08-01T00:00:00Z"
        rec = EvidenceRecord(
            evidence_id="ev_1",
            evidence_ref_type="file_id",
            source_path="a.sql",
            source_kind="sql",
            locator="t=1",
            system_id="sys",
            resource_id="res_1",
            data_category="CAT",
            observed_at="",
            fields=(),
            text="",
            captured_at="",
        )
        ass = assess_evidence(rec, cutoff)
        self.assertEqual(ass.disposition, TemporalDisposition.UNDATED)
        self.assertFalse(ass.state_usable)

    def test_conflicting_timestamps_created_after_updated(self):
        cutoff = "2026-08-01T00:00:00Z"
        rec = EvidenceRecord(
            evidence_id="ev_conflict",
            evidence_ref_type="file_id",
            source_path="a.sql",
            source_kind="sql",
            locator="t=1",
            system_id="sys",
            resource_id="res_1",
            data_category="CAT",
            observed_at="2026-07-01T00:00:00Z",
            fields=(
                ("created_at", "2026-07-10T00:00:00Z"),
                ("updated_at", "2026-07-01T00:00:00Z"),
            ),
            text="",
            captured_at="2026-07-15T00:00:00Z",
            record_created_at="2026-07-10T00:00:00Z",
            record_updated_at="2026-07-01T00:00:00Z",
        )
        ass = assess_evidence(rec, cutoff)
        self.assertEqual(ass.disposition, TemporalDisposition.CONFLICTING_TIMESTAMPS)
        self.assertFalse(ass.state_usable)
        self.assertEqual(ass.reason_code, "CREATED_AFTER_UPDATED")

    def test_deterministic_repeated_assessment(self):
        cutoff = "2026-08-01T00:00:00Z"
        rec = EvidenceRecord(
            evidence_id="ev_1",
            evidence_ref_type="file_id",
            source_path="a.sql",
            source_kind="sql",
            locator="t=1",
            system_id="sys",
            resource_id="res_1",
            data_category="CAT",
            observed_at="2026-07-01T00:00:00Z",
            fields=(),
            text="",
            captured_at="2026-07-01T00:00:00Z",
        )
        ass1 = assess_evidence(rec, cutoff)
        ass2 = assess_evidence(rec, cutoff)
        self.assertEqual(ass1, ass2)

    def test_assess_hits_wrapper(self):
        cutoff = "2026-08-01T00:00:00Z"
        rec1 = EvidenceRecord(
            evidence_id="ev_1",
            evidence_ref_type="file_id",
            source_path="a.sql",
            source_kind="sql",
            locator="t=1",
            system_id="sys",
            resource_id="res_1",
            data_category="CAT",
            observed_at="2026-07-01T00:00:00Z",
            fields=(),
            text="",
            captured_at="2026-07-01T00:00:00Z",
        )
        rec2 = EvidenceRecord(
            evidence_id="ev_2",
            evidence_ref_type="file_id",
            source_path="b.sql",
            source_kind="sql",
            locator="t=2",
            system_id="sys",
            resource_id="res_2",
            data_category="CAT",
            observed_at="2026-09-01T00:00:00Z",
            fields=(),
            text="",
            captured_at="2026-09-01T00:00:00Z",
        )
        pairs = assess_hits([rec1, rec2], cutoff)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0][1].disposition, TemporalDisposition.ADMISSIBLE)
        self.assertEqual(pairs[1][1].disposition, TemporalDisposition.POST_CUTOFF)


if __name__ == "__main__":
    unittest.main()
