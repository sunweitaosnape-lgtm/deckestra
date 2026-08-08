#!/usr/bin/env python3
"""Validate external hash-only evidence for Deckestra's frozen blind target."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any


POLICY_SCHEMA = "deckestra-certification-policy/v1"
EVIDENCE_SCHEMA = "deckestra-certification-evidence/v1"
SUMMARY_SCHEMA = "deckestra-certification-summary/v1"
MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40,64}\Z")
CASE_RE = re.compile(r"C[0-9]{4}\Z")
PAGE_RE = re.compile(r"P[0-9]{2}\Z")
REVIEWER_RE = re.compile(r"R[0-9]{3,6}\Z")
GENERATOR_RE = re.compile(r"G[0-9]{3,6}\Z")
SAFE_RUNTIME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/+:-]{0,119}\Z")
RFC3339_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
IGNORED_DIRECTORIES = frozenset(
    {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__", "node_modules"}
)

OFFICIAL_POLICY: dict[str, Any] = {
    "schema": POLICY_SCHEMA,
    "policy_id": "whole-deck-blind-v1",
    "claim_status": "target-only",
    "profile": {
        "id": "zh-cn-tech-brief-15-v1",
        "language": "zh-CN",
        "deck_type": "technical-brief",
        "page_count": 15,
        "authoring_lane": "deterministic",
        "repair_budget": 2,
    },
    "suite": {
        "case_count": 1000,
        "minimum_whole_deck_passes": 997,
        "blind": True,
        "frozen_before_execution": True,
        "private_cases": "external-only",
        "manual_fallback_allowed": False,
    },
    "review": {
        "render_reviewers_per_page": 2,
        "reviewer_must_be_independent": True,
        "reviewers_must_differ_from_generator": True,
        "all_pages_reviewed": True,
        "criteria": [
            "content_fidelity",
            "information_completeness",
            "narrative_coherence",
            "chinese_language_quality",
            "no_overlap_or_clipping",
            "readable_hierarchy",
            "visual_consistency",
            "native_editability",
        ],
        "page_pass": "all-criteria-pass-in-both-independent-reviews",
        "deck_pass": "automated-gates-pass-and-every-page-passes",
    },
    "publication": {
        "raw_cases": "forbidden",
        "rendered_pages": "forbidden",
        "review_comments": "forbidden",
        "runtime_logs": "forbidden",
        "public_evidence": "hashes-and-aggregate-counts-only",
        "claim_requires_gate_pass": True,
    },
}


class CertificationError(RuntimeError):
    """Raised when certification inputs cross a safety boundary."""


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def validate_official_policy(policy: Any) -> list[str]:
    if policy != OFFICIAL_POLICY:
        return ["official-policy-mismatch"]
    return []


def load_policy(root: Path) -> dict[str, Any]:
    path = root / "certification" / "policy.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CertificationError("certification policy is missing or invalid") from exc
    if not isinstance(payload, dict):
        raise CertificationError("certification policy must be an object")
    return payload


def require_external_evidence(root: Path, path: Path) -> tuple[Path, bytes]:
    if not path.is_absolute():
        raise CertificationError("--evidence must be an absolute external path")
    if path.is_symlink():
        raise CertificationError("evidence must be a regular file, not a symbolic link")
    resolved = path.resolve()
    root = root.resolve()
    if resolved == root or root in resolved.parents:
        raise CertificationError("certification evidence must remain outside the repository")
    try:
        info = resolved.stat()
    except OSError as exc:
        raise CertificationError("evidence file is unavailable") from exc
    if not stat.S_ISREG(info.st_mode):
        raise CertificationError("evidence must be a regular file")
    if info.st_size > MAX_EVIDENCE_BYTES:
        raise CertificationError("evidence exceeds the 64 MiB safety limit")
    data = resolved.read_bytes()
    if b"\x00" in data:
        raise CertificationError("evidence contains binary data")
    return resolved, data


def skill_tree_sha256(root: Path) -> str:
    skill = root / "skills" / "build-editable-decks"
    rows: list[tuple[str, str]] = []
    for current, directories, files in os.walk(skill, topdown=True, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in IGNORED_DIRECTORIES)
        current_path = Path(current)
        for name in sorted(files):
            path = current_path / name
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise CertificationError("Skill tree contains a non-regular entry")
            relative = path.relative_to(skill).as_posix()
            rows.append((relative, sha256_bytes(path.read_bytes())))
    if not rows:
        raise CertificationError("Skill tree is empty")
    payload = "".join(f"{path}\0{digest}\n" for path, digest in rows).encode("utf-8")
    return sha256_bytes(payload)


def dependency_lock_sha256(root: Path) -> str:
    paths = (
        "skills/build-editable-decks/requirements-core.txt",
        "skills/build-editable-decks/requirements-maintainer.txt",
    )
    rows: list[str] = []
    for relative in paths:
        path = root / relative
        if not path.is_file():
            raise CertificationError("dependency lock is incomplete")
        rows.append(f"{relative}\0{sha256_bytes(path.read_bytes())}\n")
    return sha256_bytes("".join(rows).encode("utf-8"))


def expected_ids(prefix: str, count: int, width: int) -> list[str]:
    return [f"{prefix}{index:0{width}d}" for index in range(1, count + 1)]


def suite_hash(cases: list[dict[str, Any]]) -> str:
    rows = [
        [case.get("id"), case.get("input_sha256"), case.get("constraints_sha256")]
        for case in cases
    ]
    return canonical_sha256(rows)


def _object(value: Any, context: str, issues: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        issues.append(f"expected-object:{context}")
        return None
    return value


def _array(value: Any, context: str, issues: list[str]) -> list[Any] | None:
    if not isinstance(value, list):
        issues.append(f"expected-array:{context}")
        return None
    return value


def _keys(value: dict[str, Any], expected: set[str], context: str, issues: list[str]) -> bool:
    if set(value) != expected:
        issues.append(f"field-set-mismatch:{context}")
        return False
    return True


def _hash(value: Any, context: str, issues: list[str], *, nullable: bool = False) -> bool:
    if nullable and value is None:
        return True
    valid = isinstance(value, str) and HASH_RE.fullmatch(value) is not None
    if not valid:
        issues.append(f"invalid-hash:{context}")
    return valid


def _safe_token(value: Any, pattern: re.Pattern[str], context: str, issues: list[str]) -> bool:
    valid = isinstance(value, str) and pattern.fullmatch(value) is not None
    if not valid:
        issues.append(f"invalid-token:{context}")
    return valid


def _bounded_int(value: Any, minimum: int, maximum: int, context: str, issues: list[str]) -> bool:
    valid = isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum
    if not valid:
        issues.append(f"invalid-integer:{context}")
    return valid


def _boolean(value: Any, context: str, issues: list[str]) -> bool:
    if not isinstance(value, bool):
        issues.append(f"invalid-boolean:{context}")
        return False
    return True


def evaluate_evidence(
    policy: dict[str, Any],
    evidence: Any,
    root: Path,
    *,
    evidence_bytes: bytes | None = None,
) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    evidence_obj = _object(evidence, "root", issues)
    if evidence_obj is None:
        return issues, {"certified": False}
    _keys(
        evidence_obj,
        {"schema", "policy_sha256", "suite", "runtime", "reviewers", "cases"},
        "root",
        issues,
    )
    if evidence_obj.get("schema") != EVIDENCE_SCHEMA:
        issues.append("unsupported-evidence-schema:root")
    if evidence_obj.get("policy_sha256") != canonical_sha256(policy):
        issues.append("policy-hash-mismatch:root")

    profile = policy["profile"]
    suite_policy = policy["suite"]
    review_policy = policy["review"]
    case_count = suite_policy["case_count"]
    page_count = profile["page_count"]
    reviewer_count = review_policy["render_reviewers_per_page"]
    criteria = review_policy["criteria"]

    suite = _object(evidence_obj.get("suite"), "suite", issues)
    if suite is not None:
        _keys(
            suite,
            {"profile", "frozen", "frozen_at", "case_count", "case_ids_sha256", "suite_sha256"},
            "suite",
            issues,
        )
        if suite.get("profile") != profile["id"]:
            issues.append("profile-mismatch:suite")
        if suite.get("frozen") is not True:
            issues.append("suite-not-frozen:suite")
        if not isinstance(suite.get("frozen_at"), str) or not RFC3339_RE.fullmatch(suite["frozen_at"]):
            issues.append("invalid-timestamp:suite.frozen_at")
        if suite.get("case_count") != case_count:
            issues.append("case-count-mismatch:suite")
        _hash(suite.get("case_ids_sha256"), "suite.case_ids_sha256", issues)
        _hash(suite.get("suite_sha256"), "suite.suite_sha256", issues)

    runtime = _object(evidence_obj.get("runtime"), "runtime", issues)
    runtime_skill_hash = ""
    runtime_dependency_hash = ""
    if runtime is not None:
        _keys(
            runtime,
            {
                "skill_tree_sha256",
                "evaluated_commit",
                "model_id",
                "host_version",
                "python_version",
                "os_id",
                "locale",
                "timezone",
                "dependency_lock_sha256",
                "font_bundle_sha256",
            },
            "runtime",
            issues,
        )
        for field in ("skill_tree_sha256", "dependency_lock_sha256", "font_bundle_sha256"):
            _hash(runtime.get(field), f"runtime.{field}", issues)
        runtime_skill_hash = runtime.get("skill_tree_sha256", "")
        runtime_dependency_hash = runtime.get("dependency_lock_sha256", "")
        if not isinstance(runtime.get("evaluated_commit"), str) or not COMMIT_RE.fullmatch(
            runtime["evaluated_commit"]
        ):
            issues.append("invalid-commit:runtime.evaluated_commit")
        for field in ("model_id", "host_version", "python_version", "os_id", "locale", "timezone"):
            _safe_token(runtime.get(field), SAFE_RUNTIME_RE, f"runtime.{field}", issues)
        try:
            current_skill_hash = skill_tree_sha256(root)
            current_dependency_hash = dependency_lock_sha256(root)
        except CertificationError as exc:
            issues.append(f"source-lock-error:{type(exc).__name__}")
        else:
            if runtime_skill_hash != current_skill_hash:
                issues.append("skill-tree-hash-mismatch:runtime")
            if runtime_dependency_hash != current_dependency_hash:
                issues.append("dependency-lock-hash-mismatch:runtime")

    reviewers_raw = _array(evidence_obj.get("reviewers"), "reviewers", issues) or []
    reviewer_map: dict[str, str] = {}
    for index, raw in enumerate(reviewers_raw):
        context = f"reviewers[{index}]"
        reviewer = _object(raw, context, issues)
        if reviewer is None:
            continue
        _keys(reviewer, {"id", "independence_attestation_sha256"}, context, issues)
        reviewer_id = reviewer.get("id")
        valid_id = _safe_token(reviewer_id, REVIEWER_RE, f"{context}.id", issues)
        _hash(reviewer.get("independence_attestation_sha256"), f"{context}.attestation", issues)
        if valid_id:
            if reviewer_id in reviewer_map:
                issues.append(f"duplicate-reviewer:{context}")
            else:
                reviewer_map[reviewer_id] = reviewer["independence_attestation_sha256"]
    if len(reviewer_map) < reviewer_count:
        issues.append("insufficient-reviewers:reviewers")

    cases_raw = _array(evidence_obj.get("cases"), "cases", issues) or []
    if len(cases_raw) != case_count:
        issues.append("case-count-mismatch:cases")
    expected_case_ids = expected_ids("C", case_count, 4)
    expected_page_ids = expected_ids("P", page_count, 2)

    automated_passes = 0
    reviewed_pages = 0
    rendered_pages = 0
    page_passes = 0
    whole_deck_passes = 0
    structurally_complete_cases = 0
    valid_case_records: list[dict[str, Any]] = []

    for case_index, raw_case in enumerate(cases_raw):
        context = f"cases[{case_index}]"
        case = _object(raw_case, context, issues)
        if case is None:
            continue
        case_issue_start = len(issues)
        _keys(
            case,
            {"id", "input_sha256", "constraints_sha256", "generation", "pages"},
            context,
            issues,
        )
        expected_case_id = expected_case_ids[case_index] if case_index < len(expected_case_ids) else None
        case_id = case.get("id")
        if (
            expected_case_id is None
            or not isinstance(case_id, str)
            or not CASE_RE.fullmatch(case_id)
            or case_id != expected_case_id
        ):
            issues.append(f"case-id-mismatch:{context}")
        input_valid = _hash(case.get("input_sha256"), f"{context}.input_sha256", issues)
        constraints_valid = _hash(
            case.get("constraints_sha256"), f"{context}.constraints_sha256", issues
        )
        if input_valid and constraints_valid and case_id == expected_case_id:
            valid_case_records.append(case)

        generation = _object(case.get("generation"), f"{context}.generation", issues)
        automated_pass = False
        generator_id: str | None = None
        if generation is not None:
            _keys(
                generation,
                {
                    "status",
                    "generator_id",
                    "manual_fallback",
                    "page_count",
                    "repair_budget",
                    "layout_trace_status",
                    "svg_quality_errors",
                    "svg_quality_warnings",
                    "required_native_objects",
                    "present_native_objects",
                    "postflight_status",
                    "ir_sha256",
                    "layout_trace_sha256",
                    "pptx_sha256",
                    "postflight_sha256",
                    "run_receipt_sha256",
                },
                f"{context}.generation",
                issues,
            )
            status_value = generation.get("status")
            if status_value not in {"passed", "failed"}:
                issues.append(f"invalid-enum:{context}.generation.status")
            generator_id = generation.get("generator_id")
            _safe_token(generator_id, GENERATOR_RE, f"{context}.generation.generator_id", issues)
            manual_valid = _boolean(
                generation.get("manual_fallback"), f"{context}.generation.manual_fallback", issues
            )
            page_count_valid = _bounded_int(
                generation.get("page_count"), 0, page_count, f"{context}.generation.page_count", issues
            )
            budget_valid = _bounded_int(
                generation.get("repair_budget"), 0, 2, f"{context}.generation.repair_budget", issues
            )
            if generation.get("layout_trace_status") not in {"passed", "failed", "not-run"}:
                issues.append(f"invalid-enum:{context}.generation.layout_trace_status")
            errors_valid = _bounded_int(
                generation.get("svg_quality_errors"),
                0,
                100000,
                f"{context}.generation.svg_quality_errors",
                issues,
            )
            warnings_valid = _bounded_int(
                generation.get("svg_quality_warnings"),
                0,
                100000,
                f"{context}.generation.svg_quality_warnings",
                issues,
            )
            native_required_valid = _bounded_int(
                generation.get("required_native_objects"),
                0,
                10000,
                f"{context}.generation.required_native_objects",
                issues,
            )
            native_present_valid = _bounded_int(
                generation.get("present_native_objects"),
                0,
                10000,
                f"{context}.generation.present_native_objects",
                issues,
            )
            if generation.get("postflight_status") not in {
                "passed", "passed-with-warnings", "failed", "not-run"
            }:
                issues.append(f"invalid-enum:{context}.generation.postflight_status")
            _hash(generation.get("ir_sha256"), f"{context}.generation.ir_sha256", issues)
            _hash(
                generation.get("layout_trace_sha256"),
                f"{context}.generation.layout_trace_sha256",
                issues,
                nullable=status_value == "failed",
            )
            _hash(
                generation.get("pptx_sha256"),
                f"{context}.generation.pptx_sha256",
                issues,
                nullable=status_value == "failed",
            )
            _hash(
                generation.get("postflight_sha256"),
                f"{context}.generation.postflight_sha256",
                issues,
                nullable=status_value == "failed",
            )
            _hash(
                generation.get("run_receipt_sha256"),
                f"{context}.generation.run_receipt_sha256",
                issues,
            )
            automated_pass = bool(
                status_value == "passed"
                and manual_valid
                and generation.get("manual_fallback") is False
                and page_count_valid
                and generation.get("page_count") == page_count
                and budget_valid
                and generation.get("repair_budget") == profile["repair_budget"]
                and generation.get("layout_trace_status") == "passed"
                and errors_valid
                and generation.get("svg_quality_errors") == 0
                and warnings_valid
                and native_required_valid
                and native_present_valid
                and generation.get("required_native_objects")
                == generation.get("present_native_objects")
                and generation.get("postflight_status") in {"passed", "passed-with-warnings"}
                and all(
                    isinstance(generation.get(field), str)
                    and HASH_RE.fullmatch(generation[field]) is not None
                    for field in (
                        "ir_sha256",
                        "layout_trace_sha256",
                        "pptx_sha256",
                        "postflight_sha256",
                        "run_receipt_sha256",
                    )
                )
            )
        if automated_pass:
            automated_passes += 1

        pages_raw = _array(case.get("pages"), f"{context}.pages", issues) or []
        if len(pages_raw) != page_count:
            issues.append(f"page-count-mismatch:{context}.pages")
        all_pages_pass = len(pages_raw) == page_count
        for page_index, raw_page in enumerate(pages_raw):
            page_context = f"{context}.pages[{page_index}]"
            page = _object(raw_page, page_context, issues)
            if page is None:
                all_pages_pass = False
                continue
            _keys(page, {"id", "state", "render_sha256", "reviews"}, page_context, issues)
            expected_page_id = expected_page_ids[page_index] if page_index < len(expected_page_ids) else None
            page_id = page.get("id")
            if (
                expected_page_id is None
                or not isinstance(page_id, str)
                or not PAGE_RE.fullmatch(page_id)
                or page_id != expected_page_id
            ):
                issues.append(f"page-id-mismatch:{page_context}")
                all_pages_pass = False
            state = page.get("state")
            if state not in {"rendered", "missing"}:
                issues.append(f"invalid-enum:{page_context}.state")
                all_pages_pass = False
            render_hash = page.get("render_sha256")
            if state == "rendered":
                rendered_pages += 1
                if not _hash(render_hash, f"{page_context}.render_sha256", issues):
                    all_pages_pass = False
            elif render_hash is not None:
                issues.append(f"missing-page-has-render:{page_context}")
                all_pages_pass = False

            reviews_raw = _array(page.get("reviews"), f"{page_context}.reviews", issues) or []
            if len(reviews_raw) != reviewer_count:
                issues.append(f"review-count-mismatch:{page_context}.reviews")
                all_pages_pass = False
            page_reviewers: set[str] = set()
            page_reviews_pass = len(reviews_raw) == reviewer_count and state == "rendered"
            valid_reviews = 0
            for review_index, raw_review in enumerate(reviews_raw):
                review_context = f"{page_context}.reviews[{review_index}]"
                review = _object(raw_review, review_context, issues)
                if review is None:
                    page_reviews_pass = False
                    continue
                _keys(
                    review,
                    {
                        "reviewer_id",
                        "independent",
                        "render_sha256",
                        "criteria",
                        "verdict",
                        "receipt_sha256",
                    },
                    review_context,
                    issues,
                )
                reviewer_id = review.get("reviewer_id")
                reviewer_valid = _safe_token(
                    reviewer_id, REVIEWER_RE, f"{review_context}.reviewer_id", issues
                )
                if reviewer_valid:
                    if reviewer_id not in reviewer_map:
                        issues.append(f"unknown-reviewer:{review_context}")
                        reviewer_valid = False
                    if reviewer_id == generator_id:
                        issues.append(f"reviewer-generator-conflict:{review_context}")
                        reviewer_valid = False
                    if reviewer_id in page_reviewers:
                        issues.append(f"duplicate-page-reviewer:{review_context}")
                        reviewer_valid = False
                    page_reviewers.add(reviewer_id)
                independent_valid = _boolean(
                    review.get("independent"), f"{review_context}.independent", issues
                )
                if review.get("independent") is not True:
                    independent_valid = False
                review_render = review.get("render_sha256")
                if state == "rendered":
                    review_render_valid = _hash(
                        review_render, f"{review_context}.render_sha256", issues
                    ) and review_render == render_hash
                    if isinstance(review_render, str) and review_render != render_hash:
                        issues.append(f"review-render-mismatch:{review_context}")
                else:
                    review_render_valid = review_render is None
                    if review_render is not None:
                        issues.append(f"missing-review-has-render:{review_context}")
                criteria_obj = _object(review.get("criteria"), f"{review_context}.criteria", issues)
                criteria_pass = False
                if criteria_obj is not None:
                    _keys(criteria_obj, set(criteria), f"{review_context}.criteria", issues)
                    values_valid = True
                    for criterion in criteria:
                        if not _boolean(
                            criteria_obj.get(criterion),
                            f"{review_context}.criteria.{criterion}",
                            issues,
                        ):
                            values_valid = False
                    criteria_pass = values_valid and all(criteria_obj.get(item) is True for item in criteria)
                verdict = review.get("verdict")
                if verdict not in {"pass", "fail"}:
                    issues.append(f"invalid-enum:{review_context}.verdict")
                if (verdict == "pass") != criteria_pass:
                    issues.append(f"verdict-criteria-mismatch:{review_context}")
                    criteria_pass = False
                receipt_valid = _hash(
                    review.get("receipt_sha256"), f"{review_context}.receipt_sha256", issues
                )
                review_valid = bool(
                    reviewer_valid
                    and independent_valid
                    and review_render_valid
                    and receipt_valid
                )
                if review_valid:
                    valid_reviews += 1
                if not (review_valid and criteria_pass and verdict == "pass"):
                    page_reviews_pass = False
            if valid_reviews == reviewer_count and len(page_reviewers) == reviewer_count:
                reviewed_pages += 1
            if page_reviews_pass:
                page_passes += 1
            else:
                all_pages_pass = False

        if len(issues) == case_issue_start:
            structurally_complete_cases += 1
        whole_pass = automated_pass and all_pages_pass and len(pages_raw) == page_count
        if whole_pass:
            whole_deck_passes += 1

    if suite is not None and len(valid_case_records) == case_count:
        case_ids = [case["id"] for case in valid_case_records]
        if suite.get("case_ids_sha256") != canonical_sha256(case_ids):
            issues.append("case-id-hash-mismatch:suite")
        if suite.get("suite_sha256") != suite_hash(valid_case_records):
            issues.append("suite-hash-mismatch:suite")

    threshold = suite_policy["minimum_whole_deck_passes"]
    certified = not issues and whole_deck_passes >= threshold
    if not issues and whole_deck_passes < threshold:
        issues.append("certification-threshold-not-met")
    raw = evidence_bytes if evidence_bytes is not None else canonical_bytes(evidence_obj)
    summary = {
        "schema": SUMMARY_SCHEMA,
        "policy_id": policy["policy_id"],
        "profile": profile["id"],
        "policy_sha256": canonical_sha256(policy),
        "evidence_sha256": sha256_bytes(raw),
        "suite_sha256": suite.get("suite_sha256") if suite is not None else None,
        "skill_tree_sha256": runtime_skill_hash or None,
        "dependency_lock_sha256": runtime_dependency_hash or None,
        "evaluated_cases": len(cases_raw),
        "structurally_complete_cases": structurally_complete_cases,
        "automated_passes": automated_passes,
        "reviewed_pages": reviewed_pages,
        "rendered_pages": rendered_pages,
        "page_passes": page_passes,
        "whole_deck_passes": whole_deck_passes,
        "minimum_whole_deck_passes": threshold,
        "certified": certified,
    }
    return issues, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1], help="source root")
    parser.add_argument("--evidence", type=Path, required=True, help="absolute external evidence JSON")
    parser.add_argument("--json", action="store_true", help="emit safe aggregate JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    try:
        policy = load_policy(root)
        policy_issues = validate_official_policy(policy)
        _, raw = require_external_evidence(root, args.evidence)
        evidence = json.loads(raw.decode("utf-8"))
        issues, summary = evaluate_evidence(policy, evidence, root, evidence_bytes=raw)
        issues = policy_issues + issues
        if policy_issues:
            summary["certified"] = False
    except (CertificationError, UnicodeError, json.JSONDecodeError) as exc:
        if args.json:
            print(
                json.dumps(
                    {"schema": SUMMARY_SCHEMA, "certified": False, "issues": [type(exc).__name__]},
                    sort_keys=True,
                )
            )
        else:
            print(f"[FAIL] certification gate: {type(exc).__name__}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"summary": summary, "issues": issues}, sort_keys=True, indent=2))
    elif issues:
        for issue in issues:
            print(f"[FAIL] {issue}")
        print(
            "[FAIL] certification: "
            f"whole_deck_passes={summary['whole_deck_passes']}/"
            f"{summary['evaluated_cases']} threshold={summary['minimum_whole_deck_passes']}"
        )
    else:
        print(
            "[PASS] certification: "
            f"whole_deck_passes={summary['whole_deck_passes']}/"
            f"{summary['evaluated_cases']} reviewed_pages={summary['reviewed_pages']}"
        )
    return 0 if not issues and summary.get("certified") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
