"""
Deterministic Identity Resolution Tool for Ghost Data Still Exists.

Maps an input email address to a stable user_id using current identity snapshots
and historical audit logs. Collects all known aliases (emails, email hashes, phones)
along with their provenance (timestamps, audit IDs) for downstream evidence retrieval.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping, Optional

__all__ = [
    "ResolutionStatus",
    "AliasRecord",
    "IdentityProfile",
    "IdentityResolution",
    "IdentityResolver",
    "normalize_email",
    "normalize_phone",
    "normalize_email_hash",
    "email_sha256",
]


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, order=True)
class AliasRecord:
    kind: str
    value: str
    source: str
    source_id: str = ""
    observed_at: str = ""


@dataclass(frozen=True)
class IdentityProfile:
    user_id: str
    emails: tuple[str, ...]
    email_hashes: tuple[str, ...]
    phones: tuple[str, ...]
    aliases: tuple[AliasRecord, ...]


@dataclass(frozen=True)
class IdentityResolution:
    status: ResolutionStatus
    queried_email: str
    user_id: Optional[str]
    candidate_user_ids: tuple[str, ...]
    matched_by: tuple[str, ...]
    profile: Optional[IdentityProfile]
    reason: str


_FIELD_ALIASES = {
    "user_id": {
        "userid",
        "useridentifier",
        "stableuserid",
        "owneruserid",
    },
    "email": {
        "email",
        "emailaddress",
        "primaryemail",
        "currentemail",
        "identityemail",
    },
    "email_hash": {
        "emailhash",
        "hashedemail",
        "sha256email",
        "emailsha256",
    },
    "phone": {
        "phone",
        "phonenumber",
        "mobile",
        "mobilenumber",
        "telephone",
        "telephonenumber",
    },
    "field_name": {
        "field",
        "fieldname",
        "changedfield",
        "identityfield",
        "attributename",
        "attribute",
    },
    "old_value": {
        "oldvalue",
        "previousvalue",
        "priorvalue",
        "fromvalue",
    },
    "new_value": {
        "newvalue",
        "currentvalue",
        "replacementvalue",
        "tovalue",
    },
    "audit_id": {
        "auditid",
        "identityauditid",
        "eventid",
        "logid",
    },
    "observed_at": {
        "changedat",
        "eventat",
        "timestamp",
        "occurredat",
        "observedat",
        "createdat",
        "updatedat",
        "eventtime",
        "updatedtime",
        "modifiedat",
    },
}


def _norm_col(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _clean(value: object) -> str:
    if value is None:
        return ""

    value = str(value).strip()
    if value.lower() in {"", "none", "null", "nan", "n/a", "unknown"}:
        return ""
    return value


def _pick(row: Mapping, semantic_name: str) -> str:
    aliases = _FIELD_ALIASES[semantic_name]

    for key, value in row.items():
        if _norm_col(key) in aliases:
            cleaned = _clean(value)
            if cleaned:
                return cleaned

    return ""


def normalize_email(value: object) -> str:
    email = _clean(value).lower()

    # Reject malformed values rather than making speculative matches.
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return ""

    return email


def normalize_phone(value: object) -> str:
    digits = re.sub(r"\D", "", _clean(value))

    # Avoid indexing extensions, short codes, or arbitrary numbers.
    if not 7 <= len(digits) <= 15:
        return ""

    return digits


def normalize_email_hash(value: object) -> str:
    value = _clean(value).lower()

    for prefix in ("sha256:", "sha256$"):
        if value.startswith(prefix):
            value = value[len(prefix) :]

    if not re.fullmatch(r"[0-9a-f]{64}", value):
        return ""

    return value


def email_sha256(email: object) -> str:
    normalized = normalize_email(email)
    if not normalized:
        return ""

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _canonical_kind(value: object) -> str:
    field = _norm_col(value)

    for prefix in ("previous", "prior", "current", "old", "new"):
        if field.startswith(prefix):
            field = field[len(prefix) :]
            break

    if "email" in field and "hash" in field:
        return "email_hash"

    if "email" in field:
        return "email"

    if any(token in field for token in ("phone", "mobile", "telephone")):
        return "phone"

    return ""


def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")

        return list(reader)


class IdentityResolver:
    def __init__(
        self,
        identities: Iterable[Mapping],
        audit_logs: Iterable[Mapping],
    ):
        self._index = defaultdict(lambda: defaultdict(set))
        self._aliases = defaultdict(lambda: defaultdict(list))
        self._known_users = set()
        self.diagnostics = Counter()

        for row in identities:
            self._ingest_identity(row)

        for row in audit_logs:
            self._ingest_audit(row)

    @classmethod
    def from_csv(cls, identities_path, audit_log_path):
        return cls(
            _read_csv(Path(identities_path)),
            _read_csv(Path(audit_log_path)),
        )

    def _add_alias(
        self,
        user_id: str,
        kind: str,
        value: object,
        source: str,
        source_id: str = "",
        observed_at: str = "",
        index_for_resolution: bool = True,
    ) -> None:
        if kind == "email":
            normalized = normalize_email(value)
        elif kind == "email_hash":
            normalized = normalize_email_hash(value)
        elif kind == "phone":
            normalized = normalize_phone(value)
        else:
            return

        if not normalized:
            return

        record = AliasRecord(
            kind=kind,
            value=normalized,
            source=source,
            source_id=source_id,
            observed_at=observed_at,
        )
        records = self._aliases[user_id][(kind, normalized)]

        if record not in records:
            records.append(record)
            self.diagnostics[f"{source}_aliases_added"] += 1

        if index_for_resolution:
            self._index[kind][normalized].add(user_id)

        # Email and email hash are two searchable forms of the same
        # identifier. Preserve the derivation's source provenance.
        # Derived hashes are retained for downstream evidence retrieval
        # but are not indexed as independent resolution evidence.
        if kind == "email":
            digest = email_sha256(normalized)
            if digest:
                self._add_alias(
                    user_id,
                    "email_hash",
                    digest,
                    source=source,
                    source_id=source_id,
                    observed_at=observed_at,
                    index_for_resolution=False,
                )

    def _ingest_identity(self, row: Mapping) -> None:
        self.diagnostics["identity_rows_seen"] += 1

        user_id = _pick(row, "user_id")
        if not user_id:
            self.diagnostics["identity_rows_without_user_id"] += 1
            return

        self._known_users.add(user_id)
        observed_at = _pick(row, "observed_at")

        for kind in ("email", "email_hash", "phone"):
            value = _pick(row, kind)
            if value:
                self._add_alias(
                    user_id,
                    kind,
                    value,
                    source="current_identity",
                    observed_at=observed_at,
                )

    def _ingest_audit(self, row: Mapping) -> None:
        self.diagnostics["audit_rows_seen"] += 1

        user_id = _pick(row, "user_id")
        if not user_id:
            self.diagnostics["audit_rows_without_user_id"] += 1
            return

        self._known_users.add(user_id)
        audit_id = _pick(row, "audit_id")
        observed_at = _pick(row, "observed_at")
        field_kind = _canonical_kind(_pick(row, "field_name"))
        values_added_before = self.diagnostics["audit_log_aliases_added"]

        # Common schema: field_name + old_value/new_value.
        if field_kind:
            for semantic_name in ("old_value", "new_value"):
                value = _pick(row, semantic_name)
                if value:
                    self._add_alias(
                        user_id,
                        field_kind,
                        value,
                        source="audit_log",
                        source_id=audit_id,
                        observed_at=observed_at,
                    )

        # Also support schemas with explicit old_email/new_email,
        # old_email_hash/new_email_hash, or phone-specific columns.
        for column, value in row.items():
            kind = _canonical_kind(column)
            normalized_column = _norm_col(column)

            if not kind or not _clean(value):
                continue

            if normalized_column.startswith(
                ("old", "new", "previous", "prior", "current")
            ):
                self._add_alias(
                    user_id,
                    kind,
                    value,
                    source="audit_log",
                    source_id=audit_id,
                    observed_at=observed_at,
                )

        if (
            self.diagnostics["audit_log_aliases_added"]
            == values_added_before
        ):
            self.diagnostics["audit_rows_without_recognized_alias"] += 1

    def _make_profile(self, user_id: str) -> IdentityProfile:
        records = []
        for values in self._aliases[user_id].values():
            records.extend(values)

        aliases = tuple(sorted(set(records)))

        def values_for(kind: str) -> tuple[str, ...]:
            return tuple(
                sorted({item.value for item in aliases if item.kind == kind})
            )

        return IdentityProfile(
            user_id=user_id,
            emails=values_for("email"),
            email_hashes=values_for("email_hash"),
            phones=values_for("phone"),
            aliases=aliases,
        )

    def get_profile(self, user_id: str) -> Optional[IdentityProfile]:
        user_id = _clean(user_id)

        if not user_id or user_id not in self._known_users:
            return None

        return self._make_profile(user_id)

    def resolve_email(self, email: object) -> IdentityResolution:
        query = normalize_email(email)

        if not query:
            return IdentityResolution(
                status=ResolutionStatus.UNRESOLVED,
                queried_email="",
                user_id=None,
                candidate_user_ids=(),
                matched_by=(),
                profile=None,
                reason="Invalid or empty email; no match attempted.",
            )

        matches = {
            "email": set(self._index["email"].get(query, set())),
            "email_hash": set(
                self._index["email_hash"].get(email_sha256(query), set())
            ),
        }

        candidates = tuple(sorted(set().union(*matches.values())))
        matched_by = tuple(
            kind for kind in ("email", "email_hash") if matches[kind]
        )

        if not candidates:
            return IdentityResolution(
                status=ResolutionStatus.UNRESOLVED,
                queried_email=query,
                user_id=None,
                candidate_user_ids=(),
                matched_by=(),
                profile=None,
                reason="No exact email or corresponding SHA-256 match.",
            )

        if len(candidates) > 1:
            return IdentityResolution(
                status=ResolutionStatus.AMBIGUOUS,
                queried_email=query,
                user_id=None,
                candidate_user_ids=candidates,
                matched_by=matched_by,
                profile=None,
                reason="Identifier evidence points to multiple distinct users.",
            )

        user_id = candidates[0]
        return IdentityResolution(
            status=ResolutionStatus.RESOLVED,
            queried_email=query,
            user_id=user_id,
            candidate_user_ids=candidates,
            matched_by=matched_by,
            profile=self._make_profile(user_id),
            reason="Exactly one distinct user matched exact identifier evidence.",
        )
