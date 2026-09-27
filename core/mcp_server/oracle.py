"""MCP Tools for NotebookLM oracle integration.

Exposes tools:
- oraculo_inicio
- oraculo_preguntar

Internal helpers (module-private):
- _preview
- _nlm_detectado
- _consultar_notebooklm
- _buscar_contexto_biorag_arranque
"""

import json
import logging
import shutil
import subprocess
from typing import Annotated, Any

from pydantic import Field

from core.mcp_server._shared import (
    AGENTES_VALIDOS,
    NOTEBOOK_ID_ORACULO,
    ORACULO_MAX_CHARS,
    PROMPT_INICIO_NOTEBOOKLM,
    QUERIES_BIORAG_INICIO,
)

logger = logging.getLogger("BioRAG.MCP")


def _preview(text: str, limit: int = 1500) -> str:
    if not text:
        return ""
    return text[:limit] + ("..." if len(text) > limit else "")


def _nlm_detectado() -> bool:
    """Devuelve True si el CLI nlm esta disponible en PATH."""
    return shutil.which("nlm") is not None


def _consultar_notebooklm(notebook_id: str, query: str) -> dict | None:
    """Consulta el cuaderno NotebookLM via CLI nlm y devuelve la respuesta.

    Si nlm no esta disponible, o si nlm falla por cualquier motivo
    (incluyendo query muy largo rechazado por Google), devuelve None
    para que el llamador decida devolver el query preparado en lugar
    del resultado del oraculo.
    """
    if not _nlm_detectado():
        return None
    try:
        result = subprocess.run(
            ["nlm", "notebook", "query", notebook_id, query],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            error_detail = result.stderr.strip() or result.stdout.strip()
            logger.warning(
                "nlm fallo (codigo %s): %s",
                result.returncode,
                error_detail[:500],
            )
            return None
        return {
            "status": "ok",
            "respuesta": result.stdout.strip(),
        }
    except subprocess.TimeoutExpired:
        logger.warning("nlm excedio el tiempo de espera")
        return None
    except Exception as exc:
        logger.warning("Error ejecutando nlm: %s", exc)
        return None


def _buscar_contexto_biorag_arranque(cerebro, agente: str) -> dict:
    """Consulta BioRAG con queries predefinidas y devuelve un resumen."""
    hallazgos = []
    for q in QUERIES_BIORAG_INICIO:
        try:
            resultados, _ = cerebro.buscar_por_frase(
                q,
                profundidad="activos",
                limite=2,
                preview_chars=1000,
            )
            for concepto, contenido, peso, estado, score, asociaciones in resultados:
                hallazgos.append({
                    "concepto": concepto,
                    "contenido": _preview(contenido, 1000),
                    "peso_sinaptico": peso,
                    "estado": estado,
                    "score_hibrido": score,
                })
        except Exception as exc:
            logger.warning("Error consultando '%s' en arranque: %s", q, exc)
    return {
        "agente": agente,
        "total_hallazgos": len(hallazgos),
        "hallazgos": hallazgos,
    }


def register(mcp: Any) -> None:
    from core.mcp_server._shared import _get_cerebro

    @mcp.tool(
        name="oraculo_inicio",
        description=(
            "Inicialización opcional con el oráculo NotebookLM. "
            "Si NotebookLM no está configurado (BIORAG_NOTEBOOK_ID), responde instantáneamente indicando que se use la memoria local con recordar().\n\n"
            "NO es obligatoria para operar. Para buscar recuerdos en la memoria local, usá directamente 'recordar(query=...)'.\n\n"
            "Si se dispone de un cuaderno NotebookLM configurado con el CLI nlm, consulta el cuaderno para obtener el contexto inicial de arranque."
        ),
    )
    def biorag_oraculo_inicio(
        agente: Annotated[str, Field(
            description=(
                "agente: Quién está hablando. Solo el nombre del agente (no importa mayúsculas). Si se omite o es inválido, la tool tira error."
            )
        )],
        contexto_adicional: Annotated[str, Field(
            description=(
                "contexto_adicional: Contexto extra para que el oráculo sepa de qué va la sesión (ej: 'Refactor del módulo de autenticación'). "
                "Solo sirve si NotebookLM está configurado."
            )
        )] = "",
    ) -> str:
        if not agente or not agente.strip():
            return json.dumps({
                "status": "error",
                "mensaje": "El parámetro `agente` es obligatorio. Ejemplo: agente='agente_1'.",
            }, ensure_ascii=False)

        agente_limpio = agente.strip().lower()
        if AGENTES_VALIDOS and agente_limpio not in AGENTES_VALIDOS:
            return json.dumps({
                "status": "error",
                "mensaje": f"Agente '{agente}' no reconocido. Agentes válidos: {', '.join(sorted(AGENTES_VALIDOS))}.",
            }, ensure_ascii=False)

        tiene_prompt = bool(PROMPT_INICIO_NOTEBOOKLM)
        tiene_notebook_id = bool(NOTEBOOK_ID_ORACULO)

        # Si NotebookLM no está configurado, responder DE INMEDIATO (<1ms) sin bloquear la sesión ni hacer búsquedas pesadas.
        if not tiene_notebook_id or not tiene_prompt:
            return json.dumps({
                "status": "no_configurado",
                "modo": "sin_oraculo",
                "mensaje": (
                    "El oráculo externo NotebookLM no está configurado (BIORAG_NOTEBOOK_ID no seteado). "
                    "Para buscar recuerdos o contexto en BioRAG local, usá directamente 'recordar(query=...)'."
                ),
                "agente": agente_limpio,
            }, ensure_ascii=False, indent=2)

        if not _nlm_detectado():
            return json.dumps({
                "status": "no_disponible",
                "modo": "sin_oraculo",
                "mensaje": (
                    "El CLI 'nlm' de NotebookLM no está disponible en PATH. "
                    "Para buscar recuerdos en BioRAG local, usá directamente 'recordar(query=...)'."
                ),
                "agente": agente_limpio,
                "advertencia": "Instalalo con: pip install notebooklm-cli && nlm login",
            }, ensure_ascii=False, indent=2)

        # nlm está disponible: consultar NotebookLM directamente.
        query_notebook = f"{agente.strip()}: {PROMPT_INICIO_NOTEBOOKLM}"
        if contexto_adicional and contexto_adicional.strip():
            query_notebook += f" Contexto adicional: {contexto_adicional.strip()}"

        oraculo = _consultar_notebooklm(NOTEBOOK_ID_ORACULO, query_notebook)

        if oraculo is None:
            return json.dumps({
                "status": "error",
                "modo": "sin_oraculo",
                "mensaje": "nlm está instalado pero falló la consulta a NotebookLM. Usá 'recordar' directamente para buscar en BioRAG.",
                "agente": agente_limpio,
            }, ensure_ascii=False, indent=2)

        respuesta_oraculo = oraculo["respuesta"]
        if ORACULO_MAX_CHARS > 0 and len(respuesta_oraculo) > ORACULO_MAX_CHARS:
            respuesta_oraculo = (
                respuesta_oraculo[:ORACULO_MAX_CHARS].rstrip()
                + f"\n\n[ORACULO TRUNCADO: respuesta original de {len(oraculo['respuesta'])} "
                f"caracteres truncada a {ORACULO_MAX_CHARS}. "
                "Ajusta BIORAG_ORACULO_MAX_CHARS si necesitas mas contexto.]"
            )

        resultado = {
            "status": "ok",
            "modo": "notebooklm",
            "agente": agente_limpio,
            "notebooklm_notebook_id": NOTEBOOK_ID_ORACULO,
            "nlm_detectado": True,
            "nlm_fallo": False,
            "oraculo": respuesta_oraculo,
            "mensaje": "Oraculo NotebookLM consultado. Usa la respuesta como contexto de arranque.",
        }
        return json.dumps(resultado, ensure_ascii=False, indent=2)

    # ── ORACULO PREGUNTAR ────────────────────────────────────────────────────

    @mcp.tool(
        name="oraculo_preguntar",
        description=(
            "Consultá el oráculo (cuaderno NotebookLM) con una pregunta específica. "
            "Requiere que nlm esté instalado y BIORAG_NOTEBOOK_ID configurado.\n\n"
            "Formato de la query: 'Agente: pregunta'. El nombre del agente es OBLIGATORIO — "
            "sin él, el oráculo no responde.\n\n"
            "Si nlm no está instalado → error descriptivo con instrucción de instalación.\n"
            "Si BIORAG_NOTEBOOK_ID no está configurado → error con instrucción de configuración."
        ),
    )
    def biorag_oraculo_preguntar(
        agente: Annotated[str, Field(
            description=(
                "Quién está preguntando. Solo el nombre del agente (no importa mayúsculas). "
                "OBLIGATORIO — sin esto, el oráculo no identifica al consultante."
            )
        )],
        query: Annotated[str, Field(
            description=(
                "La pregunta a hacer al oráculo. Ejemplo: '¿Qué información hay sobre la arquitectura del sistema?'. "
                "OBLIGATORIO — no puede estar vacío."
            )
        )],
    ) -> str:
        # Validar agente.
        if not agente or not agente.strip():
            return json.dumps({
                "status": "error",
                "mensaje": "El parámetro `agente` es obligatorio. Ejemplo: agente='agente_1'.",
            }, ensure_ascii=False)

        agente_limpio = agente.strip().lower()
        if AGENTES_VALIDOS and agente_limpio not in AGENTES_VALIDOS:
            return json.dumps({
                "status": "error",
                "mensaje": f"Agente '{agente}' no reconocido. Agentes válidos: {', '.join(sorted(AGENTES_VALIDOS))}.",
            }, ensure_ascii=False)

        # Validar query.
        if not query or not query.strip():
            return json.dumps({
                "status": "error",
                "mensaje": "El parámetro `query` es obligatorio. Ejemplo: query='¿Qué tengo sobre X?'.",
            }, ensure_ascii=False)

        # Verificar que nlm esté instalado.
        if not _nlm_detectado():
            return json.dumps({
                "status": "error",
                "mensaje": (
                    "NotebookLM CLI (nlm) no está instalado. "
                    "Instalalo con: pip install notebooklm-cli && nlm login"
                ),
            }, ensure_ascii=False)

        # Verificar que BIORAG_NOTEBOOK_ID esté configurado.
        if not NOTEBOOK_ID_ORACULO:
            return json.dumps({
                "status": "error",
                "mensaje": (
                    "BIORAG_NOTEBOOK_ID no está configurado en variables de entorno. "
                    "Setealo con el ID de tu cuaderno NotebookLM."
                ),
            }, ensure_ascii=False)

        # Construir query con formato "Agente: pregunta".
        query_completa = f"{agente.strip()}: {query.strip()}"

        # Ejecutar consulta.
        oraculo = _consultar_notebooklm(NOTEBOOK_ID_ORACULO, query_completa)

        if oraculo is None:
            return json.dumps({
                "status": "error",
                "mensaje": (
                    "nlm falló al consultar NotebookLM. "
                    "Posibles causas: query muy largo, timeout, o nlm no autenticado (ejecutá 'nlm login')."
                ),
                "nlm_detectado": True,
                "notebooklm_notebook_id": NOTEBOOK_ID_ORACULO,
            }, ensure_ascii=False)

        respuesta = oraculo["respuesta"]
        if ORACULO_MAX_CHARS > 0 and len(respuesta) > ORACULO_MAX_CHARS:
            respuesta = (
                respuesta[:ORACULO_MAX_CHARS].rstrip()
                + f"\n\n[TRUNCADO: respuesta original de {len(oraculo['respuesta'])} "
                f"caracteres truncada a {ORACULO_MAX_CHARS}. "
                "Ajusta BIORAG_ORACULO_MAX_CHARS si necesitas más contexto.]"
            )

        return json.dumps({
            "status": "ok",
            "agente": agente_limpio,
            "respuesta": respuesta,
            "notebooklm_notebook_id": NOTEBOOK_ID_ORACULO,
        }, ensure_ascii=False, indent=2)
