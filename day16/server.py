from datetime import date

from mcp.server import MCPServer

mcp = MCPServer("advent-demo")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@mcp.tool()
def echo(text: str) -> str:
    """Return the given text unchanged."""
    return text


@mcp.tool()
def today() -> str:
    """Return today's date in ISO format (YYYY-MM-DD)."""
    return date.today().isoformat()


if __name__ == "__main__":
    mcp.run()
