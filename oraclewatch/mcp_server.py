"""ORACLEWATCH MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from oraclewatch.core import scan, to_json

def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-oraclewatch[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-oraclewatch[mcp]'")
        return 1
    app = FastMCP("oraclewatch")

    @app.tool()
    def oraclewatch_scan(target: str) -> str:
        """Monitors price-oracle feeds for staleness, deviation, and manipulation exposure, simulating TWAP/spot attack profitability per pool.. Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
