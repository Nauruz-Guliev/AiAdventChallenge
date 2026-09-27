import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

SERVER_SCRIPT = Path(__file__).with_name("server.py")

_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "green": "\033[32m",
    "cyan": "\033[36m",
    "yellow": "\033[33m",
    "green_bold": "\033[1;32m",
}


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


def _enable_windows_ansi() -> bool:
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    return _enable_windows_ansi()


def _style(enabled: bool):
    def paint(name: str, text: str) -> str:
        if not enabled:
            return text
        return f"{_CODES[name]}{text}{_CODES['reset']}"

    return paint


def _describe_args(schema: dict) -> list[str]:
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines = []
    for name, spec in properties.items():
        type_name = spec.get("type", "any")
        marks = ["обязательный" if name in required else "необязательный"]
        if "default" in spec:
            marks.append(f"по умолчанию {spec['default']!r}")
        if spec.get("description"):
            marks.append(spec["description"])
        lines.append(f"      - {name}: {type_name} ({', '.join(marks)})")
    return lines


def format_tools(tools, color: bool = True, show_schema: bool = False) -> str:
    paint = _style(color)
    lines = [
        paint("cyan", "=" * 60),
        paint("cyan", "  MCP: подключение и список инструментов"),
        paint("cyan", "  транспорт: stdio"),
        paint("cyan", "=" * 60),
        "",
        f"{paint('green_bold', '[OK]')} Соединение установлено. "
        f"Инструментов: {len(tools)}",
        "",
    ]
    for index, tool in enumerate(tools, 1):
        header = f"{paint('dim', f'[{index}]')} {paint('green_bold', tool.name)}"
        lines.append(header)
        lines.append(f"    Описание: {tool.description or '(нет)'}")
        args = _describe_args(tool.input_schema)
        if args:
            lines.append("    Аргументы:")
            lines.extend(args)
        else:
            lines.append("    Аргументы: нет")
        if show_schema:
            schema = json.dumps(tool.input_schema, indent=2, ensure_ascii=False)
            lines.append("    Схема:")
            lines.extend(f"      {line}" for line in schema.splitlines())
        lines.append("")
    return "\n".join(lines)


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
    parser.add_argument(
        "--schema",
        action="store_true",
        help="Показывать полную JSON-схему аргументов.",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Без цветов (для терминалов без поддержки ANSI).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    color = not args.plain and supports_color()
    paint = _style(color)

    tools = asyncio.run(fetch_tools())
    print(format_tools(tools, color=color, show_schema=args.schema))

    if args.call_add:
        a, b = args.call_add
        result = asyncio.run(call_add(a, b))
        value = result.structured_content
        if isinstance(value, dict) and "result" in value:
            value = value["result"]
        print(paint("yellow", f"Вызов add({a}, {b}) -> {value}"))


if __name__ == "__main__":
    main()
