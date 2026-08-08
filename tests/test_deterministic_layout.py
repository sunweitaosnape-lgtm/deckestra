from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "skills" / "build-editable-decks" / "scripts" / "deterministic_layout.py"
SPEC = importlib.util.spec_from_file_location("deterministic_layout", MODULE_PATH)
assert SPEC and SPEC.loader
layout = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = layout
SPEC.loader.exec_module(layout)


def synthetic_ir() -> dict:
    return {
        "schema": "deckestra-ir/v1",
        "sources": [
            {"id": "synthetic", "kind": "calculated", "locator": "unit-test", "license": "synthetic"}
        ],
        "pages": [
            {
                "id": "P01",
                "slug": "overview",
                "layout": "cover",
                "title": "Deterministic Systems Brief",
                "subtitle": "Synthetic fixture with no user or uploaded content",
                "source_ids": ["synthetic"],
            },
            {
                "id": "P02",
                "slug": "controls",
                "layout": "two-column",
                "title": "Controls stay editable",
                "columns": [
                    {"title": "Inputs", "bullets": ["Typed fields", "Declared sources"]},
                    {"title": "Outputs", "bullets": ["Native text", "Native shapes"]},
                ],
            },
            {
                "id": "P03",
                "slug": "evidence",
                "layout": "bar-chart",
                "title": "Synthetic evidence",
                "chart": {"categories": ["A", "B", "C"], "values": [2, 5, 3], "source_ids": ["synthetic"]},
            },
        ],
    }


def all_layout_pages() -> list[dict]:
    return [
        {"id": "P01", "slug": "cover", "layout": "cover", "title": "Synthetic cover", "subtitle": "Local deterministic fixture"},
        {"id": "P02", "slug": "section", "layout": "section", "title": "Synthetic section", "subtitle": "A clear transition"},
        {"id": "P03", "slug": "statement", "layout": "statement", "title": "One synthetic claim", "body": "Supported by declared fixture data."},
        {"id": "P04", "slug": "body", "layout": "title-body", "title": "Typed content", "body": "A concise synthetic paragraph.", "bullets": ["First condition", "Second condition"]},
        {"id": "P05", "slug": "columns", "layout": "two-column", "title": "Two paths", "columns": [{"title": "Path A", "body": "Controlled input."}, {"title": "Path B", "body": "Verified output."}]},
        {"id": "P06", "slug": "cards", "layout": "cards", "title": "Three controls", "cards": [{"title": "Schema", "body": "Typed."}, {"title": "Layout", "body": "Bounded."}, {"title": "Trace", "body": "Hashed."}]},
        {"id": "P07", "slug": "metrics", "layout": "metrics", "title": "Synthetic metrics", "metrics": [{"value": "12", "label": "families"}, {"value": "2", "label": "repairs"}, {"value": "0", "label": "uploads"}]},
        {"id": "P08", "slug": "process", "layout": "process", "title": "Controlled process", "steps": [{"title": "Type", "body": "Validate fields."}, {"title": "Render", "body": "Solve geometry."}, {"title": "Gate", "body": "Verify hashes."}]},
        {"id": "P09", "slug": "table", "layout": "table", "title": "Synthetic matrix", "table": {"columns": ["Check", "State"], "rows": [["Schema", "Pass"], ["Trace", "Pass"]]}},
        {"id": "P10", "slug": "chart", "layout": "bar-chart", "title": "Synthetic series", "chart": {"categories": ["A", "B", "C"], "values": [3, 7, 5]}},
        {"id": "P11", "slug": "quote", "layout": "quote", "title": "Synthetic quotation", "quote": "A deterministic fixture is useful only when it fails visibly.", "attribution": "Test contract"},
        {"id": "P12", "slug": "closing", "layout": "closing", "title": "End of synthetic fixture", "subtitle": "No private content was used."},
    ]


