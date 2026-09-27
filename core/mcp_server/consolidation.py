"""MCP Tools for memory consolidation and sleep cycle management.

Exposes tools:
- consolidar
- sueno
"""

import io
import json
import sys
import time
from typing import Any

from core.mcp_server._shared import _get_cerebro, _interceptar

_ULTIMO_SUENO_TS: float = 0.0


def register(mcp: Any) -> None:
    @mcp.tool(
        name="consolidar",
        description=(
            "Fijá los recuerdos nuevos permanentemente. Llamá a consolidar después de aprender. Si no lo hacés, los nodos nuevos se borran en el siguiente ciclo.\n\n"
            "El ciclo de sueño hace: fortalece nodos nuevos, debilita los viejos, borra conexiones débiles, evita saturación, y mueve todo de memoria temporal a permanente.\n\n"
            "La energía se calcula automáticamente (nodos activos × 1.6, mínimo 10). No requiere parámetros."
        ),
    )
    def biorag_consolidar() -> str:
        global _ULTIMO_SUENO_TS
        cerebro = _get_cerebro()
        try:
            ahora = time.time()
            n_pendientes = 0
            try:
                n_pendientes = cerebro.cursor.execute("SELECT COUNT(*) FROM corto_plazo").fetchone()[0]
            except Exception:
                pass

            if n_pendientes == 0 and (ahora - _ULTIMO_SUENO_TS) < 15.0:
                return json.dumps({
                    "status": "ok",
                    "mensaje": "⚡ Consolidación omitida: No hay recuerdos nuevos en memoria temporal (corto_plazo) y el último ciclo de sueño ocurrió recientemente.",
                    "nodos_pendientes": 0,
                    "guardrail_activo": True
                }, ensure_ascii=False)

            old_stdout = sys.stdout
            sys.stdout = captured = io.StringIO()
            try:
                cerebro.ciclo_sueno_consolidacion()
                _ULTIMO_SUENO_TS = time.time()
            finally:
                sys.stdout = old_stdout
            output = captured.getvalue()
            _interceptar("consolidar", output.strip(), cerebro)
            return json.dumps({
                "status": "ok",
                "mensaje": output.strip(),
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="sueno",
        description=(
            "Alias viejo de consolidar. Usá consolidar en vez de esta. Misma funcionalidad, sin parámetros."
        ),
    )
    def biorag_sueno() -> str:
        return biorag_consolidar()
