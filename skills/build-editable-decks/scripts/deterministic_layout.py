#!/usr/bin/env python3
"""Render typed deck IR into deterministic, editable SVG pages.

The engine is intentionally local-only. It writes into an external project
workspace, never into the Skill tree, and records only hashes and layout
metrics in its trace. User text stays in the project SVG deliverable and is not
copied into logs, tests, documentation, or release evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape, quoteattr


ENGINE_VERSION = "deckestra-layout/v1"
IR_SCHEMA = "deckestra-ir/v1"
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_PAGES = 100
MAX_TOTAL_TEXT = 100_000
REPAIR_SCALES = (1.0, 0.92, 0.84)
ALLOWED_LAYOUTS = {
    "cover",
    "section",
    "statement",
    "title-body",
    "two-column",
    "cards",
    "metrics",
    "process",
    "table",
    "bar-chart",
    "quote",
    "closing",
}
COLOR_RE = re.compile(r"#[0-9A-Fa-f]{6}\Z")
PAGE_ID_RE = re.compile(r"P[0-9]{2,3}\Z")
SLUG_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\Z")
SOURCE_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
FONT_RE = re.compile(r"[A-Za-z0-9\u0080-\uffff][A-Za-z0-9\u0080-\uffff ,.\-'\"]{0,119}\Z")

SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]
REPOSITORY_ROOT = SCRIPT_PATH.parents[3]


class LayoutContractError(ValueError):
    """Raised when typed IR or the output boundary is invalid."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _known_fields(value: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise LayoutContractError(f"{context}: unknown field(s): {', '.join(unknown)}")


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LayoutContractError(f"{context}: expected object")
    return value


def _list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise LayoutContractError(f"{context}: expected array")
    return value


def _text(value: Any, context: str, *, maximum: int, required: bool = False) -> str:
    if not isinstance(value, str):
        raise LayoutContractError(f"{context}: expected string")
    if required and not value.strip():
        raise LayoutContractError(f"{context}: must not be blank")
    if len(value) > maximum:
        raise LayoutContractError(f"{context}: exceeds {maximum} characters")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise LayoutContractError(f"{context}: contains a forbidden control character")
    return value


