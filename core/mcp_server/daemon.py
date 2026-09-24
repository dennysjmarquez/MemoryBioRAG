"""MCP Tools for background daemon maintenance, Hormiguita node processing, and DMN state.

Exposes tools:
- hormiguita
- hormiguita_estado
- estado_dmn
"""

import os
import json
from typing import Any

from core.paths import project_root
from core.mcp_server._shared import _get_cerebro


def register(mcp: Any) -> None:
    @mcp.tool(
        name="hormiguita",
        description=(
            "Procesa UN nodo específico con la Hormiguita (Gemini). "
            "Evalúa sinapsis directas y latentes del nodo usando IA y poda conexiones espurias. "
            "Usa pre-filtrado para ahorrar tokens.\n\n"
            "NOTA: Solo procesa nodos individuales. El ciclo completo del daemon "
            "corre como proceso separado (siempre vivo), no en el dashboard.\n\n"
            "Parámetros:\n"
            "- nodo_especifico (str, OBLIGATORIO): Nombre del nodo a procesar\n\n"
            "Retorna: resultado del procesamiento con veredictos, aplicados, eliminados."
        ),
    )
    def biorag_hormiguita(max_nodos: int = 5, nodo_especifico: str = "", force: bool = True) -> str:
        from core.dmn_reflexion import (
            procesar_nodo_unico,
            _cargar_estado,
            _guardar_estado,
        )

        if not nodo_especifico:
            return json.dumps({
                "status": "error",
                "error": "Modo general desactivado. Usá 'nodo_especifico' para procesar un nodo concreto.",
                "mensaje": "El daemon es el único que ejecuta ciclos completos. "
                           "El MCP solo procesa nodos individuales bajo demanda.",
            }, ensure_ascii=False, default=str)

        # Guard visitados_hoy: si ya se procesó hoy, no llamar a Gemini
        ESTADO_HORMIGA_PATH = os.path.join(project_root(), "estado_hormiga.json")
        os.environ["BIORAG_DMN_ESTADO_PATH"] = ESTADO_HORMIGA_PATH
        estado = _cargar_estado()
        if not force and nodo_especifico in estado.get("visitados_hoy", []):
            return json.dumps({
                "status": "ya_procesado",
                "mensaje": f"'{nodo_especifico}' ya fue procesado hoy. Usá force=True para reprocesar.",
                "nodo": nodo_especifico,
                "veredictos": 0,
                "aplicados": 0,
                "eliminados": 0,
                "prefiltrados": 0,
                "lotes": 0,
                "completo": True,
            }, ensure_ascii=False, default=str)

        cerebro = _get_cerebro()
        try:
            resultado = procesar_nodo_unico(nodo_especifico, cerebro, force=force)
            # Marcar como procesado hoy
            if resultado.get("status") == "ok":
                estado = _cargar_estado()
                if nodo_especifico not in estado.get("visitados_hoy", []):
                    estado["visitados_hoy"].append(nodo_especifico)
                    _guardar_estado(estado)
            return json.dumps(resultado, ensure_ascii=False, default=str)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="hormiguita_estado",
        description=(
            "Muestra el estado actual de la hormiguita: nodos visitados, "
            "frontier pendiente, ciclos completados, tokens gastados. Sin parámetros."
        ),
    )
    def biorag_hormiguita_estado() -> str:
        from core.dmn_reflexion import _cargar_estado
        estado = _cargar_estado()
        return json.dumps({
            "ciclos_completados": estado.get("ciclos_completados", 0),
            "nodo_actual": estado.get("nodo_actual"),
            "visitados_hoy": len(estado.get("visitados_hoy", [])),
            "visitados_total": len(estado.get("visitados_total", [])),
            "frontier_pendiente": len(estado.get("frontier", [])),
            "tokens_gastados_hoy": estado.get("tokens_gastados_hoy", 0),
            "frontier_preview": estado.get("frontier", [])[:10],
        }, ensure_ascii=False, default=str)

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
