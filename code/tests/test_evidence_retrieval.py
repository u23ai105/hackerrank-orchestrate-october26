import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.evidence_retrieval import (
    EvidenceHit,
    EvidenceIndex,
    EvidenceQueryResult,
    EvidenceRecord,
    match_structured_fields,
    match_unstructured_text,
    redact_pii,
)
from tools.identity_resolution import (
    AliasRecord,
    IdentityProfile,
    email_sha256,
    normalize_email,
    normalize_phone,
)


class EvidenceRetrievalTests(unittest.TestCase):
    def make_profile(
        self,
        user_id="user_test1",
        emails=("alice@example.com",),
        email_hashes=(),
        phones=(),
        aliases=(),
    ) -> IdentityProfile:
        norm_emails = tuple(sorted({normalize_email(e) for e in emails if normalize_email(e)}))
        norm_hashes = tuple(sorted(set(email_hashes)))
        norm_phones = tuple(sorted({normalize_phone(p) for p in phones if normalize_phone(p)}))
        return IdentityProfile(
            user_id=user_id,
            emails=norm_emails,
            email_hashes=norm_hashes,
            phones=norm_phones,
            aliases=tuple(aliases),
        )

    def test_1_exact_current_email_match_structured(self):
        prof = self.make_profile(emails=("alice@example.com",))
        rec = EvidenceRecord(
            evidence_id="evidence_01",
            evidence_ref_type="file_id",
            source_path="db.sql",
            source_kind="sql",
            locator="table=accounts:row=1:pk=account_101",
            system_id="account_service",
            resource_id="account_101",
            data_category="ACCOUNT",
            observed_at="2026-01-01T00:00:00Z",
            fields=(("email", "alice@example.com"), ("resource_id", "account_101")),
            text="account_101 alice@example.com",
        )
        index = EvidenceIndex([rec])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 1)
        self.assertEqual(res.hits[0].match_scope, "DIRECT_IDENTIFIER")
        self.assertIn("email", res.hits[0].match_pathways)

    def test_2_historical_email_alias_match(self):
        prof = self.make_profile(
            emails=("new@example.com", "old@example.com"),
            aliases=(
                AliasRecord(kind="email", value="new@example.com", source="current_identity"),
                AliasRecord(kind="email", value="old@example.com", source="audit_log"),
            ),
        )
        rec = EvidenceRecord(
            evidence_id="evidence_02",
            evidence_ref_type="file_id",
            source_path="archive.json",
            source_kind="json",
            locator="$.records[0]",
            system_id="archive_service",
            resource_id="account_102",
            data_category="ARCHIVE",
            observed_at="2025-01-01T00:00:00Z",
            fields=(("email", "old@example.com"), ("resource_id", "account_102")),
            text="account_102 old@example.com",
        )
        index = EvidenceIndex([rec])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 1)
        self.assertIn("email", res.hits[0].match_pathways)

    def test_3_exact_email_hash_alias_match(self):
        digest = email_sha256("bob@example.com")
        prof = self.make_profile(
            user_id="user_bob",
            emails=("bob@example.com",),
            email_hashes=(digest,),
        )
        rec = EvidenceRecord(
            evidence_id="evidence_03",
            evidence_ref_type="file_id",
            source_path="security_cache.json",
            source_kind="json",
            locator="$.items[0]",
            system_id="cache_service",
            resource_id="cache_103",
            data_category="CACHE",
            observed_at="2026-02-01T00:00:00Z",
            fields=(("email_hash", digest), ("resource_id", "cache_103")),
            text=f"cache_103 {digest}",
        )
        index = EvidenceIndex([rec])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 1)
        self.assertIn("email_hash", res.hits[0].match_pathways)

    def test_4_stable_user_id_match_in_structured_record(self):
        prof = self.make_profile(user_id="user_444")
        rec = EvidenceRecord(
            evidence_id="evidence_04",
            evidence_ref_type="file_id",
            source_path="users.sql",
            source_kind="sql",
            locator="table=users:row=4:pk=user_444",
            system_id="user_service",
            resource_id="account_104",
            data_category="USER",
            observed_at="2026-03-01T00:00:00Z",
            fields=(("user_id", "user_444"), ("resource_id", "account_104")),
            text="user_444 account_104",
        )
        index = EvidenceIndex([rec])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 1)
        self.assertIn("user_id", res.hits[0].match_pathways)

    def test_5_polymorphic_reference_handling(self):
        digest = email_sha256("charlie@example.com")
        prof = self.make_profile(
            user_id="user_charlie",
            emails=("charlie@example.com",),
            email_hashes=(digest,),
        )
        # customer_reference holding user_id
        rec1 = EvidenceRecord(
            evidence_id="evidence_05a",
            evidence_ref_type="file_id",
            source_path="export.json",
            source_kind="json",
            locator="$.records[0]",
            system_id="export_service",
            resource_id="export_001",
            data_category="EXPORT",
            observed_at="2026-04-01T00:00:00Z",
            fields=(("customer_reference", "user_charlie"), ("resource_id", "export_001")),
            text="customer_reference=user_charlie",
        )
        # subject_reference holding email
        rec2 = EvidenceRecord(
            evidence_id="evidence_05b",
            evidence_ref_type="file_id",
            source_path="export.json",
            source_kind="json",
            locator="$.records[1]",
            system_id="export_service",
            resource_id="export_002",
            data_category="EXPORT",
            observed_at="2026-04-01T00:00:00Z",
            fields=(("subject_reference", "charlie@example.com"), ("resource_id", "export_002")),
            text="subject_reference=charlie@example.com",
        )
        # subject_reference holding hash
        rec3 = EvidenceRecord(
            evidence_id="evidence_05c",
            evidence_ref_type="file_id",
            source_path="export.json",
            source_kind="json",
            locator="$.records[2]",
            system_id="export_service",
            resource_id="export_003",
            data_category="EXPORT",
            observed_at="2026-04-01T00:00:00Z",
            fields=(("subject_reference", digest), ("resource_id", "export_003")),
            text=f"subject_reference={digest}",
        )
        index = EvidenceIndex([rec1, rec2, rec3])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 3)

    def test_6_similar_looking_non_identical_email_does_not_match(self):
        prof = self.make_profile(emails=("alice@example.com",))
        rec1 = EvidenceRecord(
            evidence_id="evidence_06",
            evidence_ref_type="file_id",
            source_path="db.sql",
            source_kind="sql",
            locator="table=accounts:row=1:pk=account_1",
            system_id="account_service",
            resource_id="account_1",
            data_category="ACCOUNT",
            observed_at="2026-01-01T00:00:00Z",
            fields=(("email", "alice2@example.com"),),
            text="alice2@example.com",
        )
        rec2 = EvidenceRecord(
            evidence_id="evidence_06b",
            evidence_ref_type="file_id",
            source_path="db.sql",
            source_kind="sql",
            locator="table=accounts:row=2:pk=account_2",
            system_id="account_service",
            resource_id="account_2",
            data_category="ACCOUNT",
            observed_at="2026-01-01T00:00:00Z",
            fields=(("email", "alice@example.org"),),
            text="alice@example.org",
        )
        index = EvidenceIndex([rec1, rec2])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 0)

    def test_7_formatted_and_unformatted_phone_handling(self):
        prof = self.make_profile(phones=("+1 (202) 555-0103",))
        rec1 = EvidenceRecord(
            evidence_id="evidence_07",
            evidence_ref_type="file_id",
            source_path="profiles.json",
            source_kind="json",
            locator="$.records[0]",
            system_id="profile_service",
            resource_id="profile_07",
            data_category="PROFILE",
            observed_at="2026-01-01T00:00:00Z",
            fields=(("phone", "+1 202 555 0103"),),
            text="phone=+1 202 555 0103",
        )
        rec2 = EvidenceRecord(
            evidence_id="evidence_07b",
            evidence_ref_type="file_id",
            source_path="log.txt",
            source_kind="txt",
            locator="line:1",
            system_id="log_service",
            resource_id="log_07",
            data_category="LOG",
            observed_at="2026-01-01T00:00:00Z",
            fields=(),
            # Should not match arbitrary date formatted numbers
            text="Logged on 2026-05-24 by operator 1234567890",
        )
        index = EvidenceIndex([rec1, rec2])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 1)
        self.assertEqual(res.hits[0].record.evidence_id, "evidence_07")

    def test_8_unstructured_log_match_preserves_locator_and_file_id(self):
        prof = self.make_profile(emails=("operator@example.com",))
        rec = EvidenceRecord(
            evidence_id="evidence_27",
            evidence_ref_type="file_id",
            source_path="evidence/logs/server.log",
            source_kind="log",
            locator="line:42",
            system_id="logging_service",
            resource_id="account_999",
            data_category="LOG",
            observed_at="2026-05-15T10:00:00Z",
            fields=(("resource_id", "account_999"),),
            text="[2026-05-15T10:00:00Z] Login attempt for operator@example.com (account_999)",
        )
        index = EvidenceIndex([rec])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 1)
        self.assertEqual(res.hits[0].record.evidence_id, "evidence_27")
        self.assertEqual(res.hits[0].record.locator, "line:42")

    def test_9_nested_json_traversal_preserves_json_path(self):
        prof = self.make_profile(emails=("dave@example.com",))
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            json_file = tmp / "data.json"
            json_file.write_text(
                json.dumps(
                    {
                        "snapshots": [
                            {"records": []},
                            {
                                "records": [
                                    {
                                        "resource_id": "account_77",
                                        "email": "dave@example.com",
                                    }
                                ]
                            },
                        ]
                    }
                )
            )
            manifest = tmp / "evidence_files.csv"
            manifest.write_text(
                "file_id,file_path,origin,captured_at\nevidence_99,data.json,test_sys,2026-01-01T00:00:00Z\n"
            )
            index = EvidenceIndex.from_dataset(tmp)
            res = index.retrieve(prof)
            self.assertEqual(len(res.hits), 1)
            self.assertEqual(res.hits[0].record.locator, "$.snapshots[1].records[0]")

    def test_10_dynamic_sqlite_discovery_with_serialized_json(self):
        prof = self.make_profile(emails=("elena@example.com",))
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sql_file = tmp / "export.sql"
            sql_file.write_text(
                """
                CREATE TABLE arbitrary_custom_table_name (
                    resource_id TEXT,
                    record_json TEXT,
                    updated_at TEXT
                );
                INSERT INTO arbitrary_custom_table_name VALUES (
                    'account_888',
                    '{"customer_info": {"owner_email": "elena@example.com", "tier": "gold"}}',
                    '2026-06-01T12:00:00Z'
                );
                """
            )
            manifest = tmp / "evidence_files.csv"
            manifest.write_text(
                "file_id,file_path,origin,captured_at\nevidence_88,export.sql,test_origin,2026-06-01T00:00:00Z\n"
            )
            index = EvidenceIndex.from_dataset(tmp)
            res = index.retrieve(prof)
            self.assertEqual(len(res.hits), 1)
            self.assertEqual(res.hits[0].record.resource_id, "account_888")
            self.assertTrue(any(k == "owner_email" and v == "elena@example.com" for k, v in res.hits[0].record.fields))

    def test_11_activity_referencing_grounded_resource_includes_true_activity_id(self):
        prof = self.make_profile(user_id="user_555", emails=("user555@example.com",))
        # Direct hit grounds account_555
        rec_direct = EvidenceRecord(
            evidence_id="evidence_55",
            evidence_ref_type="file_id",
            source_path="accounts.sql",
            source_kind="sql",
            locator="table=accounts:row=1:pk=account_555",
            system_id="account_service",
            resource_id="account_555",
            data_category="ACCOUNT",
            observed_at="2026-01-01T00:00:00Z",
            fields=(("email", "user555@example.com"), ("resource_id", "account_555")),
            text="account_555 user555@example.com",
        )
        # Activity references account_555
        rec_act = EvidenceRecord(
            evidence_id="activity_9999",
            evidence_ref_type="activity_id",
            source_path="system_activity.csv",
            source_kind="activity",
            locator="row:99:activity_id=activity_9999",
            system_id="account_service",
            resource_id="account_555",
            data_category="DELETE_RECORD",
            observed_at="2026-01-02T00:00:00Z",
            fields=(("resource_id", "account_555"), ("event_type", "DELETE_RECORD")),
            text="activity_9999 DELETE_RECORD account_555",
        )
        index = EvidenceIndex([rec_direct, rec_act])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 2)
        act_hit = [h for h in res.hits if h.record.evidence_ref_type == "activity_id"][0]
        self.assertEqual(act_hit.record.evidence_id, "activity_9999")
        self.assertEqual(act_hit.match_scope, "RESOURCE_LINK")

    def test_12_explicit_secondary_resource_expansion(self):
        prof = self.make_profile(user_id="user_666", emails=("user666@example.com",))
        # Direct hit grounds account_666
        rec1 = EvidenceRecord(
            evidence_id="evidence_66",
            evidence_ref_type="file_id",
            source_path="account.json",
            source_kind="json",
            locator="$.records[0]",
            system_id="account_service",
            resource_id="account_666",
            data_category="ACCOUNT",
            observed_at="2026-01-01T00:00:00Z",
            fields=(("email", "user666@example.com"), ("resource_id", "account_666")),
            text="user666@example.com",
        )
        # Activity explicitly links account_666 to downstream resource search_777
        rec_sync = EvidenceRecord(
            evidence_id="activity_661",
            evidence_ref_type="activity_id",
            source_path="system_activity.csv",
            source_kind="activity",
            locator="row:661:activity_id=activity_661",
            system_id="sync_service",
            resource_id="account_666",
            data_category="SYNC_RECORD",
            observed_at="2026-01-02T00:00:00Z",
            fields=(("resource_id", "account_666"), ("target_resource_id", "search_777")),
            text="Active connector repopulated downstream resource search_777.",
        )
        # Search record for search_777 without any user identity tokens
        rec_search = EvidenceRecord(
            evidence_id="evidence_77",
            evidence_ref_type="file_id",
            source_path="search.sql",
            source_kind="sql",
            locator="table=search:row=1:pk=search_777",
            system_id="search_service",
            resource_id="search_777",
            data_category="SEARCH",
            observed_at="2026-01-03T00:00:00Z",
            fields=(("resource_id", "search_777"),),
            text="search_777 index entry",
        )
        index = EvidenceIndex([rec1, rec_sync, rec_search])
        res = index.retrieve(prof)
        self.assertIn("search_777", res.grounded_resource_ids)
        self.assertEqual(len(res.hits), 3)

    def test_13_multiple_identifiers_matching_same_location_merged(self):
        prof = self.make_profile(user_id="user_888", emails=("user888@example.com",))
        rec = EvidenceRecord(
            evidence_id="evidence_888",
            evidence_ref_type="file_id",
            source_path="users.json",
            source_kind="json",
            locator="$.records[0]",
            system_id="user_service",
            resource_id="",
            data_category="USER",
            observed_at="2026-01-01T00:00:00Z",
            fields=(
                ("email", "user888@example.com"),
                ("user_id", "user_888"),
            ),
            text="user_888 user888@example.com",
        )
        index = EvidenceIndex([rec])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 1)
        hit = res.hits[0]
        self.assertEqual(hit.match_scope, "DIRECT_IDENTIFIER")
        self.assertEqual(hit.match_pathways, ("email", "user_id"))

    def test_14_independent_source_locations_remain_independently_traceable(self):
        prof = self.make_profile(emails=("user_split@example.com",))
        rec1 = EvidenceRecord(
            evidence_id="evidence_primary",
            evidence_ref_type="file_id",
            source_path="primary.sql",
            source_kind="sql",
            locator="table=accounts:row=1:pk=account_split",
            system_id="primary_db",
            resource_id="account_split",
            data_category="ACCOUNT",
            observed_at="2026-01-01T00:00:00Z",
            fields=(("email", "user_split@example.com"), ("resource_id", "account_split")),
            text="account_split",
        )
        rec2 = EvidenceRecord(
            evidence_id="evidence_replica",
            evidence_ref_type="file_id",
            source_path="replica.sql",
            source_kind="sql",
            locator="table=accounts:row=1:pk=account_split",
            system_id="replica_db",
            resource_id="account_split",
            data_category="ACCOUNT",
            observed_at="2026-01-02T00:00:00Z",
            fields=(("email", "user_split@example.com"), ("resource_id", "account_split")),
            text="account_split",
        )
        index = EvidenceIndex([rec1, rec2])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 2)
        source_paths = {h.record.source_path for h in res.hits}
        self.assertEqual(source_paths, {"primary.sql", "replica.sql"})

    def test_15_evidence_captured_after_cutoff_is_still_returned(self):
        prof = self.make_profile(emails=("future@example.com",))
        rec = EvidenceRecord(
            evidence_id="evidence_future",
            evidence_ref_type="file_id",
            source_path="future.log",
            source_kind="log",
            locator="line:1",
            system_id="log_service",
            resource_id="account_future",
            data_category="LOG",
            observed_at="2029-01-01T00:00:00Z",
            fields=(("email", "future@example.com"),),
            text="future@example.com",
        )
        index = EvidenceIndex([rec])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 1)
        self.assertEqual(res.hits[0].record.observed_at, "2029-01-01T00:00:00Z")

    def test_16_invalid_or_empty_profile_returns_safe_empty(self):
        index = EvidenceIndex([])
        res1 = index.retrieve(None)
        self.assertEqual(len(res1.hits), 0)
        self.assertTrue(len(res1.diagnostics) > 0)

        empty_prof = IdentityProfile(user_id="", emails=(), email_hashes=(), phones=(), aliases=())
        res2 = index.retrieve(empty_prof)
        self.assertEqual(len(res2.hits), 0)

    def test_17_missing_files_malformed_json_sql_errors_in_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Create bad json
            (tmp / "bad.json").write_text("{malformed json")
            # Create bad sql
            (tmp / "bad.sql").write_text("THIS IS NOT SQL SYNTAX;")
            # Create unsupported file on disk
            (tmp / "file.xyz").write_text("unsupported content")
            manifest = tmp / "evidence_files.csv"
            manifest.write_text(
                "file_id,file_path,origin,captured_at\n"
                "e_bad_json,bad.json,sys1,2026-01-01T00:00:00Z\n"
                "e_bad_sql,bad.sql,sys2,2026-01-01T00:00:00Z\n"
                "e_missing,missing.log,sys3,2026-01-01T00:00:00Z\n"
                "e_unsupported,file.xyz,sys4,2026-01-01T00:00:00Z\n"
            )
            index = EvidenceIndex.from_dataset(tmp)
            diag_str = " ".join(index.diagnostics)
            self.assertIn("bad.json", diag_str)
            self.assertIn("bad.sql", diag_str)
            self.assertIn("Missing evidence file", diag_str)
            self.assertIn("Unsupported evidence file extension", diag_str)

    def test_18_repeated_retrieval_returns_same_ordered_results(self):
        prof = self.make_profile(user_id="user_repeat", emails=("repeat@example.com",))
        rec1 = EvidenceRecord(
            evidence_id="e1",
            evidence_ref_type="file_id",
            source_path="b.json",
            source_kind="json",
            locator="$.records[1]",
            system_id="sys",
            resource_id="res_1",
            data_category="CAT",
            observed_at="2026-02-01T00:00:00Z",
            fields=(("email", "repeat@example.com"),),
            text="repeat@example.com",
        )
        rec2 = EvidenceRecord(
            evidence_id="e2",
            evidence_ref_type="file_id",
            source_path="a.json",
            source_kind="json",
            locator="$.records[0]",
            system_id="sys",
            resource_id="res_2",
            data_category="CAT",
            observed_at="2026-01-01T00:00:00Z",
            fields=(("email", "repeat@example.com"),),
            text="repeat@example.com",
        )
        index = EvidenceIndex([rec1, rec2])
        res1 = index.retrieve(prof)
        res2 = index.retrieve(prof)
        self.assertEqual(res1.hits, res2.hits)
        # Should be ordered by observed_at ascending
        self.assertEqual(res1.hits[0].record.evidence_id, "e2")
        self.assertEqual(res1.hits[1].record.evidence_id, "e1")

    def test_19_distinct_timestamp_provenance_and_boundaries(self):
        """Test snapshot capture time vs row updated_at/event_time distinction, boundary, and missing values."""
        synthetic_cutoff = "2026-08-01T00:00:00Z"

        # Record 1: Snapshot captured AFTER cutoff (2026-09-01), but row updated BEFORE cutoff (2026-07-15)
        rec1 = EvidenceRecord(
            evidence_id="e_snap_late",
            evidence_ref_type="file_id",
            source_path="inventory_late.sql",
            source_kind="sql",
            locator="table=users:row=1:pk=account_1",
            system_id="account_service",
            resource_id="account_1",
            data_category="ACCOUNT",
            observed_at="2026-07-15T09:30:00Z",
            fields=(("email", "ts@example.com"), ("updated_at", "2026-07-15T09:30:00Z")),
            text="ts@example.com",
            captured_at="2026-09-01T12:00:00Z",
            event_time="",
            record_updated_at="2026-07-15T09:30:00Z",
            record_created_at="2026-01-01T00:00:00Z",
        )
        self.assertGreater(rec1.captured_at, synthetic_cutoff)
        self.assertLess(rec1.record_updated_at, synthetic_cutoff)
        self.assertNotEqual(rec1.captured_at, rec1.record_updated_at)

        # Record 2: Boundary timestamp (exactly on cutoff)
        rec2 = EvidenceRecord(
            evidence_id="e_boundary",
            evidence_ref_type="file_id",
            source_path="boundary.json",
            source_kind="json",
            locator="$.records[0]",
            system_id="sys",
            resource_id="res_b",
            data_category="BOUNDARY",
            observed_at=synthetic_cutoff,
            fields=(("email", "ts@example.com"),),
            text="ts@example.com",
            captured_at=synthetic_cutoff,
            event_time=synthetic_cutoff,
            record_updated_at=synthetic_cutoff,
        )
        self.assertEqual(rec2.captured_at, synthetic_cutoff)
        self.assertEqual(rec2.record_updated_at, synthetic_cutoff)

        # Record 3: Missing timestamps
        rec3 = EvidenceRecord(
            evidence_id="e_missing_ts",
            evidence_ref_type="file_id",
            source_path="no_ts.txt",
            source_kind="txt",
            locator="line:1",
            system_id="sys",
            resource_id="res_m",
            data_category="TXT",
            observed_at="",
            fields=(("email", "ts@example.com"),),
            text="ts@example.com",
            captured_at="",
            event_time="",
            record_updated_at="",
        )
        self.assertEqual(rec3.captured_at, "")
        self.assertEqual(rec3.record_updated_at, "")
        self.assertEqual(rec3.observed_at, "")

        prof = self.make_profile(user_id="user_ts", emails=("ts@example.com",))
        index = EvidenceIndex([rec1, rec2, rec3])
        res = index.retrieve(prof)
        self.assertEqual(len(res.hits), 3)

    def test_20_pathway_merging_direct_and_resource_link(self):
        """Verify that a directly matched record encountered during resource correlation preserves both pathways and DIRECT_IDENTIFIER scope."""
        prof = self.make_profile(user_id="user_merge", emails=("merge@example.com",))

        # Record 1 matches directly by email AND has resource_id="account_999"
        rec1 = EvidenceRecord(
            evidence_id="e_direct",
            evidence_ref_type="file_id",
            source_path="account.json",
            source_kind="json",
            locator="$.records[0]",
            system_id="account_service",
            resource_id="account_999",
            data_category="ACCOUNT",
            observed_at="2026-01-01T00:00:00Z",
            fields=(("email", "merge@example.com"), ("resource_id", "account_999")),
            text="account_999 merge@example.com",
        )

        # Record 2 links account_999 to search_888
        rec2 = EvidenceRecord(
            evidence_id="activity_991",
            evidence_ref_type="activity_id",
            source_path="system_activity.csv",
            source_kind="activity",
            locator="row:991:activity_id=activity_991",
            system_id="sync_service",
            resource_id="account_999",
            data_category="SYNC_RECORD",
            observed_at="2026-01-02T00:00:00Z",
            fields=(("resource_id", "account_999"), ("target_resource_id", "search_888")),
            text="repopulated search_888 from account_999",
        )

        # Record 3 is also for account_999, directly matched by email, and encountered again during correlation for account_999
        rec3 = EvidenceRecord(
            evidence_id="e_replica",
            evidence_ref_type="file_id",
            source_path="replica.sql",
            source_kind="sql",
            locator="table=replica:row=1:pk=account_999",
            system_id="replica_service",
            resource_id="account_999",
            data_category="REPLICA",
            observed_at="2026-01-03T00:00:00Z",
            fields=(("email", "merge@example.com"), ("resource_id", "account_999")),
            text="replica account_999 merge@example.com",
        )

        index = EvidenceIndex([rec1, rec2, rec3])
        res = index.retrieve(prof)

        # Find the hit for rec3
        replica_hits = [h for h in res.hits if h.record.locator == "table=replica:row=1:pk=account_999"]
        self.assertEqual(len(replica_hits), 1, "Exactly one hit must be emitted without duplication")
        hit = replica_hits[0]

        # Scope must remain DIRECT_IDENTIFIER
        self.assertEqual(hit.match_scope, "DIRECT_IDENTIFIER")
        # Pathways must contain both direct 'email' and 'resource_link:account_999'
        self.assertIn("email", hit.match_pathways)
        self.assertIn("resource_link:account_999", hit.match_pathways)
        # Reason must mention both
        self.assertIn("Direct identifier match", hit.reason)
        self.assertIn("resource_link:account_999", hit.reason)

    def test_21_manifest_diagnostics_completeness(self):
        """Test diagnostics for duplicate IDs, duplicate paths, missing files, unlisted files, and empty extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ev_dir = tmp / "evidence"
            ev_dir.mkdir(parents=True)

            # Create 1 valid file
            f_valid = ev_dir / "valid.txt"
            f_valid.write_text("user_valid line user_id=user_100\n")

            # Create 1 empty file
            f_empty = ev_dir / "empty.txt"
            f_empty.write_text("\n\n")

            # Create 1 unlisted file on disk
            f_unlisted = ev_dir / "unlisted.txt"
            f_unlisted.write_text("some unlisted data\n")

            manifest = tmp / "evidence_files.csv"
            manifest.write_text(
                "file_id,file_path,origin,captured_at\n"
                "e_1,evidence/valid.txt,sys,2026-01-01T00:00:00Z\n"
                "e_1,evidence/valid.txt,sys,2026-01-01T00:00:00Z\n"  # Duplicate file_id and file_path
                "e_empty,evidence/empty.txt,sys,2026-01-01T00:00:00Z\n"
                "e_missing,evidence/nonexistent.log,sys,2026-01-01T00:00:00Z\n"
            )

            index = EvidenceIndex.from_dataset(tmp)
            diag_str = " ".join(index.diagnostics)

            self.assertIn("Duplicate manifest file_id: e_1", diag_str)
            self.assertIn("Duplicate manifest file_path: evidence/valid.txt", diag_str)
            self.assertIn("Missing evidence file: e_missing", diag_str)
            self.assertIn("Unlisted evidence file on disk: evidence/unlisted.txt", diag_str)
            self.assertIn("Empty or unusable extraction from e_empty", diag_str)

    def test_22_pdf_table_extraction(self):
        """Verify structured PDF table extraction with page/table/row locators."""
        pdf_path = Path("dataset/evidence/documents/account_history_report_20260718.pdf")
        if not pdf_path.exists():
            self.skipTest("account_history_report_20260718.pdf fixture not available")

        recs = []
        diags = []
        EvidenceIndex._parse_pdf(
            pdf_path,
            "evidence_18",
            "evidence/documents/account_history_report_20260718.pdf",
            "doc_service",
            "2026-07-18T10:00:00Z",
            recs,
            diags,
        )
        table_recs = [r for r in recs if ":table:" in r.locator]
        self.assertGreater(len(table_recs), 0, "Must extract structured table records from PDF")
        # Check locator format
        first_tbl = table_recs[0]
        self.assertTrue(first_tbl.locator.startswith("page:"))
        self.assertIn(":table:", first_tbl.locator)
        self.assertIn(":row:", first_tbl.locator)
        self.assertEqual(first_tbl.data_category, "DOCUMENT_TABLE")

    def test_23_path_traversal_rejection(self):
        """Verify that path traversal in evidence_files.csv is safely rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest = tmp / "evidence_files.csv"
            manifest.write_text(
                "file_id,file_path,origin,captured_at\n"
                "e_bad,../../outside.json,sys,2026-01-01T00:00:00Z\n"
            )
            index = EvidenceIndex.from_dataset(tmp)
            diag_str = " ".join(index.diagnostics)
            self.assertIn("Rejected path traversal", diag_str)

    def test_24_sql_snapshot_distinctions(self):
        """Distinguish successful empty SQL snapshot, real SQL execution failure, and non-empty snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ev_dir = tmp / "evidence"
            ev_dir.mkdir(parents=True)

            # 1. Successful empty SQL snapshot (valid schema, snapshot_scope, zero resource rows)
            empty_sql = ev_dir / "empty_snapshot.sql"
            empty_sql.write_text(
                "CREATE TABLE snapshot_scope (origin_system TEXT PRIMARY KEY, captured_at TEXT NOT NULL);\n"
                "CREATE TABLE customer_profiles (resource_id TEXT PRIMARY KEY, email TEXT, updated_at TEXT);\n"
                "INSERT INTO snapshot_scope VALUES ('account_service', '2026-09-01T00:00:00Z');\n"
            )

            # 2. Real SQL execution failure (syntax error)
            broken_sql = ev_dir / "broken_syntax.sql"
            broken_sql.write_text("CREATE TABLE broken (id INT; INVALID SYNTAX HERE\n")

            # 3. Non-empty SQL snapshot (valid schema, 1 row inserted)
            valid_sql = ev_dir / "populated_snapshot.sql"
            valid_sql.write_text(
                "CREATE TABLE snapshot_scope (origin_system TEXT PRIMARY KEY, captured_at TEXT NOT NULL);\n"
                "CREATE TABLE customer_profiles (resource_id TEXT PRIMARY KEY, email TEXT, updated_at TEXT);\n"
                "INSERT INTO snapshot_scope VALUES ('account_service', '2026-09-01T00:00:00Z');\n"
                "INSERT INTO customer_profiles VALUES ('acc_1', 'user@example.com', '2026-09-01T00:00:00Z');\n"
            )

            manifest = tmp / "evidence_files.csv"
            manifest.write_text(
                "file_id,file_path,origin,captured_at\n"
                "e_empty,evidence/empty_snapshot.sql,account_service,2026-09-01T00:00:00Z\n"
                "e_broken,evidence/broken_syntax.sql,account_service,2026-09-01T00:00:00Z\n"
                "e_valid,evidence/populated_snapshot.sql,account_service,2026-09-01T00:00:00Z\n"
            )

            index = EvidenceIndex.from_dataset(tmp)
            outcomes = index.file_outcomes

            # 1. Empty snapshot: successful execution, zero resource records, distinct EMPTY_SNAPSHOT status
            self.assertEqual(outcomes["e_empty"]["status"], "EMPTY_SNAPSHOT")
            self.assertEqual(outcomes["e_empty"]["record_count"], 0)
            self.assertTrue(any("zero resource records" in d and "e_empty" in d for d in index.diagnostics))

            # 2. Broken SQL: real execution failure, PARSE_ERROR status
            self.assertEqual(outcomes["e_broken"]["status"], "PARSE_ERROR")
            self.assertEqual(outcomes["e_broken"]["record_count"], 0)
            self.assertTrue(any("Error parsing e_broken" in d for d in index.diagnostics))

            # 3. Valid populated SQL: SUCCESS status, 1 record
            self.assertEqual(outcomes["e_valid"]["status"], "SUCCESS")
            self.assertEqual(outcomes["e_valid"]["record_count"], 1)


if __name__ == "__main__":
    unittest.main()