def _number(value: Any, context: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LayoutContractError(f"{context}: expected number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise LayoutContractError(f"{context}: expected {minimum}..{maximum}")
    return result


def _color(value: Any, context: str) -> str:
    text = _text(value, context, maximum=7, required=True)
    if not COLOR_RE.fullmatch(text):
        raise LayoutContractError(f"{context}: expected #RRGGBB")
    return text.upper()


def _font(value: Any, context: str) -> str:
    text = _text(value, context, maximum=120, required=True)
    if not FONT_RE.fullmatch(text):
        raise LayoutContractError(f"{context}: unsafe font-family value")
    return text


def _source_ids(value: Any, context: str, known_sources: set[str]) -> list[str]:
    if value is None:
        return []
    items = _list(value, context)
    if len(items) > 16:
        raise LayoutContractError(f"{context}: at most 16 source ids")
    result: list[str] = []
    for index, raw in enumerate(items):
        source_id = _text(raw, f"{context}[{index}]", maximum=64, required=True)
        if not SOURCE_ID_RE.fullmatch(source_id):
            raise LayoutContractError(f"{context}[{index}]: invalid source id")
        if source_id not in known_sources:
            raise LayoutContractError(f"{context}[{index}]: undeclared source id {source_id!r}")
        if source_id in result:
            raise LayoutContractError(f"{context}[{index}]: duplicate source id {source_id!r}")
        result.append(source_id)
    return result


def _text_list(value: Any, context: str, *, minimum: int, maximum: int, item_limit: int) -> list[str]:
    items = _list(value, context)
    if not minimum <= len(items) <= maximum:
        raise LayoutContractError(f"{context}: expected {minimum}..{maximum} items")
    return [
        _text(item, f"{context}[{index}]", maximum=item_limit, required=True)
        for index, item in enumerate(items)
    ]


def _validate_item(
    raw: Any,
    context: str,
    known_sources: set[str],
    *,
    allowed: set[str],
) -> dict[str, Any]:
    item = _object(raw, context)
    _known_fields(item, allowed | {"source_ids"}, context)
    result: dict[str, Any] = {}
    if "title" in item:
        result["title"] = _text(item["title"], f"{context}.title", maximum=220, required=True)
    if "body" in item:
        result["body"] = _text(item["body"], f"{context}.body", maximum=1800, required=True)
    if "bullets" in item:
        result["bullets"] = _text_list(item["bullets"], f"{context}.bullets", minimum=1, maximum=8, item_limit=500)
    if "value" in item:
        result["value"] = _text(item["value"], f"{context}.value", maximum=80, required=True)
    if "label" in item:
        result["label"] = _text(item["label"], f"{context}.label", maximum=180, required=True)
    if "detail" in item:
        result["detail"] = _text(item["detail"], f"{context}.detail", maximum=500, required=True)
    result["source_ids"] = _source_ids(item.get("source_ids"), f"{context}.source_ids", known_sources)
    return result


def validate_ir(raw: Any) -> dict[str, Any]:
    root = _object(raw, "root")
    _known_fields(root, {"schema", "canvas", "theme", "sources", "pages"}, "root")
    if root.get("schema") != IR_SCHEMA:
        raise LayoutContractError(f"root.schema: expected {IR_SCHEMA!r}")

    canvas_raw = _object(root.get("canvas", {}), "root.canvas")
    _known_fields(canvas_raw, {"width", "height"}, "root.canvas")
    width = _number(canvas_raw.get("width", 1280), "root.canvas.width", minimum=800, maximum=3840)
    height = _number(canvas_raw.get("height", 720), "root.canvas.height", minimum=600, maximum=2160)
    if not 1.2 <= width / height <= 2.0:
        raise LayoutContractError("root.canvas: aspect ratio must be between 1.2 and 2.0")

    theme_raw = _object(root.get("theme", {}), "root.theme")
    _known_fields(
        theme_raw,
        {
            "background", "panel", "primary", "accent", "text", "muted",
            "title_font", "body_font",
        },
        "root.theme",
    )
    theme_defaults = {
        "background": "#FFFFFF",
        "panel": "#F4F6F8",
        "primary": "#173B6C",
        "accent": "#E89B2C",
        "text": "#18212F",
        "muted": "#667085",
        "title_font": "Arial",
        "body_font": "Arial",
    }
    theme: dict[str, str] = {}
    for key, default in theme_defaults.items():
        value = theme_raw.get(key, default)
        theme[key] = _font(value, f"root.theme.{key}") if key.endswith("_font") else _color(value, f"root.theme.{key}")

    source_rows = _list(root.get("sources", []), "root.sources")
    if len(source_rows) > 500:
        raise LayoutContractError("root.sources: at most 500 sources")
    sources: list[dict[str, str]] = []
    known_sources: set[str] = set()
    for index, raw_source in enumerate(source_rows):
        context = f"root.sources[{index}]"
        source = _object(raw_source, context)
        _known_fields(source, {"id", "kind", "locator", "license"}, context)
        source_id = _text(source.get("id"), f"{context}.id", maximum=64, required=True)
        if not SOURCE_ID_RE.fullmatch(source_id):
            raise LayoutContractError(f"{context}.id: invalid source id")
        if source_id in known_sources:
            raise LayoutContractError(f"{context}.id: duplicate source id")
        kind = _text(source.get("kind"), f"{context}.kind", maximum=32, required=True)
        if kind not in {"input", "user", "calculated", "public", "licensed-asset"}:
            raise LayoutContractError(f"{context}.kind: unsupported kind")
        locator = _text(source.get("locator", ""), f"{context}.locator", maximum=1200)
        license_name = _text(source.get("license", ""), f"{context}.license", maximum=240)
        sources.append({"id": source_id, "kind": kind, "locator": locator, "license": license_name})
        known_sources.add(source_id)

    pages_raw = _list(root.get("pages"), "root.pages")
    if not 1 <= len(pages_raw) <= MAX_PAGES:
        raise LayoutContractError(f"root.pages: expected 1..{MAX_PAGES} pages")
    page_width = max(2, len(str(len(pages_raw))))
    pages: list[dict[str, Any]] = []
    total_text = 0
    page_fields = {
        "id", "slug", "layout", "title", "subtitle", "eyebrow", "body",
        "bullets", "columns", "cards", "metrics", "steps", "table", "chart",
        "quote", "attribution", "source_ids",
    }
    for index, raw_page in enumerate(pages_raw, start=1):
        context = f"root.pages[{index - 1}]"
        page = _object(raw_page, context)
        _known_fields(page, page_fields, context)
        expected_id = f"P{index:0{page_width}d}"
        page_id = _text(page.get("id"), f"{context}.id", maximum=4, required=True)
        if not PAGE_ID_RE.fullmatch(page_id) or page_id != expected_id:
            raise LayoutContractError(f"{context}.id: expected sequential id {expected_id!r}")
        slug = _text(page.get("slug"), f"{context}.slug", maximum=64, required=True)
        if not SLUG_RE.fullmatch(slug):
            raise LayoutContractError(f"{context}.slug: use lowercase ASCII letters, digits, and hyphens")
        layout = _text(page.get("layout"), f"{context}.layout", maximum=32, required=True)
        if layout not in ALLOWED_LAYOUTS:
            raise LayoutContractError(f"{context}.layout: unsupported layout {layout!r}")

        normalized: dict[str, Any] = {
            "id": page_id,
            "slug": slug,
            "layout": layout,
            "source_ids": _source_ids(page.get("source_ids"), f"{context}.source_ids", known_sources),
        }
        for key, maximum, required in (
            ("title", 500, True),
            ("subtitle", 900, False),
            ("eyebrow", 160, False),
            ("body", 4000, False),
            ("quote", 1800, False),
            ("attribution", 240, False),
        ):
            if key in page:
                normalized[key] = _text(page[key], f"{context}.{key}", maximum=maximum, required=required)
        if "title" not in normalized:
            raise LayoutContractError(f"{context}.title: required")
        if "bullets" in page:
            normalized["bullets"] = _text_list(page["bullets"], f"{context}.bullets", minimum=1, maximum=10, item_limit=600)

        if "columns" in page:
            raw_items = _list(page["columns"], f"{context}.columns")
            if len(raw_items) != 2:
                raise LayoutContractError(f"{context}.columns: expected exactly 2 columns")
            normalized["columns"] = [
                _validate_item(item, f"{context}.columns[{item_index}]", known_sources, allowed={"title", "body", "bullets"})
                for item_index, item in enumerate(raw_items)
            ]
        if "cards" in page:
            raw_items = _list(page["cards"], f"{context}.cards")
            if not 2 <= len(raw_items) <= 4:
                raise LayoutContractError(f"{context}.cards: expected 2..4 cards")
            normalized["cards"] = [
                _validate_item(item, f"{context}.cards[{item_index}]", known_sources, allowed={"title", "body", "bullets"})
                for item_index, item in enumerate(raw_items)
            ]
        if "metrics" in page:
            raw_items = _list(page["metrics"], f"{context}.metrics")
            if not 1 <= len(raw_items) <= 4:
                raise LayoutContractError(f"{context}.metrics: expected 1..4 metrics")
            normalized["metrics"] = [
                _validate_item(item, f"{context}.metrics[{item_index}]", known_sources, allowed={"value", "label", "detail"})
                for item_index, item in enumerate(raw_items)
            ]
            if any("value" not in item or "label" not in item for item in normalized["metrics"]):
                raise LayoutContractError(f"{context}.metrics: every metric needs value and label")
        if "steps" in page:
            raw_items = _list(page["steps"], f"{context}.steps")
            if not 2 <= len(raw_items) <= 5:
                raise LayoutContractError(f"{context}.steps: expected 2..5 steps")
            normalized["steps"] = [
                _validate_item(item, f"{context}.steps[{item_index}]", known_sources, allowed={"title", "body"})
                for item_index, item in enumerate(raw_items)
            ]
            if any("title" not in item for item in normalized["steps"]):
                raise LayoutContractError(f"{context}.steps: every step needs a title")
        if "table" in page:
            table_context = f"{context}.table"
            table = _object(page["table"], table_context)
            _known_fields(table, {"columns", "rows", "source_ids"}, table_context)
            columns = _text_list(table.get("columns"), f"{table_context}.columns", minimum=2, maximum=6, item_limit=120)
            raw_rows = _list(table.get("rows"), f"{table_context}.rows")
            if not 1 <= len(raw_rows) <= 12:
                raise LayoutContractError(f"{table_context}.rows: expected 1..12 rows")
            rows: list[list[str]] = []
            for row_index, raw_row in enumerate(raw_rows):
                row = _list(raw_row, f"{table_context}.rows[{row_index}]")
                if len(row) != len(columns):
                    raise LayoutContractError(f"{table_context}.rows[{row_index}]: expected {len(columns)} cells")
                rows.append([
                    _text(cell, f"{table_context}.rows[{row_index}][{cell_index}]", maximum=300, required=True)
                    for cell_index, cell in enumerate(row)
                ])
            normalized["table"] = {
                "columns": columns,
                "rows": rows,
                "source_ids": _source_ids(table.get("source_ids"), f"{table_context}.source_ids", known_sources),
            }
        if "chart" in page:
            chart_context = f"{context}.chart"
            chart = _object(page["chart"], chart_context)
            _known_fields(chart, {"categories", "values", "series_label", "source_ids"}, chart_context)
            categories = _text_list(chart.get("categories"), f"{chart_context}.categories", minimum=2, maximum=8, item_limit=80)
            raw_values = _list(chart.get("values"), f"{chart_context}.values")
            if len(raw_values) != len(categories):
                raise LayoutContractError(f"{chart_context}.values: expected {len(categories)} values")
            values = [
                _number(value, f"{chart_context}.values[{value_index}]", minimum=0, maximum=1e15)
                for value_index, value in enumerate(raw_values)
            ]
            if max(values) <= 0:
                raise LayoutContractError(f"{chart_context}.values: at least one value must be positive")
            normalized["chart"] = {
                "categories": categories,
                "values": values,
                "series_label": _text(chart.get("series_label", ""), f"{chart_context}.series_label", maximum=160),
                "source_ids": _source_ids(chart.get("source_ids"), f"{chart_context}.source_ids", known_sources),
            }

        requirements = {
            "two-column": "columns",
            "cards": "cards",
            "metrics": "metrics",
            "process": "steps",
            "table": "table",
            "bar-chart": "chart",
            "quote": "quote",
        }
        required_field = requirements.get(layout)
        if required_field and required_field not in normalized:
            raise LayoutContractError(f"{context}.{required_field}: required for layout {layout!r}")

        def count_text(value: Any) -> int:
            if isinstance(value, str):
                return len(value)
            if isinstance(value, list):
                return sum(count_text(item) for item in value)
            if isinstance(value, dict):
                return sum(count_text(item) for key, item in value.items() if key != "source_ids")
            return 0

        total_text += count_text(normalized)
        pages.append(normalized)

    if total_text > MAX_TOTAL_TEXT:
        raise LayoutContractError(f"root.pages: total text exceeds {MAX_TOTAL_TEXT} characters")

    return {
        "schema": IR_SCHEMA,
        "canvas": {"width": width, "height": height},
        "theme": theme,
        "sources": sources,
        "pages": pages,
    }


def load_ir(path: Path) -> tuple[dict[str, Any], str]:
    payload = path.read_bytes()
    if len(payload) > MAX_INPUT_BYTES:
        raise LayoutContractError(f"input exceeds {MAX_INPUT_BYTES} bytes")
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LayoutContractError(f"invalid UTF-8 JSON: {exc}") from exc
    return validate_ir(raw), _sha256_bytes(payload)


def _fmt(value: float) -> str:
    if abs(value - round(value)) < 1e-7:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _char_width(char: str, font_size: float, bold: bool = False) -> float:
    if char == "\t":
        factor = 1.28
    elif char.isspace():
        factor = 0.32
    elif unicodedata.east_asian_width(char) in {"W", "F"}:
        factor = 1.0
    elif char.isdigit():
        factor = 0.56
    elif char.isupper():
        factor = 0.62
    elif char.islower():
        factor = 0.53
    elif unicodedata.category(char).startswith("P"):
        factor = 0.42
    else:
        factor = 0.62
    return font_size * factor * (1.04 if bold else 1.0)


def _measure(text: str, font_size: float, bold: bool = False) -> float:
    return sum(_char_width(char, font_size, bold) for char in text)


TOKEN_RE = re.compile(r"\s+|[A-Za-z0-9]+(?:[-'’][A-Za-z0-9]+)*|.", re.DOTALL)


def wrap_text(text: str, font_size: float, max_width: float, *, bold: bool = False) -> list[str]:
    lines: list[str] = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for token in TOKEN_RE.findall(paragraph):
            token = " " if token.isspace() else token
            candidate = (current + token).rstrip() if current else token.lstrip()
            if current and _measure(candidate, font_size, bold) > max_width:
                lines.append(current.rstrip())
                current = token.lstrip()
            else:
                current = candidate
            if current and _measure(current, font_size, bold) > max_width:
                fragment = ""
                for char in current:
                    if fragment and _measure(fragment + char, font_size, bold) > max_width:
                        lines.append(fragment)
                        fragment = char
                    else:
                        fragment += char
                current = fragment
        lines.append(current.rstrip())
    return lines or [""]


@dataclass(frozen=True)
class Tokens:
    width: float
    height: float
    sx: float
    sy: float
    unit: float
    margin_x: float
    margin_top: float
    margin_bottom: float
    title_y: float
    title_h: float
    content_y: float
    content_h: float

    @classmethod
    def from_canvas(cls, width: float, height: float) -> "Tokens":
        sx = width / 1280.0
        sy = height / 720.0
        unit = min(sx, sy)
        margin_x = 72 * sx
        margin_top = 48 * sy
        margin_bottom = 48 * sy
        title_y = margin_top
        title_h = 94 * sy
        content_y = 166 * sy
        content_h = height - content_y - margin_bottom
        return cls(width, height, sx, sy, unit, margin_x, margin_top, margin_bottom, title_y, title_h, content_y, content_h)


@dataclass
class RenderContext:
    page_id: str
    theme: dict[str, str]
    tokens: Tokens
    attempt: int
    issues: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)

    @property
    def scale(self) -> float:
        return REPAIR_SCALES[self.attempt]

    @property
    def gap_scale(self) -> float:
        return (1.0, 0.88, 0.76)[self.attempt]

    def text(
        self,
        *,
        key: str,
        value: str,
        x: float,
        y: float,
        width: float,
        height: float,
        font_size: float,
        color: str,
        bold: bool = False,
        family: str | None = None,
        align: str = "start",
        line_height: float = 1.3,
    ) -> str:
        actual_size = max(12 * self.tokens.unit, font_size * self.tokens.unit * self.scale)
        actual_line_height = actual_size * line_height
        lines = wrap_text(value, actual_size, width, bold=bold)
        needed_height = len(lines) * actual_line_height
        max_lines = max(1, int((height + 1e-6) // actual_line_height))
        overflow = needed_height > height + 0.5
        if overflow:
            self.issues.append({
                "page_id": self.page_id,
                "code": "text-overflow",
                "element": key,
                "line_count": len(lines),
                "max_lines": max_lines,
                "needed_height": round(needed_height, 2),
                "box_height": round(height, 2),
            })
        self.metrics.append({
            "element": key,
            "characters": len(value),
            "lines": len(lines),
            "font_size": round(actual_size, 2),
            "box": [round(x, 2), round(y, 2), round(width, 2), round(height, 2)],
            "overflow": overflow,
        })
        anchor = {"start": "start", "middle": "middle", "end": "end"}[align]
        text_x = x if align == "start" else (x + width / 2 if align == "middle" else x + width)
        attrs = [
            f"x={quoteattr(_fmt(text_x))}",
            f"y={quoteattr(_fmt(y + actual_size))}",
            f"font-size={quoteattr(_fmt(actual_size))}",
            f"fill={quoteattr(color)}",
            f"text-anchor={quoteattr(anchor)}",
        ]
        if bold:
            attrs.append('font-weight="700"')
        attrs.append(f"font-family={quoteattr(family or self.theme['body_font'])}")
        positioned_lines = "".join(
            f'<tspan x={quoteattr(_fmt(text_x))} dy={quoteattr(_fmt(0 if index == 0 else actual_line_height))}>{escape(line)}</tspan>'
            for index, line in enumerate(lines)
        )
        return f"<text {' '.join(attrs)}>{positioned_lines}</text>"


def _source_attr(value: dict[str, Any]) -> str:
    source_ids = value.get("source_ids", [])
    if not source_ids:
        return ""
    return f" data-deckestra-source-ids={quoteattr(','.join(source_ids))}"


def _group(
    group_id: str,
    bounds: tuple[float, float, float, float],
    body: Iterable[str],
    source: dict[str, Any] | None = None,
    attributes: dict[str, str] | None = None,
) -> str:
    x, y, width, height = bounds
    source_attr = _source_attr(source or {})
    extra_attrs = "".join(
        f" {name}={quoteattr(value)}"
        for name, value in sorted((attributes or {}).items())
    )
    payload = "".join(body)
    return (
        f'<g id={quoteattr(group_id)} data-pptx-bounds={quoteattr(" ".join(_fmt(v) for v in bounds))}{source_attr}{extra_attrs}>'
        f"{payload}</g>"
    )


def _metadata(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f'<metadata type="application/json">{escape(encoded)}</metadata>'


def _header(ctx: RenderContext, page: dict[str, Any]) -> str:
    t = ctx.tokens
    title = ctx.text(
        key="title", value=page["title"], x=t.margin_x, y=t.title_y,
        width=t.width - 2 * t.margin_x, height=t.title_h,
        font_size=40, color=ctx.theme["text"], bold=True,
        family=ctx.theme["title_font"], line_height=1.15,
    )
    accent_y = t.title_y + t.title_h - 8 * t.sy
    accent = f'<rect x={quoteattr(_fmt(t.margin_x))} y={quoteattr(_fmt(accent_y))} width={quoteattr(_fmt(68 * t.sx))} height={quoteattr(_fmt(5 * t.sy))} rx={quoteattr(_fmt(2.5 * t.unit))} fill={quoteattr(ctx.theme["accent"])} />'
    return _group("header", (t.margin_x, t.title_y, t.width - 2 * t.margin_x, t.title_h), (title, accent), page)


def _body_and_bullets(ctx: RenderContext, page: dict[str, Any], x: float, y: float, width: float, height: float, key: str) -> str:
    parts: list[str] = []
    body = page.get("body", "")
    bullets = page.get("bullets", [])
    gap = 18 * ctx.tokens.sy * ctx.gap_scale
    body_height = height * (0.36 if body and bullets else 1.0)
    if body:
        parts.append(ctx.text(
            key=f"{key}.body", value=body, x=x, y=y, width=width,
            height=body_height if bullets else height, font_size=24,
            color=ctx.theme["text"], line_height=1.45,
        ))
    if bullets:
        bullet_y = y + (body_height + gap if body else 0)
        available = height - (bullet_y - y)
        per_item = available / len(bullets)
        for index, bullet in enumerate(bullets):
            item_y = bullet_y + index * per_item
            radius = 4.5 * ctx.tokens.unit
            parts.append(f'<circle cx={quoteattr(_fmt(x + radius))} cy={quoteattr(_fmt(item_y + 15 * ctx.tokens.unit))} r={quoteattr(_fmt(radius))} fill={quoteattr(ctx.theme["accent"])} />')
            parts.append(ctx.text(
                key=f"{key}.bullet-{index + 1}", value=bullet,
                x=x + 24 * ctx.tokens.sx, y=item_y,
                width=width - 24 * ctx.tokens.sx, height=max(1, per_item - 5 * ctx.tokens.sy),
                font_size=22, color=ctx.theme["text"], line_height=1.35,
            ))
    return "".join(parts)


def _card(ctx: RenderContext, item: dict[str, Any], index: int, bounds: tuple[float, float, float, float], prefix: str) -> str:
    x, y, width, height = bounds
    pad_x = 24 * ctx.tokens.sx * ctx.gap_scale
    pad_y = 22 * ctx.tokens.sy * ctx.gap_scale
    title_height = min(84 * ctx.tokens.sy, height * 0.28)
    body = [
        f'<rect x={quoteattr(_fmt(x))} y={quoteattr(_fmt(y))} width={quoteattr(_fmt(width))} height={quoteattr(_fmt(height))} rx={quoteattr(_fmt(18 * ctx.tokens.unit))} fill={quoteattr(ctx.theme["panel"])} />',
    ]
    if item.get("title"):
        body.append(ctx.text(
            key=f"{prefix}-{index}.title", value=item["title"],
            x=x + pad_x, y=y + pad_y, width=width - 2 * pad_x, height=title_height,
            font_size=26, color=ctx.theme["primary"], bold=True,
            family=ctx.theme["title_font"], line_height=1.2,
        ))
    content_y = y + pad_y + (title_height if item.get("title") else 0)
    content_h = y + height - pad_y - content_y
    body.append(_body_and_bullets(ctx, item, x + pad_x, content_y, width - 2 * pad_x, max(1, content_h), f"{prefix}-{index}"))
    return _group(f"{prefix}-{index}", bounds, body, item)


def render_page(page: dict[str, Any], theme: dict[str, str], tokens: Tokens, attempt: int) -> tuple[bytes, list[dict[str, Any]], list[dict[str, Any]]]:
    ctx = RenderContext(page_id=page["id"], theme=theme, tokens=tokens, attempt=attempt)
    t = tokens
    elements: list[str] = [
        f'<rect id="background" data-pptx-role="background" x="0" y="0" width={quoteattr(_fmt(t.width))} height={quoteattr(_fmt(t.height))} fill={quoteattr(theme["background"])} />'
    ]
    layout = page["layout"]

    if layout in {"cover", "section", "statement", "quote", "closing"}:
        accent_width = 12 * t.sx
        elements.append(f'<rect id="accent-rail" data-pptx-role="decoration" x="0" y="0" width={quoteattr(_fmt(accent_width))} height={quoteattr(_fmt(t.height))} fill={quoteattr(theme["accent"])} />')
        box_x = 126 * t.sx
        box_w = t.width - box_x - 110 * t.sx
        if layout == "quote":
            quote_value = page["quote"]
            quote_svg = ctx.text(
                key="quote", value=quote_value, x=box_x, y=170 * t.sy,
                width=box_w, height=300 * t.sy, font_size=38,
                color=theme["text"], bold=True, family=theme["title_font"], line_height=1.3,
            )
            attribution = page.get("attribution", "")
            attrib_svg = ctx.text(
                key="attribution", value=attribution, x=box_x, y=515 * t.sy,
                width=box_w, height=80 * t.sy, font_size=22,
                color=theme["muted"], line_height=1.3,
            ) if attribution else ""
            elements.append(_group("quote", (box_x, 150 * t.sy, box_w, 450 * t.sy), (quote_svg, attrib_svg), page))
        else:
            title_size = 56 if layout in {"cover", "closing"} else 48
            title_y = 190 * t.sy if layout in {"cover", "closing"} else 220 * t.sy
            title_h = 210 * t.sy
            title_svg = ctx.text(
                key="title", value=page["title"], x=box_x, y=title_y,
                width=box_w, height=title_h, font_size=title_size,
                color=theme["text"], bold=True, family=theme["title_font"], line_height=1.16,
            )
            subtitle = page.get("subtitle") or page.get("body", "")
            subtitle_svg = ctx.text(
                key="subtitle", value=subtitle, x=box_x, y=title_y + title_h + 18 * t.sy,
                width=box_w, height=135 * t.sy, font_size=24,
                color=theme["muted"], line_height=1.4,
            ) if subtitle else ""
            eyebrow = page.get("eyebrow", "")
            eyebrow_svg = ctx.text(
                key="eyebrow", value=eyebrow, x=box_x, y=112 * t.sy,
                width=box_w, height=48 * t.sy, font_size=18,
                color=theme["primary"], bold=True, line_height=1.2,
            ) if eyebrow else ""
            elements.append(_group("hero", (box_x, 100 * t.sy, box_w, 520 * t.sy), (eyebrow_svg, title_svg, subtitle_svg), page))
    else:
        elements.append(_header(ctx, page))
        cx = t.margin_x
        cy = t.content_y
        cw = t.width - 2 * t.margin_x
        ch = t.content_h

        if layout == "title-body":
            content = _body_and_bullets(ctx, page, cx, cy, cw, ch, "content")
            elements.append(_group("content", (cx, cy, cw, ch), (content,), page))

        elif layout == "two-column":
            gap = 28 * t.sx * ctx.gap_scale
            column_width = (cw - gap) / 2
            for index, item in enumerate(page["columns"], start=1):
                x = cx + (index - 1) * (column_width + gap)
                elements.append(_card(ctx, item, index, (x, cy, column_width, ch), "column"))

        elif layout == "cards":
            cards = page["cards"]
            gap_x = 24 * t.sx * ctx.gap_scale
            gap_y = 22 * t.sy * ctx.gap_scale
            columns = 2 if len(cards) == 4 else len(cards)
            rows = 2 if len(cards) == 4 else 1
            card_w = (cw - gap_x * (columns - 1)) / columns
            card_h = (ch - gap_y * (rows - 1)) / rows
            for offset, item in enumerate(cards):
                row = offset // columns
                col = offset % columns
                bounds = (cx + col * (card_w + gap_x), cy + row * (card_h + gap_y), card_w, card_h)
                elements.append(_card(ctx, item, offset + 1, bounds, "card"))

        elif layout == "metrics":
            metrics = page["metrics"]
            gap = 22 * t.sx * ctx.gap_scale
            card_w = (cw - gap * (len(metrics) - 1)) / len(metrics)
            for index, item in enumerate(metrics, start=1):
                x = cx + (index - 1) * (card_w + gap)
                pad = 22 * t.sx * ctx.gap_scale
                parts = [
                    f'<rect x={quoteattr(_fmt(x))} y={quoteattr(_fmt(cy))} width={quoteattr(_fmt(card_w))} height={quoteattr(_fmt(ch))} rx={quoteattr(_fmt(18 * t.unit))} fill={quoteattr(theme["panel"])} />',
                    ctx.text(key=f"metric-{index}.value", value=item["value"], x=x + pad, y=cy + 58 * t.sy, width=card_w - 2 * pad, height=105 * t.sy, font_size=48, color=theme["primary"], bold=True, family=theme["title_font"], line_height=1.1),
                    ctx.text(key=f"metric-{index}.label", value=item["label"], x=x + pad, y=cy + 200 * t.sy, width=card_w - 2 * pad, height=105 * t.sy, font_size=24, color=theme["text"], bold=True, line_height=1.25),
                ]
                if item.get("detail"):
                    parts.append(ctx.text(key=f"metric-{index}.detail", value=item["detail"], x=x + pad, y=cy + 330 * t.sy, width=card_w - 2 * pad, height=ch - 350 * t.sy, font_size=19, color=theme["muted"], line_height=1.35))
                elements.append(_group(f"metric-{index}", (x, cy, card_w, ch), parts, item))

        elif layout == "process":
            steps = page["steps"]
            gap = 18 * t.sx * ctx.gap_scale
            step_w = (cw - gap * (len(steps) - 1)) / len(steps)
            for index, item in enumerate(steps, start=1):
                x = cx + (index - 1) * (step_w + gap)
                marker_r = 26 * t.unit
                parts = [
                    f'<circle cx={quoteattr(_fmt(x + step_w / 2))} cy={quoteattr(_fmt(cy + marker_r))} r={quoteattr(_fmt(marker_r))} fill={quoteattr(theme["primary"])} />',
                    ctx.text(key=f"step-{index}.number", value=str(index), x=x, y=cy + 8 * t.sy, width=step_w, height=42 * t.sy, font_size=22, color="#FFFFFF", bold=True, align="middle", line_height=1.0),
                    ctx.text(key=f"step-{index}.title", value=item["title"], x=x + 8 * t.sx, y=cy + 86 * t.sy, width=step_w - 16 * t.sx, height=95 * t.sy, font_size=24, color=theme["text"], bold=True, align="middle", line_height=1.25),
                ]
                if item.get("body"):
                    parts.append(ctx.text(key=f"step-{index}.body", value=item["body"], x=x + 8 * t.sx, y=cy + 205 * t.sy, width=step_w - 16 * t.sx, height=ch - 215 * t.sy, font_size=18, color=theme["muted"], align="middle", line_height=1.35))
                if index < len(steps):
                    arrow_y = cy + marker_r
                    parts.append(f'<path d={quoteattr(f"M {_fmt(x + step_w - 4 * t.sx)} {_fmt(arrow_y)} H {_fmt(x + step_w + gap - 6 * t.sx)}")} fill="none" stroke={quoteattr(theme["accent"])} stroke-width={quoteattr(_fmt(4 * t.unit))} stroke-linecap="round" />')
                elements.append(_group(f"step-{index}", (x, cy, step_w, ch), parts, item))

        elif layout == "table":
            table = page["table"]
            columns = table["columns"]
            rows = table["rows"]
            row_h = ch / (len(rows) + 1)
            col_w = cw / len(columns)
            min_row_h = 34 * t.unit * ctx.scale
            if row_h < min_row_h:
                ctx.issues.append({"page_id": page["id"], "code": "table-overflow", "element": "table", "rows": len(rows), "row_height": round(row_h, 2), "minimum_row_height": round(min_row_h, 2)})
            native_table = {
                "x": cx,
                "y": cy,
                "width": cw,
                "height": ch,
                "columns": columns,
                "rows": rows,
                "strict_grid": True,
                "header_rows": 1,
                "style": {
                    "font_family": theme["body_font"],
                    "font_size": 17 * t.unit * ctx.scale,
                    "header_font_size": 18 * t.unit * ctx.scale,
                    "band_row": False,
                },
            }
            parts: list[str] = [
                _metadata(native_table),
                f'<rect x={quoteattr(_fmt(cx))} y={quoteattr(_fmt(cy))} width={quoteattr(_fmt(cw))} height={quoteattr(_fmt(ch))} rx={quoteattr(_fmt(12 * t.unit))} fill={quoteattr(theme["panel"])} />',
            ]
            for col_index, column in enumerate(columns):
                x = cx + col_index * col_w
                parts.append(ctx.text(key=f"table.header-{col_index + 1}", value=column, x=x + 12 * t.sx, y=cy + 6 * t.sy, width=col_w - 24 * t.sx, height=row_h - 10 * t.sy, font_size=18, color=theme["primary"], bold=True, line_height=1.2))
            for row_index, row in enumerate(rows):
                y = cy + (row_index + 1) * row_h
                parts.append(f'<line x1={quoteattr(_fmt(cx))} y1={quoteattr(_fmt(y))} x2={quoteattr(_fmt(cx + cw))} y2={quoteattr(_fmt(y))} stroke="#D0D5DD" stroke-width={quoteattr(_fmt(t.unit))} />')
                for col_index, cell in enumerate(row):
                    x = cx + col_index * col_w
                    parts.append(ctx.text(key=f"table.r{row_index + 1}c{col_index + 1}", value=cell, x=x + 12 * t.sx, y=y + 5 * t.sy, width=col_w - 24 * t.sx, height=row_h - 9 * t.sy, font_size=17, color=theme["text"], line_height=1.2))
            elements.append(_group(
                "table", (cx, cy, cw, ch), parts, table,
                attributes={"data-pptx-replace-with": "table"},
            ))

        elif layout == "bar-chart":
            chart = page["chart"]
            categories = chart["categories"]
            values = chart["values"]
            max_value = max(values)
            left = cx + 96 * t.sx
            top = cy + 18 * t.sy
            chart_w = cw - 130 * t.sx
            chart_h = ch - 92 * t.sy
            gap = 16 * t.sx
            bar_w = (chart_w - gap * (len(values) - 1)) / len(values)
            native_chart = {
                "x": cx,
                "y": cy,
                "width": cw,
                "height": ch,
                "type": "column",
                "categories": categories,
                "series": [{
                    "name": chart.get("series_label") or "Value",
                    "values": values,
                }],
                "data_labels": True,
                "style": {
                    "colors": [theme["primary"]],
                    "chart_area_fill": theme["background"],
                    "plot_area_fill": theme["background"],
                    "text_color": theme["text"],
                    "axis_color": theme["muted"],
                    "grid_color": "#D0D5DD",
                    "font_family": theme["body_font"],
                    "axis_font_size": 15 * t.unit * ctx.scale,
                },
            }
            parts = [
                _metadata(native_chart),
                f'<line x1={quoteattr(_fmt(left))} y1={quoteattr(_fmt(top + chart_h))} x2={quoteattr(_fmt(left + chart_w))} y2={quoteattr(_fmt(top + chart_h))} stroke={quoteattr(theme["muted"])} stroke-width={quoteattr(_fmt(1.5 * t.unit))} />'
            ]
            for index, (category, value) in enumerate(zip(categories, values), start=1):
                x = left + (index - 1) * (bar_w + gap)
                bar_h = chart_h * (value / max_value)
                y = top + chart_h - bar_h
                parts.append(f'<rect x={quoteattr(_fmt(x))} y={quoteattr(_fmt(y))} width={quoteattr(_fmt(bar_w))} height={quoteattr(_fmt(bar_h))} rx={quoteattr(_fmt(5 * t.unit))} fill={quoteattr(theme["primary"])} />')
                parts.append(ctx.text(key=f"chart.value-{index}", value=f"{value:g}", x=x, y=max(top - 2 * t.sy, y - 36 * t.sy), width=bar_w, height=34 * t.sy, font_size=16, color=theme["text"], bold=True, align="middle", line_height=1.0))
                parts.append(ctx.text(key=f"chart.category-{index}", value=category, x=x - 4 * t.sx, y=top + chart_h + 12 * t.sy, width=bar_w + 8 * t.sx, height=62 * t.sy, font_size=15, color=theme["muted"], align="middle", line_height=1.2))
            elements.append(_group(
                "chart", (cx, cy, cw, ch), parts, chart,
                attributes={"data-pptx-replace-with": "chart"},
            ))

    page_role = {
        "cover": "cover",
        "section": "section",
        "closing": "ending",
    }.get(layout, "content")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(t.width)} {_fmt(t.height)}" '
        f'font-family={quoteattr(theme["body_font"])} data-pptx-page-role={quoteattr(page_role)}>'
        + "".join(elements)
        + "</svg>\n"
    ).encode("utf-8")
    return svg, ctx.issues, ctx.metrics


def render_deck(ir: dict[str, Any], repair_budget: int) -> tuple[dict[str, bytes], dict[str, Any]]:
    if repair_budget not in {0, 1, 2}:
        raise LayoutContractError("repair budget must be 0, 1, or 2")
    tokens = Tokens.from_canvas(ir["canvas"]["width"], ir["canvas"]["height"])
    width = max(2, len(str(len(ir["pages"]))))
    attempts: list[dict[str, Any]] = []
    final_outputs: dict[str, bytes] = {}
    final_metrics: dict[str, list[dict[str, Any]]] = {}
    for attempt in range(repair_budget + 1):
        outputs: dict[str, bytes] = {}
        issues: list[dict[str, Any]] = []
        page_metrics: dict[str, list[dict[str, Any]]] = {}
        for index, page in enumerate(ir["pages"], start=1):
            svg, page_issues, metrics = render_page(page, ir["theme"], tokens, attempt)
            filename = f"{index:0{width}d}_{page['slug']}.svg"
            outputs[filename] = svg
            issues.extend(page_issues)
            page_metrics[page["id"]] = metrics
        issues.sort(key=lambda issue: (issue["page_id"], issue["code"], issue["element"]))
        attempts.append({
            "attempt": attempt,
            "font_scale": REPAIR_SCALES[attempt],
            "gap_scale": (1.0, 0.88, 0.76)[attempt],
            "issues": issues,
        })
        final_outputs = outputs
        final_metrics = page_metrics
        if not issues:
            break

    passed = not attempts[-1]["issues"]
    trace = {
        "engine": ENGINE_VERSION,
        "schema": IR_SCHEMA,
        "status": "passed" if passed else "failed",
        "repair_budget": repair_budget,
        "attempts": attempts,
        "page_metrics": final_metrics,
        "pages": [
            {"id": page["id"], "layout": page["layout"]}
            for page in ir["pages"]
        ],
        "source_count": len(ir["sources"]),
    }
    return (final_outputs if passed else {}), trace


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _relative_inside(project: Path, path: Path, context: str) -> Path:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project)
    except ValueError as exc:
        raise LayoutContractError(f"{context}: path must stay inside the project workspace") from exc


def require_external_project(project: Path) -> Path:
    resolved = project.resolve()
    if not resolved.is_dir():
        raise LayoutContractError(f"project directory not found: {resolved}")
    try:
        resolved.relative_to(REPOSITORY_ROOT)
    except ValueError:
        return resolved
    raise LayoutContractError("project workspace must be outside the Deckestra source repository")


def _verified_previous_outputs(project: Path) -> dict[str, str]:
    trace_path = project / "validation" / "layout_trace.json"
    if not trace_path.is_file():
        return {}
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if trace.get("engine") != ENGINE_VERSION or trace.get("status") != "passed":
        return {}
    result: dict[str, str] = {}
    for row in trace.get("outputs", []):
        if not isinstance(row, dict):
            return {}
        relative = row.get("path")
        digest = row.get("sha256")
        if not isinstance(relative, str) or not isinstance(digest, str):
            return {}
        if not relative.startswith("svg_output/") or Path(relative).name != relative.split("/", 1)[1]:
            return {}
        path = project / relative
        if not path.is_file() or _sha256_file(path) != digest:
            return {}
        result[relative] = digest
    return result


def _write_success_outputs(project: Path, outputs: dict[str, bytes], trace: dict[str, Any], *, replace_managed: bool) -> None:
    output_dir = project / "svg_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_files = sorted(path for path in output_dir.iterdir() if path.is_file())
    existing_relatives = {f"svg_output/{path.name}" for path in existing_files}
    planned_relatives = {f"svg_output/{name}" for name in outputs}
    previous = _verified_previous_outputs(project)
    if existing_files:
        if set(previous) != existing_relatives:
            raise LayoutContractError("svg_output contains files not bound to the previous deterministic layout trace")
        if existing_relatives != planned_relatives and not replace_managed:
            raise LayoutContractError("page roster changed; rerun with --replace-managed after reviewing the managed output set")

    validation_dir = project / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".layout-stage-", dir=validation_dir) as temporary:
        staging = Path(temporary)
        for name, payload in outputs.items():
            (staging / name).write_bytes(payload)
        for name in sorted(outputs):
            os.replace(staging / name, output_dir / name)

    if replace_managed:
        stale = existing_relatives - planned_relatives
        for relative in sorted(stale):
            (project / relative).unlink()

    trace["outputs"] = [
        {
            "path": f"svg_output/{name}",
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        }
        for name, payload in sorted(outputs.items())
    ]
    _atomic_write(project / "validation" / "layout_trace.json", _canonical_json(trace))


