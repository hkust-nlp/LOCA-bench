"""Entry point for the simplified YFinance MCP package."""

from __future__ import annotations

import asyncio


def main() -> None:
    """Launch the YFinance MCP server."""
    from mcps.yfinance.server import YFinanceMCPServer

    asyncio.run(YFinanceMCPServer().run())


__all__ = ["main"]

