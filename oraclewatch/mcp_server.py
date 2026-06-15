"""ORACLEWATCH MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
import json
import sys

from oraclewatch.core import analyze_feeds, has_blocking, load_feeds


def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-oraclewatch[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-oraclewatch[mcp]'",
              file=sys.stderr)
        return 1
    app = FastMCP("oraclewatch")

    @app.tool()
    def oraclewatch_scan(feeds_file: str) -> str:
        """Analyze a JSON feeds file for oracle staleness, deviation, and
        manipulation exposure. Returns a JSON findings report."""
        try:
            feeds = load_feeds(feeds_file)
        except FileNotFoundError:
            return json.dumps({"error": f"file not found: {feeds_file}"})
        except (ValueError, json.JSONDecodeError) as exc:
            return json.dumps({"error": f"could not parse feeds: {exc}"})
        from oraclewatch import TOOL_NAME, TOOL_VERSION
        reports = analyze_feeds(feeds)
        return json.dumps({
            "tool": TOOL_NAME,
            "version": TOOL_VERSION,
            "feed_count": len(reports),
            "blocking": has_blocking(reports),
            "reports": [r.to_dict() for r in reports],
        }, indent=2)

    app.run()
    return 0
