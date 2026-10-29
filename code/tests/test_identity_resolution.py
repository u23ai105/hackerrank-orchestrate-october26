import unittest

from tools.identity_resolution import (
    IdentityResolver,
    ResolutionStatus,
    email_sha256,
    normalize_email,
    normalize_email_hash,
    normalize_phone,
)


class IdentityResolutionTests(unittest.TestCase):
    def make_resolver(self, identities=(), audits=()):
        return IdentityResolver(identities, audits)

    def test_normalizes_email(self):
        self.assertEqual(
            normalize_email("  ALICE@Example.COM  "),
            "alice@example.com",
        )

    def test_hash_is_sha256_of_normalized_email(self):
        self.assertEqual(
            email_sha256(" ALICE@Example.COM "),
            email_sha256("alice@example.com"),
        )
        self.assertEqual(len(email_sha256("alice@example.com")), 64)

    def test_normalizes_phone_formatting(self):
        self.assertEqual(
            normalize_phone("+1 (202) 555-0103"),
            "12025550103",
        )

    def test_resolves_current_email(self):
        resolver = self.make_resolver([
            {
                "user_id": "user_a",
                "email": "Alice@Example.com",
                "phone": "+1 202 555 0103",
            }
        ])

        result = resolver.resolve_email(" alice@example.COM ")

        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.user_id, "user_a")
        self.assertIn("alice@example.com", result.profile.emails)
        self.assertIn("12025550103", result.profile.phones)

    def test_resolves_historical_email(self):
        resolver = self.make_resolver(
            identities=[
                {
                    "user_id": "user_a",
                    "email": "new@example.com",
                }
            ],
            audits=[
                {
                    "audit_id": "audit_a",
                    "user_id": "user_a",
                    "field_name": "email",
                    "old_value": "old@example.com",
                    "new_value": "new@example.com",
                    "changed_at": "2025-01-01T00:00:00Z",
                }
            ],
        )

        result = resolver.resolve_email("old@example.com")

        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.user_id, "user_a")
        self.assertIn("old@example.com", result.profile.emails)
        self.assertIn("new@example.com", result.profile.emails)
        self.assertTrue(
            any(
                item.source_id == "audit_a"
                and item.value == "old@example.com"
                for item in result.profile.aliases
            )
        )

    def test_resolves_using_stored_email_hash_only(self):
        digest = email_sha256("hashed@example.com")
        resolver = self.make_resolver([
            {
                "user_id": "user_a",
                "email_hash": digest,
            }
        ])

        result = resolver.resolve_email("hashed@example.com")

        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.user_id, "user_a")
        self.assertIn("email_hash", result.matched_by)

    def test_historical_email_creates_hash_lookup(self):
        resolver = self.make_resolver(
            identities=[{"user_id": "user_a"}],
            audits=[
                {
                    "audit_id": "audit_a",
                    "user_id": "user_a",
                    "field_name": "email",
                    "old_value": "old@example.com",
                    "new_value": "",
                }
            ],
        )

        result = resolver.resolve_email("old@example.com")

        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.user_id, "user_a")
        self.assertIn(
            email_sha256("old@example.com"),
            result.profile.email_hashes,
        )

    def test_same_email_repeated_for_same_user_is_not_ambiguous(self):
        resolver = self.make_resolver(
            identities=[
                {"user_id": "user_a", "email": "same@example.com"},
                {"user_id": "user_a", "email": "same@example.com"},
            ]
        )

        result = resolver.resolve_email("same@example.com")

        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.user_id, "user_a")

    def test_same_email_for_two_users_is_ambiguous(self):
        resolver = self.make_resolver([
            {"user_id": "user_a", "email": "shared@example.com"},
            {"user_id": "user_b", "email": "shared@example.com"},
        ])

        result = resolver.resolve_email("shared@example.com")

        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertIsNone(result.user_id)
        self.assertEqual(
            result.candidate_user_ids,
            ("user_a", "user_b"),
        )
        self.assertIsNone(result.profile)

    def test_direct_email_and_hash_collision_is_ambiguous(self):
        digest = email_sha256("shared@example.com")
        resolver = self.make_resolver([
            {"user_id": "user_a", "email": "shared@example.com"},
            {"user_id": "user_b", "email_hash": digest},
        ])

        result = resolver.resolve_email("shared@example.com")

        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertIsNone(result.user_id)

    def test_unrecognized_email_is_unresolved(self):
        resolver = self.make_resolver([
            {"user_id": "user_a", "email": "alice@example.com"}
        ])

        result = resolver.resolve_email("nobody@example.com")

        self.assertEqual(result.status, ResolutionStatus.UNRESOLVED)
        self.assertIsNone(result.user_id)

    def test_invalid_email_is_unresolved(self):
        resolver = self.make_resolver([
            {"user_id": "user_a", "email": "alice@example.com"}
        ])

        for value in ("", "   ", None, "not-an-email"):
            with self.subTest(value=value):
                result = resolver.resolve_email(value)
                self.assertEqual(
                    result.status, ResolutionStatus.UNRESOLVED
                )

    def test_matching_is_exact_not_fuzzy(self):
        resolver = self.make_resolver([
            {"user_id": "user_a", "email": "alice@example.com"}
        ])

        for value in (
            "alice2@example.com",
            "alice+tag@example.com",
            "prefix-alice@example.com",
        ):
            with self.subTest(value=value):
                self.assertEqual(
                    resolver.resolve_email(value).status,
                    ResolutionStatus.UNRESOLVED,
                )

    def test_does_not_match_person_name(self):
        resolver = self.make_resolver([
            {
                "user_id": "user_a",
                "email": "alice@example.com",
                "full_name": "Example Person",
            }
        ])

        result = resolver.resolve_email("example person")

        self.assertEqual(result.status, ResolutionStatus.UNRESOLVED)

    def test_named_historical_email_columns(self):
        resolver = self.make_resolver(
            identities=[{"user_id": "user_a"}],
            audits=[
                {
                    "audit_id": "audit_a",
                    "user_id": "user_a",
                    "old_email": "old@example.com",
                    "new_email": "new@example.com",
                    "changed_at": "2025-01-01T00:00:00Z",
                }
            ],
        )

        result = resolver.resolve_email("old@example.com")

        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.user_id, "user_a")

    def test_get_profile_for_unknown_user(self):
        resolver = self.make_resolver([])

        self.assertIsNone(resolver.get_profile("unknown_user"))

    def test_alias_order_is_deterministic(self):
        resolver = self.make_resolver(
            identities=[
                {"user_id": "user_a", "email": "z@example.com"},
                {"user_id": "user_a", "email": "a@example.com"},
            ]
        )

        profile = resolver.get_profile("user_a")

        self.assertEqual(
            profile.emails,
            ("a@example.com", "z@example.com"),
        )

    def test_malformed_identity_row_is_not_guessed(self):
        resolver = self.make_resolver([
            {"email": "no-user@example.com"}
        ])

        result = resolver.resolve_email("no-user@example.com")

        self.assertEqual(result.status, ResolutionStatus.UNRESOLVED)
        self.assertEqual(
            resolver.diagnostics["identity_rows_without_user_id"],
            1,
        )

    # --- Additional Boundary and Header-Variation Regression Tests ---

    def test_normalize_phone_boundaries(self):
        # Digits < 7 should be rejected (empty string)
        self.assertEqual(normalize_phone("123456"), "")
        # Digits > 15 should be rejected
        self.assertEqual(normalize_phone("1234567890123456"), "")
        # Valid range 7 to 15 digits
        self.assertEqual(normalize_phone("1234567"), "1234567")
        self.assertEqual(normalize_phone("+44 7911 123456"), "447911123456")

    def test_normalize_email_hash_prefixes_and_casing(self):
        raw_hash = "d4e1f59abcf9a1e0cfdc7c27ad6c07ed4ff88b326a16ed5eed5ec6bc31618c93"
        self.assertEqual(
            normalize_email_hash(f"sha256:{raw_hash.upper()}"),
            raw_hash,
        )
        self.assertEqual(
            normalize_email_hash(f"sha256${raw_hash}"),
            raw_hash,
        )
        # Invalid length or non-hex characters
        self.assertEqual(normalize_email_hash("not-a-hash"), "")
        self.assertEqual(normalize_email_hash(raw_hash[:63]), "")

    def test_supports_updated_at_and_event_time_headers(self):
        resolver = self.make_resolver(
            identities=[
                {
                    "user_id": "user_x",
                    "email": "user.x@test.com",
                    "updated_at": "2026-05-28T04:03:00Z",
                }
            ],
            audits=[
                {
                    "audit_id": "audit_99",
                    "user_id": "user_x",
                    "field_name": "phone",
                    "old_value": "+1-555-0100",
                    "new_value": "+1-555-0199",
                    "event_time": "2025-02-14T12:00:00Z",
                }
            ],
        )

        profile = resolver.get_profile("user_x")
        self.assertIsNotNone(profile)
        # Check that observed_at was picked up from updated_at for identity
        id_aliases = [a for a in profile.aliases if a.source == "current_identity"]
        self.assertTrue(any(a.observed_at == "2026-05-28T04:03:00Z" for a in id_aliases))
        # Check that observed_at was picked up from event_time for audit
        audit_aliases = [a for a in profile.aliases if a.source == "audit_log"]
        self.assertTrue(any(a.observed_at == "2025-02-14T12:00:00Z" for a in audit_aliases))

    def test_direct_email_match_does_not_claim_independent_hash_match(self):
        resolver = self.make_resolver([
            {
                "user_id": "user_a",
                "email": "alice@example.com",
            }
        ])

        result = resolver.resolve_email("alice@example.com")

        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.user_id, "user_a")
        self.assertEqual(result.matched_by, ("email",))

        # Derived hashes remain available for evidence retrieval.
        self.assertIn(
            email_sha256("alice@example.com"),
            result.profile.email_hashes,
        )

    def test_explicit_stored_hash_only_can_resolve_email(self):
        digest = email_sha256("hashed@example.com")

        resolver = self.make_resolver([
            {
                "user_id": "user_a",
                "email_hash": digest,
            }
        ])

        result = resolver.resolve_email("hashed@example.com")

        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.user_id, "user_a")
        self.assertEqual(result.matched_by, ("email_hash",))

    def test_direct_email_and_stored_hash_collision_is_ambiguous(self):
        digest = email_sha256("shared@example.com")

        resolver = self.make_resolver([
            {"user_id": "user_a", "email": "shared@example.com"},
            {"user_id": "user_b", "email_hash": digest},
        ])

        result = resolver.resolve_email("shared@example.com")

        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertIsNone(result.user_id)
        self.assertEqual(
            result.candidate_user_ids,
            ("user_a", "user_b"),
        )


if __name__ == "__main__":
    unittest.main()

