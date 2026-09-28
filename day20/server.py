from mcp.server import MCPServer

import client
import orchestrator
import registry

mcp = MCPServer("orchestrator")


@mcp.tool()
def list_servers() -> dict:
    """Список MCP-серверов, доступных оркестратору."""
    return {
        "servers": [{"name": s.name, "script": str(s.script)} for s in registry.SERVERS.values()]
    }


@mcp.tool()
def plan(goal: str) -> dict:
    """Показать план маршрутизации: какие инструменты и в каком порядке будут вызваны.

    Args:
        goal: Цель на естественном языке.
    """
    try:
        params = orchestrator.parse_goal(goal)
        steps = orchestrator.route(**params)
    except orchestrator.OrchestrationError as exc:
        raise ValueError(str(exc)) from exc
    return {"goal": goal, "params": params, "steps": [s.as_dict() for s in steps]}


@mcp.tool()
async def run_flow(goal: str) -> dict:
    """Выполнить длинный флоу по нескольким MCP-серверам и вернуть trace.

    Args:
        goal: Цель на естественном языке.
    """
    try:
        return await orchestrator.run_flow(goal)
    except orchestrator.OrchestrationError as exc:
        raise ValueError(str(exc)) from exc


@mcp.tool()
async def call(server: str, tool: str, args: dict | None = None) -> dict:
    """Прямой вызов инструмента на конкретном MCP-сервере.

    Args:
        server: Имя сервера (weather/compose/scheduler/notes).
        tool: Имя инструмента.
        args: Аргументы инструмента.
    """
    if server not in registry.SERVERS:
        raise ValueError(f"Неизвестный сервер: {server}")
    try:
        return await client.call_tool(registry.SERVERS[server], tool, args or {})
    except client.ClientError as exc:
        raise ValueError(str(exc)) from exc


if __name__ == "__main__":
    mcp.run()
