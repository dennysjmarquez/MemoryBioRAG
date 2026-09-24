"""MCP Tools for session context management (interceptor v2).

Exposes tools:
- contexto_inicio
- contexto_fin
"""

import io
import json
import sys
import time
from typing import Annotated, Any
from pydantic import Field

from core.mcp_server._shared import _get_cerebro, _sesiones_activas
from middleware.auto_guardado import registrar_accion, analizar_y_autoguardar


def register(mcp: Any) -> None:
    @mcp.tool(
        name="contexto_inicio",
        description=(
            "Avisá que empezó una sesión importante. Guardá el contexto para que el interceptor detecte automáticamente lecciones, errores y patrones durante la charla. Llamá al inicio de cada sesión de trabajo importante."
        ),
    )
    def biorag_contexto_inicio(
        agente: Annotated[str, Field(
            description=(
                "agente: Quién está hablando (ej: 'Agente 1', 'Agente 1', 'Agente 3', 'Etc..')"
            )
        )],
        contexto: Annotated[str, Field(
            description=(
                "Descripción breve del contexto o tarea de la sesión "
                "(ej: 'Refactor del módulo de autenticación', 'Análisis de logs de producción'). "
                "Ayuda al interceptor a categorizar correctamente los autoguardados."
            )
        )] = "",
    ) -> str:
        cerebro = _get_cerebro()
        try:
            _sesiones_activas[agente] = time.time()
            registrar_accion("inicio", f"[{agente}] {contexto}")
            return json.dumps({"status": "ok", "mensaje": "Contexto de inicio registrado.", "ventana_extension": True}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="contexto_fin",
        description=(
            "Avisá que terminó la sesión. Revisá todo lo que pasó — si hay algo valioso (lecciones, errores, patrones), guardalo automáticamente. Si hay nodos nuevos sin consolidar, consolidalos. Llamá al final de cada sesión importante."
        ),
    )
    def biorag_contexto_fin(
        agente: Annotated[str, Field(
            description="Nombre del agente que cierra la sesión (ej: 'agente_1')."
        )],
        resumen: Annotated[str, Field(
            description=(
                "resumen: Qué hiciste en la sesión en una línea (ej: 'Corregimos el bug de autenticación y actualizamos los tests'). Mejora el autoguardado del interceptor."
            )
        )] = "",
    ) -> str:
        cerebro = _get_cerebro()
        try:
            _sesiones_activas.pop(agente, None)
            registrar_accion("fin", f"[{agente}] {resumen}")
            resultado = analizar_y_autoguardar(cerebro, fuerza=True)
            if resultado:
                consolidado = cerebro.consolidar_concepto(resultado["concepto"])
                if consolidado:
                    msg = f"Auto-guardado y consolidado: '{resultado['concepto']}' ({resultado['categoria']}). Ya en corteza permanente."
                else:
                    msg = f"Auto-guardado en corto plazo: '{resultado['concepto']}'. Consolidacion pendiente."
            else:
                msg = "No se detecto nada nuevo que amerite guardado."

            # Auto-sueño: consolidar si hay datos en corto_plazo
            cerebro.cursor.execute("SELECT COUNT(*) FROM corto_plazo")
            n_corto = cerebro.cursor.fetchone()[0]
            if n_corto > 0:
                old_stdout = sys.stdout
                sys.stdout = captured = io.StringIO()
                try:
                    cerebro.ciclo_sueno_consolidacion()
                finally:
                    sys.stdout = old_stdout
                sleep_output = captured.getvalue().strip()
                msg += f" | Auto-sueño: {n_corto} nodo(s) consolidado(s)."

            return json.dumps({
                "status": "ok",
                "mensaje": msg,
                "auto_guardado": resultado,
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()
