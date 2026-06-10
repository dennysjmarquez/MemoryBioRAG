#!/usr/bin/env python3
"""BioRAG MCP Server — Memoria compartida OEC via Model Context Protocol.

Expone la corteza biologica de BioRAG como herramientas MCP para que
cualquier IDE/CLI (OpenCode, VS Code, Cursor, Cline) se conecte a la
memoria compartida de los agentes OEC sin ejecutar comandos shell.

Uso:
  python3 mcp_server.py              # stdio transport (modo subproceso)
  python3 mcp_server.py --sse        # SSE transport (modo servidor HTTP)

Para conectar desde OpenCode, anadir a opencode.json:
  "mcpServers": {
    "biorag": {
      "command": "python3",
      "args": ["/ruta/a/MemoryBioRAG/mcp_server.py"]
    }
  }

Para conectar desde VS Code, anadir a .vscode/mcp.json:
  {
    "servers": {
      "biorag": {
        "type": "stdio",
        "command": "python3",
        "args": ["/ruta/a/MemoryBioRAG/mcp_server.py"]
      }
    }
  }
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from typing import Any, Optional

logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] biorag-mcp: %(message)s",
)
logger = logging.getLogger(__name__)


# --- Boot -------------------------------------------------------------------

_DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "MemoryBioRAG_Data",
    "memory_biorag.db",
)
DB_PATH = os.environ.get("BIORAG_PATH") or _DEFAULT_DB

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.memory_store import SQLiteMemoryBioRAG
from core.sinapsis import auto_vincular, vincular_por_sinonimos
from core.categorizador import inferir_categoria
from middleware.auto_guardado import registrar_accion, analizar_y_autoguardar


# --- Helpers ----------------------------------------------------------------

def _get_cerebro() -> SQLiteMemoryBioRAG:
    return SQLiteMemoryBioRAG(db_path=DB_PATH)


def _preview(text: str, limit: int = 1500) -> str:
    if not text:
        return ""
    return text[:limit] + ("..." if len(text) > limit else "")


def _interceptar(accion: str, texto: str, cerebro) -> dict | None:
    registrar_accion(accion, texto)
    resultado = analizar_y_autoguardar(cerebro)
    if resultado:
        logger.info("auto-guardado: %s (%s)", resultado["concepto"], resultado["categoria"])
    return resultado


# --- MCP Server ------------------------------------------------------------

def _build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise ImportError(
            "BioRAG MCP server requires the 'mcp' package.\n"
            f"  pip install mcp\n  ({exc})"
        ) from exc

    mcp = FastMCP(
        "biorag",
        instructions=(
            "BioRAG: sistema de memoria biomimetica compartida para agentes OEC. "
            "Expone una corteza cerebral con busqueda hibrida (FTS5 trigram + "
            "peso sinaptico + asociaciones), consolidacion por sueno, plasticidad "
            "sináptica (LTP/LTD), y comunicacion entre agentes. "
            "Usa estas herramientas para acceder a la memoria persistente "
            "de la familia OEC (Athena, Artemis, Hermes)."
        ),
    )

    # ── TOOLS ────────────────────────────────────────────────────────────────

    @mcp.tool(
        name="biorag_buscar",
        description=(
            "Busca recuerdos en la corteza compartida. "
            "Usa busqueda hibrida: 60% BM25 + 25% peso sinaptico + 15% asociaciones. "
            "FTS5 trigram tolera typos automaticamente. "
            "Los sinonimos del nodo se buscan tambien."
        ),
    )
    def biorag_buscar(
        query: str,
        deep: bool = False,
        cat: Optional[str] = None,
        completo: bool = False,
        asociados: bool = False,
        limite: int = 10,
        preview_chars: Optional[int] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            if preview_chars is None:
                preview_chars = 0 if completo else 1500
            profundidad = "profundo" if deep else "activos"
            resultados, total = cerebro.buscar_por_frase(
                query, profundidad=profundidad, limite=limite,
                categoria=cat, preview_chars=preview_chars
            )
            if not resultados:
                cerebro.cerrar_sistema()
                return json.dumps({"total": 0, "resultados": []}, ensure_ascii=False)

            items = []
            for concepto, contenido, peso, estado, score, asociaciones in resultados:
                items.append({
                    "concepto": concepto,
                    "contenido": contenido,
                    "peso_sinaptico": peso,
                    "estado": estado,
                    "score_hibrido": score,
                    "asociaciones": [
                        v.strip() for v in (asociaciones or "").split(",") if v.strip()
                    ] if asociados and asociaciones else [],
                })

            resultado = json.dumps({
                "total": total,
                "resultados": items,
                "profundidad": profundidad,
            }, ensure_ascii=False)
            _interceptar("buscar", query, cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="biorag_guardar",
        description=(
            "Guarda un recuerdo en la memoria de corto plazo. "
            "Usar biorag_sueno despues para consolidar a largo plazo."
        ),
    )
    def biorag_guardar(
        concepto: str,
        contenido: str,
        syn: Optional[str] = None,
        cat: Optional[str] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            clave = concepto.lower().replace(" ", "_")
            categoria = cat or inferir_categoria(contenido)
            cerebro.percibir_corto_plazo(clave, contenido, syn or "", categoria)

            enlaces = auto_vincular(cerebro, clave, contenido)
            sinapsis_count = len(enlaces)

            if syn:
                syn_enlaces = vincular_por_sinonimos(cerebro, clave, syn)
                todas = list({e[0]: e for e in enlaces + syn_enlaces}.values())
                sinapsis_count = len(todas)

            msg = f"'{clave}' guardado en corto plazo."
            if syn:
                msg += f" Sinonimos: {syn}."
            if categoria != "general":
                msg += f" Categoria: {categoria}."
            if sinapsis_count:
                msg += f" Vinculado con {sinapsis_count} nodo(s)."
            msg += " Usa biorag_sueno para consolidar."
            _interceptar("guardar", f"{clave}: {contenido}", cerebro)
            return json.dumps({
                "status": "ok",
                "mensaje": msg,
                "concepto": clave,
                "sinapsis": sinapsis_count,
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="biorag_asociar",
        description="Crea un enlace sinaptico bidireccional entre dos conceptos.",
    )
    def biorag_asociar(a: str, b: str) -> str:
        cerebro = _get_cerebro()
        try:
            cerebro.establecer_asociacion(a, b)
            _interceptar("asociar", f"{a} <--> {b}", cerebro)
            return json.dumps({
                "status": "ok",
                "mensaje": f"Sinapsis: '{a}' <--> '{b}'",
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="biorag_comunicar",
        description=(
            "Envia un mensaje a otro agente OEC (athena, artemis, hermes, todos). "
            "Identificate con AGENT_NAME."
        ),
    )
    def biorag_comunicar(destino: str, mensaje: str, origen: Optional[str] = None) -> str:
        agente = origen or os.environ.get("AGENT_NAME", "desconocido")
        cerebro = _get_cerebro()
        try:
            cerebro.enviar_comunicado(agente, destino, mensaje)
            _interceptar("comunicar", f"{agente} -> {destino}: {mensaje}", cerebro)
            return json.dumps({
                "status": "ok",
                "mensaje": f"Mensaje de {agente} para {destino} registrado.",
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="biorag_leer_mensajes",
        description="Lee mensajes del canal compartido entre agentes OEC.",
    )
    def biorag_leer_mensajes(
        no_leidos: bool = False,
        ultimos: int = 10,
        para: Optional[str] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            mensajes = cerebro.leer_comunicados(
                destino=para, solo_no_leidos=no_leidos, ultimos=ultimos
            )
            if not mensajes:
                return json.dumps({"total": 0, "mensajes": []}, ensure_ascii=False)

            items = []
            ids_a_marcar = []
            for msg_id, origen, dest, contenido, ts, leido in reversed(mensajes):
                items.append({
                    "id": msg_id,
                    "origen": origen,
                    "destino": dest,
                    "contenido": contenido,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)),
                    "leido": bool(leido),
                })
                if not leido:
                    ids_a_marcar.append(msg_id)

            if ids_a_marcar:
                cerebro.marcar_como_leido(ids_a_marcar)

            resultado = json.dumps({"total": len(items), "mensajes": items}, ensure_ascii=False)
            if items:
                textos = [m["contenido"] for m in items[:3]]
                _interceptar("leer_mensajes", " ".join(textos), cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="biorag_sueno",
        description=(
            "Consolida la memoria de corto plazo a largo plazo. "
            "Aplica LTP a nuevos recuerdos, LTD por decaimiento, "
            "duerme nodos debiles, e inhibicion lateral. "
            "limite_energia: opcional, defecto dinamico (n_activos * 1.3, min 10.0)."
        ),
    )
    def biorag_sueno(limite_energia: Optional[float] = None) -> str:
        cerebro = _get_cerebro()
        try:
            import io
            old_stdout = sys.stdout
            sys.stdout = captured = io.StringIO()
            try:
                cerebro.ciclo_sueno_consolidacion(limite_energia=limite_energia)
            finally:
                sys.stdout = old_stdout
            output = captured.getvalue()
            _interceptar("sueno", output.strip(), cerebro)
            return json.dumps({
                "status": "ok",
                "mensaje": output.strip(),
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="biorag_estado",
        description="Muestra estadisticas de la corteza: nodos activos, dormidos, energia sinaptica.",
    )
    def biorag_estado() -> str:
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
            _interceptar("estado", f"activos:{activos} dormidos:{dormidos}", cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="biorag_corteza",
        description="Lista todos los nodos de la corteza permanente (activos y dormidos).",
    )
    def biorag_corteza() -> str:
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
            _interceptar("corteza", "", cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()

    # ── TOOLS (Interceptor V2) ──────────────────────────────────────────────

    @mcp.tool(
        name="biorag_contexto_inicio",
        description=(
            "Anuncia el inicio de una interaccion significativa. "
            "Almacena el contexto en el buffer de sesion para que el "
            "interceptor pueda autoguardar si detecta algo importante."
        ),
    )
    def biorag_contexto_inicio(agente: str, contexto: str = "") -> str:
        cerebro = _get_cerebro()
        try:
            registrar_accion("inicio", f"[{agente}] {contexto}")
            return json.dumps({"status": "ok", "mensaje": "Contexto de inicio registrado."}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="biorag_contexto_fin",
        description=(
            "Anuncia el fin de una interaccion. Fuerza el analisis del "
            "buffer de sesion acumulado y autoguarda si detecta algo nuevo."
        ),
    )
    def biorag_contexto_fin(agente: str, resumen: str = "") -> str:
        cerebro = _get_cerebro()
        try:
            registrar_accion("fin", f"[{agente}] {resumen}")
            resultado = analizar_y_autoguardar(cerebro, fuerza=True)
            if resultado:
                consolidado = cerebro.consolidar_concepto(resultado["concepto"])
                if consolidado:
                    msg = f"Auto-guardado y consolidado: '{resultado['concepto']}' ({resultado['categoria']}). Ya en corteza permanente."
                else:
                    msg = f"Auto-guardado en corto plazo: '{resultado['concepto']}' ({resultado['categoria']}). Consolidacion fallo."
            else:
                msg = "No se detecto nada nuevo que amerite guardado."
            return json.dumps({
                "status": "ok",
                "mensaje": msg,
                "auto_guardado": resultado,
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    # ── RESOURCES ────────────────────────────────────────────────────────────

    @mcp.resource(
        uri="biorag://concepto/{nombre}",
        name="Concepto de la corteza",
        description="Contenido completo de un concepto almacenado en la corteza.",
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
        description="Mensajes pendientes en el canal compartido OEC.",
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

    # ── PROMPTS ──────────────────────────────────────────────────────────────

    @mcp.prompt(
        name="biorag-system-prompt",
        description="Reglas de acceso a memoria BioRAG para incorporar en el system prompt del agente.",
    )
    def prompt_biorag() -> str:
        return (
            "## BioRAG — Memoria Compartida OEC\n\n"
            "Tienes acceso a una corteza cerebral compartida via MCP tools "
            "(biorag_buscar, biorag_guardar, biorag_asociar, ...).\n\n"
            "Reglas:\n"
            "1. Si el usuario menciona algo ya visto -> biorag_buscar\n"
            "2. Si el usuario ensena algo nuevo -> biorag_guardar + biorag_sueno\n"
            "3. Si dos conceptos estan relacionados -> biorag_asociar\n"
            "4. Si necesitas dejar mensaje a otro agente -> biorag_comunicar\n"
            "5. Si al iniciar sesion quieres ver mensajes -> biorag_leer_mensajes\n"
            "6. Si despues de 2 busquedas no encuentras -> preguntar al humano\n\n"
            "Interceptor V2 (autoguardado):\n"
            "- Al iniciar una interaccion importante -> biorag_contexto_inicio\n"
            "- Al terminar una interaccion -> biorag_contexto_fin\n"
            "- El interceptor analiza el buffer acumulado y autoguarda si\n"
            "  detecta lecciones, patrones, errores o preferencias.\n"
            "- No necesitas recordar llamar guardar explicitamente cada vez.\n\n"
            "TTL: 30 min de inactividad resetean el buffer (siesta biomimetica).\n\n"
            "La memoria decae naturalmente (LTD). Los nodos no usados se "
            "duermen solos. Usa biorag_sueno para consolidar recuerdos nuevos."
        )

    return mcp


# --- Entry point ------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    argv = argv or sys.argv[1:]
    use_sse = "--sse" in argv
    port = 8080
    for i, a in enumerate(argv):
        if a == "--port" and i + 1 < len(argv):
            try:
                port = int(argv[i + 1])
            except ValueError:
                pass

    try:
        server = _build_server()
    except ImportError as exc:
        sys.stderr.write(f"BioRAG MCP: {exc}\n")
        return 2

    try:
        if use_sse:
            sys.stderr.write(f"BioRAG MCP iniciado en SSE :{port}\n")
            server.run(transport="sse", port=port)
        else:
            sys.stderr.write("BioRAG MCP iniciado (stdio)\n")
            server.run(transport="stdio")
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        logger.exception("BioRAG MCP server crashed")
        sys.stderr.write(f"BioRAG MCP server error: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
