import argparse
import asyncio
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

SERVER_SCRIPT = Path(__file__).with_name("server.py")


def server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
    )


async def fetch_tools() -> list:
    async with Client(server_params()) as client:
        result = await client.list_tools()
        return result.tools


async def call_add(a: int, b: int):
    async with Client(server_params()) as client:
        return await client.call_tool("add", {"a": a, "b": b})


def print_tools(tools) -> None:
    print(f"MCP вернул инструментов: {len(tools)}")
    for tool in tools:
        print(f"- {tool.name}: {tool.description}")
        print(f"    input_schema: {tool.input_schema}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Подключается к MCP-серверу и выводит список инструментов."
    )
    parser.add_argument(
        "--call-add",
        nargs=2,
        type=int,
        metavar=("A", "B"),
        help="Дополнительно вызвать инструмент add(A, B).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print_tools(asyncio.run(fetch_tools()))
    if args.call_add:
        a, b = args.call_add
        result = asyncio.run(call_add(a, b))
        print(f"\nadd({a}, {b}) = {result.structured_content}")


if __name__ == "__main__":
    main()
