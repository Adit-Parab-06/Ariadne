import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from mcp.server.mcpserver import MCPServer
from app.tools import call_tool, list_tools

logger = logging.getLogger(__name__)

# Initialize MCP server named 'ariadne'
mcp_server = MCPServer("ariadne")


def _format_result(res) -> str:
    return json.dumps({
        "summary": res.summary,
        "data": res.data,
        "cypher": res.cypher,
        "ms": res.ms,
    }, indent=2)


@mcp_server.tool(name="resolve_service", description="Resolves service name or ID via case-insensitive match")
def resolve_service(query: str, tenant: str = "northwind") -> str:
    res = call_tool(tenant, "resolve_service", {"query": query})
    return _format_result(res)


@mcp_server.tool(name="blast_radius", description="Computes blast radius upstream (dependents) or downstream (dependencies)")
def blast_radius(service_id: str, direction: str = "dependents", max_hops: int = 4, tenant: str = "northwind") -> str:
    res = call_tool(tenant, "blast_radius", {"service_id": service_id, "direction": direction, "max_hops": max_hops})
    return _format_result(res)


@mcp_server.tool(name="service_criticality", description="Ranks services by PageRank on dependency graph")
def service_criticality(top_k: int = 5, tenant: str = "northwind") -> str:
    res = call_tool(tenant, "service_criticality", {"top_k": top_k})
    return _format_result(res)


@mcp_server.tool(name="choke_points", description="Computes betweenness centrality over service topology")
def choke_points(top_k: int = 5, tenant: str = "northwind") -> str:
    res = call_tool(tenant, "choke_points", {"top_k": top_k})
    return _format_result(res)


@mcp_server.tool(name="dependency_path", description="Finds shortest path between two services")
def dependency_path(from_id: str, to_id: str, tenant: str = "northwind") -> str:
    res = call_tool(tenant, "dependency_path", {"from_id": from_id, "to_id": to_id})
    return _format_result(res)


@mcp_server.tool(name="find_experts", description="Ranks on-call/domain experts based on commits and past incident resolution")
def find_experts(service_id: str, k: int = 3, tenant: str = "northwind") -> str:
    res = call_tool(tenant, "find_experts", {"service_id": service_id, "k": k})
    return _format_result(res)


@mcp_server.tool(name="customer_history", description="Fetches tickets and past incidents for a customer within a time window")
def customer_history(customer_query: str, days: int = 30, tenant: str = "northwind") -> str:
    res = call_tool(tenant, "customer_history", {"customer_query": customer_query, "days": days})
    return _format_result(res)


@mcp_server.tool(name="trace_decision", description="Traces active and superseded architecture decisions (ADRs) for a service")
def trace_decision(service_id: str, tenant: str = "northwind") -> str:
    res = call_tool(tenant, "trace_decision", {"service_id": service_id})
    return _format_result(res)


@mcp_server.tool(name="get_doc", description="Retrieves runbook, ADR, or postmortem text by document ID")
def get_doc(doc_id: str, tenant: str = "northwind") -> str:
    res = call_tool(tenant, "get_doc", {"doc_id": doc_id})
    return _format_result(res)


@mcp_server.tool(name="recall_memory", description="Recalls past episodes, active facts, and procedures via hybrid vector and graph search")
def recall_memory(text: str, service_ids: Optional[List[str]] = None, k: int = 3, tenant: str = "northwind") -> str:
    res = call_tool(tenant, "recall_memory", {"text": text, "service_ids": service_ids or [], "k": k})
    return _format_result(res)


@mcp_server.tool(name="similar_incidents", description="Finds past incidents semantically similar to alert text")
def similar_incidents(text: str, service_ids: Optional[List[str]] = None, k: int = 3, tenant: str = "northwind") -> str:
    res = call_tool(tenant, "similar_incidents", {"text": text, "service_ids": service_ids or [], "k": k})
    return _format_result(res)


def main():
    parser = argparse.ArgumentParser(description="Ariadne MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Transport type (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host (for streamable-http/sse)")
    parser.add_argument("--port", type=int, default=8001, help="HTTP port (for streamable-http/sse)")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp_server.run(transport="stdio")
    elif args.transport == "streamable-http":
        mcp_server.run(transport="streamable-http", host=args.host, port=args.port)
    elif args.transport == "sse":
        mcp_server.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
