"""MCP Resources for BioRAG cortex concepts and messages.

Exposes resources:
- recurso_concepto (biorag://concepto/{nombre})
- recurso_mensajes (biorag://mensajes)
"""

import json
import time
from typing import Any

from core.mcp_server._shared import _get_cerebro


def register(mcp: Any) -> None:
    @mcp.resource(
        uri="biorag://concepto/{nombre}",
        name="Concepto de la corteza",
        description=(
            "Contenido completo de un concepto almacenado en la corteza. "
            "URI: biorag://concepto/{nombre} donde nombre es la clave snake_case del concepto. "
            "Retorna: {concepto, categoria, contenido, peso_sinaptico, estado, asociaciones[], sinonimos[]}"
        ),
        mime_type="application/json",
    )
    def recurso_concepto(nombre: str) -> str:
        cerebro = _get_cerebro()
        try:
            key = nombre.lower().strip()
            cerebro.cursor.execute(
                "SELECT concepto, categoria, contenido, peso_sinaptico, estado, "
                "asociaciones, sinonimos FROM largo_plazo WHERE concepto = ?",
                (key,),
            )
            fila = cerebro.cursor.fetchone()
            if not fila:
                return json.dumps({"error": f"Concepto '{nombre}' no encontrado."}, ensure_ascii=False)
            return json.dumps({
                "concepto": fila[0],
                "categoria": fila[1],
                "contenido": fila[2],
                "peso_sinaptico": fila[3],
                "estado": fila[4],
                "asociaciones": [
                    v.strip() for v in (fila[5] or "").split(",") if v.strip()
                ],
                "sinonimos": [
                    v.strip() for v in (fila[6] or "").split(",") if v.strip()
                ],
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.resource(
        uri="biorag://mensajes",
        name="Mensajes no leidos",
        description=(
            "Mensajes pendientes (no leídos) en el canal compartido OEC. "
            "Devuelve hasta 20 mensajes no leídos. "
            "Retorna: {total (int), mensajes: [{id, origen, destino, contenido, timestamp}]}"
        ),
        mime_type="application/json",
    )
    def recurso_mensajes() -> str:
        cerebro = _get_cerebro()
        try:
            mensajes = cerebro.leer_comunicados(solo_no_leidos=True, ultimos=20)
            items = [
                {
                    "id": m[0],
                    "origen": m[1],
                    "destino": m[2],
                    "contenido": m[3],
                    "timestamp": time.strftime("%Y-%m-%d %H:%M", time.localtime(m[4])),
                }
                for m in mensajes
            ]
            return json.dumps({"total": len(items), "mensajes": items}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()
