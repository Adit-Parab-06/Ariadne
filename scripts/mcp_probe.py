import asyncio
import json
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    print("=== ARIADNE MCP SERVER PROBE ===")

    server_env = dict(os.environ)
    server_env["PYTHONPATH"] = str(backend_dir)
    server_env["PYTHONUNBUFFERED"] = "1"

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server", "--transport", "stdio"],
        env=server_env,
    )

    print("Starting MCP server process over stdio...")
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("Session initialized successfully.\n")

            # 1. List tools
            tools_response = await session.list_tools()
            tool_names = [t.name for t in tools_response.tools]
            print(f"Tools reported by MCP server ({len(tool_names)} total):")
            for t in tool_names:
                print(f"  - {t}")
            assert len(tool_names) >= 8, f"Expected at least 8 tools, got {len(tool_names)}"
            print(f"\nTool count check: PASS ({len(tool_names)} >= 8 tools)")

            # 2. Call blast_radius tool
            print("\nCalling blast_radius for 'svc_payments_api' on tenant 'northwind'...")
            call_res = await session.call_tool(
                "blast_radius",
                {"service_id": "svc_payments_api", "direction": "dependents", "tenant": "northwind"},
            )
            print("Call response received:")
            for content in call_res.content:
                if content.type == "text":
                    print(content.text)
                else:
                    print(content)

            # Assert real blast radius content
            res_text = "".join([c.text for c in call_res.content if hasattr(c, "text")])
            assert "svc_checkout_api" in res_text or "checkout-api" in res_text
            print("\nblast_radius verification: PASS (real dependents found)")

    print("\n=== MCP PROBE COMPLETE: ALL PASS ===")


if __name__ == "__main__":
    asyncio.run(main())
