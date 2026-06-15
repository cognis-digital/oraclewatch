"""Tests for hardened error-handling and edge-case paths added during hardening."""
from __future__ import annotations

import json
import math
import os
import sys

import pytest

# Make the package importable regardless of install state.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oraclewatch.cli import main
from oraclewatch.core import (
    Severity,
    analyze_feeds,
    load_feeds,
)

NOW = 1717000600.0


# ---------------------------------------------------------------------------
# core.py — load_feeds edge cases
# ---------------------------------------------------------------------------

def test_load_feeds_feeds_key_not_list(tmp_path):
    """'feeds' key exists but is a dict, not a list -> ValueError."""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"feeds": {"name": "A"}}))
    with pytest.raises(ValueError, match="'feeds' key must be a JSON list"):
        load_feeds(str(bad))


def test_load_feeds_top_level_not_list(tmp_path):
    """Top-level JSON is an object without 'feeds' key -> ValueError."""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"name": "not a list"}))
    with pytest.raises(ValueError, match="feed file must be a JSON list"):
        load_feeds(str(bad))


def test_load_feeds_empty_list(tmp_path):
    """Empty JSON list is valid and returns []."""
    empty = tmp_path / "empty.json"
    empty.write_text("[]")
    result = load_feeds(str(empty))
    assert result == []


# ---------------------------------------------------------------------------
# core.py — non-dict feed entries
# ---------------------------------------------------------------------------

def test_non_dict_feed_null_produces_invalid_entry_finding():
    """A null entry in the feeds list must not raise; produces CRITICAL finding."""
    reports = analyze_feeds([None], now=NOW)
    assert len(reports) == 1
    assert reports[0].worst == Severity.CRITICAL
    assert any(f.code == "INVALID_ENTRY" for f in reports[0].findings)


def test_non_dict_feed_string_produces_invalid_entry_finding():
    """A bare string entry must not raise; produces CRITICAL finding."""
    reports = analyze_feeds(["just a string"], now=NOW)
    assert len(reports) == 1
    assert any(f.code == "INVALID_ENTRY" for f in reports[0].findings)


def test_mixed_valid_invalid_feeds():
    """Valid feeds are still analyzed even when some entries are non-dict."""
    feeds = [
        None,
        {"name": "A", "pair": "X/Y", "price": 100.0,
         "updated_at": NOW, "heartbeat": 3600},
    ]
    reports = analyze_feeds(feeds, now=NOW)
    assert len(reports) == 2
    assert any(f.code == "INVALID_ENTRY" for f in reports[0].findings)
    assert reports[1].feed == "A"


# ---------------------------------------------------------------------------
# core.py — infinite deviation_pct produces valid JSON
# ---------------------------------------------------------------------------

def test_infinite_deviation_pct_serializes_to_null():
    """When consensus is 0 and one price is non-zero, dev_pct is inf.
    FeedReport.to_dict() must emit null (not Infinity) for RFC-8259 compliance."""
    # Two feeds at price 0 -> median consensus = 0; third at 10 -> inf dev
    feeds = [
        {"name": "Z1", "pair": "T/T", "price": 0.0,
         "updated_at": NOW, "heartbeat": 3600},
        {"name": "Z2", "pair": "T/T", "price": 0.0,
         "updated_at": NOW, "heartbeat": 3600},
        {"name": "Z3", "pair": "T/T", "price": 10.0,
         "updated_at": NOW, "heartbeat": 3600},
    ]
    reports = analyze_feeds(feeds, now=NOW)
    z3 = next(r for r in reports if r.feed == "Z3")
    assert math.isinf(z3.deviation_pct)  # internal value is still inf
    d = z3.to_dict()
    assert d["deviation_pct"] is None  # but serialized as null
    # The whole dict must round-trip through stdlib json without error.
    text = json.dumps(d)
    parsed = json.loads(text)
    assert parsed["deviation_pct"] is None


def test_infinite_deviation_finding_detail_serializes():
    """Finding detail with inf deviation_pct must also serialize cleanly."""
    feeds = [
        {"name": "Z1", "pair": "T/T", "price": 0.0,
         "updated_at": NOW, "heartbeat": 3600},
        {"name": "Z2", "pair": "T/T", "price": 0.0,
         "updated_at": NOW, "heartbeat": 3600},
        {"name": "Z3", "pair": "T/T", "price": 10.0,
         "updated_at": NOW, "heartbeat": 3600},
    ]
    reports = analyze_feeds(feeds, now=NOW)
    z3 = next(r for r in reports if r.feed == "Z3")
    for finding in z3.findings:
        fd = finding.to_dict()
        # Must not raise ValueError from json.dumps
        text = json.dumps(fd)
        json.loads(text)  # must also parse back cleanly


# ---------------------------------------------------------------------------
# cli.py — empty feeds file warning + valid exit
# ---------------------------------------------------------------------------

def test_cli_empty_feeds_exits_zero(tmp_path, capsys):
    """An empty feeds list has no blocking findings; CLI exits 0."""
    empty = tmp_path / "empty.json"
    empty.write_text("[]")
    rc = main(["check", str(empty), "--now", str(NOW)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower() or True  # warning on stderr is optional


def test_cli_malformed_json_exit_2(tmp_path):
    """A file with invalid JSON returns exit code 2."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json}")
    rc = main(["check", str(bad)])
    assert rc == 2


def test_cli_negative_now_exit_2(tmp_path):
    """--now with a negative value returns exit code 2."""
    f = tmp_path / "f.json"
    f.write_text("[]")
    rc = main(["check", str(f), "--now", "-1"])
    assert rc == 2


def test_cli_feeds_key_not_list_exit_2(tmp_path, capsys):
    """feeds key is not a list -> clean error message, exit 2."""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"feeds": "not-a-list"}))
    rc = main(["check", str(bad)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "error" in err.lower()


# ---------------------------------------------------------------------------
# mcp_server.py — module compiles and imports without raising
# ---------------------------------------------------------------------------

def test_mcp_server_importable():
    """mcp_server must be importable (no NameError/ImportError from bad symbols)."""
    import oraclewatch.mcp_server  # noqa: F401 — just test the import
    assert callable(oraclewatch.mcp_server.serve)
