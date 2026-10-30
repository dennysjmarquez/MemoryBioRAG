"""La tool MCP `metricas_historial` debe leer la tabla real `metricas_cognitivas`.

POR QUÉ existe: la tool pedía la columna `categoria_dominante`, pero la tabla la
guarda como `categoria_dominante_id` (FK a `categories`). Resultado: en cualquier
base con al menos un ciclo de sueño la tool fallaba con
"no such column: categoria_dominante". Este test fija el arreglo: la tool responde
y muestra el NOMBRE de la categoría, no el id.
"""
import json
import time

from core.memory_store import SQLiteMemoryBioRAG
from core.mcp_server import introspection


class _MCPFalso:
    """Captura las funciones que `register` declara como tools."""

    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def deco(fn):
            self.tools[name] = fn
            return fn
        return deco


def _tool_con_db(tmp_path, monkeypatch):
    cerebro = SQLiteMemoryBioRAG(db_path=str(tmp_path / "m.db"))
    cerrar_real = cerebro.cerrar_sistema
    monkeypatch.setattr(cerebro, "cerrar_sistema", lambda: None)
    monkeypatch.setattr(introspection, "_get_cerebro", lambda: cerebro)
    mcp = _MCPFalso()
    introspection.register(mcp)
    return mcp.tools["metricas_historial"], cerebro, cerrar_real


def test_sin_ciclos_responde_vacio(tmp_path, monkeypatch):
    tool, _cerebro, cerrar = _tool_con_db(tmp_path, monkeypatch)
    try:
        out = json.loads(tool(n=10))
        assert out["status"] == "ok"
        assert out["total_registros"] == 0
    finally:
        cerrar()


def test_con_ciclos_no_falla_y_muestra_nombre_de_categoria(tmp_path, monkeypatch):
    tool, cerebro, cerrar = _tool_con_db(tmp_path, monkeypatch)
    try:
        cur = cerebro.cursor
        cur.execute("INSERT OR IGNORE INTO categories (name) VALUES ('leccion')")
        cat_id = cur.execute("SELECT id FROM categories WHERE name = 'leccion'").fetchone()[0]
        ahora = time.time()
        for i in range(4):
            cur.execute(
                "INSERT INTO metricas_cognitivas (timestamp, nodos_consolidados, "
                "nodos_dormidos_ciclo, sinapsis_creadas, sinapsis_podadas, "
                "categoria_dominante_id, ratio_consolidacion) VALUES (?,?,?,?,?,?,?)",
                (ahora - 3600 * i, 5 + i, 1, 3, 1, cat_id, 0.5),
            )
        cerebro.conn.commit()

        out = json.loads(tool(n=10))
        assert out["status"] == "ok", out
        assert out["total_registros"] == 4
        assert out["ultimos_ciclos"] == 4
        assert out["tendencias"]["categoria_dominante"] == "leccion"
        assert "leccion" in out["tabla"]
    finally:
        cerrar()
