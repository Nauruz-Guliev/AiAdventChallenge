from __future__ import annotations

import re
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

import client
import registry

DEFAULT_REMINDER_SECONDS = 60
_CITY_RE = re.compile(r"(?:^|\s)(?:в|во)\s+([А-ЯЁ][а-яё]+)")
_TOPIC_MARKERS = ("про ", "о ", "об ")


class OrchestrationError(Exception):
    """Ошибка оркестрации (некорректная цель, отсутствие данных для шага)."""


@dataclass(frozen=True)
class Step:
    server: str
    tool: str
    args: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"server": self.server, "tool": self.tool, "args": self.args}


def _extract_topic(goal: str) -> str:
    low = goal.lower()
    for marker in _TOPIC_MARKERS:
        idx = low.find(marker)
        if idx != -1:
            return goal[idx + len(marker):].strip(" .,!?;:")
    return goal.strip(" .,!?;:")


def parse_goal(goal: str) -> dict:
    goal = (goal or "").strip()
    if not goal:
        raise OrchestrationError("Пустая цель")
    match = _CITY_RE.search(goal)
    city = match.group(1) if match else None
    reminder = "напомн" in goal.lower()
    return {"topic": _extract_topic(goal), "city": city, "reminder": reminder}


def route(
    topic: str,
    city: str | None = None,
    reminder: bool = False,
    in_seconds: int = DEFAULT_REMINDER_SECONDS,
    reminder_text: str | None = None,
) -> list[Step]:
    steps: list[Step] = []
    if city:
        steps.append(Step("weather", "get_weather", {"city": city}))
    steps.append(Step("compose", "search", {"query": topic}))
    steps.append(Step("compose", "summarize", {"text": "$search_text"}))
    steps.append(Step("compose", "save_to_file", {"content": "$markdown"}))
    if reminder:
        steps.append(
            Step(
                "scheduler",
                "add_reminder",
                {"text": reminder_text or f"Проверить: {topic}", "in_seconds": in_seconds},
            )
        )
    steps.append(Step("notes", "add_note", {"title": topic, "body": "$summary"}))
    return steps


def _resolve_args(args: dict, ctx: dict) -> dict:
    resolved = {}
    for key, value in args.items():
        if isinstance(value, str) and value.startswith("$"):
            ref = value[1:]
            if ref not in ctx:
                raise OrchestrationError(f"Нет данных для аргумента '{key}' (нужен {value})")
            resolved[key] = ctx[ref]
        else:
            resolved[key] = value
    return resolved


def _build_markdown(topic: str, results: list[dict], summary: str) -> str:
    lines = [f"# {topic}", "", f"Источников: {len(results)}", ""]
    for item in results:
        lines.append(f"- [{item['title']}]({item['url']})")
    lines.extend(["", "## Summary", "", summary, ""])
    return "\n".join(lines)


def _update_ctx(tool: str, result: dict, ctx: dict, topic: str) -> None:
    if tool == "search":
        results = result.get("results", [])
        ctx["search_results"] = results
        ctx["search_text"] = " ".join(f"{r['title']}. {r['snippet']}" for r in results)
    elif tool == "summarize":
        ctx["summary"] = result.get("summary", "")
        ctx["markdown"] = _build_markdown(topic, ctx.get("search_results", []), ctx["summary"])
    elif tool == "save_to_file":
        ctx["output_path"] = result.get("path")


def _real_caller_factory(stack: AsyncExitStack, python: str | None):
    clients: dict[str, object] = {}

    async def call(server: str, tool: str, args: dict) -> dict:
        spec = registry.SERVERS[server]
        mcp_client = clients.get(server)
        if mcp_client is None:
            mcp_client = await stack.enter_async_context(
                client.Client(client.make_params(spec, python=python))
            )
            clients[server] = mcp_client
        result = await mcp_client.call_tool(tool, args)
        if result.is_error:
            text = result.content[0].text if result.content else "ошибка инструмента"
            raise client.ClientError(f"{server}.{tool}: {text}")
        return client._parse(result)

    return call


async def run_flow(goal: str, caller=None, python: str | None = None) -> dict:
    params = parse_goal(goal)
    steps = route(**params)
    trace: list[dict] = []
    ctx: dict = {"topic": params["topic"]}
    ok = True
    error_message: str | None = None

    async with AsyncExitStack() as stack:
        active = caller or await _real_caller_factory(stack, python)
        for index, step in enumerate(steps):
            try:
                args = _resolve_args(step.args, ctx)
                result = await active(step.server, step.tool, args)
                _update_ctx(step.tool, result, ctx, params["topic"])
                trace.append(
                    {
                        "index": index,
                        "server": step.server,
                        "tool": step.tool,
                        "args": args,
                        "ok": True,
                        "result": result,
                    }
                )
            except Exception as exc:  # noqa: BLE001 — фиксируем и останавливаем флоу
                ok = False
                error_message = str(exc)
                trace.append(
                    {
                        "index": index,
                        "server": step.server,
                        "tool": step.tool,
                        "args": step.args,
                        "ok": False,
                        "error": str(exc),
                    }
                )
                break

    return {
        "goal": goal,
        "params": params,
        "steps_planned": len(steps),
        "trace": trace,
        "ok": ok,
        "error": error_message,
        "output_path": ctx.get("output_path"),
    }
