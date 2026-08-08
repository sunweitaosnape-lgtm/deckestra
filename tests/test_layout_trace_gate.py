from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / "skills" / "build-editable-decks" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "layout_trace_gate.py"
SPEC = importlib.util.spec_from_file_location("layout_trace_gate", MODULE_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def fixture() -> dict:
    return {
        "schema": "deckestra-ir/v1",
        "pages": [{
            "id": "P01",
            "slug": "synthetic",
            "layout": "title-body",
            "title": "Synthetic gate fixture",
            "bullets": ["No user data", "No uploaded images"],
        }],
    }


class LayoutTraceGateTests(unittest.TestCase):
    def make_project(self, temporary: str) -> tuple[Path, Path]:
        project = Path(temporary)
        input_path = project / "deck_ir.json"
        input_path.write_text(json.dumps(fixture()), encoding="utf-8")
        gate.engine.execute(project, input_path)
        return project, input_path

    def test_current_trace_and_outputs_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project, input_path = self.make_project(temporary)
            self.assertEqual(gate.audit(project, input_path), [])

    def test_changed_input_invalidates_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project, input_path = self.make_project(temporary)
            changed = fixture()
            changed["pages"][0]["title"] = "Changed synthetic title"
            input_path.write_text(json.dumps(changed), encoding="utf-8")
            issues = gate.audit(project, input_path)
            self.assertIn("stale-layout-input-hash", issues)

    def test_changed_svg_invalidates_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project, input_path = self.make_project(temporary)
            svg = next((project / "svg_output").glob("*.svg"))
            svg.write_text(svg.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            issues = gate.audit(project, input_path)
            self.assertTrue(any(issue.startswith("layout-output-") for issue in issues), issues)

    def test_unknown_trace_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project, input_path = self.make_project(temporary)
            trace_path = project / "validation" / "layout_trace.json"
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            trace["raw_user_text"] = "forbidden"
            trace_path.write_text(json.dumps(trace), encoding="utf-8")
            issues = gate.audit(project, input_path)
            self.assertTrue(any(issue.startswith("trace-content-leak-risk:") for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
