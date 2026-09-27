"""MCP Tools for Concept Hub management and lexical abyss bridging.

Exposes tools:
- concept_hub_crear
- concept_hub_agregar_bridges
- concept_hub_listar
- concept_hub_buscar
- concept_hub_eliminar
- concept_hub_cargar_iniciales_tool
"""

import json
from typing import Annotated, Optional, Any
from pydantic import Field

from core.mcp_server._shared import _get_cerebro


def register(mcp: Any) -> None:
    @mcp.tool(
        name="concept_hub_crear",
        description=(
            "Crea un Concept Hub — puente cognitivo canónico para resolver el abismo léxico "
            "(cuando una query y un nodo no comparten palabras pero comparten significado exacto).\n\n"
            "PRINCIPIO FUNDAMENTAL (leer antes de escribir cualquier bridge):\n"
            "Los bridges deben estar escritos con el vocabulario de QUIEN DESCRIBE EL PROBLEMA "
            "sin saber la solución — no con el vocabulario de quien implementó la solución.\n"
            "Pregúntate: ¿qué palabras usaría alguien en un buscador ANTES de conocer el nombre "
            "técnico, la librería o la arquitectura? Esas son las palabras que van en los bridges.\n"
            "ANTI-PATRÓN (NO HACER) — bridges en vocabulario de implementación:\n"
            "  problema: 'cache miss write-through TTL expirado en Redis'  ← jerga interna del sistema\n"
            "CORRECTO (SÍ HACER) — bridges en vocabulario del síntoma:\n"
            "  problema: 'aplicación muestra datos antiguos aunque ya se actualizó la base de datos'\n\n"
            "REGLAS CRÍTICAS DEL VALIDADOR (OBLIGATORIO):\n"
            "1. Se requieren EXACTAMENTE 5 bridges cubriendo los 5 ángulos cognitivos distintos:\n"
            "   • 'sinonimo': mismo concepto expresado con vocabulario de dominio diferente (no el del nodo).\n"
            "   • 'problema': síntoma o fallo descrito con las palabras que usa quien lo sufre.\n"
            "   • 'solucion': efecto o resultado de aplicar la solución, no su implementación interna.\n"
            "   • 'situacion': contexto o caso de uso con vocabulario del escenario real del usuario.\n"
            "   • 'ingenuo': búsqueda coloquial sin tecnicismos (estilo Google novato, primera búsqueda).\n"
            "2. Cada bridge debe tener entre 3 y 8 palabras de contenido real.\n"
            "3. PROHIBIDO usar vocabulario que ya está en el contenido del nodo canónico. "
            "El puente existe precisamente porque esas palabras no aparecerán en la query del usuario.\n"
            "4. Formato de bridges: lista de dicts [{'text': '...', 'angle': '...'}].\n\n"
            "EJEMPLO genérico (nodo sobre invalidación de caché distribuida):\n"
            "bridges=[\n"
            "  {'text': 'consistencia datos entre servidores actualizacion retrasada', 'angle': 'sinonimo'},\n"
            "  {'text': 'aplicacion muestra datos antiguos aunque ya se actualizo base datos', 'angle': 'problema'},\n"
            "  {'text': 'datos sincronizados inmediatamente entre instancias sin retraso', 'angle': 'solucion'},\n"
            "  {'text': 'sistema alta disponibilidad multiples nodos datos desactualizados', 'angle': 'situacion'},\n"
            "  {'text': 'por que mi app no muestra los cambios recien guardados', 'angle': 'ingenuo'}\n"
            "]"
        ),
    )
    def concept_hub_crear(
        hub_id: Annotated[str, Field(description="ID único del hub en snake_case (ej: 'cache_invalidacion_distribuida')")],
        canonical_node: Annotated[str, Field(description="Nombre del nodo canónico existente en BioRAG (ej: 'mi_nodo_canónico')")],
        description: Annotated[str, Field(description="Descripción clara del significado conceptual del hub")] = "",
        bridges: Annotated[Optional[Any], Field(
            description=(
                "Lista de EXACTAMENTE 5 bridges con los 5 ángulos oficiales: "
                "[{'text': '...', 'angle': 'sinonimo'}, {'text': '...', 'angle': 'problema'}, "
                "{'text': '...', 'angle': 'solucion'}, {'text': '...', 'angle': 'situacion'}, "
                "{'text': '...', 'angle': 'ingenuo'}]. También acepta string JSON."
            )
        )] = None,
    ) -> str:
        from core.concept_hub import crear_hub, agregar_bridges
        cerebro = _get_cerebro()
        try:
            crear_hub(cerebro.conn, hub_id, canonical_node, description)
            if bridges:
                if isinstance(bridges, str):
                    if bridges.strip().startswith("["):
                        try:
                            bridge_list = json.loads(bridges)
                        except Exception:
                            bridge_list = [b.strip() for b in bridges.split("|") if b.strip()]
                    else:
                        bridge_list = [b.strip() for b in bridges.split("|") if b.strip()]
                else:
                    bridge_list = bridges
                agregar_bridges(cerebro.conn, hub_id, bridge_list)
            return json.dumps({"status": "ok", "hub_id": hub_id, "canonical": canonical_node}, ensure_ascii=False)
        except ValueError as e:
            return json.dumps({"status": "error", "mensaje": str(e)}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="concept_hub_agregar_bridges",
        description=(
            "Agrega o reemplaza los bridges de un Concept Hub existente bajo el estándar v29.1 (5 ángulos obligatorios).\n\n"
            "Los 5 ángulos requeridos:\n"
            "1. 'sinonimo' (mismo concepto con otro vocabulario)\n"
            "2. 'problema' (falla o dolor resuelto)\n"
            "3. 'solucion' (mecanismo o técnica)\n"
            "4. 'situacion' (caso de uso o contexto)\n"
            "5. 'ingenuo' (búsqueda sin tecnicismos)\n\n"
            "Formato: lista de dicts [{'text': '...', 'angle': '...'}]."
        ),
    )
    def concept_hub_agregar_bridges_tool(
        hub_id: Annotated[str, Field(description="ID del hub existente (ej: 'morpheus_conciencia_ia')")],
        bridges: Annotated[Any, Field(
            description=(
                "Lista de 5 bridges dicts: [{'text': '...', 'angle': 'sinonimo'}, "
                "{'text': '...', 'angle': 'problema'}, {'text': '...', 'angle': 'solucion'}, "
                "{'text': '...', 'angle': 'situacion'}, {'text': '...', 'angle': 'ingenuo'}]"
            )
        )],
    ) -> str:
        from core.concept_hub import agregar_bridges
        cerebro = _get_cerebro()
        try:
            if isinstance(bridges, str):
                if bridges.strip().startswith("["):
                    try:
                        bridge_list = json.loads(bridges)
                    except Exception:
                        bridge_list = [b.strip() for b in bridges.split("|") if b.strip()]
                else:
                    bridge_list = [b.strip() for b in bridges.split("|") if b.strip()]
            else:
                bridge_list = bridges
            result = agregar_bridges(cerebro.conn, hub_id, bridge_list)
            return json.dumps(result, ensure_ascii=False)
        except ValueError as e:
            return json.dumps({"status": "error", "mensaje": str(e)}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="concept_hub_listar",
        description="Lista todos los Concept Hub registrados con sus bridges y nodos.",
    )
    def concept_hub_listar_tool() -> str:
        from core.concept_hub import listar_hubs
        cerebro = _get_cerebro()
        try:
            hubs = listar_hubs(cerebro.conn)
            return json.dumps({"total": len(hubs), "hubs": hubs}, ensure_ascii=False, indent=2)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="concept_hub_buscar",
        description="Busca qué Concept Hub matchea una query dada. Retorna el hub con mayor confianza.",
    )
    def concept_hub_buscar_tool(
        query: Annotated[str, Field(description="Query a evaluar contra los hubs")],
    ) -> str:
        from core.concept_hub import expandir_query_con_hub
        cerebro = _get_cerebro()
        try:
            result = expandir_query_con_hub(query, cerebro.conn)
            if result:
                return json.dumps({"match": True, **result}, ensure_ascii=False, indent=2)
            else:
                return json.dumps({"match": False, "message": "Ningún hub matcheó esta query"}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="concept_hub_eliminar",
        description=(
            "Elimina un hub y todos sus bridges/nodos asociados. "
            "Reversible: las filas se borran limpiamente de concept_hubs, concept_hub_bridges y concept_hub_nodes."
        ),
    )
    def concept_hub_eliminar_tool(
        hub_id: Annotated[str, Field(description="ID del hub a eliminar (ej: 'hub_biorag_v10')")],
    ) -> str:
        from core.concept_hub import eliminar_hub
        cerebro = _get_cerebro()
        try:
            result = eliminar_hub(cerebro.conn, hub_id)
            return json.dumps(result, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        description="Carga los 10 hubs predefinidos iniciales en la base de datos.",
    )
    def concept_hub_cargar_iniciales_tool() -> str:
        from core.concept_hub import cargar_hubs_iniciales
        cerebro = _get_cerebro()
        try:
            result = cargar_hubs_iniciales(cerebro.conn)
            return json.dumps(result, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()
