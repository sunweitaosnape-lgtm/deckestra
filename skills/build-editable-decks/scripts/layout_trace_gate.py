#!/usr/bin/env python3
"""Verify that deterministic SVG outputs match their content-free trace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import deterministic_layout as engine


ROOT_FIELDS = {
    "engine", "schema", "status", "repair_budget", "attempts", "page_metrics",
    "pages", "source_count", "input", "outputs",
}
ATTEMPT_FIELDS = {"attempt", "font_scale", "gap_scale", "issues"}
ISSUE_FIELDS = {
    "page_id", "code", "element", "line_count", "max_lines", "needed_height",
    "box_height", "rows", "row_height", "minimum_row_height",
}
METRIC_FIELDS = {"element", "characters", "lines", "font_size", "box", "overflow"}
PAGE_FIELDS = {"id", "layout"}
INPUT_FIELDS = {"path", "sha256"}
OUTPUT_FIELDS = {"path", "bytes", "sha256"}


def _unknown(value: Any, allowed: set[str], context: str, issues: list[str]) -> None:
    if not isinstance(value, dict):
        issues.append(f"invalid-trace-shape: {context} is not an object")
        return
    extra = sorted(set(value) - allowed)
    if extra:
        issues.append(f"trace-content-leak-risk: {context} has unknown field(s) {', '.join(extra)}")


def _validate_trace_shape(trace: Any) -> list[str]:
    issues: list[str] = []
    _unknown(trace, ROOT_FIELDS, "root", issues)
    if not isinstance(trace, dict):
        return issues
    attempts = trace.get("attempts")
    if not isinstance(attempts, list):
        issues.append("invalid-trace-shape: attempts is not an array")
    else:
        for index, attempt in enumerate(attempts):
            _unknown(attempt, ATTEMPT_FIELDS, f"attempts[{index}]", issues)
            if not isinstance(attempt, dict):
                continue
            rows = attempt.get("issues")
            if not isinstance(rows, list):
                issues.append(f"invalid-trace-shape: attempts[{index}].issues is not an array")
                continue
            for issue_index, row in enumerate(rows):
                _unknown(row, ISSUE_FIELDS, f"attempts[{index}].issues[{issue_index}]", issues)
    metrics = trace.get("page_metrics")
    if not isinstance(metrics, dict):
        issues.append("invalid-trace-shape: page_metrics is not an object")
    else:
        for page_id, rows in metrics.items():
            if not isinstance(page_id, str) or not isinstance(rows, list):
                issues.append("invalid-trace-shape: invalid page_metrics entry")
                continue
            for index, row in enumerate(rows):
                _unknown(row, METRIC_FIELDS, f"page_metrics.{page_id}[{index}]", issues)
    for key, fields in (("pages", PAGE_FIELDS), ("outputs", OUTPUT_FIELDS)):
        rows = trace.get(key)
        if not isinstance(rows, list):
            issues.append(f"invalid-trace-shape: {key} is not an array")
            continue
        for index, row in enumerate(rows):
            _unknown(row, fields, f"{key}[{index}]", issues)
    _unknown(trace.get("input"), INPUT_FIELDS, "input", issues)
    return issues


def audit(project: Path, input_path: Path = Path("deck_ir.json"), *, required_budget: int = 2) -> list[str]:
    issues: list[str] = []
    try:
        project = engine.require_external_project(project)
    except (OSError, engine.LayoutContractError) as exc:
        return [f"invalid-project: {exc}"]
    input_path = input_path if input_path.is_absolute() else project / input_path
    try:
        input_relative = input_path.resolve().relative_to(project).as_posix()
    except ValueError:
        return ["invalid-input-path: input must stay inside the project"]
    trace_path = project / "validation" / "layout_trace.json"
    if not trace_path.is_file():
        return ["missing-layout-trace: validation/layout_trace.json"]
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"invalid-layout-trace: {exc}"]
    issues.extend(_validate_trace_shape(trace))
    if not isinstance(trace, dict):
        return sorted(set(issues))
    if trace.get("engine") != engine.ENGINE_VERSION:
        issues.append("wrong-layout-engine")
    if trace.get("schema") != engine.IR_SCHEMA:
        issues.append("wrong-ir-schema")
    if trace.get("status") != "passed":
        issues.append("layout-status-not-passed")
    if trace.get("repair_budget") != required_budget:
        issues.append(f"wrong-repair-budget: expected {required_budget}")
    attempts = trace.get("attempts", [])
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= required_budget + 1:
        issues.append("invalid-attempt-count")
    elif not isinstance(attempts[-1], dict) or attempts[-1].get("issues") != []:
        issues.append("unresolved-layout-issues")

    if not input_path.is_file():
        issues.append(f"missing-layout-input: {input_relative}")
        ir = None
    else:
        try:
            ir, input_hash = engine.load_ir(input_path)
        except (OSError, engine.LayoutContractError) as exc:
            issues.append(f"invalid-layout-input: {exc}")
            ir = None
        else:
            trace_input = trace.get("input", {})
            if not isinstance(trace_input, dict):
                issues.append("invalid-trace-input")
            else:
                if trace_input.get("path") != input_relative:
                    issues.append("layout-input-path-mismatch")
                if trace_input.get("sha256") != input_hash:
                    issues.append("stale-layout-input-hash")

    trace_pages = trace.get("pages", [])
    if ir is not None:
        expected_pages = [{"id": page["id"], "layout": page["layout"]} for page in ir["pages"]]
        if trace_pages != expected_pages:
            issues.append("layout-page-roster-mismatch")
        if trace.get("source_count") != len(ir["sources"]):
            issues.append("layout-source-count-mismatch")

    output_rows = trace.get("outputs", [])
    expected_files: dict[str, dict[str, Any]] = {}
    if isinstance(output_rows, list):
        for index, row in enumerate(output_rows):
            if not isinstance(row, dict):
                continue
            relative = row.get("path")
            if not isinstance(relative, str) or not relative.startswith("svg_output/"):
                issues.append(f"invalid-output-path: outputs[{index}]")
                continue
            path = project / relative
            try:
                path.resolve().relative_to(project / "svg_output")
            except ValueError:
                issues.append(f"output-path-escape: {relative}")
                continue
            if path.is_symlink() or not path.is_file():
                issues.append(f"missing-layout-output: {relative}")
                continue
            actual_bytes = path.stat().st_size
            actual_hash = engine._sha256_file(path)
            if row.get("bytes") != actual_bytes:
                issues.append(f"layout-output-size-mismatch: {relative}")
            if row.get("sha256") != actual_hash:
                issues.append(f"layout-output-hash-mismatch: {relative}")
            if relative in expected_files:
                issues.append(f"duplicate-layout-output: {relative}")
            expected_files[relative] = row
    live_files = {
        f"svg_output/{path.name}"
        for path in (project / "svg_output").glob("*.svg")
        if path.is_file()
    } if (project / "svg_output").is_dir() else set()
    if live_files != set(expected_files):
        issues.append("layout-output-closure-mismatch")
    if ir is not None and len(expected_files) != len(ir["pages"]):
        issues.append("layout-output-count-mismatch")
    return sorted(set(issues))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify deterministic layout trace and SVG closure.")
    parser.add_argument("project", type=Path, help="External project workspace")
    parser.add_argument("--input", type=Path, default=Path("deck_ir.json"), help="IR path inside the project")
    parser.add_argument("--require-budget", type=int, choices=(0, 1, 2), default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    issues = audit(args.project, args.input, required_budget=args.require_budget)
    if issues:
        for issue in issues:
            print(f"[FAIL] {issue}", file=sys.stderr)
        return 1
    print("[PASS] deterministic layout trace and SVG closure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
