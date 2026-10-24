"""En stdio, el stdout del proceso es el canal JSON-RPC del MCP: nadie más puede escribir ahí.

Bug reproducido (docs/Mi neurona en el sistema/experimento_07_la_neurona_escucha):
los print() del motor se acumulaban en el búfer de sys.stdout y se volcaban en
medio del protocolo (120 `vincular` => 77 líneas no-JSON en el canal).
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_HIJO = r"""
import os, sys
sys.path.insert(0, %r)
from core.mcp_server.server import _proteger_canal_stdio
assert _proteger_canal_stdio()
print("[MemoryBioRAG] Sinapsis establecida: 'a' <--> 'b'")      # print de Python
os.write(1, b"ruido de C o de un proceso hijo\n")                  # escritura directa al fd 1
sys.stdout.write("write directo\n"); sys.stdout.flush()
# lo que hace mcp.server.stdio.stdio_server: escribir en sys.stdout.buffer
from io import TextIOWrapper
canal = TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
canal.write('{"jsonrpc": "2.0", "id": 1, "result": {"ñ": "ok"}}\n'); canal.flush()
""" % REPO


def test_el_canal_stdio_solo_lleva_protocolo():
    r = subprocess.run([sys.executable, "-c", _HIJO], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert r.returncode == 0, r.stderr
    lineas = [l for l in r.stdout.splitlines() if l.strip()]
    assert len(lineas) == 1 and json.loads(lineas[0])["result"]["ñ"] == "ok"
    for ruido in ("Sinapsis establecida", "ruido de C", "write directo"):
        assert ruido in r.stderr        # el log no se pierde: va a stderr
        assert ruido not in r.stdout
