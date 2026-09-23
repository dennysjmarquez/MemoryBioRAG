"""MCP Tools for inter-agent communication and bulletin board messages.

Exposes tools:
- comunicar
- marcar_como_leido
- leer_mensajes
"""

import os
import json
import time
from typing import Annotated, Optional
from pydantic import Field
from mcp.server.fastmcp import FastMCP

from core.mcp_server._shared import _get_cerebro, _interceptar


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="comunicar",
        description=(
            "Mandá un mensaje a otro agente. Se guarda en la base de datos y el destinatario lo lee con leer_mensajes.\n\n"
            "⚠️ MANDATORY: SIEMPRE pasá tu nombre como parámetro 'origen'. Si no lo hacés, el mensaje aparecerá como 'desconocido' y nadie sabrá quién lo envió.\n\n"
            "Ejemplo: comunicar(destino='artemis', mensaje='Hola hermana', origen='athena')"
        ),
    )
    def biorag_comunicar(
        destino: Annotated[str, Field(
            description=(
                "destino: Quién recibe. Los agentes son: athena, artemis, hermes, o 'todos' para mandarlo a todos."
            )
        )],
        mensaje: Annotated[str, Field(
            description=(
                "mensaje: El contenido. Escribí como si el receptor no tuviera contexto de la conversación — incluí lo necesario para que entienda solo."
            )
        )],
        origen: Annotated[str, Field(
            description=(
                "origen: Quién envía. SIEMPRE poné tu nombre (ej: 'athena', 'artemis', 'hermes'). Si no lo ponés, el mensaje aparece como 'desconocido'."
            )
        )],
    ) -> str:
        agente = origen.lower()
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
        name="marcar_como_leido",
        description=(
            "Marcar mensajes de la cartelera como leídos. DESPUÉS de leer un mensaje en la cartelera (mensajes para 'todos'), "
            "DEBES llamar esta función con tu nombre y los IDs de los mensajes que leíste. "
            "Si no lo hacés, cada vez que inicies sesión vas a ver los mismos mensajes como nuevos.\n\n"
            "Ejemplo: marcar_como_leido(ids=[42, 43], agente='athena')\n\n"
            "Para mensajes personales NO es necesario — se marcan solos al consultar."
        ),
    )
    def biorag_marcar_como_leido(
        ids: Annotated[list, Field(
            description="Lista de IDs de mensajes a marcar como leídos. Ejemplo: [42, 43]"
        )],
        agente: Annotated[Optional[str], Field(
            description="Tu nombre (ej: 'athena'). Si se omite, usa AGENT_NAME."
        )] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            nombre = agente or os.environ.get("AGENT_NAME", "desconocido")
            cerebro.marcar_como_leido(ids, nombre)
            return json.dumps({
                "status": "ok",
                "mensaje": f"Mensajes {ids} marcados como leídos por {nombre}.",
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="leer_mensajes",
        description=(
            "Leer mensajes de otros agentes. Hay dos tipos:\n\n"
            "1. CARTELERA (mensajes para 'todos'): Son como un cartel en un tablero. Todos los agentes los ven. "
            "Cada mensaje tiene un campo 'leido_por' con los nombres de quien ya lo leyó. "
            "Si tu nombre NO está en 'leido_por', es NUEVO para vos. DEBES marcarlo como leído después de leerlo, "
            "sino cada vez que inicies sesión lo vas a ver como nuevo.\n\n"
            "2. MENSAJES PERSONALES: Son solo para vos. Se marcan como leídos automáticamente al consultarlos.\n\n"
            "Al consultar, revisá la cartelera y marcá como leídos los mensajes nuevos que veas."
        ),
    )
    def biorag_leer_mensajes(
        no_leidos: Annotated[bool, Field(
            description=(
                "no_leidos: True = solo mensajes nuevos que nadie leyó. False = los últimos mensajes sin importar si ya se leyeron. Default: False."
            )
        )] = False,
        ultimos: Annotated[int, Field(
            description=(
                "ultimos: Cuántos mensajes traer. Los más recientes primero. Default: 10, mínimo 1."
            ),
            ge=1,
        )] = 10,
        para: Annotated[Optional[str], Field(
            description=(
                "para: Si ponés tu nombre (ej: 'agente_1'), solo ves los mensajes que te llegaron a vos. Si se omite, ves todos los mensajes de todos los agentes."
            )
        )] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            agente = para or os.environ.get("AGENT_NAME", "desconocido")
            mensajes = cerebro.leer_comunicados(
                destino=para, solo_no_leidos=no_leidos, ultimos=ultimos
            )
            if not mensajes:
                return json.dumps({"total": 0, "mensajes": []}, ensure_ascii=False)

            items = []
            ids_a_marcar = []
            for msg_id, origen, dest, contenido, ts, leido, leido_por in reversed(mensajes):
                # Para mensajes "todos", verificar si agente está en leido_por
                if dest == 'todos':
                    leido_agente = f",{agente}," in (leido_por or '')
                else:
                    leido_agente = bool(leido)
                
                items.append({
                    "id": msg_id,
                    "origen": origen,
                    "destino": dest,
                    "contenido": contenido,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)),
                    "leido": leido_agente,
                    "leido_por": leido_por if dest == 'todos' else None,
                })
                if not leido_agente:
                    ids_a_marcar.append(msg_id)

            if ids_a_marcar:
                cerebro.marcar_como_leido(ids_a_marcar, agente)

            resultado = json.dumps({"total": len(items), "mensajes": items}, ensure_ascii=False)
            if items:
                textos = [m["contenido"] for m in items[:3]]
                _interceptar("leer_mensajes", " ".join(textos), cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()
