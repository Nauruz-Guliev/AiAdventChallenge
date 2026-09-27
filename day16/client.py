import argparse
import asyncio
import json
import os
import shlex
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


def parse_input(line: str) -> tuple[str, list[str]]:
    parts = shlex.split(line)
    if not parts:
        return "", []
    return parts[0], parts[1:]


def coerce_arg(name: str, spec: dict, raw: str):
    type_name = spec.get("type")
    try:
        if type_name == "integer":
            return int(raw)
        if type_name == "number":
            return float(raw)
        if type_name == "boolean":
            low = raw.strip().lower()
            if low in ("true", "1", "yes", "y", "да", "д"):
                return True
            if low in ("false", "0", "no", "n", "нет", "н"):
                return False
            raise ValueError
        if type_name in ("array", "object"):
            return json.loads(raw)
        return raw
    except ValueError:
        raise ValueError(
            f"аргумент {name!r}: ожидалось {type_name or 'значение'}, "
            f"получено {raw!r}"
        )


def bind_positional(schema: dict, args: list[str]) -> dict:
    properties = schema.get("properties", {})
    names = list(properties.keys())
    required = schema.get("required", [])
    minimum = len([name for name in names if name in required])
    if len(args) < minimum or len(args) > len(names):
        expected = ", ".join(names) or "нет аргументов"
        raise ValueError(
            f"ожидалось аргументов {minimum}..{len(names)} ({expected}), "
            f"получено {len(args)}"
        )
    return {
        name: coerce_arg(name, properties[name], raw)
        for name, raw in zip(names, args)
    }


def tool_signature(tool) -> str:
    properties = tool.input_schema.get("properties", {})
    required = set(tool.input_schema.get("required", []))
    parts = []
    for name, spec in properties.items():
        optional = "" if name in required else "?"
        parts.append(f"{name}{optional}:{spec.get('type', 'any')}")
    return tool.name + (" " + " ".join(parts) if parts else "")


def format_help(tools) -> str:
    lines = [
        "Команды:",
        "  <инструмент> <аргументы...>   вызвать инструмент (позиционно)",
        "  help [инструмент]             справка (по всем или по одному)",
        "  tools                         показать список инструментов",
        "  quit                          выйти",
        "",
        "Инструменты:",
    ]
    for tool in tools:
        lines.append(f"  {tool_signature(tool)}")
        if tool.description:
            lines.append(f"      {tool.description}")
    return "\n".join(lines)


def format_result(result) -> str:
    if hasattr(result, "model_dump"):
        payload = result.model_dump(by_alias=True, exclude_none=True)
    else:
        payload = result
    return json.dumps(payload, indent=2, ensure_ascii=False)


async def interactive() -> None:
    color = supports_color()
    paint = _style(color)

    async with Client(server_params()) as client:
        tools = (await client.list_tools()).tools
        by_name = {tool.name: tool for tool in tools}

        print(format_tools(tools, color=color))
        print("Подключено. Введи имя инструмента, help или quit.")
        print("")

        while True:
            try:
                line = input(paint("cyan", "mcp> "))
            except (EOFError, KeyboardInterrupt):
                print("")
                break

            command, args = parse_input(line)
            if not command:
                continue
            if command in ("quit", "exit", "q"):
                break
            if command == "help":
                if args and args[0] in by_name:
                    tool = by_name[args[0]]
                    print(f"{tool_signature(tool)}")
                    print(f"    {tool.description or '(нет описания)'}")
                    schema = json.dumps(
                        tool.input_schema, indent=2, ensure_ascii=False
                    )
                    print("    Схема:")
                    print("\n".join(f"      {row}" for row in schema.splitlines()))
                else:
                    print(format_help(tools))
                continue
            if command == "tools":
                print(format_tools(tools, color=color))
                continue

            tool = by_name.get(command)
            if tool is None:
                print(
                    paint(
                        "yellow",
                        f"Нет инструмента {command!r}. Доступны: "
                        f"{', '.join(by_name)}",
                    )
                )
                continue

            try:
                arguments = bind_positional(tool.input_schema, args)
            except ValueError as exc:
                print(paint("yellow", f"Ошибка аргументов: {exc}"))
                print(f"  формат: {tool_signature(tool)}")
                continue

            try:
                result = await client.call_tool(command, arguments)
            except Exception as exc:  # noqa: BLE001 - показать любую ошибку вызова
                print(paint("yellow", f"Ошибка вызова: {exc}"))
                continue

            label = "Ошибка" if getattr(result, "is_error", False) else "Результат"
            tone = "yellow" if getattr(result, "is_error", False) else "green"
            print(paint(tone, f"{label} (как MCP отдаёт):"))
            print(format_result(result))
            print("")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Подключается к MCP-серверу и выводит список инструментов."
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Интерактивный режим: вызывать инструменты в одной сессии.",
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
    if args.interactive:
        asyncio.run(interactive())
        return

    color = not args.plain and supports_color()
    paint = _style(color)

    tools = asyncio.run(fetch_tools())
    print(format_tools(tools, color=color, show_schema=args.schema))
    print(paint("dim", "Подсказка: запусти с -i для интерактивного режима."))

    if args.call_add:
        a, b = args.call_add
        result = asyncio.run(call_add(a, b))
        print(paint("yellow", f"Вызов: add(a={a}, b={b})"))
        print(format_result(result))


if __name__ == "__main__":
    main()
