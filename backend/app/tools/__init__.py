import functools
import inspect
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from app.tools.evidence import Evidence, ToolResult

logger = logging.getLogger(__name__)


class RegisteredTool:
    def __init__(
        self,
        name: str,
        description: str,
        params: Dict[str, Any],
        agents: List[str],
        fn: Callable,
        readonly: bool = True,
    ):
        self.name = name
        self.description = description
        self.params = params
        self.agents = agents
        self.fn = fn
        self.readonly = readonly


_REGISTRY: Dict[str, RegisteredTool] = {}


def _ensure_tools_loaded():
    """Dynamically imports tool modules to trigger @tool registrations."""
    try:
        import app.tools.knowledge  # noqa: F401
    except ImportError:
        pass
    try:
        import app.tools.memory  # noqa: F401
    except ImportError:
        pass
    try:
        import app.tools.actions  # noqa: F401
    except ImportError:
        pass


def tool(
    name: str,
    description: str,
    params: Dict[str, Any],
    agents: List[str],
    readonly: bool = True,
):
    """Decorator to register a tool function into the unified registry."""
    def decorator(fn: Callable):
        tool_obj = RegisteredTool(
            name=name,
            description=description,
            params=params,
            agents=agents,
            fn=fn,
            readonly=readonly,
        )
        _REGISTRY[name] = tool_obj

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def gemini_declarations(agent: str) -> List[Dict[str, Any]]:
    """Returns Gemini function declarations filtered for the specified agent."""
    _ensure_tools_loaded()
    declarations = []
    for t in _REGISTRY.values():
        if agent in t.agents:
            declarations.append({
                "type": "function",
                "name": t.name,
                "description": t.description,
                "parameters": t.params,
            })
    return declarations


def call_tool(tenant: str, name: str, args: Dict[str, Any]) -> ToolResult:
    """
    Executes a registered tool for a given tenant with argument validation.
    Catches all exceptions and returns a ToolResult with summary 'Tool error: ...' instead of raising.
    """
    _ensure_tools_loaded()
    start_time = time.perf_counter()
    if name not in _REGISTRY:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return ToolResult(
            summary=f"Tool error: Unknown tool '{name}'",
            data={"error": f"Tool '{name}' is not registered"},
            evidence=Evidence(),
            cypher=[],
            ms=duration_ms,
        )

    registered = _REGISTRY[name]
    try:
        # Validate required parameters
        required = registered.params.get("required", [])
        for req in required:
            if req not in args or args[req] is None:
                raise ValueError(f"Missing required parameter '{req}' for tool '{name}'")

        # Call tool with tenant as first argument
        result: ToolResult = registered.fn(tenant, **args)
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        result.ms = duration_ms
        return result
    except Exception as e:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        logger.warning(f"Error calling tool {name} with args {args}: {e}")
        return ToolResult(
            summary=f"Tool error: {str(e)}",
            data={"error": str(e)},
            evidence=Evidence(),
            cypher=[],
            ms=duration_ms,
        )


def list_tools() -> List[Dict[str, Any]]:
    """Returns list of registered tools and metadata for the API and MCP."""
    _ensure_tools_loaded()
    return [
        {
            "name": t.name,
            "description": t.description,
            "agents": t.agents,
            "readonly": t.readonly,
            "parameters": t.params,
        }
        for t in _REGISTRY.values()
    ]
