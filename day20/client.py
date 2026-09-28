from __future__ import annotations

import json
import os

from mcp import Client, StdioServerParameters

import registry


class ClientError(Exception):
    """Ошибка вызова инструмента на удалённом MCP-сервере."""


def make_params(
    spec: registry.ServerSpec,
    python: str | None = None,
    env: dict | None = None,
) -> StdioServerParameters:
    if python:
        command = [python, str(spec.script)]
    else:
        command = ["uv", "run", "--no-project", "--with", "mcp>=2,<3", str(spec.script)]
    kwargs: dict = {"command": command[0], "args": command[1:], "cwd": str(spec.script.parent)}
    if env is not None:
        kwargs["env"] = {**os.environ, **env}
    return StdioServerParameters(**kwargs)


def _parse(result) -> dict:
    text = result.content[0].text if result.content else ""
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return {"text": text}


async def call_tool(
    spec: registry.ServerSpec,
    tool: str,
    args: dict,
    python: str | None = None,
    env: dict | None = None,
) -> dict:
    async with Client(make_params(spec, python=python, env=env)) as client:
        result = await client.call_tool(tool, args)
        if result.is_error:
            text = result.content[0].text if result.content else "ошибка инструмента"
            raise ClientError(f"{spec.name}.{tool}: {text}")
        return _parse(result)
