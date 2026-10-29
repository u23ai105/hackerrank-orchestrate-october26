"""
Deterministic Evidence Retrieval and Normalization Tool for Ghost Data Still Exists.

Searches structured and unstructured evidence across databases, JSON records, logs,
PDFs, OCR text, system activity, and identity audit logs. Correlates records using
grounded resource-ID relationships to fixed-point convergence.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from tools.identity_resolution import (
    IdentityProfile,
    email_sha256,
    normalize_email,
    normalize_email_hash,
    normalize_phone,
)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None


__all__ = [
    "EvidenceRecord",
    "EvidenceHit",
    "EvidenceQueryResult",
    "EvidenceIndex",
    "normalized_column",
    "match_structured_fields",
    "match_unstructured_text",
    "redact_pii",
]


@dataclass(frozen=True)
class EvidenceRecord:
    """Normalized evidence record preserving source provenance and distinct timestamps.

    Timestamp Provenance:
    - captured_at: file-level snapshot capture timestamp (from manifest captured_at,
      SQL snapshot_scope, or JSON root export metadata).
    - event_time: discrete event timestamp (from system activity, user audit log,
      or timestamped log lines).
    - record_updated_at: entity-level modification timestamp (updated_at column or JSON property).
    - record_created_at: entity-level creation timestamp (created_at column or JSON property).
    - observed_at: primary observed timestamp retained for deterministic sorting
      and backward compatibility.
    """
    evidence_id: str
    evidence_ref_type: str  # file_id, activity_id, or audit_id
    source_path: str
    source_kind: str
    locator: str
    system_id: str
    resource_id: str
    data_category: str
    observed_at: str
    fields: tuple[tuple[str, str], ...]
    text: str
    captured_at: str = ""
    event_time: str = ""
    record_updated_at: str = ""
    record_created_at: str = ""


@dataclass(frozen=True)
class EvidenceHit:
    record: EvidenceRecord
    match_pathways: tuple[str, ...]
    match_scope: str  # DIRECT_IDENTIFIER or RESOURCE_LINK
    reason: str


@dataclass(frozen=True)
class EvidenceQueryResult:
    user_id: str
    hits: tuple[EvidenceHit, ...]
    grounded_resource_ids: tuple[str, ...]
    diagnostics: tuple[str, ...]


EMAIL_TOKEN_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
HASH_TOKEN_RE = re.compile(r"(?i)\b[0-9a-f]{64}\b")
PHONE_TOKEN_RE = re.compile(
    r"(?:\+\d{1,3}[\s\-().]*|\(\d{2,4}\)[\s\-().]*)(?:\d[\s\-().]*){6,14}\d"
)
RESOURCE_ID_RE = re.compile(r"\b([a-zA-Z0-9_]+_[0-9]+)\b")
KV_RE = re.compile(r'([a-zA-Z0-9_]+)=("[^"]*"|\S+)')

FIELD_KINDS = {
    "email": {
        "email",
        "emailaddress",
        "primaryemail",
        "currentemail",
        "requesteremail",
        "owneremail",
        "useremail",
        "contactemail",
        "oldemail",
        "newemail",
    },
    "email_hash": {
        "emailhash",
        "hashedemail",
        "sha256email",
        "emailsha256",
        "subjecthash",
        "customerhash",
        "oldemailhash",
        "newemailhash",
    },
    "phone": {
        "phone",
        "phonenumber",
        "mobile",
        "mobilenumber",
        "telephone",
        "telephonenumber",
        "requesterphone",
        "ownerphone",
        "contactphone",
        "userphone",
        "oldphone",
        "newphone",
    },
    "user_id": {
        "userid",
        "owneruserid",
        "stableuserid",
        "useridentifier",
        "accountuserid",
        "targetuserid",
        "subjectid",
    },
}

POLYMORPHIC_REFERENCE_FIELDS = {
    "customerreference",
    "subjectreference",
    "lookupkey",
    "correlationkey",
    "subjectkey",
    "matchkey",
    "subjectref",
    "matchedvalue",
}

RESOURCE_LINK_FIELDS = {
    "resourceid",
    "sourceresourceid",
    "targetresourceid",
    "linkedresourceid",
    "downstreamresourceid",
    "upstreamresourceid",
    "accountid",
    "customerid",
    "parentresourceid",
}

RELATION_PATTERNS = [
    re.compile(r"(?i)downstream\s+resource\s+([a-zA-Z0-9_]+_[0-9]+)"),
    re.compile(r"(?i)upstream\s+resource\s+([a-zA-Z0-9_]+_[0-9]+)"),
    re.compile(r"(?i)source_resource_id[=:]\s*([a-zA-Z0-9_]+_[0-9]+)"),
    re.compile(r"(?i)target_resource_id[=:]\s*([a-zA-Z0-9_]+_[0-9]+)"),
    re.compile(r"(?i)repopulated\s+([a-zA-Z0-9_]+_[0-9]+)"),
    re.compile(r"(?i)linked\s+([a-zA-Z0-9_]+_[0-9]+)\s+to\s+([a-zA-Z0-9_]+_[0-9]+)"),
]


def normalized_column(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def redact_pii(text: str) -> str:
    s = EMAIL_TOKEN_RE.sub("<EMAIL_REDACTED>", str(text))
    s = HASH_TOKEN_RE.sub("<HASH_REDACTED>", s)
    s = PHONE_TOKEN_RE.sub("<PHONE_REDACTED>", s)
    return s


def profile_identifier_sets(profile: Optional[IdentityProfile]) -> dict[str, set[str]]:
    if not profile:
        return {"email": set(), "email_hash": set(), "phone": set(), "user_id": set()}

    return {
        "email": {normalize_email(v) for v in profile.emails if normalize_email(v)},
        "email_hash": {
            normalize_email_hash(v)
            for v in profile.email_hashes
            if normalize_email_hash(v)
        },
        "phone": {normalize_phone(v) for v in profile.phones if normalize_phone(v)},
        "user_id": {str(profile.user_id).strip()} if profile.user_id else set(),
    }


def match_structured_fields(
    fields: Iterable[tuple[str, str]] | Mapping[str, Any],
    profile: Optional[IdentityProfile],
) -> tuple[str, ...]:
    """Return exact identifier types matched; never use fuzzy or name matching."""
    if not profile:
        return ()

    wanted = profile_identifier_sets(profile)
    matched = set()
    items = fields.items() if isinstance(fields, dict) else fields

    for raw_name, raw_value in items:
        full_name = normalized_column(raw_name)
        leaf_name = normalized_column(str(raw_name).split(".")[-1])
        value = str(raw_value or "").strip()
        if not value:
            continue

        recognized = {
            kind
            for kind, names in FIELD_KINDS.items()
            if full_name in names or leaf_name in names
        }
        if (
            full_name in POLYMORPHIC_REFERENCE_FIELDS
            or leaf_name in POLYMORPHIC_REFERENCE_FIELDS
        ):
            recognized.update(("email", "email_hash", "user_id"))

        for kind in recognized:
            if kind == "email":
                normalized = normalize_email(value) if "@" in value else ""
            elif kind == "email_hash":
                normalized = (
                    normalize_email_hash(value)
                    if HASH_TOKEN_RE.fullmatch(value)
                    else ""
                )
            elif kind == "phone":
                normalized = normalize_phone(value)
            else:
                normalized = value
            if normalized and normalized in wanted[kind]:
                matched.add(kind)

        # `uploaded_by` is deliberately value-tested rather than assumed to
        # have one fixed type. Only exact email/user-ID matches count.
        if full_name == "uploadedby" or leaf_name == "uploadedby":
            normalized_email = normalize_email(value) if "@" in value else ""
            if normalized_email and normalized_email in wanted["email"]:
                matched.add("email")
            if value in wanted["user_id"]:
                matched.add("user_id")

    return tuple(sorted(matched))


def match_unstructured_text(
    text: str, profile: Optional[IdentityProfile]
) -> tuple[str, ...]:
    """Find exact known identifiers in text; leave source locators to adapters."""
    if not profile or not text:
        return ()

    wanted = profile_identifier_sets(profile)
    matched = set()

    for token in EMAIL_TOKEN_RE.findall(text):
        if normalize_email(token) in wanted["email"]:
            matched.add("email")
    for token in HASH_TOKEN_RE.findall(text):
        if normalize_email_hash(token) in wanted["email_hash"]:
            matched.add("email_hash")
    for user_id in wanted["user_id"]:
        if user_id and re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(user_id)}(?![A-Za-z0-9_])",
            text,
        ):
            matched.add("user_id")

    # Phone matching is conservative: accept phone-shaped tokens or an
    # explicitly labeled phone value. Do not scan arbitrary digit runs.
    for token in PHONE_TOKEN_RE.findall(text):
        if re.search(r"\d{4}-\d{2}-\d{2}", token):
            continue
        normalized = normalize_phone(token)
        if normalized and normalized in wanted["phone"]:
            matched.add("phone")
    for match in re.finditer(
        r"(?i)\b(?:phone|mobile|tel|telephone)\s*[:=]\s*['\"]?"
        r"([+0-9()][0-9\s\-().]{6,20}\d)",
        text,
    ):
        normalized = normalize_phone(match.group(1))
        if normalized and normalized in wanted["phone"]:
            matched.add("phone")

    return tuple(sorted(matched))


def _sort_fields(fields: Iterable[tuple[str, Any]]) -> tuple[tuple[str, str], ...]:
    items = [(str(k), str(v)) for k, v in fields if v is not None and str(v).strip() != ""]
    return tuple(
        sorted(
            items,
            key=lambda kv: (normalized_column(kv[0]), str(kv[0]), str(kv[1])),
        )
    )


def _extract_linked_resources(record: EvidenceRecord) -> set[str]:
    """Extract secondary resource IDs explicitly linked by this record."""
    linked = set()
    for field_name, field_value in record.fields:
        norm = normalized_column(field_name)
        val = str(field_value).strip()
        if norm in RESOURCE_LINK_FIELDS and val and val != record.resource_id:
            if RESOURCE_ID_RE.fullmatch(val):
                linked.add(val)
        elif norm in POLYMORPHIC_REFERENCE_FIELDS and val and val != record.resource_id:
            if RESOURCE_ID_RE.fullmatch(val) and not val.startswith("user_"):
                linked.add(val)

    # Search relation patterns in details / text
    if record.text:
        for pat in RELATION_PATTERNS:
            for match in pat.findall(record.text):
                if isinstance(match, tuple):
                    for m in match:
                        if m and m != record.resource_id and RESOURCE_ID_RE.fullmatch(m):
                            linked.add(m)
                elif match and match != record.resource_id and RESOURCE_ID_RE.fullmatch(match):
                    linked.add(match)

    return linked


class EvidenceIndex:
    def __init__(
        self,
        records: Iterable[EvidenceRecord] = (),
        diagnostics: Iterable[str] = (),
        file_outcomes: Optional[Mapping[str, Mapping[str, Any]]] = None,
    ):
        self._records: list[EvidenceRecord] = []
        self._diagnostics: list[str] = list(diagnostics)
        self._file_outcomes: dict[str, dict[str, Any]] = (
            {k: dict(v) for k, v in file_outcomes.items()} if file_outcomes else {}
        )

        self.by_email: dict[str, set[int]] = defaultdict(set)
        self.by_email_hash: dict[str, set[int]] = defaultdict(set)
        self.by_phone: dict[str, set[int]] = defaultdict(set)
        self.by_user_id: dict[str, set[int]] = defaultdict(set)
        self.by_resource_id: dict[str, set[int]] = defaultdict(set)

        seen_locations = set()
        for rec in records:
            loc_key = (
                rec.evidence_ref_type,
                rec.evidence_id,
                rec.source_path,
                rec.locator,
            )
            if loc_key in seen_locations:
                continue
            seen_locations.add(loc_key)

            idx = len(self._records)
            self._records.append(rec)
            self._index_record(idx, rec)

    @property
    def records(self) -> tuple[EvidenceRecord, ...]:
        return tuple(self._records)

    @property
    def diagnostics(self) -> tuple[str, ...]:
        return tuple(self._diagnostics)

    @property
    def file_outcomes(self) -> dict[str, dict[str, Any]]:
        return dict(self._file_outcomes)

    def _index_record(self, idx: int, record: EvidenceRecord) -> None:
        if record.resource_id:
            self.by_resource_id[record.resource_id].add(idx)

        # Index structured fields
        for field_name, field_value in record.fields:
            full_name = normalized_column(field_name)
            leaf_name = normalized_column(str(field_name).split(".")[-1])
            val = str(field_value).strip()
            if not val:
                continue

            if full_name in FIELD_KINDS["email"] or leaf_name in FIELD_KINDS["email"]:
                norm_em = normalize_email(val) if "@" in val else ""
                if norm_em:
                    self.by_email[norm_em].add(idx)
            elif full_name in FIELD_KINDS["email_hash"] or leaf_name in FIELD_KINDS["email_hash"]:
                norm_h = normalize_email_hash(val)
                if norm_h:
                    self.by_email_hash[norm_h].add(idx)
            elif full_name in FIELD_KINDS["phone"] or leaf_name in FIELD_KINDS["phone"]:
                norm_ph = normalize_phone(val)
                if norm_ph:
                    self.by_phone[norm_ph].add(idx)
            elif full_name in FIELD_KINDS["user_id"] or leaf_name in FIELD_KINDS["user_id"]:
                self.by_user_id[val].add(idx)
            elif full_name in POLYMORPHIC_REFERENCE_FIELDS or leaf_name in POLYMORPHIC_REFERENCE_FIELDS:
                if "@" in val:
                    em = normalize_email(val)
                    if em:
                        self.by_email[em].add(idx)
                elif HASH_TOKEN_RE.fullmatch(val):
                    h = normalize_email_hash(val)
                    if h:
                        self.by_email_hash[h].add(idx)
                elif val.startswith("user_"):
                    self.by_user_id[val].add(idx)
                elif RESOURCE_ID_RE.fullmatch(val):
                    self.by_resource_id[val].add(idx)
            elif full_name == "uploadedby" or leaf_name == "uploadedby":
                if "@" in val:
                    em = normalize_email(val)
                    if em:
                        self.by_email[em].add(idx)
                elif val.startswith("user_"):
                    self.by_user_id[val].add(idx)

            if full_name in RESOURCE_LINK_FIELDS or leaf_name in RESOURCE_LINK_FIELDS:
                if RESOURCE_ID_RE.fullmatch(val):
                    self.by_resource_id[val].add(idx)

        # Index unstructured text tokens
        if record.text:
            for token in EMAIL_TOKEN_RE.findall(record.text):
                norm_em = normalize_email(token)
                if norm_em:
                    self.by_email[norm_em].add(idx)
            for token in HASH_TOKEN_RE.findall(record.text):
                norm_h = normalize_email_hash(token)
                if norm_h:
                    self.by_email_hash[norm_h].add(idx)
            for token in PHONE_TOKEN_RE.findall(record.text):
                norm_ph = normalize_phone(token)
                if norm_ph:
                    self.by_phone[norm_ph].add(idx)
            for m in re.finditer(r"\b(user_[0-9]+)\b", record.text):
                self.by_user_id[m.group(1)].add(idx)
            for m in RESOURCE_ID_RE.finditer(record.text):
                self.by_resource_id[m.group(1)].add(idx)

    def retrieve(self, profile: Optional[IdentityProfile]) -> EvidenceQueryResult:
        if not profile or not profile.user_id:
            return EvidenceQueryResult(
                user_id=profile.user_id if profile else "",
                hits=(),
                grounded_resource_ids=(),
                diagnostics=("Empty or invalid profile supplied; zero hits returned.",),
            )

        wanted = profile_identifier_sets(profile)
        diagnostics = list(self._diagnostics)

        # Phase 1: Direct Identity Matching
        candidate_indices = set()
        for em in wanted["email"]:
            candidate_indices.update(self.by_email.get(em, set()))
        for eh in wanted["email_hash"]:
            candidate_indices.update(self.by_email_hash.get(eh, set()))
        for ph in wanted["phone"]:
            candidate_indices.update(self.by_phone.get(ph, set()))
        for uid in wanted["user_id"]:
            candidate_indices.update(self.by_user_id.get(uid, set()))

        direct_hits: dict[tuple, tuple[EvidenceRecord, set[str]]] = {}
        grounded_resources: set[str] = set()

        for idx in candidate_indices:
            rec = self._records[idx]
            pathways = set(match_structured_fields(rec.fields, profile))
            pathways.update(match_unstructured_text(rec.text, profile))

            if pathways:
                key = (
                    rec.evidence_ref_type,
                    rec.evidence_id,
                    rec.source_path,
                    rec.locator,
                )
                direct_hits[key] = (rec, pathways)
                if rec.resource_id:
                    grounded_resources.add(rec.resource_id)
                grounded_resources.update(_extract_linked_resources(rec))

        # Phase 2: Bounded Fixed-Point Correlation
        visited_resources = set(grounded_resources)
        frontier = set(grounded_resources)
        safety_bound = 15
        step = 0
        resource_hits: dict[tuple, tuple[EvidenceRecord, set[str]]] = {}

        while frontier and step < safety_bound:
            step += 1
            next_frontier = set()

            for rid in sorted(frontier):
                for idx in self.by_resource_id.get(rid, set()):
                    rec = self._records[idx]
                    key = (
                        rec.evidence_ref_type,
                        rec.evidence_id,
                        rec.source_path,
                        rec.locator,
                    )

                    # Always record correlation pathway even if directly matched
                    if key not in resource_hits:
                        resource_hits[key] = (rec, set())
                    resource_hits[key][1].add(f"resource_link:{rid}")

                    # Check if this record explicitly links to secondary resource IDs
                    for linked_rid in _extract_linked_resources(rec):
                        if linked_rid and linked_rid not in visited_resources:
                            visited_resources.add(linked_rid)
                            next_frontier.add(linked_rid)

            frontier = next_frontier

        if frontier and step >= safety_bound:
            diagnostics.append(
                f"Correlation expansion safety bound ({safety_bound}) reached before convergence."
            )

        # Phase 3: Merging Hits and Deduplication
        final_hits = []
        all_keys = set(direct_hits.keys()).union(set(resource_hits.keys()))

        for key in all_keys:
            if key in direct_hits:
                rec, direct_paths = direct_hits[key]
                combined_paths = set(direct_paths)
                if key in resource_hits:
                    combined_paths.update(resource_hits[key][1])
                sorted_paths = tuple(sorted(combined_paths))
                reason = f"Direct identifier match via {','.join(sorted(direct_paths))}"
                if key in resource_hits:
                    reason += f"; correlated via {','.join(sorted(resource_hits[key][1]))}"
                final_hits.append(
                    EvidenceHit(
                        record=rec,
                        match_pathways=sorted_paths,
                        match_scope="DIRECT_IDENTIFIER",
                        reason=redact_pii(reason),
                    )
                )
            else:
                rec, res_paths = resource_hits[key]
                sorted_paths = tuple(sorted(res_paths))
                reason = f"Resource correlation via {','.join(sorted_paths)}"
                final_hits.append(
                    EvidenceHit(
                        record=rec,
                        match_pathways=sorted_paths,
                        match_scope="RESOURCE_LINK",
                        reason=redact_pii(reason),
                    )
                )

        # Stable Sort Order: (observed_at or "", evidence_ref_type, evidence_id, source_path, locator)
        sorted_hits = tuple(
            sorted(
                final_hits,
                key=lambda hit: (
                    hit.record.observed_at or "",
                    hit.record.evidence_ref_type,
                    hit.record.evidence_id,
                    hit.record.source_path,
                    hit.record.locator,
                ),
            )
        )

        return EvidenceQueryResult(
            user_id=profile.user_id,
            hits=sorted_hits,
            grounded_resource_ids=tuple(sorted(visited_resources)),
            diagnostics=tuple(sorted(set(diagnostics))),
        )

    @classmethod
    def from_dataset(cls, dataset_root: str | Path) -> "EvidenceIndex":
        root = Path(dataset_root).resolve()
        records: list[EvidenceRecord] = []
        diagnostics: list[str] = []

        manifest_path = root / "evidence_files.csv"
        activity_path = root / "system_activity.csv"
        audit_path = root / "user_audit_log.csv"

        seen_file_ids: set[str] = set()
        seen_file_paths: set[str] = set()
        file_outcomes: dict[str, dict[str, Any]] = {}

        # 1. Parse manifest and evidence files
        if not manifest_path.exists():
            diagnostics.append(f"Manifest missing at {manifest_path}")
        else:
            with open(manifest_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                manifest_rows = list(reader)

            for row in manifest_rows:
                fid = row.get("file_id", "").strip()
                rel_path = row.get("file_path", "").strip()
                origin = row.get("origin", "").strip()
                captured_at = row.get("captured_at", "").strip()

                if not fid or not rel_path:
                    diagnostics.append(f"Manifest row missing file_id or file_path: {row}")
                    continue

                if fid in seen_file_ids:
                    diagnostics.append(f"Duplicate manifest file_id: {fid}")
                seen_file_ids.add(fid)

                if rel_path in seen_file_paths:
                    diagnostics.append(f"Duplicate manifest file_path: {rel_path}")
                seen_file_paths.add(rel_path)

                # Safety check against path traversal
                try:
                    full_path = (root / rel_path).resolve()
                    full_path.relative_to(root)
                except ValueError:
                    diagnostics.append(f"Rejected path traversal: {rel_path}")
                    file_outcomes[fid] = {
                        "file_id": fid,
                        "file_path": rel_path,
                        "ext": Path(rel_path).suffix.lower(),
                        "status": "REJECTED_TRAVERSAL",
                        "record_count": 0,
                    }
                    continue

                if not full_path.exists():
                    diagnostics.append(f"Missing evidence file: {fid} at {rel_path}")
                    file_outcomes[fid] = {
                        "file_id": fid,
                        "file_path": rel_path,
                        "ext": full_path.suffix.lower(),
                        "status": "MISSING",
                        "record_count": 0,
                    }
                    continue

                ext = full_path.suffix.lower()
                count_before = len(records)
                err_occurred = False

                try:
                    if ext == ".sql":
                        cls._parse_sql(
                            full_path, fid, rel_path, origin, captured_at, records, diagnostics
                        )
                    elif ext == ".json":
                        cls._parse_json(
                            full_path, fid, rel_path, origin, captured_at, records, diagnostics
                        )
                    elif ext in (".log", ".txt"):
                        cls._parse_log_or_txt(
                            full_path, fid, rel_path, origin, captured_at, ext[1:], records, diagnostics
                        )
                    elif ext == ".pdf":
                        cls._parse_pdf(
                            full_path, fid, rel_path, origin, captured_at, records, diagnostics
                        )
                    elif ext == ".png":
                        cls._parse_png(
                            full_path, fid, rel_path, origin, captured_at, records, diagnostics
                        )
                    else:
                        diagnostics.append(f"Unsupported evidence file extension: {ext} for {fid}")
                        err_occurred = True
                        file_outcomes[fid] = {
                            "file_id": fid,
                            "file_path": rel_path,
                            "ext": ext,
                            "status": "UNSUPPORTED_EXTENSION",
                            "record_count": 0,
                        }
                        continue
                except Exception as exc:
                    diagnostics.append(f"Error parsing {fid} ({rel_path}): {exc}")
                    err_occurred = True

                records_added = len(records) - count_before
                if err_occurred:
                    file_outcomes[fid] = {
                        "file_id": fid,
                        "file_path": rel_path,
                        "ext": ext,
                        "status": "PARSE_ERROR",
                        "record_count": 0,
                    }
                elif records_added == 0:
                    if ext == ".sql":
                        diagnostics.append(
                            f"Valid SQL snapshot executed successfully but contains zero resource records: {fid} ({rel_path})"
                        )
                        file_outcomes[fid] = {
                            "file_id": fid,
                            "file_path": rel_path,
                            "ext": ext,
                            "status": "EMPTY_SNAPSHOT",
                            "record_count": 0,
                        }
                    elif ext == ".json":
                        diagnostics.append(
                            f"Valid JSON snapshot parsed successfully but contains zero resource records: {fid} ({rel_path})"
                        )
                        file_outcomes[fid] = {
                            "file_id": fid,
                            "file_path": rel_path,
                            "ext": ext,
                            "status": "EMPTY_SNAPSHOT",
                            "record_count": 0,
                        }
                    else:
                        diagnostics.append(f"Empty or unusable extraction from {fid} ({rel_path})")
                        file_outcomes[fid] = {
                            "file_id": fid,
                            "file_path": rel_path,
                            "ext": ext,
                            "status": "EMPTY_CONTENT",
                            "record_count": 0,
                        }
                else:
                    file_outcomes[fid] = {
                        "file_id": fid,
                        "file_path": rel_path,
                        "ext": ext,
                        "status": "SUCCESS",
                        "record_count": records_added,
                    }

        # Check for unlisted evidence files on disk under evidence directory
        evidence_dir = root / "evidence"
        if evidence_dir.exists():
            for p in sorted(evidence_dir.rglob("*")):
                if p.is_file():
                    try:
                        disk_rel = str(p.relative_to(root))
                    except ValueError:
                        continue
                    if disk_rel not in seen_file_paths:
                        diagnostics.append(f"Unlisted evidence file on disk: {disk_rel}")

        # 2. Parse system_activity.csv
        if activity_path.exists():
            try:
                cls._parse_system_activity(activity_path, records, diagnostics)
            except Exception as exc:
                diagnostics.append(f"Error parsing system_activity.csv: {exc}")
        else:
            diagnostics.append("Missing system_activity.csv")

        # 3. Parse user_audit_log.csv
        if audit_path.exists():
            try:
                cls._parse_user_audit_log(audit_path, records, diagnostics)
            except Exception as exc:
                diagnostics.append(f"Error parsing user_audit_log.csv: {exc}")
        else:
            diagnostics.append("Missing user_audit_log.csv")

        return cls(records=records, diagnostics=diagnostics, file_outcomes=file_outcomes)

    @classmethod
    def _parse_sql(
        cls,
        path: Path,
        file_id: str,
        rel_path: str,
        origin: str,
        captured_at: str,
        records: list[EvidenceRecord],
        diagnostics: list[str],
    ) -> None:
        sql_content = path.read_text(encoding="utf-8")
        conn = sqlite3.connect(":memory:")
        try:
            conn.executescript(sql_content)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            all_tables = [row[0] for row in cursor.fetchall()]

            # Inspect snapshot_scope metadata table if present
            snapshot_scope_map: dict[str, str] = {}
            if "snapshot_scope" in all_tables:
                cursor.execute('PRAGMA table_info("snapshot_scope")')
                ss_cols = [c[1] for c in cursor.fetchall()]
                cursor.execute('SELECT * FROM "snapshot_scope"')
                for ss_row in cursor.fetchall():
                    ss_dict = dict(zip(ss_cols, ss_row))
                    orig = str(ss_dict.get("origin_system", "")).strip()
                    cap = str(ss_dict.get("captured_at", "")).strip()
                    if orig and cap:
                        snapshot_scope_map[orig] = cap

            tables = [t for t in all_tables if t != "snapshot_scope"]

            for table in tables:
                cursor.execute(f'PRAGMA table_info("{table}")')
                cols = [c[1] for c in cursor.fetchall()]

                cursor.execute(f'SELECT rowid, * FROM "{table}"')
                rows = cursor.fetchall()

                for row_tuple in rows:
                    row_idx = row_tuple[0]
                    row_vals = row_tuple[1:]
                    row_dict = dict(zip(cols, row_vals))

                    fields_list = []
                    # Add base columns
                    for k, v in row_dict.items():
                        if k not in ("record_json", "metrics_json") and v is not None:
                            fields_list.append((k, v))

                    # Parse serialized record_json / metrics_json
                    json_timestamps: dict[str, str] = {}
                    for json_col in ("record_json", "metrics_json"):
                        if json_col in row_dict and row_dict[json_col]:
                            raw_j = str(row_dict[json_col])
                            try:
                                parsed = json.loads(raw_j)
                                if isinstance(parsed, dict):
                                    for fk, fv in cls._flatten_dict(parsed, prefix=json_col):
                                        fields_list.append((fk, fv))
                                        # Also retain leaf name
                                        leaf = fk.split(".")[-1]
                                        fields_list.append((leaf, fv))
                                        if leaf in ("updated_at", "created_at", "event_time", "timestamp"):
                                            json_timestamps[leaf] = str(fv).strip()
                            except Exception:
                                fields_list.append((json_col, raw_j))

                    resource_id = str(
                        row_dict.get("resource_id")
                        or row_dict.get("account_id")
                        or row_dict.get("customer_id")
                        or ""
                    )
                    system_id = str(row_dict.get("origin_system") or origin or table)
                    data_category = str(
                        row_dict.get("collection_name") or row_dict.get("category") or table
                    )

                    # Distinct timestamp semantics
                    row_updated_at = str(
                        row_dict.get("updated_at")
                        or json_timestamps.get("updated_at")
                        or ""
                    )
                    row_created_at = str(
                        row_dict.get("created_at")
                        or json_timestamps.get("created_at")
                        or ""
                    )
                    row_event_time = str(
                        row_dict.get("event_time")
                        or json_timestamps.get("event_time")
                        or json_timestamps.get("timestamp")
                        or ""
                    )
                    file_captured_at = snapshot_scope_map.get(system_id) or captured_at
                    observed_at = row_updated_at or row_event_time or row_created_at or file_captured_at

                    if file_captured_at:
                        fields_list.append(("captured_at", file_captured_at))
                    if row_updated_at:
                        fields_list.append(("record_updated_at", row_updated_at))
                    if row_created_at:
                        fields_list.append(("record_created_at", row_created_at))
                    if row_event_time:
                        fields_list.append(("event_time", row_event_time))

                    locator = f"table={table}:row={row_idx}:pk={resource_id or row_idx}"
                    text_repr = f"table={table} " + " ".join(
                        f"{k}={v}" for k, v in fields_list if v is not None
                    )

                    records.append(
                        EvidenceRecord(
                            evidence_id=file_id,
                            evidence_ref_type="file_id",
                            source_path=rel_path,
                            source_kind="sql",
                            locator=locator,
                            system_id=system_id,
                            resource_id=resource_id,
                            data_category=data_category,
                            observed_at=observed_at,
                            fields=_sort_fields(fields_list),
                            text=text_repr,
                            captured_at=file_captured_at,
                            event_time=row_event_time,
                            record_updated_at=row_updated_at,
                            record_created_at=row_created_at,
                        )
                    )
        finally:
            conn.close()

    @classmethod
    def _flatten_dict(cls, d: Mapping, prefix: str = "") -> list[tuple[str, Any]]:
        items = []
        for k, v in d.items():
            full_key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                items.extend(cls._flatten_dict(v, prefix=full_key))
            elif isinstance(v, list):
                for idx, elem in enumerate(v):
                    if isinstance(elem, dict):
                        items.extend(cls._flatten_dict(elem, prefix=f"{full_key}[{idx}]"))
                    else:
                        items.append((f"{full_key}[{idx}]", elem))
            else:
                items.append((full_key, v))
        return items

    @classmethod
    def _parse_json(
        cls,
        path: Path,
        file_id: str,
        rel_path: str,
        origin: str,
        captured_at: str,
        records: list[EvidenceRecord],
        diagnostics: list[str],
    ) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))

        def walk_json(node, current_path="$", parent_context=None):
            if parent_context is None:
                parent_context = {}

            if isinstance(node, dict):
                ctx = dict(parent_context)
                for k in (
                    "source",
                    "origin",
                    "system",
                    "exported_at",
                    "captured_at",
                    "snapshot_time",
                    "collection",
                    "region",
                ):
                    if k in node and isinstance(node[k], (str, int, float)):
                        ctx[k] = str(node[k])

                is_record = any(
                    k in node
                    for k in (
                        "resource_id",
                        "customer_reference",
                        "subject_reference",
                        "email",
                        "phone",
                        "email_hash",
                        "user_id",
                        "record_type",
                        "event_type",
                    )
                )

                if (
                    is_record
                    and "records" not in node
                    and "snapshots" not in node
                    and "service_exports" not in node
                ):
                    yield current_path, node, ctx
                    return

                for k, v in node.items():
                    child_ctx = dict(ctx)
                    if k in (
                        "account_service",
                        "analytics_platform",
                        "backup_service",
                        "export_service",
                        "integration_service",
                        "search_service",
                        "security_service",
                        "support_platform",
                    ):
                        child_ctx["system"] = k
                    yield from walk_json(v, f"{current_path}.{k}", child_ctx)

            elif isinstance(node, list):
                for idx, item in enumerate(node):
                    yield from walk_json(item, f"{current_path}[{idx}]", parent_context)

        for json_path, record_dict, ctx in walk_json(data):
            fields_list = []
            for fk, fv in cls._flatten_dict(record_dict):
                fields_list.append((fk, fv))
                leaf = fk.split(".")[-1]
                if leaf != fk:
                    fields_list.append((leaf, fv))

            # Add context fields
            for ck, cv in ctx.items():
                fields_list.append((f"context.{ck}", cv))

            resource_id = str(
                record_dict.get("resource_id")
                or record_dict.get("id")
                or record_dict.get("account_id")
                or ""
            )
            system_id = str(
                record_dict.get("system")
                or ctx.get("system")
                or ctx.get("source")
                or origin
            )
            data_category = str(
                record_dict.get("data_category")
                or record_dict.get("record_type")
                or ctx.get("collection")
                or ""
            )

            # Distinct timestamp semantics
            row_updated_at = str(record_dict.get("updated_at") or "")
            row_created_at = str(record_dict.get("created_at") or "")
            row_event_time = str(
                record_dict.get("timestamp")
                or record_dict.get("event_time")
                or record_dict.get("recorded_at")
                or ""
            )
            node_captured_at = str(
                ctx.get("captured_at")
                or ctx.get("exported_at")
                or ctx.get("snapshot_time")
                or captured_at
            )

            observed_at = (
                row_updated_at
                or row_event_time
                or str(record_dict.get("observed_at") or "")
                or row_created_at
                or node_captured_at
            )

            if node_captured_at:
                fields_list.append(("captured_at", node_captured_at))
            if row_updated_at:
                fields_list.append(("record_updated_at", row_updated_at))
            if row_created_at:
                fields_list.append(("record_created_at", row_created_at))
            if row_event_time:
                fields_list.append(("event_time", row_event_time))

            text_repr = json.dumps(record_dict, ensure_ascii=False)

            records.append(
                EvidenceRecord(
                    evidence_id=file_id,
                    evidence_ref_type="file_id",
                    source_path=rel_path,
                    source_kind="json",
                    locator=json_path,
                    system_id=system_id,
                    resource_id=resource_id,
                    data_category=data_category,
                    observed_at=observed_at,
                    fields=_sort_fields(fields_list),
                    text=text_repr,
                    captured_at=node_captured_at,
                    event_time=row_event_time,
                    record_updated_at=row_updated_at,
                    record_created_at=row_created_at,
                )
            )

    @classmethod
    def _parse_log_or_txt(
        cls,
        path: Path,
        file_id: str,
        rel_path: str,
        origin: str,
        captured_at: str,
        source_kind: str,
        records: list[EvidenceRecord],
        diagnostics: list[str],
    ) -> None:
        lines = path.read_text(encoding="utf-8").splitlines()

        # Pass 1: collect trace context across multi-line traces
        trace_context: dict[str, dict[str, str]] = defaultdict(dict)
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            kvs = dict(KV_RE.findall(line))
            tr_m = re.search(r"\b(tr-[a-zA-Z0-9_-]+)\b", line)
            t_id = tr_m.group(1) if tr_m else kvs.get("trace_id")
            if t_id:
                for k in (
                    "lookup_key",
                    "correlation_key",
                    "customer_reference",
                    "subject_reference",
                    "subject_ref",
                    "subject_key",
                    "match_key",
                    "matched_value",
                    "email",
                    "user_id",
                    "service",
                    "system",
                ):
                    if k in kvs and kvs[k].strip('"'):
                        trace_context[t_id][k] = kvs[k].strip('"')
                rids = RESOURCE_ID_RE.findall(line)
                if rids:
                    trace_context[t_id]["resource_id"] = rids[0]

        for line_no, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line:
                continue

            fields_list = []
            for k, v in KV_RE.findall(line):
                fields_list.append((k, v.strip('"')))

            # Extract resource ID if present
            rids = RESOURCE_ID_RE.findall(line)
            resource_id = rids[0] if rids else ""

            # Enrich from trace_id context if available
            tr_m = re.search(r"\b(tr-[a-zA-Z0-9_-]+)\b", line)
            t_id = tr_m.group(1) if tr_m else dict(fields_list).get("trace_id")
            if t_id and t_id in trace_context:
                ctx = trace_context[t_id]
                for k, v in ctx.items():
                    if k not in dict(fields_list):
                        fields_list.append((k, v))
                if not resource_id and "resource_id" in ctx:
                    resource_id = ctx["resource_id"]

            if resource_id:
                fields_list.append(("resource_id", resource_id))

            # Extract timestamps
            ts_matches = re.findall(
                r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b", line
            )
            event_time = ts_matches[0] if ts_matches else ""
            observed_at = event_time if event_time else captured_at

            if captured_at:
                fields_list.append(("captured_at", captured_at))
            if event_time:
                fields_list.append(("event_time", event_time))

            records.append(
                EvidenceRecord(
                    evidence_id=file_id,
                    evidence_ref_type="file_id",
                    source_path=rel_path,
                    source_kind=source_kind,
                    locator=f"line:{line_no}",
                    system_id=origin,
                    resource_id=resource_id,
                    data_category=origin,
                    observed_at=observed_at,
                    fields=_sort_fields(fields_list),
                    text=line,
                    captured_at=captured_at,
                    event_time=event_time,
                )
            )

    @classmethod
    def _parse_pdf(
        cls,
        path: Path,
        file_id: str,
        rel_path: str,
        origin: str,
        captured_at: str,
        records: list[EvidenceRecord],
        diagnostics: list[str],
    ) -> None:
        if fitz is None and pdfplumber is None:
            diagnostics.append(f"Neither PyMuPDF/fitz nor pdfplumber available; cannot parse PDF {file_id}")
            return

        text_lines_found = 0
        tables_found = 0

        doc_rids = []
        # 1. Digital text stream lines using PyMuPDF (fitz)
        if fitz is not None:
            try:
                doc = fitz.open(path)
                try:
                    full_doc_text = "\n".join(page.get_text() or "" for page in doc)
                    for m in RESOURCE_ID_RE.findall(full_doc_text):
                        if not m.startswith("user_") and m not in doc_rids:
                            doc_rids.append(m)

                    for page_idx, page in enumerate(doc, start=1):
                        text = page.get_text() or ""
                        lines = text.splitlines()
                        for line_no, raw_line in enumerate(lines, start=1):
                            line = raw_line.strip()
                            if not line:
                                continue
                            text_lines_found += 1

                            fields_list = []
                            for k, v in KV_RE.findall(line):
                                fields_list.append((k, v.strip('"')))
                            rids = RESOURCE_ID_RE.findall(line)
                            resource_id = rids[0] if rids else (doc_rids[0] if doc_rids else "")
                            if resource_id:
                                fields_list.append(("resource_id", resource_id))

                            ts_matches = re.findall(
                                r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b", line
                            )
                            event_time = ts_matches[0] if ts_matches else ""
                            observed_at = event_time if event_time else captured_at

                            if captured_at:
                                fields_list.append(("captured_at", captured_at))
                            if event_time:
                                fields_list.append(("event_time", event_time))

                            records.append(
                                EvidenceRecord(
                                    evidence_id=file_id,
                                    evidence_ref_type="file_id",
                                    source_path=rel_path,
                                    source_kind="pdf",
                                    locator=f"page:{page_idx}:line:{line_no}",
                                    system_id=origin,
                                    resource_id=resource_id,
                                    data_category="DOCUMENT",
                                    observed_at=observed_at,
                                    fields=_sort_fields(fields_list),
                                    text=line,
                                    captured_at=captured_at,
                                    event_time=event_time,
                                )
                            )
                finally:
                    doc.close()
            except Exception as exc:
                diagnostics.append(f"Error in PyMuPDF text stream extraction for {file_id}: {exc}")

        # 2. Structured table extraction using pdfplumber
        if pdfplumber is not None:
            try:
                with pdfplumber.open(path) as pl_pdf:
                    for page_idx, pl_page in enumerate(pl_pdf.pages, start=1):
                        tables = pl_page.extract_tables() or []
                        for table_idx, tbl in enumerate(tables, start=1):
                            tables_found += 1
                            for row_idx, row in enumerate(tbl, start=1):
                                if not row:
                                    continue
                                row_cells = [str(c or "").strip() for c in row if c is not None]
                                row_text = " | ".join(row_cells).strip()
                                if not row_text:
                                    continue

                                fields_list = []
                                # If two cells like ['Detail', 'user_18'] or ['Record', 'Customer ...']
                                if len(row) == 2:
                                    k_cell, v_cell = str(row[0] or "").strip(), str(row[1] or "").strip()
                                    if k_cell and v_cell:
                                        fields_list.append((k_cell, v_cell))
                                else:
                                    for c_idx, cell_val in enumerate(row_cells, start=1):
                                        fields_list.append((f"col_{c_idx}", cell_val))

                                # Extract identifiers from table cells
                                for cell in row_cells:
                                    for em in EMAIL_TOKEN_RE.findall(cell):
                                        fields_list.append(("email", em))
                                    for h in HASH_TOKEN_RE.findall(cell):
                                        fields_list.append(("email_hash", h))
                                    for uid in re.findall(r"\b(user_[0-9]+)\b", cell):
                                        fields_list.append(("user_id", uid))
                                    for rid in RESOURCE_ID_RE.findall(cell):
                                        if not rid.startswith("user_"):
                                            fields_list.append(("resource_id", rid))

                                rids = [v for k, v in fields_list if k == "resource_id"]
                                resource_id = rids[0] if rids else (doc_rids[0] if doc_rids else "")
                                if resource_id and ("resource_id", resource_id) not in fields_list:
                                    fields_list.append(("resource_id", resource_id))

                                ts_matches = re.findall(
                                    r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b", row_text
                                )
                                event_time = ts_matches[0] if ts_matches else ""
                                observed_at = event_time if event_time else captured_at

                                if captured_at:
                                    fields_list.append(("captured_at", captured_at))
                                if event_time:
                                    fields_list.append(("event_time", event_time))

                                records.append(
                                    EvidenceRecord(
                                        evidence_id=file_id,
                                        evidence_ref_type="file_id",
                                        source_path=rel_path,
                                        source_kind="pdf",
                                        locator=f"page:{page_idx}:table:{table_idx}:row:{row_idx}",
                                        system_id=origin,
                                        resource_id=resource_id,
                                        data_category="DOCUMENT_TABLE",
                                        observed_at=observed_at,
                                        fields=_sort_fields(fields_list),
                                        text=row_text,
                                        captured_at=captured_at,
                                        event_time=event_time,
                                    )
                                )
            except Exception as exc:
                diagnostics.append(f"Error in pdfplumber table extraction for {file_id}: {exc}")

        if text_lines_found == 0 and tables_found == 0:
            diagnostics.append(f"PDF {file_id} ({rel_path}) has no extractable text or tables")

    @classmethod
    def _parse_png(
        cls,
        path: Path,
        file_id: str,
        rel_path: str,
        origin: str,
        captured_at: str,
        records: list[EvidenceRecord],
        diagnostics: list[str],
    ) -> None:
        if Image is None or pytesseract is None:
            diagnostics.append(f"PIL/pytesseract not available; cannot OCR PNG {file_id}")
            return

        with Image.open(path) as img:
            ocr_text = pytesseract.image_to_string(img) or ""

        for line_no, raw_line in enumerate(ocr_text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue

            fields_list = []
            for k, v in KV_RE.findall(line):
                fields_list.append((k, v.strip('"')))
            rids = RESOURCE_ID_RE.findall(line)
            resource_id = rids[0] if rids else ""
            if resource_id:
                fields_list.append(("resource_id", resource_id))

            ts_matches = re.findall(
                r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b", line
            )
            event_time = ts_matches[0] if ts_matches else ""
            observed_at = event_time if event_time else captured_at

            if captured_at:
                fields_list.append(("captured_at", captured_at))
            if event_time:
                fields_list.append(("event_time", event_time))

            records.append(
                EvidenceRecord(
                    evidence_id=file_id,
                    evidence_ref_type="file_id",
                    source_path=rel_path,
                    source_kind="png",
                    locator=f"ocr_line:{line_no}",
                    system_id=origin,
                    resource_id=resource_id,
                    data_category="SCREENSHOT",
                    observed_at=observed_at,
                    fields=_sort_fields(fields_list),
                    text=line,
                    captured_at=captured_at,
                    event_time=event_time,
                )
            )

    @classmethod
    def _parse_system_activity(
        cls,
        path: Path,
        records: list[EvidenceRecord],
        diagnostics: list[str],
    ) -> None:
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader, start=1):
                act_id = row.get("activity_id", "").strip()
                event_time = row.get("event_time", "").strip()
                event_type = row.get("event_type", "").strip()
                src_sys = row.get("source_system", "").strip()
                tgt_sys = row.get("target_system", "").strip()
                resource_id = row.get("resource_id", "").strip()
                result = row.get("reported_result", "").strip()
                details = row.get("details", "").strip()

                fields_list = [
                    ("activity_id", act_id),
                    ("event_type", event_type),
                    ("source_system", src_sys),
                    ("target_system", tgt_sys),
                    ("resource_id", resource_id),
                    ("reported_result", result),
                ]

                # Extract explicit key-values from details
                for k, v in KV_RE.findall(details):
                    fields_list.append((k, v.strip('"')))

                # Extract emails, hashes, user_ids, and resource links from details
                for em in EMAIL_TOKEN_RE.findall(details):
                    fields_list.append(("email", em))
                for h in HASH_TOKEN_RE.findall(details):
                    fields_list.append(("email_hash", h))
                for uid in re.findall(r"\b(user_[0-9]+)\b", details):
                    fields_list.append(("user_id", uid))

                # Extract downstream / upstream resource links
                for pat in RELATION_PATTERNS:
                    for match in pat.findall(details):
                        if isinstance(match, tuple):
                            for m in match:
                                if m and m != resource_id:
                                    fields_list.append(("linked_resource_id", m))
                        elif match and match != resource_id:
                            fields_list.append(("linked_resource_id", match))

                system_id = src_sys or tgt_sys or "system_activity"
                locator = f"row:{row_idx}:activity_id={act_id}"
                text_repr = f"{act_id} {event_type} {resource_id} {details}"

                if event_time:
                    fields_list.append(("event_time", event_time))

                records.append(
                    EvidenceRecord(
                        evidence_id=act_id,
                        evidence_ref_type="activity_id",
                        source_path="system_activity.csv",
                        source_kind="activity",
                        locator=locator,
                        system_id=system_id,
                        resource_id=resource_id,
                        data_category=event_type,
                        observed_at=event_time,
                        fields=_sort_fields(fields_list),
                        text=text_repr,
                        captured_at="",
                        event_time=event_time,
                    )
                )

    @classmethod
    def _parse_user_audit_log(
        cls,
        path: Path,
        records: list[EvidenceRecord],
        diagnostics: list[str],
    ) -> None:
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader, start=1):
                audit_id = row.get("audit_id", "").strip()
                uid = row.get("user_id", "").strip()
                event_time = row.get("event_time", "").strip()
                field_name = row.get("field_name", "").strip()
                old_val = row.get("old_value", "").strip()
                new_val = row.get("new_value", "").strip()

                fields_list = [
                    ("audit_id", audit_id),
                    ("user_id", uid),
                    ("field_name", field_name),
                ]

                # Map old_value and new_value based on field_name
                if field_name == "email":
                    if old_val:
                        fields_list.append(("old_email", old_val))
                        fields_list.append(("email", old_val))
                    if new_val:
                        fields_list.append(("new_email", new_val))
                        fields_list.append(("email", new_val))
                elif field_name == "email_hash":
                    if old_val:
                        fields_list.append(("old_email_hash", old_val))
                        fields_list.append(("email_hash", old_val))
                    if new_val:
                        fields_list.append(("new_email_hash", new_val))
                        fields_list.append(("email_hash", new_val))
                elif field_name == "phone":
                    if old_val:
                        fields_list.append(("old_phone", old_val))
                        fields_list.append(("phone", old_val))
                    if new_val:
                        fields_list.append(("new_phone", new_val))
                        fields_list.append(("phone", new_val))
                else:
                    if old_val:
                        fields_list.append((f"old_{field_name}", old_val))
                    if new_val:
                        fields_list.append((f"new_{field_name}", new_val))

                locator = f"row:{row_idx}:audit_id={audit_id}"
                text_repr = f"{audit_id} {uid} {field_name}: {old_val} -> {new_val}"

                if event_time:
                    fields_list.append(("event_time", event_time))

                records.append(
                    EvidenceRecord(
                        evidence_id=audit_id,
                        evidence_ref_type="audit_id",
                        source_path="user_audit_log.csv",
                        source_kind="audit",
                        locator=locator,
                        system_id="identity_service",
                        resource_id="",
                        data_category="IDENTITY",
                        observed_at=event_time,
                        fields=_sort_fields(fields_list),
                        text=text_repr,
                        captured_at="",
                        event_time=event_time,
                    )
                )
