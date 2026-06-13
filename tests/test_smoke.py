"""Smoke tests for ORACLEWATCH. No network. Runs against the demo file."""

import json
import os
import subprocess
import sys


from oraclewatch import (
    TOOL_NAME,
    TOOL_VERSION,
    Severity,
    analyze_feeds,
    consensus_price,
    has_blocking,
    load_feeds,
)
from oraclewatch.cli import main

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEMO = os.path.join(ROOT, "demos", "01-basic", "feeds.json")
NOW = 1717000600.0


def _reports():
    feeds = load_feeds(DEMO)
    return {r.feed: r for r in analyze_feeds(feeds, now=NOW)}


def test_metadata():
    assert TOOL_NAME == "oraclewatch"
    assert TOOL_VERSION.count(".") == 2


def test_demo_loads():
    feeds = load_feeds(DEMO)
    assert isinstance(feeds, list)
    assert len(feeds) == 6


def test_consensus_is_median():
    feeds = load_feeds(DEMO)
    # ETH peers: 3001.25, 3000.00, 2999.40 -> median 3000.00
    assert consensus_price(feeds, "ETH/USD") == 3000.00
    # BTC peers: 68500, 65420 -> median 66960
    assert consensus_price(feeds, "BTC/USD") == 66960.0


def test_healthy_feed_has_no_blocking():
    rep = _reports()["ETH/USD chainlink"]
    codes = {f.code for f in rep.findings}
    # ETH chainlink is on-consensus and fresh; only allowed info-level codes
    assert rep.worst < Severity.WARNING
    assert "STALE" not in codes
    assert "DEVIATION" not in codes


def test_stale_feed_detected():
    rep = _reports()["ETH/USD dex-twap"]
    codes = {f.code for f in rep.findings}
    assert "STALE" in codes
    stale = next(f for f in rep.findings if f.code == "STALE")
    # 7200s old vs 3600s heartbeat -> over 2x -> CRITICAL
    assert stale.severity == Severity.CRITICAL
    assert stale.detail["age_seconds"] == 7200


def test_deviation_detected():
    rep = _reports()["BTC/USD chainlink"]
    codes = {f.code for f in rep.findings}
    assert "DEVIATION" in codes
    assert rep.deviation_pct is not None and rep.deviation_pct > 2.0


def test_frozen_and_round_stalled_detected():
    rep = _reports()["LINK/USD chainlink"]
    codes = {f.code for f in rep.findings}
    assert "FROZEN" in codes
    assert "ROUND_STALLED" in codes
    assert "CHEAP_TO_ATTACK" in codes


def test_round_regression_detected():
    feeds = [
        {"name": "A", "pair": "X/Y", "price": 10, "updated_at": NOW,
         "heartbeat": 3600, "round_id": 5, "prev_round_id": 9},
    ]
    rep = analyze_feeds(feeds, now=NOW)[0]
    assert any(f.code == "ROUND_REGRESSION" and f.severity == Severity.CRITICAL
               for f in rep.findings)


def test_has_blocking_true_on_demo():
    feeds = load_feeds(DEMO)
    reports = analyze_feeds(feeds, now=NOW)
    assert has_blocking(reports) is True


def test_cli_exit_nonzero_with_findings(capsys):
    rc = main(["check", DEMO, "--now", str(NOW)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "STALE" in out
    assert "DEVIATION" in out


def test_cli_json_is_valid_and_blocking(capsys):
    rc = main(["--format", "json", "check", DEMO, "--now", str(NOW)])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "oraclewatch"
    assert payload["blocking"] is True
    assert payload["feed_count"] == 6
    assert len(payload["reports"]) == 6


def test_cli_clean_feed_exit_zero(tmp_path, capsys):
    clean = tmp_path / "clean.json"
    clean.write_text(json.dumps([
        {"name": "A", "pair": "X/Y", "price": 100.0, "updated_at": NOW,
         "heartbeat": 3600, "deviation_threshold": 0.5,
         "round_id": 2, "prev_round_id": 1, "prev_price": 99.5,
         "liquidity_usd": 50000000},
        {"name": "B", "pair": "X/Y", "price": 100.1, "updated_at": NOW,
         "heartbeat": 3600, "deviation_threshold": 0.5,
         "round_id": 2, "prev_round_id": 1, "prev_price": 99.6,
         "liquidity_usd": 50000000},
    ]))
    rc = main(["check", str(clean), "--now", str(NOW)])
    assert rc == 0
    assert "healthy" in capsys.readouterr().out


def test_module_runs_as_subprocess():
    rc = subprocess.call(
        [sys.executable, "-m", "oraclewatch", "--version"],
        cwd=ROOT,
    )
    assert rc == 0


def test_missing_file_exit_2():
    assert main(["check", os.path.join(HERE, "does_not_exist.json")]) == 2
