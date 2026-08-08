#!/usr/bin/env python3
"""Content-free operational receipts for private runtime inputs."""

from __future__ import annotations

import hashlib


def content_receipt(value: str) -> str:
    """Return bounded non-content evidence suitable for operational logs."""
    payload = value.encode("utf-8", errors="replace")
    return f"sha256={hashlib.sha256(payload).hexdigest()} chars={len(value)}"


def exception_receipt(exc: BaseException) -> str:
    """Describe an exception without echoing its message, URL, or payload."""
    return f"type={type(exc).__name__} {content_receipt(str(exc))}"


def file_receipt(path: str) -> str:
    """Hash a local input without logging its path, basename, or bytes."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return f"sha256={digest.hexdigest()} bytes={size}"
