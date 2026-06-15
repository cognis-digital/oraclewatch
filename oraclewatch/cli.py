"""Command-line interface for ORACLEWATCH.

Examples
--------
  # Human-readable table
  oraclewatch check feeds.json

  # JSON for CI / piping (exit 1 if any WARNING+ finding)
  oraclewatch check feeds.json --format json

  # Pin the evaluation clock for reproducible output
  oraclewatch check feeds.json --now 1717000000

  python -m oraclewatch --version
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional, Sequence

from . import TOOL_NAME, TOOL_VERSION
from .core import (
    FeedReport,
    Severity,
    analyze_feeds,
    load_feeds,
    has_blocking,
)

_SEV_ABBR = {
    Severity.OK: "OK ",
    Severity.INFO: "INFO",
    Severity.WARNING: "WARN",
    Severity.CRITICAL: "CRIT",
}


def _fmt_table(reports: Sequence[FeedReport]) -> str:
    lines: List[str] = []
    header = f"{'SEV':<4}  {'FEED':<26} {'PAIR':<10} {'CODE':<17} MESSAGE"
    lines.append(header)
    lines.append("-" * len(header))
    any_finding = False
    for r in reports:
        if not r.findings:
            lines.append(f"{'OK ':<4}  {r.feed:<26} {r.pair:<10} {'-':<17} "
                         f"healthy (dev={r.deviation_pct}%, age={r.age_seconds}s)")
            continue
        for f in sorted(r.findings, key=lambda x: -int(x.severity)):
            any_finding = True
            abbr = _SEV_ABBR.get(f.severity, "?")
            lines.append(f"{abbr:<4}  {f.feed:<26} {f.pair:<10} "
                         f"{f.code:<17} {f.message}")
    # summary
    counts = {Severity.CRITICAL: 0, Severity.WARNING: 0,
              Severity.INFO: 0, Severity.OK: 0}
    for r in reports:
        for f in r.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
    lines.append("-" * len(header))
    lines.append(
        f"feeds={len(reports)}  "
        f"critical={counts[Severity.CRITICAL]}  "
        f"warning={counts[Severity.WARNING]}  "
        f"info={counts[Severity.INFO]}"
    )
    if counts.get(Severity.CRITICAL, 0) == 0 and counts.get(Severity.WARNING, 0) == 0:
        lines.append("all feeds healthy")     # info-level notes don't gate / don't unhealth
    return "\n".join(lines)


def _fmt_json(reports: Sequence[FeedReport]) -> str:
    blocking = has_blocking(reports)
    payload = {
        "tool": TOOL_NAME,
        "version": TOOL_VERSION,
        "feed_count": len(reports),
        "blocking": blocking,
        "reports": [r.to_dict() for r in reports],
    }
    return json.dumps(payload, indent=2)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Monitor price-oracle feeds for staleness, deviation, "
                    "frozen values, round regression and cost-to-attack.",
        epilog="Exit code is non-zero when any finding is WARNING or worse "
               "(use for CI gates).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version",
                   version=f"{TOOL_NAME} {TOOL_VERSION}")
    p.add_argument("--format", choices=["table", "json"], default="table",
                   help="output format (default: table)")

    sub = p.add_subparsers(dest="command")
    chk = sub.add_parser(
        "check",
        help="analyze a JSON file of oracle feeds",
        description="Analyze a JSON file describing one or more oracle feeds.",
    )
    chk.add_argument("feeds_file", help="path to feeds JSON (list or {feeds:[...]})")
    chk.add_argument("--now", type=float, default=None,
                     help="override evaluation clock (unix seconds) for "
                          "reproducible staleness checks")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command != "check":
        parser.print_help()
        return 2

    try:
        feeds = load_feeds(args.feeds_file)
    except FileNotFoundError:
        print(f"error: file not found: {args.feeds_file}", file=sys.stderr)
        return 2
    except (ValueError, json.JSONDecodeError) as e:
        print(f"error: could not parse feeds: {e}", file=sys.stderr)
        return 2

    reports = analyze_feeds(feeds, now=args.now)

    if args.format == "json":
        print(_fmt_json(reports))
    else:
        print(_fmt_table(reports))

    return 1 if has_blocking(reports) else 0


if __name__ == "__main__":
    sys.exit(main())
