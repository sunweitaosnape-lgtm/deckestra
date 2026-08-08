from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import certification_gate as gate


def digest(label: str) -> str:
    return gate.sha256_bytes(label.encode("utf-8"))


def small_policy() -> dict:
    policy = copy.deepcopy(gate.OFFICIAL_POLICY)
    policy["profile"]["id"] = "synthetic-two-page-v1"
    policy["profile"]["page_count"] = 2
    policy["suite"]["case_count"] = 2
    policy["suite"]["minimum_whole_deck_passes"] = 2
    return policy


def passing_evidence(policy: dict) -> dict:
    criteria = policy["review"]["criteria"]
    reviewers = [
        {"id": "R001", "independence_attestation_sha256": digest("attestation-1")},
        {"id": "R002", "independence_attestation_sha256": digest("attestation-2")},
    ]
    cases = []
    for case_index in range(1, policy["suite"]["case_count"] + 1):
        case_id = f"C{case_index:04d}"
        pages = []
        for page_index in range(1, policy["profile"]["page_count"] + 1):
            page_id = f"P{page_index:02d}"
            render_hash = digest(f"{case_id}-{page_id}-render")
            reviews = []
            for reviewer in reviewers:
                reviewer_id = reviewer["id"]
                reviews.append(
                    {
                        "reviewer_id": reviewer_id,
                        "independent": True,
                        "render_sha256": render_hash,
                        "criteria": {criterion: True for criterion in criteria},
                        "verdict": "pass",
                        "receipt_sha256": digest(f"{case_id}-{page_id}-{reviewer_id}"),
                    }
                )
            pages.append(
                {
                    "id": page_id,
                    "state": "rendered",
                    "render_sha256": render_hash,
                    "reviews": reviews,
                }
            )
        cases.append(
            {
                "id": case_id,
                "input_sha256": digest(f"{case_id}-input"),
                "constraints_sha256": digest(f"{case_id}-constraints"),
                "generation": {
                    "status": "passed",
                    "generator_id": "G001",
                    "manual_fallback": False,
                    "page_count": policy["profile"]["page_count"],
                    "repair_budget": policy["profile"]["repair_budget"],
                    "layout_trace_status": "passed",
                    "svg_quality_errors": 0,
                    "svg_quality_warnings": 0,
                    "required_native_objects": 2,
                    "present_native_objects": 2,
                    "postflight_status": "passed",
                    "ir_sha256": digest(f"{case_id}-ir"),
                    "layout_trace_sha256": digest(f"{case_id}-trace"),
                    "pptx_sha256": digest(f"{case_id}-pptx"),
                    "postflight_sha256": digest(f"{case_id}-postflight"),
                    "run_receipt_sha256": digest(f"{case_id}-receipt"),
                },
                "pages": pages,
            }
        )
    case_ids = [case["id"] for case in cases]
    return {
        "schema": gate.EVIDENCE_SCHEMA,
        "policy_sha256": gate.canonical_sha256(policy),
        "suite": {
            "profile": policy["profile"]["id"],
            "frozen": True,
            "frozen_at": "2026-01-01T00:00:00Z",
            "case_count": policy["suite"]["case_count"],
            "case_ids_sha256": gate.canonical_sha256(case_ids),
            "suite_sha256": gate.suite_hash(cases),
        },
        "runtime": {
            "skill_tree_sha256": gate.skill_tree_sha256(ROOT),
            "evaluated_commit": "a" * 40,
            "model_id": "synthetic-model-v1",
            "host_version": "synthetic-host-v1",
            "python_version": "3.12.0",
            "os_id": "synthetic-linux",
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "dependency_lock_sha256": gate.dependency_lock_sha256(ROOT),
            "font_bundle_sha256": digest("synthetic-font-bundle"),
        },
        "reviewers": reviewers,
        "cases": cases,
    }


class CertificationGateTests(unittest.TestCase):
    def test_committed_policy_is_exact_official_target(self) -> None:
        policy = gate.load_policy(ROOT)
        self.assertEqual(gate.validate_official_policy(policy), [])

    def test_complete_hash_only_evidence_passes(self) -> None:
        policy = small_policy()
        evidence = passing_evidence(policy)
        issues, summary = gate.evaluate_evidence(policy, evidence, ROOT)
        self.assertEqual(issues, [])
        self.assertTrue(summary["certified"])
        self.assertEqual(summary["whole_deck_passes"], 2)
        self.assertEqual(summary["reviewed_pages"], 4)

    def test_one_failed_page_fails_whole_deck_threshold(self) -> None:
        policy = small_policy()
        evidence = passing_evidence(policy)
        review = evidence["cases"][0]["pages"][0]["reviews"][0]
        review["criteria"]["content_fidelity"] = False
        review["verdict"] = "fail"
        issues, summary = gate.evaluate_evidence(policy, evidence, ROOT)
        self.assertEqual(issues, ["certification-threshold-not-met"])
        self.assertFalse(summary["certified"])
        self.assertEqual(summary["whole_deck_passes"], 1)

    def test_extra_evidence_field_is_rejected_as_leak_risk(self) -> None:
        policy = small_policy()
        evidence = passing_evidence(policy)
        evidence["cases"][0]["pages"][0]["reviews"][0]["raw_comment"] = "not allowed"
        issues, summary = gate.evaluate_evidence(policy, evidence, ROOT)
        self.assertIn("field-set-mismatch:cases[0].pages[0].reviews[0]", issues)
        self.assertFalse(summary["certified"])

    def test_evidence_inside_repository_is_rejected_before_read(self) -> None:
        with self.assertRaises(gate.CertificationError):
            gate.require_external_evidence(ROOT, ROOT / "certification" / "evidence.json")


if __name__ == "__main__":
    unittest.main()
