from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "build-editable-decks"
CLI = SKILL / "scripts" / "project_manager.py"
IMAGE_CLI = SKILL / "scripts" / "image_gen.py"
LATEX_CLI = SKILL / "scripts" / "latex_render.py"
DOC_TO_MD_DIR = SKILL / "scripts" / "source_to_md"
AUDIO_CLI = SKILL / "scripts" / "notes_to_audio.py"


class RuntimePrivacyTests(unittest.TestCase):
    def test_default_project_uses_external_private_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "private-workspaces"
            env = os.environ.copy()
            env["DECKESTRA_WORKSPACE_ROOT"] = str(workspace)
            process = subprocess.run(
                [sys.executable, str(CLI), "init", "synthetic", "--quick-generate"],
                cwd=temporary,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            projects = list(workspace.glob("synthetic_ppt169_*"))
            self.assertEqual(len(projects), 1)
            self.assertNotIn(ROOT.resolve(), projects[0].resolve().parents)

            for command, filename in (
                ("scaffold-spec", "design_spec.md"),
                ("scaffold-lock", "spec_lock.md"),
            ):
                scaffold = subprocess.run(
                    [sys.executable, str(CLI), command, str(projects[0])],
                    cwd=temporary,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(scaffold.returncode, 0, scaffold.stderr)
                self.assertTrue((projects[0] / filename).is_file())

            forbidden_probe = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; "
                        f"sys.path.insert(0, {str(SKILL / 'scripts')!r}); "
                        "from project_management.project_specs import "
                        "default_spec_lock_forbidden; "
                        "items=default_spec_lock_forbidden(); "
                        "assert items and any('mask' in item for item in items)"
                    ),
                ],
                cwd=temporary,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(forbidden_probe.returncode, 0, forbidden_probe.stderr)

    def test_project_inside_source_tree_is_rejected(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "init",
                "synthetic",
                "--quick-generate",
                "--dir",
                str(ROOT / "runtime-work"),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertIn(
            "outside the Deckestra source package",
            process.stdout + process.stderr,
        )

    def test_repository_env_files_are_not_discovered(self) -> None:
        code = (
            "import sys; "
            f"sys.path.insert(0, {str(SKILL / 'scripts')!r}); "
            "import config; "
            "print('\\n'.join(str(p) for p in config.get_env_candidates()))"
        )
        env = os.environ.copy()
        env.pop("DECKESTRA_ENV_FILE", None)
        process = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        candidates = {Path(line).resolve() for line in process.stdout.splitlines() if line.strip()}
        self.assertNotIn((ROOT / ".env").resolve(), candidates)
        self.assertNotIn((SKILL / ".env").resolve(), candidates)

    def test_external_retrieval_and_reference_upload_require_explicit_consent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            reference = Path(temporary) / "private-reference.bin"
            reference.write_bytes(b"synthetic test bytes")
            process = subprocess.run(
                [
                    sys.executable,
                    str(IMAGE_CLI),
                    "synthetic edit",
                    "--reference-image",
                    str(reference),
                ],
                cwd=temporary,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            output = process.stdout + process.stderr
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("--allow-remote-reference-upload", output)
            self.assertNotIn(str(reference), output)

            project = Path(temporary) / "formula-project"
            manifest = project / "images" / "formula_manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                '{"items":[{"id":"f1","latex":"x + y"}]}\n',
                encoding="utf-8",
            )
            formula = subprocess.run(
                [sys.executable, str(LATEX_CLI), str(project)],
                cwd=temporary,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            formula_output = formula.stdout + formula.stderr
            self.assertNotEqual(formula.returncode, 0)
            self.assertIn("--allow-remote-formula-rendering", formula_output)
            self.assertNotIn("x + y", formula_output)

            remote_image_guard = (
                "import sys, tempfile; "
                f"sys.path.insert(0, {str(DOC_TO_MD_DIR)!r}); "
                "import doc_to_md; "
                "from pathlib import Path; "
                "d=Path(tempfile.mkdtemp()); "
                "\ntry:\n"
                " doc_to_md._download_remote_image('https://example.invalid/private.png', d, 1)\n"
                "except RuntimeError as exc:\n"
                " print(exc)\n"
                "else:\n"
                " raise SystemExit('remote guard did not fail closed')\n"
            )
            remote_image = subprocess.run(
                [sys.executable, "-c", remote_image_guard],
                cwd=temporary,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(remote_image.returncode, 0, remote_image.stderr)
            self.assertIn("--allow-remote-images", remote_image.stdout)

            tts = subprocess.run(
                [sys.executable, str(AUDIO_CLI), "--list-voices", "--locale", "en-US"],
                cwd=temporary,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            tts_output = tts.stdout + tts.stderr
            self.assertNotEqual(tts.returncode, 0)
            self.assertIn("--allow-remote-tts", tts_output)

        topic_research = (
            SKILL / "workflows" / "stages" / "topic-research.md"
        ).read_text(encoding="utf-8")
        quick_generate = (
            SKILL / "workflows" / "profiles" / "quick-generate.md"
        ).read_text(encoding="utf-8")
        image_base = (SKILL / "references" / "image-base.md").read_text(
            encoding="utf-8"
        )
        for policy in (topic_research, quick_generate, image_base):
            self.assertIn("explicit", policy.lower())
        self.assertIn("external research is opt-in", topic_research.lower())
        self.assertIn("acquisition permission is opt-in", image_base.lower())
        self.assertNotIn(
            "External factual enrichment allowed",
            topic_research,
        )

    def test_content_receipts_do_not_echo_private_text_or_paths(self) -> None:
        code = (
            "import sys; "
            f"sys.path.insert(0, {str(SKILL / 'scripts')!r}); "
            "from privacy_receipts import content_receipt, file_receipt; "
            "print(content_receipt('private prompt text')); "
            "print(file_receipt(sys.argv[1]))"
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "private-name.bin"
            source.write_bytes(b"private image bytes")
            process = subprocess.run(
                [sys.executable, "-c", code, str(source)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            self.assertNotIn("private prompt text", process.stdout)
            self.assertNotIn("private-name", process.stdout)
            self.assertNotIn("private image bytes", process.stdout)
            self.assertEqual(process.stdout.count("sha256="), 2)

        remote_error_code = (
            "import io, sys, types; "
            "from urllib.error import HTTPError; "
            f"sys.path.insert(0, {str(SKILL / 'scripts')!r}); "
            "from tts_backends.backend_common import read_http_error, response_receipt; "
            "requests=types.ModuleType('requests'); "
            "requests.Response=type('Response', (), {}); "
            "sys.modules['requests']=requests; "
            "from image_backends.backend_common import http_error; "
            "secret='synthetic-private-response-body'; "
            "url='https://example.invalid/private?opaque=synthetic-value'; "
            "exc=HTTPError(url, 503, 'synthetic-reason', {}, io.BytesIO(secret.encode())); "
            "print(read_http_error(exc)); "
            "response=requests.Response(); response.status_code=502; "
            "response.text=secret; response.url=url; "
            "print(http_error(response, 'Synthetic provider')); "
            "print(response_receipt({'url':url, 'body':secret}))"
        )
        remote_error = subprocess.run(
            [sys.executable, "-c", remote_error_code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        self.assertGreaterEqual(remote_error.stdout.count("sha256="), 3)
        self.assertNotIn("synthetic-private-response-body", remote_error.stdout)
        self.assertNotIn("example.invalid", remote_error.stdout)
        self.assertNotIn("synthetic-value", remote_error.stdout)

    def test_workflow_transcript_hashes_private_arguments_and_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "private-project-name"
            validation = project / "validation"
            validation.mkdir(parents=True)
            log = validation / "workflow.log"
            log.write_text("", encoding="utf-8")
            private_argument = "private customer prompt"
            code = (
                "import sys; "
                f"sys.path.insert(0, {str(SKILL / 'scripts')!r}); "
                "from console_encoding import configure_utf8_stdio; "
                "configure_utf8_stdio(); "
                "print('[OK] synthetic receipt')"
            )
            env = os.environ.copy()
            env["DECKESTRA_PROJECT_PATH"] = str(project)
            process = subprocess.run(
                [sys.executable, "-c", code, private_argument, str(project)],
                cwd=project,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            text = log.read_text(encoding="utf-8")
            self.assertIn("argv:", text)
            self.assertIn("sha256=", text)
            self.assertNotIn(private_argument, text)
            self.assertNotIn(str(project), text)
            self.assertNotIn("private-project-name", text)
            self.assertNotIn("synthetic receipt", text)

    def test_manual_workflow_note_is_stored_as_a_receipt(self) -> None:
        code = (
            "import sys; "
            f"sys.path.insert(0, {str(SKILL / 'scripts')!r}); "
            "from workflow_log import append_note; "
            "append_note(sys.argv[1], sys.argv[2])"
        )
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            private_note = "private manual audit detail"
            subprocess.run(
                [sys.executable, "-c", code, str(project), private_note],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            log = (project / "validation" / "workflow.log").read_text(encoding="utf-8")
            self.assertIn("category=manual-note", log)
            self.assertIn("sha256=", log)
            self.assertNotIn(private_note, log)


if __name__ == "__main__":
    unittest.main()
