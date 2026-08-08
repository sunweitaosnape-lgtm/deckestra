from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "build-editable-decks"
LEGAL_EXCEPTIONS = {
    "THIRD_PARTY_NOTICES.md",
    "third_party/ppt-master/MIT.txt",
}


class IdentityTests(unittest.TestCase):
    def test_skill_folder_and_frontmatter_match(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"---\n(.*?)\n---\n", text, flags=re.DOTALL)
        self.assertIsNotNone(match)
        metadata = match.group(1)
        fields = re.findall(r"(?m)^([a-z][a-z0-9_-]*):", metadata)
        self.assertEqual(fields, ["name", "description"])
        self.assertRegex(metadata, r"(?m)^name:\s*build-editable-decks\s*$")

    def test_legacy_product_identity_is_legal_notice_only(self) -> None:
        failures: list[str] = []
        for path in SKILL.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(SKILL).as_posix()
            if relative in LEGAL_EXCEPTIONS:
                continue
            text = path.read_text(encoding="utf-8")
            legacy_lines = [
                line
                for line in text.splitlines()
                if (
                    "ppt-master" in line.lower()
                    or "ppt master" in line.lower()
                    or "ppt_master" in line.lower()
                )
                and "third_party/ppt-master" not in line.lower()
            ]
            if legacy_lines:
                failures.append(relative)
        self.assertEqual(failures, [])
        self.assertFalse(
            (SKILL / "scripts" / "pptx_animation_presets.json").exists()
        )
        animation_source = (SKILL / "scripts" / "pptx_animations.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("OBJECT_ANIMATION_AUTHORING_AVAILABLE = False", animation_source)
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys\n"
                    f"sys.path.insert(0, {str(SKILL / 'scripts')!r})\n"
                    "import pptx_animations as a\n"
                    "assert a.get_available_animations() == []\n"
                    "assert a.normalize_animation_effect('none') is None\n"
                    "assert '<p:transition' in a.create_transition_xml('fade', 0.5)\n"
                    "assert a.create_sequence_timing_xml([]) == ''\n"
                    "for effect in ('entrance_fade','fade','auto','mixed','random'):\n"
                    "    try:\n"
                    "        a.normalize_animation_effect(effect)\n"
                    "    except ValueError as exc:\n"
                    "        assert 'object-animation authoring is unavailable' in str(exc)\n"
                    "    else:\n"
                    "        raise AssertionError(effect)\n"
                    "for writer in (\n"
                    "    lambda: a.create_timing_xml(),\n"
                    "    lambda: a.create_sequence_timing_xml([(2, 0, 'entrance_fade')]),\n"
                    "    lambda: a.describe_animation_effect('entrance_fade'),\n"
                    "):\n"
                    "    try:\n"
                    "        writer()\n"
                    "    except ValueError as exc:\n"
                    "        assert 'object-animation authoring is unavailable' in str(exc)\n"
                    "    else:\n"
                    "        raise AssertionError('writer did not fail closed')\n"
                ),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)

    def test_upstream_owner_does_not_appear_as_product_maintainer(self) -> None:
        failures: list[str] = []
        for path in SKILL.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(SKILL).as_posix()
            if relative in LEGAL_EXCEPTIONS:
                continue
            if "hugohe3" in path.read_text(encoding="utf-8").lower():
                failures.append(relative)
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