class DeterministicLayoutTests(unittest.TestCase):
    def test_all_twelve_layout_families_render(self) -> None:
        ir = layout.validate_ir({"schema": "deckestra-ir/v1", "pages": all_layout_pages()})
        outputs, trace = layout.render_deck(ir, repair_budget=2)
        self.assertEqual(trace["status"], "passed")
        self.assertEqual(len(outputs), 12)
        self.assertEqual({page["layout"] for page in trace["pages"]}, layout.ALLOWED_LAYOUTS)
        self.assertTrue(all(b'data-pptx-page-role=' in payload for payload in outputs.values()))
        self.assertIn(b'data-pptx-replace-with="table"', outputs["09_table.svg"])
        self.assertIn(b'data-pptx-replace-with="chart"', outputs["10_chart.svg"])

    def test_all_layout_families_pass_existing_svg_quality_gate_without_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            input_path = project / "deck_ir.json"
            input_path.write_text(
                json.dumps({"schema": "deckestra-ir/v1", "pages": all_layout_pages()}),
                encoding="utf-8",
            )
            trace = layout.execute(project, input_path)
            self.assertEqual(trace["status"], "passed")
            checker = ROOT / "skills" / "build-editable-decks" / "scripts" / "svg_quality_checker.py"
            result = subprocess.run(
                [sys.executable, str(checker), str(project), "--stage", "final", "--quick-generate", "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Fully passed: 12 (100%)", result.stdout)
            self.assertIn("With warnings: 0 (0%)", result.stdout)
            self.assertIn("With errors: 0 (0%)", result.stdout)

    def test_native_table_and_chart_export_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            pages = [
                {
                    "id": "P01",
                    "slug": "table",
                    "layout": "table",
                    "title": "Synthetic table",
                    "table": {"columns": ["Control", "State"], "rows": [["Schema", "Pass"], ["Privacy", "Pass"]]},
                },
                {
                    "id": "P02",
                    "slug": "chart",
                    "layout": "bar-chart",
                    "title": "Synthetic chart",
                    "chart": {"categories": ["A", "B", "C"], "values": [2, 6, 4]},
                },
            ]
            input_path = project / "deck_ir.json"
            input_path.write_text(json.dumps({"schema": "deckestra-ir/v1", "pages": pages}), encoding="utf-8")
            trace = layout.execute(project, input_path)
            self.assertEqual(trace["status"], "passed")

            scripts = ROOT / "skills" / "build-editable-decks" / "scripts"
            checker = subprocess.run(
                [sys.executable, str(scripts / "svg_quality_checker.py"), str(project), "--stage", "final", "--quick-generate", "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(checker.returncode, 0, checker.stdout + checker.stderr)

            output = project / "exports" / "native-smoke.pptx"
            exporter = subprocess.run(
                [
                    sys.executable,
                    str(scripts / "svg_to_pptx.py"),
                    str(project),
                    "--quick-generate",
                    "--no-notes",
                    "--native-charts-and-tables",
                    "--conversion-trace",
                    "-o",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(exporter.returncode, 0, exporter.stdout + exporter.stderr)
            self.assertTrue(output.is_file())
            with zipfile.ZipFile(output) as archive:
                table_slide = archive.read("ppt/slides/slide1.xml")
                chart_slide = archive.read("ppt/slides/slide2.xml")
                names = archive.namelist()
            self.assertIn(b"<a:tbl>", table_slide)
            self.assertIn(b"<c:chart", chart_slide)
            self.assertTrue(any(name.startswith("ppt/charts/chart") for name in names))
            self.assertTrue(any(name.startswith("ppt/embeddings/") for name in names))
            report = json.loads((project / "validation" / "native-smoke.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "passed")

    def test_fixed_repair_sequence_recovers_without_truncation(self) -> None:
        ir = layout.validate_ir({
            "schema": "deckestra-ir/v1",
            "pages": [{
                "id": "P01",
                "slug": "repair",
                "layout": "title-body",
                "title": "Synthetic repair test",
                "body": "dense " * 240,
            }],
        })
        outputs, trace = layout.render_deck(ir, repair_budget=2)
        self.assertEqual(trace["status"], "passed")
        self.assertEqual(len(trace["attempts"]), 2)
        self.assertTrue(trace["attempts"][0]["issues"])
        self.assertEqual(trace["attempts"][1]["issues"], [])
        self.assertEqual(next(iter(outputs.values())).count(b"dense"), 240)

    def test_repeat_run_is_byte_identical_and_trace_omits_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            input_path = project / "deck_ir.json"
            input_path.write_text(json.dumps(synthetic_ir(), ensure_ascii=False), encoding="utf-8")
            first = layout.execute(project, input_path)
            first_bytes = {path.name: path.read_bytes() for path in (project / "svg_output").glob("*.svg")}
            second = layout.execute(project, input_path)
            second_bytes = {path.name: path.read_bytes() for path in (project / "svg_output").glob("*.svg")}
            self.assertEqual(first["status"], "passed")
            self.assertEqual(second["status"], "passed")
            self.assertEqual(first_bytes, second_bytes)
            trace_text = (project / "validation" / "layout_trace.json").read_text(encoding="utf-8")
            self.assertNotIn("Deterministic Systems Brief", trace_text)
            self.assertNotIn("Synthetic fixture", trace_text)

    def test_unresolved_overflow_stops_after_two_repairs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            ir = synthetic_ir()
            ir["pages"] = [{
                "id": "P01",
                "slug": "overflow",
                "layout": "title-body",
                "title": "Overflow must fail",
                "body": "dense " * 650,
            }]
            input_path = project / "deck_ir.json"
            input_path.write_text(json.dumps(ir), encoding="utf-8")
            trace = layout.execute(project, input_path, repair_budget=2)
            self.assertEqual(trace["status"], "failed")
            self.assertEqual(len(trace["attempts"]), 3)
            self.assertFalse((project / "svg_output").exists())
            self.assertTrue((project / "validation" / "layout_trace.failed.json").is_file())

    def test_undeclared_source_is_rejected(self) -> None:
        ir = synthetic_ir()
        ir["pages"][0]["source_ids"] = ["missing"]
        with self.assertRaises(layout.LayoutContractError):
            layout.validate_ir(ir)

    def test_repository_runtime_workspace_is_rejected(self) -> None:
        with self.assertRaises(layout.LayoutContractError):
            layout.require_external_project(ROOT)


if __name__ == "__main__":
    unittest.main()
