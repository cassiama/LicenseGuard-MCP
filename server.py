from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("LicenseGuard-MCP")


@mcp.tool("get_time")
def get_time() -> datetime:
    return datetime.now()
