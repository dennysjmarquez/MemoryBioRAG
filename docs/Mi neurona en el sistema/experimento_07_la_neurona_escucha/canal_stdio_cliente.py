"""Cliente MCP stdio mínimo: ¿llega ruido no-JSON al canal JSON-RPC?

Levanta `mcp_server.py` como lo hace un IDE (subproceso stdio), llama `recordar` y
N veces `vincular`, y clasifica cada línea del stdout del server.
Uso (sobre una COPIA de la DB, en el cwd):
  cp snapshots/qa_escape_qcr_20260811.db s.db
  N_VINC=120 python canal_stdio_cliente.py /ruta/al/python "tasajera"
"""
import json, subprocess, sys, os, time
env = dict(os.environ, BIORAG_PATH=os.path.abspath("s.db"), BIORAG_NEURONA="0", PYTHONHASHSEED="1", BIORAG_NO_DAEMON="1")
p = subprocess.Popen([sys.argv[1], "mcp_server.py"], cwd=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")), env=env,
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
def send(o): p.stdin.write(json.dumps(o) + "\n"); p.stdin.flush()
send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}})
lineas = []
def leer_hasta(i):
    while True:
        l = p.stdout.readline()
        if not l: return
        lineas.append(l.rstrip("\n"))
        try:
            if json.loads(l).get("id") == i: return
        except Exception: pass
leer_hasta(1)
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
qs = sys.argv[2:] or ["configuracion del servidor", "tipografia del dashboard", "leccion guardar todo"]
for i, q in enumerate(qs, 2):
    send({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": "recordar", "arguments": {"query": q, "sustantivos_clave": "consulta"}}})
    leer_hasta(i)
N = int(os.environ.get("N_VINC", "1"))
for k in range(N):
    send({"jsonrpc": "2.0", "id": 1000 + k, "method": "tools/call", "params": {"name": "vincular", "arguments": {"a": "historia_tasajera_fumigador_rufino", "b": "notebooklm-sync-protocol"}}})
    leer_hasta(1000 + k)
p.terminate()
malas = []
for l in lineas:
    try: json.loads(l)
    except Exception: malas.append(l)
print(f"líneas en stdout: {len(lineas)}; NO-JSON (corrompen JSON-RPC): {len(malas)}")
for l in malas[:8]: print("  ", l[:120])
