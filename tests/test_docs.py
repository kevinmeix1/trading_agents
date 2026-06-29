from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("reportlab")

_SPEC = importlib.util.spec_from_file_location(
    "generate_architecture_pdf",
    Path(__file__).resolve().parent.parent / "docs" / "generate_architecture_pdf.py",
)


def _load_module():
    module = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(module)
    return module


def test_architecture_pdf_builds(tmp_path):
    module = _load_module()
    out = module.build(tmp_path / "architecture.pdf")
    assert out.exists()
    # A valid, non-trivial PDF file.
    assert out.stat().st_size > 3000
    assert out.read_bytes()[:5] == b"%PDF-"
