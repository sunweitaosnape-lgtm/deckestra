from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "privacy_gate.py"
SPEC = importlib.util.spec_from_file_location("privacy_gate", MODULE_PATH)
assert SPEC and SPEC.loader
privacy_gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = privacy_gate
SPEC.loader.exec_module(privacy_gate)


def write_text(root: Path, name: str, text: str = "safe\n") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def codes(issues: list[object]) -> set[str]:
    return {issue.code for issue in issues}


def write_origin_policy(root: Path) -> None:
    skill_root = privacy_gate.PurePosixPath("skills/build-editable-decks")
    payload = {
        "schema_version": 1,
        "skill_root": skill_root.as_posix(),
        "skill_path_roster_sha256": privacy_gate._skill_roster_sha256(root, skill_root),
        "upstream": {
            "name": "hugohe3/ppt-master",
            "commit": "bbb323f0ebd6a6a230dd6063209326b53bfd2e1d",
            "license": "MIT",
        },
        "project_original_skill_paths": [],
        "third_party_paths": [],
    }
    write_text(root, "release/origin-policy.json", json.dumps(payload) + "\n")


class PrivacyGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_clean_text_tree_passes(self) -> None:
        write_text(self.root, "SKILL.md", "---\nname: build-editable-decks\ndescription: Build slides.\n---\n")
        issues, hashes = privacy_gate.scan_worktree(self.root)
        self.assertEqual(issues, [])
        self.assertEqual(set(hashes), {"SKILL.md"})

    def test_forbidden_media_extension_fails(self) -> None:
        write_text(self.root, "sample" + ".png", "not really an image")
        issues, _ = privacy_gate.scan_worktree(self.root)
        self.assertIn("forbidden-file-type", codes(issues))

    def test_media_magic_fails_even_when_renamed(self) -> None:
        (self.root / "renamed.txt").write_bytes(b"\x89PNG\r\n\x1a\nprivate")
        issues, _ = privacy_gate.scan_worktree(self.root)
        self.assertIn("binary-signature", codes(issues))

        captured = write_text(self.root, "renamed-generated-data.txt", "synthetic capture\n")
        original_hashes = privacy_gate.FORBIDDEN_HISTORY_SHA256
        privacy_gate.FORBIDDEN_HISTORY_SHA256 = frozenset(
            {privacy_gate.sha256_bytes(captured.read_bytes())}
        )
        try:
            issues, _ = privacy_gate.scan_worktree(self.root)
            self.assertIn("unreviewed-generated-data", codes(issues))
        finally:
            privacy_gate.FORBIDDEN_HISTORY_SHA256 = original_hashes

    def test_non_placeholder_embedded_image_fails(self) -> None:
        prefix = "data:" + "image/png;base64,"
        payload = "A" * 96
        write_text(
            self.root,
            "template.svg",
            f'<svg xmlns="http://www.w3.org/2000/svg"><image href="{prefix}{payload}"/></svg>',
        )
        issues, _ = privacy_gate.scan_worktree(self.root)
        self.assertIn("embedded-raster-image", codes(issues))

    def test_fixed_transparent_carrier_is_allowed(self) -> None:
        prefix = "data:" + "image/png;base64,"
        payload = privacy_gate.TRANSPARENT_PIXEL_PAYLOAD
        write_text(
            self.root,
            "template.svg",
            f'<svg xmlns="http://www.w3.org/2000/svg"><image href="{prefix}{payload}"/></svg>',
        )
        issues, _ = privacy_gate.scan_worktree(self.root)
        self.assertEqual(issues, [])

    def test_secret_fails(self) -> None:
        token = "gh" + "p_" + ("A" * 36)
        write_text(self.root, "notes.txt", token)
        issues, _ = privacy_gate.scan_worktree(self.root)
        self.assertIn("secret-pattern", codes(issues))

    def test_private_runtime_reference_fails(self) -> None:
        term = "oai" + "usercontent"
        write_text(self.root, "notes.txt", f"https://x.{term}.com/a")
        issues, _ = privacy_gate.scan_worktree(self.root)
        self.assertIn("private-service-reference", codes(issues))

    def test_symlink_fails(self) -> None:
        target = write_text(self.root, "safe.txt")
        (self.root / "alias.txt").symlink_to(target)
        issues, _ = privacy_gate.scan_worktree(self.root)
        self.assertIn("symlink", codes(issues))

    def test_private_certification_evidence_fails(self) -> None:
        write_text(self.root, "certification/evidence.json", "{}\n")
        issues, _ = privacy_gate.scan_worktree(self.root)
        self.assertIn("private-certification-artifact", codes(issues))

    def test_provenance_detects_added_file(self) -> None:
        write_text(self.root, "SKILL.md")
        write_origin_policy(self.root)
        issues, hashes = privacy_gate.scan_worktree(self.root)
        self.assertEqual(issues, [])
        privacy_gate.write_provenance(self.root, hashes)
        write_text(self.root, "unexpected.md")
        _, new_hashes = privacy_gate.scan_worktree(self.root)
        self.assertIn(
            "provenance-missing",
            codes(privacy_gate.verify_provenance(self.root, new_hashes)),
        )

    def test_provenance_origin_must_match_locked_policy(self) -> None:
        write_text(self.root, "SKILL.md")
        write_origin_policy(self.root)
        issues, hashes = privacy_gate.scan_worktree(self.root)
        self.assertEqual(issues, [])
        privacy_gate.write_provenance(self.root, hashes)
        provenance_path = self.root / privacy_gate.PROVENANCE_PATH
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["files"]["SKILL.md"]["origin"] = "adapted-mit-upstream"
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
        _, current = privacy_gate.scan_worktree(self.root)
        self.assertIn(
            "provenance-origin-mismatch",
            codes(privacy_gate.verify_provenance(self.root, current)),
        )

    def test_skill_roster_change_invalidates_origin_policy(self) -> None:
        write_text(self.root, "SKILL.md")
        write_origin_policy(self.root)
        issues, hashes = privacy_gate.scan_worktree(self.root)
        self.assertEqual(issues, [])
        privacy_gate.write_provenance(self.root, hashes)
        write_text(self.root, "skills/build-editable-decks/new_tool.py")
        _, current = privacy_gate.scan_worktree(self.root)
        self.assertIn(
            "origin-policy-invalid",
            codes(privacy_gate.verify_provenance(self.root, current)),
        )

    def test_history_scan_finds_deleted_secret(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Privacy Test"], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.email", "privacy-test@example.invalid"],
            check=True,
        )
        token = "gh" + "p_" + ("B" * 36)
        secret = write_text(self.root, "temporary.txt", token)
        subprocess.run(["git", "-C", str(self.root), "add", "temporary.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "temporary"], check=True)
        secret.unlink()
        subprocess.run(["git", "-C", str(self.root), "add", "-u"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "remove"], check=True)
        self.assertIn("secret-pattern", codes(privacy_gate.scan_history(self.root)))

        captured = write_text(self.root, "renamed-generated-data.txt", "synthetic capture\n")
        subprocess.run(
            ["git", "-C", str(self.root), "add", captured.name], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-qm", "captured"], check=True
        )
        original_hashes = privacy_gate.FORBIDDEN_HISTORY_SHA256
        privacy_gate.FORBIDDEN_HISTORY_SHA256 = frozenset(
            {privacy_gate.sha256_bytes(captured.read_bytes())}
        )
        try:
            self.assertIn(
                "history-unreviewed-generated-data",
                codes(privacy_gate.scan_history(self.root)),
            )
        finally:
            privacy_gate.FORBIDDEN_HISTORY_SHA256 = original_hashes


if __name__ == "__main__":
    unittest.main()
