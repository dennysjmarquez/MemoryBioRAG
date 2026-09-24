"""MCP Tools for categories and semantic dimensions catalog inspection.

Exposes tools:
- listar_categorias
- listar_dimensiones
- listar_tipos_dimension
- listar_dimensiones_por_tipo
"""
import json
from typing import Annotated, Any
from pydantic import Field

from core.mcp_server._shared import _get_cerebro


def register(mcp: Any) -> None:
    @mcp.tool(
        name="listar_categorias",
        description=(
            "Mostrá las carpetas disponibles para clasificar nodos. Llamá a esto antes de aprender para saber qué categoría elegir. Sin parámetros."
        ),
    )
    def biorag_listar_categorias() -> str:
        cerebro = _get_cerebro()
        try:
            cats = cerebro.listar_categorias()
            items = [{"id": cid, "nombre": name, "descripcion": desc} for cid, name, desc in cats]
            return json.dumps({"total": len(items), "categorias": items}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="listar_dimensiones",
        description=(
            "Mostrá los ejes semánticos (emoción, entidad, acción, cualidad, coordenada, Etc...) y todos sus valores disponibles. Llamá a esto antes de aprender para saber qué nombres usar. Sin parámetros."
        ),
    )
    def biorag_listar_dimensiones() -> str:
        cerebro = _get_cerebro()
        try:
            cerebro.cursor.execute("""
                SELECT t.nombre, t.description, d.id, d.name, d.description,
                       COALESCE(d.auto_generada, 0), COALESCE(d.confianza, 1.0)
                FROM tipos_dimension t
                LEFT JOIN dimensiones_semanticas d ON d.tipo_id = t.id
                ORDER BY t.id, d.id
            """)
            filas = cerebro.cursor.fetchall()
            resultado = {}
            for tipo, tdesc, did, dname, ddesc, auto_gen, conf in filas:
                if tipo not in resultado:
                    resultado[tipo] = {
                        "descripcion": tdesc or "",
                        "dimensiones": []
                    }
                if did:
                    resultado[tipo]["dimensiones"].append({
                        "id": did,
                        "nombre": dname,
                        "descripcion": ddesc or "",
                        "auto_generada": bool(auto_gen),
                        "confianza": conf
                    })
            total = sum(len(v["dimensiones"]) for v in resultado.values())
            return json.dumps({"total": total, "dimensiones": resultado}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="listar_tipos_dimension",
        description=(
            "Mostrá los 13 tipos de dimensión semántica (emoción, entidad, acción, cualidad, coordenada, intención, dominio, "
            "cualia, epistemia, escala_abstraccion, centralidad_identitaria, textura_experiencial, modalidad) "
            "con sus descripciones. Llamá esto PRIMERO para ver qué categorías existen. "
            "Después usá listar_dimensiones_por_tipo para traer los sub-values de una categoría específica. Sin parámetros."
        ),
    )
    def biorag_listar_tipos_dimension() -> str:
        """Retorna los 13 tipos de dimensión con sus descripciones."""
        cerebro = _get_cerebro()
        try:
            cerebro.cursor.execute("""
                SELECT id, nombre, description
                FROM tipos_dimension
                ORDER BY id
            """)
            tipos = []
            for tid, nombre, desc in cerebro.cursor.fetchall():
                # Contar dimensiones de este tipo
                cerebro.cursor.execute(
                    "SELECT COUNT(*) FROM dimensiones_semanticas WHERE tipo_id = ?",
                    (tid,)
                )
                count = cerebro.cursor.fetchone()[0]
                tipos.append({
                    "id": tid,
                    "nombre": nombre,
                    "descripcion": desc or "",
                    "num_dimensiones": count,
                })
            return json.dumps({"total": len(tipos), "tipos": tipos}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="listar_dimensiones_por_tipo",
        description=(
            "Trae las dimensiones semánticas de UNO O MÁS tipos específicos (emoción, entidad, acción, cualidad, coordenada, intención, dominio, "
            "cualia, epistemia, escala_abstraccion, centralidad_identitaria, textura_experiencial, modalidad). "
            "Llamá esto después de listar_tipos_dimension para ver los valores disponibles. "
            "Acepta múltiples tipos separados por coma (ej: 'emocion,dominio'). "
            "Úsalo para clasificar nodos con precisión sin traer las 102 dimensiones de golpe."
        ),
    )
    def biorag_listar_dimensiones_por_tipo(
        tipo: Annotated[str, Field(
            description="Nombre del tipo o tipos separados por coma: emocion, entidad, accion, cualidad, coordenada, intencion, dominio, cualia, epistemia, escala_abstraccion, centralidad_identitaria, textura_experiencial, modalidad. Ej: 'emocion' o 'emocion,dominio'"
        )],
    ) -> str:
        """Retorna las dimensiones de uno o más tipos específicos con IDs y descripciones."""
        cerebro = _get_cerebro()
        try:
            # Soporte para múltiples tipos separados por coma
            tipos_nombres = [t.strip().lower() for t in tipo.split(",") if t.strip()]
            
            # Buscar cada tipo por nombre o ID
            tipos_encontrados = []
            for t in tipos_nombres:
                cerebro.cursor.execute(
                    "SELECT id, nombre, description FROM tipos_dimension WHERE nombre = ? OR nombre LIKE ?",
                    (t, f"%{t}%")
                )
                tipo_row = cerebro.cursor.fetchone()
                if not tipo_row:
                    # Intentar por ID numérico
                    try:
                        tipo_id = int(t)
                        cerebro.cursor.execute(
                            "SELECT id, nombre, description FROM tipos_dimension WHERE id = ?",
                            (tipo_id,)
                        )
                        tipo_row = cerebro.cursor.fetchone()
                    except (ValueError, TypeError):
                        pass
                if tipo_row:
                    tipos_encontrados.append(tipo_row)
            
            if not tipos_encontrados:
                return json.dumps({
                    "error": f"Ninguno de los tipos '{tipo}' fue encontrado. Tipos válidos: emocion, entidad, accion, cualidad, coordenada, intencion, dominio, cualia, epistemia, escala_abstraccion, centralidad_identitaria, textura_experiencial, modalidad"
                }, ensure_ascii=False)
            
            # Recopilar IDs y descripciones de los tipos encontrados
            tipo_ids = []
            tipos_info = []
            for tid, tnombre, tdesc in tipos_encontrados:
                tipo_ids.append(tid)
                tipos_info.append({"nombre": tnombre, "descripcion": tdesc or ""})
            
            # Consultar dimensiones de todos los tipos encontrados
            placeholders = ",".join("?" * len(tipo_ids))
            cerebro.cursor.execute(
                f"SELECT id, name, description, tipo_id, COALESCE(auto_generada, 0), COALESCE(confianza, 1.0) "
                f"FROM dimensiones_semanticas WHERE tipo_id IN ({placeholders}) ORDER BY tipo_id, id",
                tipo_ids
            )
            dimensiones = []
            for did, dname, ddesc, dtipo_id, auto_gen, conf in cerebro.cursor.fetchall():
                dimensiones.append({
                    "id": did,
                    "nombre": dname,
                    "descripcion": ddesc or "",
                    "tipo": next((ti["nombre"] for ti in tipos_info if ti["nombre"]), ""),
                    "auto_generada": bool(auto_gen),
                    "confianza": conf,
                })
            
            # Construir respuesta
            resultado = {
                "tipos_consultados": [ti["nombre"] for ti in tipos_info],
                "total": len(dimensiones),
                "dimensiones": dimensiones,
            }
            return json.dumps(resultado, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()
