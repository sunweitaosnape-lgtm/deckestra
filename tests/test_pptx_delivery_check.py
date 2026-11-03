"""Delivery failures built from synthetic packages, never from user decks."""

from __future__ import annotations

import io
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image
from pptx import Presentation
from pptx.util import Inches

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "build-editable-decks" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from pptx_delivery_check import audit_pptx_delivery  # noqa: E402

SLIDE = "ppt/slides/slide1.xml"
SLIDE_RELS = "ppt/slides/_rels/slide1.xml.rels"


class PptxDeliveryCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="deckestra-delivery-test-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.path = self.directory / "synthetic.pptx"
        presentation = Presentation()
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text = "Synthetic delivery"
        image = io.BytesIO()
        Image.new("RGB", (8, 8), (32, 64, 96)).save(image, format="PNG")
        image.seek(0)
        slide.shapes.add_picture(image, Inches(1), Inches(2), width=Inches(1))
        presentation.save(self.path)
        with zipfile.ZipFile(self.path) as archive:
            self.parts = {name: archive.read(name) for name in archive.namelist()}
        self.media = next(name for name in self.parts if name.startswith("ppt/media/"))

    def write_parts(self, *, compression: int = zipfile.ZIP_DEFLATED) -> None:
        with zipfile.ZipFile(self.path, "w", compression=compression) as archive:
            for name, data in self.parts.items():
                archive.writestr(name, data)

    def edit_xml(self, part: str, edit) -> None:
        root = ET.fromstring(self.parts[part])
        edit(root)
        self.parts[part] = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    def audit(self) -> dict:
        before = self.path.read_bytes()
        report = audit_pptx_delivery(self.path)
        self.assertEqual(self.path.read_bytes(), before, "audit must be read-only")
        json.dumps(report)  # Every failure must remain machine-readable.
        return report

    def assert_failure(self, code: str) -> dict:
        report = self.audit()
        self.assertEqual(report["status"], "failed", report)
        self.assertIn(code, {issue["code"] for issue in report["errors"]}, report)
        return report

    def test_valid_synthetic_package_and_reopen(self) -> None:
        report = self.audit()
        self.assertIn(report["status"], {"passed", "passed-with-advisories"})
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["package"]["zip_integrity"], "passed")
        self.assertEqual(report["slides"]["count"], 1)
        self.assertEqual(report["media"]["embedded_count"], 1)
        reopened = Presentation(self.path)
        self.assertEqual(len(reopened.slides), 1)
        self.assertEqual(reopened.slides[0].shapes[0].text, "Synthetic delivery")

    def test_truncated_zip(self) -> None:
        self.path.write_bytes(self.path.read_bytes()[:-22])
        report = self.assert_failure("invalid_zip_package")
        self.assertEqual(report["package"]["zip_integrity"], "failed")

    def test_non_zip_download_body(self) -> None:
        # A saved error page is not a PPTX. This does not test any download URL.
        self.path.write_text("<html>Synthetic unavailable response</html>", encoding="utf-8")
        self.assert_failure("invalid_zip_package")

    def test_missing_local_file(self) -> None:
        report = audit_pptx_delivery(self.directory / "absent.pptx")
        self.assertEqual(report["status"], "failed")
        self.assertEqual([issue["code"] for issue in report["errors"]], ["file_not_found"])

    def test_missing_content_types_registry(self) -> None:
        del self.parts["[Content_Types].xml"]
        self.write_parts()
        self.assert_failure("missing_content_types")

    def test_malformed_content_types(self) -> None:
        self.parts["[Content_Types].xml"] = b"<Types"
        self.write_parts()
        self.assert_failure("invalid_content_types")

    def test_missing_media_content_type(self) -> None:
        self.edit_xml("[Content_Types].xml", lambda root: [
            root.remove(node) for node in list(root)
            if node.get("Extension") == "png"
        ])
        self.write_parts()
        report = self.assert_failure("missing_part_content_type")
        issue = next(item for item in report["errors"] if item["code"] == "missing_part_content_type")
        self.assertIn(self.media, issue["parts"])

    def test_missing_required_slide_content_type(self) -> None:
        # The generic application/xml default must not hide a missing slide type.
        self.edit_xml("[Content_Types].xml", lambda root: [
            root.remove(node) for node in list(root)
            if node.get("PartName") == "/" + SLIDE
        ])
        self.write_parts()
        self.assert_failure("invalid_required_content_type")

    def test_missing_required_presentation_content_type(self) -> None:
        self.edit_xml("[Content_Types].xml", lambda root: [
            root.remove(node) for node in list(root)
            if node.get("PartName") == "/ppt/presentation.xml"
        ])
        self.write_parts()
        self.assert_failure("invalid_required_content_type")

    def test_incorrect_slide_content_type(self) -> None:
        self.edit_xml("[Content_Types].xml", lambda root: [
            node.set("ContentType", "application/xml") for node in root
            if node.get("PartName") == "/" + SLIDE
        ])
        self.write_parts()
        report = self.assert_failure("invalid_required_content_type")
        issue = next(item for item in report["errors"] if item["code"] == "invalid_required_content_type")
        self.assertEqual(issue["part"], SLIDE)
        self.assertEqual(issue["declared"], "application/xml")

    def test_valid_nonstandard_slide_part_name(self) -> None:
        renamed = "ppt/slides/synthetic.xml"
        self.parts[renamed] = self.parts.pop(SLIDE)
        self.parts["ppt/slides/_rels/synthetic.xml.rels"] = self.parts.pop(SLIDE_RELS)
        self.edit_xml("[Content_Types].xml", lambda root: [
            node.set("PartName", "/" + renamed) for node in root
            if node.get("PartName") == "/" + SLIDE
        ])
        self.edit_xml("ppt/_rels/presentation.xml.rels", lambda root: [
            node.set("Target", "slides/synthetic.xml") for node in root
            if node.get("Type", "").endswith("/slide")
        ])
        self.write_parts()
        report = self.audit()
        self.assertEqual(report["errors"], [], report)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["slides"]["count"], 1)

    def test_duplicate_office_document_relationship(self) -> None:
        def duplicate(root):
            node = next(node for node in root if node.get("Type", "").endswith("/officeDocument"))
            attributes = dict(node.attrib, Id="rIdSyntheticDuplicate")
            ET.SubElement(root, node.tag, attributes)
        self.edit_xml("_rels/.rels", duplicate)
        self.write_parts()
        self.assert_failure("duplicate_office_document_relationship")

    def test_dangling_slide_relationship(self) -> None:
        del self.parts[SLIDE]
        self.write_parts()
        report = self.assert_failure("dangling_internal_relationship")
        self.assertTrue(any(SLIDE in item for item in report["package"]["relationships"]["problems"]))

    def test_dangling_media_relationship(self) -> None:
        del self.parts[self.media]
        self.write_parts()
        report = self.assert_failure("dangling_internal_relationship")
        self.assertTrue(any(self.media in item for item in report["package"]["relationships"]["problems"]))

    def test_missing_root_relationships(self) -> None:
        del self.parts["_rels/.rels"]
        self.write_parts()
        self.assert_failure("missing_office_document_relationship")

    def test_missing_office_document_relationship(self) -> None:
        self.edit_xml("_rels/.rels", lambda root: [
            root.remove(node) for node in list(root)
            if node.get("Type", "").endswith("/officeDocument")
        ])
        self.write_parts()
        self.assert_failure("missing_office_document_relationship")

    def test_duplicate_parts(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.path, "a") as archive:
                archive.writestr(SLIDE, self.parts[SLIDE])
        report = self.assert_failure("duplicate_package_parts")
        self.assertEqual(report["package"]["duplicate_parts"], [SLIDE])

    def test_equivalent_part_names(self) -> None:
        self.parts["ppt/slides/SLIDE1.xml"] = self.parts[SLIDE]
        self.write_parts()
        self.assert_failure("duplicate_opc_part_names")

    def test_malformed_slide_xml(self) -> None:
        self.parts[SLIDE] = b"<p:sld"
        self.write_parts()
        self.assert_failure("invalid_xml_part")

    def test_malformed_relationship_xml(self) -> None:
        self.parts[SLIDE_RELS] = b"<Relationships"
        self.write_parts()
        self.assert_failure("invalid_relationship_part")

    def test_duplicate_relationship_id(self) -> None:
        def duplicate(root):
            root[1].set("Id", root[0].get("Id"))
        self.edit_xml(SLIDE_RELS, duplicate)
        self.write_parts()
        self.assert_failure("invalid_internal_relationship")

    def test_crc_corruption(self) -> None:
        self.write_parts(compression=zipfile.ZIP_STORED)
        with zipfile.ZipFile(self.path) as archive:
            info = archive.getinfo(SLIDE)
        payload = bytearray(self.path.read_bytes())
        name_length, extra_length = struct.unpack_from("<HH", payload, info.header_offset + 26)
        offset = info.header_offset + 30 + name_length + extra_length
        payload[offset] ^= 1  # Do not update either stored CRC.
        self.path.write_bytes(payload)
        report = self.assert_failure("zip_integrity_failed")
        self.assertEqual(report["package"]["corrupt_member"], SLIDE)

    def corrupt_deflate_stream(self) -> None:
        with zipfile.ZipFile(self.path) as archive:
            info = archive.getinfo(SLIDE)
        payload = bytearray(self.path.read_bytes())
        name_length, extra_length = struct.unpack_from("<HH", payload, info.header_offset + 26)
        offset = info.header_offset + 30 + name_length + extra_length
        payload[offset] = (payload[offset] & ~7) | 7  # Reserved DEFLATE block type.
        self.path.write_bytes(payload)

    def test_invalid_deflate_stream_returns_report(self) -> None:
        self.corrupt_deflate_stream()
        report = self.assert_failure("zip_integrity_failed")
        self.assertEqual(report["package"]["zip_integrity"], "failed")

    def test_cli_reports_json_and_failure_exit_code(self) -> None:
        for failure in (None, "truncated", "missing-content-types", "invalid-deflate"):
            with self.subTest(failure=failure):
                self.write_parts()
                if failure == "truncated":
                    self.path.write_bytes(self.path.read_bytes()[:-22])
                elif failure == "missing-content-types":
                    content_types = self.parts.pop("[Content_Types].xml")
                    self.write_parts()
                    self.parts["[Content_Types].xml"] = content_types
                elif failure == "invalid-deflate":
                    self.corrupt_deflate_stream()
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / "pptx_delivery_check.py"), str(self.path)],
                    capture_output=True, text=True, timeout=30, check=False,
                )
                self.assertEqual(result.returncode, int(failure is not None), result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["status"] == "failed", failure is not None)


if __name__ == "__main__":
    unittest.main()
