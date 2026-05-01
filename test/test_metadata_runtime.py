"""Tests that metadata normalizers preserve the runtime_seconds field."""

import json
from pathlib import Path

from arm.services.metadata import _normalize_omdb

_FIXTURES = Path(__file__).parent / "fixtures" / "metadata"


def test_normalize_omdb_keeps_runtime():
    data = json.loads((_FIXTURES / "omdb_movie_with_runtime.json").read_text())
    result = _normalize_omdb(data)
    assert result["runtime_seconds"] == 8880  # 148 * 60


def test_normalize_omdb_runtime_na_returns_none():
    data = json.loads((_FIXTURES / "omdb_runtime_na.json").read_text())
    result = _normalize_omdb(data)
    assert result["runtime_seconds"] is None
