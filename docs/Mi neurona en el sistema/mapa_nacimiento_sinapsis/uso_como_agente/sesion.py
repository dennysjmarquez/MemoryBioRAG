"""Varias llamadas MCP en UNA sola sesión (un solo proceso servidor), como un agente real."""
import asyncio, json, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
ENV = dict(os.environ, BIORAG_PATH="/tmp/agente/cerebro.db", HOME="/tmp/agente/home", PYTHONHASHSEED="1")
async def main():
    pasos = json.load(open(sys.argv[1]))
    p = StdioServerParameters(command="/home/user/biorag-venv/bin/python", args=["mcp_server.py"], cwd="/home/user/MemoryBioRAG", env=ENV)
    async with stdio_client(p, errlog=open("/tmp/agente/server.err","a")) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for tool, args in pasos:
                if tool == "_sleep": await asyncio.sleep(args); continue
                res = await s.call_tool(tool, args)
                txt = " ".join(getattr(c, "text", "") for c in res.content)
                print(f"== {tool}: {txt[-300:]}".replace("\n", " "))
                if os.environ.get("FOTO"): os.system("python3 /tmp/agente/estado.py | sed -n 2,3p")
asyncio.run(main())