def execute(
    project: Path,
    input_path: Path,
    *,
    repair_budget: int = 2,
    check_only: bool = False,
    replace_managed: bool = False,
) -> dict[str, Any]:
    project = require_external_project(project)
    input_path = input_path if input_path.is_absolute() else project / input_path
    input_relative = _relative_inside(project, input_path, "input")
    if not input_path.is_file():
        raise LayoutContractError(f"input file not found: {input_relative.as_posix()}")
    ir, input_hash = load_ir(input_path)
    outputs, trace = render_deck(ir, repair_budget)
    trace["input"] = {"path": input_relative.as_posix(), "sha256": input_hash}
    if check_only:
        trace["outputs"] = [
            {"path": f"svg_output/{name}", "bytes": len(payload), "sha256": _sha256_bytes(payload)}
            for name, payload in sorted(outputs.items())
        ]
        return trace
    if trace["status"] != "passed":
        trace["outputs"] = []
        _atomic_write(project / "validation" / "layout_trace.failed.json", _canonical_json(trace))
        return trace
    _write_success_outputs(project, outputs, trace, replace_managed=replace_managed)
    return trace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render deckestra-ir/v1 into deterministic editable SVG pages."
    )
    parser.add_argument("project", type=Path, help="External project workspace")
    parser.add_argument("--input", type=Path, default=Path("deck_ir.json"), help="IR path inside the project")
    parser.add_argument("--repair-budget", type=int, choices=(0, 1, 2), default=2, help="Maximum deterministic repair attempts")
    parser.add_argument("--check-only", action="store_true", help="Validate and render in memory without writing")
    parser.add_argument("--replace-managed", action="store_true", help="Replace a changed roster only when prior outputs still match their trace")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        trace = execute(
            args.project,
            args.input,
            repair_budget=args.repair_budget,
            check_only=args.check_only,
            replace_managed=args.replace_managed,
        )
    except (OSError, LayoutContractError) as exc:
        print(f"[ERROR] deterministic layout: {exc}", file=sys.stderr)
        return 2
    status = trace["status"]
    attempts = len(trace["attempts"])
    if status != "passed":
        issue_count = len(trace["attempts"][-1]["issues"])
        print(f"[FAIL] deterministic layout: {issue_count} unresolved issue(s) after {attempts} attempt(s)", file=sys.stderr)
        return 1
    print(f"[PASS] deterministic layout: {len(trace['pages'])} page(s), {attempts} attempt(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
