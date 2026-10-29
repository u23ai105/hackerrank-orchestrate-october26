#!/usr/bin/env python3
"""
Stage 6 Evaluation Script: Evaluate Case Audit Engine against the 32 sample cases.
Measures status accuracy, step-level precision/recall/F1, field accuracy,
and sequence matches against dataset/sample_output.csv.
Generates code/docs/audit_engine_evaluation.md.
"""

from __future__ import annotations

import csv
import json
import time
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "dataset"
DOCS = ROOT / "code" / "docs"

from tools.audit_engine import build_audit_engine, sort_and_number_steps


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_steps(row: dict[str, Any]) -> list[dict[str, Any]]:
    value = row.get("steps_json", "[]")
    steps = json.loads(value) if isinstance(value, str) else value
    if not isinstance(steps, list):
        raise ValueError(f"steps_json must be a list for case {row.get('case_id')}")
    return steps


def step_signature(step: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(step.get(k, "") or "")
        for k in (
            "phase",
            "system_id",
            "resource_id",
            "operation",
            "state",
            "evidence_id",
        )
    )


def prf(expected_signatures, predicted_signatures):
    expected = Counter(expected_signatures)
    predicted = Counter(predicted_signatures)
    tp = sum((expected & predicted).values())
    fp = sum((predicted - expected).values())
    fn = sum((expected - predicted).values())
    precision = tp / (tp + fp) if tp + fp else (1.0 if not fn else 0.0)
    recall = tp / (tp + fn) if tp + fn else (1.0 if not fp else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def measure_sample(expected_rows, predicted_rows):
    exp = {str(r["case_id"]): r for r in expected_rows}
    pred = {str(r["case_id"]): r for r in predicted_rows}
    common = sorted(set(exp) & set(pred))
    if set(exp) != set(pred):
        raise ValueError(
            f"Sample case sets differ; expected_only={len(set(exp)-set(pred))}, "
            f"predicted_only={len(set(pred)-set(exp))}"
        )

    status_correct = sum(
        exp[c]["deletion_status"] == pred[c]["deletion_status"] for c in common
    )
    expected_steps = {c: parse_steps(exp[c]) for c in common}
    predicted_steps = {c: parse_steps(pred[c]) for c in common}

    expected_flat, predicted_flat = [], []
    full_sequence = 0
    sequence_similarity = []
    field_counts = Counter()
    field_total = 0
    fields = (
        "phase",
        "system_id",
        "resource_id",
        "operation",
        "state",
        "evidence_id",
    )

    for case_id in common:
        es, ps = expected_steps[case_id], predicted_steps[case_id]
        e_sig = [step_signature(x) for x in es]
        p_sig = [step_signature(x) for x in ps]
        expected_flat.extend(e_sig)
        predicted_flat.extend(p_sig)
        full_sequence += int(e_sig == p_sig)
        sequence_similarity.append(
            SequenceMatcher(a=e_sig, b=p_sig, autojunk=False).ratio()
        )

        for i in range(max(len(es), len(ps))):
            e = es[i] if i < len(es) else {}
            p = ps[i] if i < len(ps) else {}
            for field in fields:
                field_total += 1
                field_counts["correct"] += int(
                    i < len(es)
                    and i < len(ps)
                    and str(e.get(field, "") or "")
                    == str(p.get(field, "") or "")
                )

    return {
        "n_cases": len(common),
        "status_correct": status_correct,
        "status_accuracy": status_correct / len(common) if common else 0.0,
        "step_metrics": prf(expected_flat, predicted_flat),
        "field_accuracy": field_counts["correct"] / field_total
        if field_total
        else 0.0,
        "field_correct": field_counts["correct"],
        "field_total": field_total,
        "sequence_exact": full_sequence / len(common) if common else 0.0,
        "sequence_correct": full_sequence,
        "mean_sequence_similarity": sum(sequence_similarity)
        / len(sequence_similarity)
        if sequence_similarity
        else 0.0,
    }


def main():
    started = time.perf_counter()
    print("Building AuditEngine...")
    engine = build_audit_engine(dataset_root=DATASET)

    sample_requests = read_csv(DATASET / "sample_deletion_requests.csv")
    sample_labels = read_csv(DATASET / "sample_output.csv")

    print(f"Auditing {len(sample_requests)} sample cases...")
    predicted = []
    case_diagnostics = []

    for req in sample_requests:
        cid = req["case_id"]
        res = engine.audit_case(req)
        predicted.append({
            "case_id": cid,
            "deletion_status": res.deletion_status,
            "steps_json": json.dumps(res.steps, ensure_ascii=False, separators=(",", ":")),
        })
        case_diagnostics.append((cid, res.deletion_status, len(res.steps), res.blockers))

    metrics = measure_sample(sample_labels, predicted)
    elapsed = time.perf_counter() - started

    # Generate Markdown documentation
    doc_lines = [
        "# Stage 6 Evaluation: Case Audit Engine and Step Builder",
        "",
        "## Summary Metrics on 32 Public Sample Cases",
        f"- **Cases Evaluated**: {metrics['n_cases']}",
        f"- **Status Accuracy**: {metrics['status_accuracy']:.2%} ({metrics['status_correct']}/{metrics['n_cases']})",
        f"- **Step Precision**: {metrics['step_metrics']['precision']:.2%}",
        f"- **Step Recall**: {metrics['step_metrics']['recall']:.2%}",
        f"- **Step F1**: {metrics['step_metrics']['f1']:.2%}",
        f"- **Field Accuracy**: {metrics['field_accuracy']:.2%} ({metrics['field_correct']}/{metrics['field_total']})",
        f"- **Exact Sequence Match**: {metrics['sequence_exact']:.2%} ({metrics['sequence_correct']}/{metrics['n_cases']})",
        f"- **Mean Sequence Similarity**: {metrics['mean_sequence_similarity']:.2%}",
        f"- **Elapsed Time**: {elapsed:.2f}s",
        "",
        "## Per-Case Breakdown",
        "| Case ID | Predicted Status | Steps Count | Blockers |",
        "|---|---|---|---|",
    ]
    for cid, status, step_count, blockers in case_diagnostics:
        blockers_str = ", ".join(blockers) if blockers else "None"
        doc_lines.append(f"| {cid} | {status} | {step_count} | {blockers_str} |")

    doc_content = "\n".join(doc_lines) + "\n"
    DOCS.mkdir(parents=True, exist_ok=True)
    report_path = DOCS / "audit_engine_evaluation.md"
    report_path.write_text(doc_content, encoding="utf-8")
    print(f"Report written to {report_path}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
