"""MCP Tools for synaptic graph link management and dopaminergic feedback.

Exposes tools:
- feedback
- vincular
- desvincular
- asociar
"""

import json
from typing import Annotated, Optional, Any
from pydantic import Field

from core.mcp_server._shared import _get_cerebro, _interceptar


def register(mcp: Any) -> None:
    @mcp.tool(
        name="feedback",
        description=(
            "Refuerzo Dopaminérgico por Error de Predicción de Recompensa (RPE v20.0 - Schultz 1997).\n"
            "HÁBITO OBLIGATORIO (no excepción): usá esta tool cada vez que un recuerdo recuperado con recordar() INFLUYA en tu respuesta — marcá util=True si sirvió, util=False si fue ruido.\n"
            "Casos activables: 1) confirmación explícita del usuario, 2) verificación por test/build, 3) tras usar un recuerdo en la respuesta (caso más común), 4) al cierre de sesión, 5) excepción única: duda real sin evidencia → no disparar.\n"
            "Aplica el Factor de Inercia Sináptica: nodos consolidados con historial de éxitos resisten fallos aislados, mientras que nodos nuevos son corregibles al instante."
        ),
    )
    def biorag_feedback(
        concepto: Annotated[str, Field(description="Nombre del concepto/nodo a retroalimentar (snake_case).")],
        util: Annotated[bool, Field(description="True si la memoria fue útil para resolver la tarea; False si fue irrelevante o errónea.")],
        motivo: Annotated[Optional[str], Field(description="Motivo u observación opcional sobre el feedback.")] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            exito = cerebro.aplicar_refuerzo_dopaminergico(concepto, exito=util, motivo=motivo)
            if not exito:
                return json.dumps({"status": "error", "mensaje": f"El concepto '{concepto}' no existe en largo plazo."}, ensure_ascii=False)
            accion = "Disparo dopaminérgico (+LTP)" if util else "Depresión por fracaso (-LTD)"
            return json.dumps({"status": "ok", "mensaje": f"Feedback dopaminérgico aplicado a '{concepto}': {accion}"}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="vincular",
        description=(
            "Conectá dos nodos entre sí. Si A se conecta con B, B también se conecta con A. Ambos nodos deben existir ya en la memoria (guardados con aprender o consolidados). Cuando buscás uno, el otro aparece como resultado relacionado."
        ),
    )
    def biorag_vincular(
        a: Annotated[str, Field(
            description=(
                "a: Nombre del primer nodo (snake_case). Debe existir en la memoria."
            )
        )],
        b: Annotated[str, Field(
            description=(
                "b: Nombre del segundo nodo (snake_case). Debe existir en la memoria.\n\n"
                "La conexión es bidireccional: buscar A trae B, y buscar B trae A."
            )
        )],
    ) -> str:
        cerebro = _get_cerebro()
        try:
            cerebro.establecer_asociacion(a, b)
            _interceptar("vincular", f"{a} <--> {b}", cerebro)
            return json.dumps({
                "status": "ok",
                "mensaje": f"Sinapsis: '{a}' <--> '{b}'",
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="desvincular",
        description=(
            "Borrá la conexión entre dos nodos. Si al buscar A aparece B pero no tiene relación, llamá\n\n"
            "desvincular(a='A', b='B'). Cada conexión incorrecta que borrás mejora las búsquedas futuras."
        ),
    )
    def biorag_desvincular(
        a: Annotated[str, Field(
            description="Primer concepto (clave normalizada)."
        )],
        b: Annotated[str, Field(
            description="Segundo concepto (clave normalizada)."
        )],
        autor: Annotated[Optional[str], Field(
            description="Nombre del agente que reporta el falso positivo (para trazabilidad)."
        )] = None,
        query: Annotated[Optional[str], Field(
            description="Query que generó el falso positivo (para trazabilidad)."
        )] = None,
    ) -> str:
        from core.sinapsis import desvincular
        cerebro = _get_cerebro()
        try:
            eliminadas = desvincular(cerebro, a, b, autor=autor, query=query)
            return json.dumps({
                "status": "ok",
                "mensaje": f"Sinapsis eliminadas entre '{a}' y '{b}'",
                "eliminadas": eliminadas,
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="asociar",
        description=(
            "(legado) Alias de 'vincular' — preferir 'vincular' para identificar la operación cognitiva real. "
            "Parámetros: a (str), b (str) — ambos deben existir en la corteza. "
            "Retorna: {status, mensaje}"
        ),
    )
    def biorag_asociar(
        a: Annotated[str, Field(description="Primer concepto (clave normalizada).")],
        b: Annotated[str, Field(description="Segundo concepto (clave normalizada). La asociación es bidireccional.")],
    ) -> str:
        return biorag_vincular(a, b)
