"""MCP Tools for system introspection, graph mapping and DMN state.

Exposes tools:
- introspeccion
- estado
- estado_dmn
- mapear
- corteza
"""

import json
from typing import Any

from core.mcp_server._shared import _get_cerebro, _interceptar


def register(mcp: Any) -> None:
    @mcp.tool(
        name="introspeccion",
        description=(
            "Mirá el estado de la memoria. No modifica nada — solo muestra cuántos nodos activos, dormidos, en corto plazo, y cuánta energía sináptica queda. Sin parámetros."
        ),
    )
    def biorag_introspeccion() -> str:
        cerebro = _get_cerebro()
        try:
            cerebro.cursor.execute(
                "SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'"
            )
            activos = cerebro.cursor.fetchone()[0]
            cerebro.cursor.execute(
                "SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido'"
            )
            dormidos = cerebro.cursor.fetchone()[0]
            cerebro.cursor.execute("SELECT COUNT(*) FROM corto_plazo")
            corto = cerebro.cursor.fetchone()[0]
            cerebro.cursor.execute(
                "SELECT ROUND(SUM(peso_sinaptico), 2) FROM largo_plazo WHERE estado = 'activo'"
            )
            energia = cerebro.cursor.fetchone()[0] or 0.0
            resultado = json.dumps({
                "activos": activos,
                "dormidos": dormidos,
                "corto_plazo": corto,
                "energia_sinaptica": energia,
            }, ensure_ascii=False)
            _interceptar("introspeccion", f"activos:{activos} dormidos:{dormidos}", cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="estado",
        description=(
            "(legado) Alias de 'introspeccion' — preferir 'introspeccion' para identificar la operación cognitiva real. "
            "Sin parámetros. "
            "Retorna: {activos (int), dormidos (int), corto_plazo (int), energia_sinaptica (float)}"
        ),
    )
    def biorag_estado() -> str:
        return biorag_introspeccion()

    @mcp.tool(
        name="estado_dmn",
        description=(
            "Consulta el estado operativo de la Red por Defecto (Default Mode Network - DMN) y la curiosidad espontánea autónoma de BioRAG v21.0. "
            "Devuelve si el hilo autónomo está activo, el tiempo de inactividad actual y la última idea/insight generada en reposo."
        ),
    )
    def biorag_estado_dmn() -> str:
        cerebro = _get_cerebro()
        if hasattr(cerebro, 'dmn') and cerebro.dmn is not None:
            estado = cerebro.dmn.obtener_estado()
            return json.dumps(estado, ensure_ascii=False, indent=2)
        return json.dumps({"activo": False, "mensaje": "DMN no iniciado en esta instancia."}, ensure_ascii=False)

    @mcp.tool(
        name="mapear",
        description=(
            "Listá todos los nodos de la memoria — activos y dormidos — ordenados de más fuerte a más débil. Para explorar qué hay, detectar nodos huérfanos, revisar categorías, o verificar que algo se guardó bien. Ojo: si hay muchos nodos, la respuesta es larga. Sin parámetros."
        ),
    )
    def biorag_mapear() -> str:
        cerebro = _get_cerebro()
        try:
            cerebro.cursor.execute(
                "SELECT concepto, categoria, peso_sinaptico, estado, asociaciones "
                "FROM largo_plazo ORDER BY peso_sinaptico DESC, estado ASC"
            )
            filas = cerebro.cursor.fetchall()
            items = [
                {
                    "concepto": c,
                    "categoria": cat,
                    "peso_sinaptico": p,
                    "estado": est,
                    "asociaciones": [v.strip() for v in (a or "").split(",") if v.strip()],
                }
                for c, cat, p, est, a in filas
            ]
            resultado = json.dumps({"total": len(items), "nodos": items}, ensure_ascii=False)
            _interceptar("mapear", "", cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="corteza",
        description=(
            "Alias viejo de mapear. Usá mapear en vez de esta."
        ),
    )
    def biorag_corteza() -> str:
        return biorag_mapear()
