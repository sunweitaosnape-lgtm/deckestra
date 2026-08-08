from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_release
import privacy_gate


class ReleaseBuildTests(unittest.TestCase):
    def make_source(self, root: Path) -> dict[str, str]:
        (root / "nested").mkdir(parents=True)
        (root / "SKILL.md").write_text("---\nname: synthetic\n---\n", encoding="utf-8")
        (root / "nested" / "tool.py").write_text("#!/usr/bin/env python3\nprint('safe')\n", encoding="utf-8")
        issues, hashes = privacy_gate.scan_worktree(root)
        self.assertEqual(issues, [])
        return hashes

    def test_archive_is_byte_reproducible_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            source.mkdir()
            hashes = self.make_source(source)
            first = base / "first.zip"
            second = base / "second.zip"
            build_release.write_archive(source, first, hashes)
            build_release.write_archive(source, second, hashes)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            extracted = build_release.safe_extract(first, base / "unpacked")
            build_release.verify_extracted_tree(extracted, hashes)
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    archive.namelist(),
                    ["deckestra/SKILL.md", "deckestra/nested/tool.py"],
                )
                self.assertTrue(all(info.date_time == build_release.FIXED_TIMESTAMP for info in archive.infolist()))

    def test_output_inside_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with self.assertRaises(build_release.ReleaseBuildError):
                build_release.validate_output(root, root / "release.zip")

    def test_existing_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = base / "source"
            root.mkdir()
            output = base / "release.zip"
            output.write_text("existing", encoding="utf-8")
            with self.assertRaises(build_release.ReleaseBuildError):
                build_release.validate_output(root, output)


if __name__ == "__main__":
    unittest.main()
