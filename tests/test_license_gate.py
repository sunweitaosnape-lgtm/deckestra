from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "tools" / "license_gate.py"
SPEC = importlib.util.spec_from_file_location("license_gate", MODULE_PATH)
assert SPEC and SPEC.loader
license_gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = license_gate
SPEC.loader.exec_module(license_gate)


class LicenseGateTests(unittest.TestCase):
    def test_repository_license_inventory_passes(self) -> None:
        self.assertEqual(license_gate.audit(ROOT), [])

    def test_tampered_third_party_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            test_root = Path(temporary)
            for relative in license_gate.EXPECTED_SHA256:
                source = ROOT / relative
                destination = test_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            notice = test_root / license_gate.NOTICE_PATH
            notice.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / license_gate.NOTICE_PATH, notice)
            icons = test_root / license_gate.ICON_ROOT
            icons.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / license_gate.ICON_ROOT / "README.md", icons / "README.md")

            target = test_root / next(iter(license_gate.EXPECTED_SHA256))
            target.write_text("tampered\n", encoding="utf-8")
            issues = license_gate.audit(test_root)
            self.assertTrue(
                any(issue.startswith("third-party-hash-mismatch:") for issue in issues),
                issues,
            )

    def test_bundled_icon_asset_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            test_root = Path(temporary)
            icons = test_root / license_gate.ICON_ROOT
            icons.mkdir(parents=True)
            (icons / "README.md").write_text("policy\n", encoding="utf-8")
            (icons / "logo.svg").write_text("<svg/>\n", encoding="utf-8")
            excluded = test_root / next(iter(license_gate.FORBIDDEN_UNREVIEWED_FILES))
            excluded.parent.mkdir(parents=True, exist_ok=True)
            excluded.write_text("synthetic generated data\n", encoding="utf-8")
            issues = license_gate.audit(test_root)
            self.assertTrue(any(issue.startswith("bundled-icon-assets:") for issue in issues))
            self.assertTrue(
                any(issue.startswith("unreviewed-generated-data:") for issue in issues)
            )


if __name__ == "__main__":
    unittest.main()
