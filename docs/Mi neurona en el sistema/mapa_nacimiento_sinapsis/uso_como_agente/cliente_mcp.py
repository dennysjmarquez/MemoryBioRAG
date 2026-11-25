"""Cliente MCP mínimo: python mcp.py list | python mcp.py <tool> '<json>'  (BIORAG_PATH = copia)."""
import asyncio, json, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
ENV = dict(os.environ, BIORAG_PATH="/tmp/agente/cerebro.db", HOME="/tmp/agente/home", PYTHONHASHSEED="1")
async def main():
    p = StdioServerParameters(command="/home/user/biorag-venv/bin/python", args=["mcp_server.py"],
                              cwd="/home/user/MemoryBioRAG", env=ENV)
    async with stdio_client(p, errlog=open("/tmp/agente/server.err","a")) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if sys.argv[1] == "list":
                for t in (await s.list_tools()).tools:
                    props = list((t.inputSchema or {}).get("properties", {}).keys())
                    print(f"- {t.name}({', '.join(props)}): {(t.description or '').splitlines()[0][:150]}")
                return
            if sys.argv[1] == "schema":
                for t in (await s.list_tools()).tools:
                    if t.name == sys.argv[2]: print(t.description); print(json.dumps(t.inputSchema, ensure_ascii=False, indent=1))
                return
            res = await s.call_tool(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {})
            for c in res.content: print(getattr(c, "text", c))
asyncio.run(main())
