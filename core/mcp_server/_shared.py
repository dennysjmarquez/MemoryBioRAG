"""Shared utilities and singleton accessors for core.mcp_server."""

import os
import json
import logging
from typing import Optional, Dict
from core.memory_service import get_cerebro as _svc_get_cerebro
from core.memory_store import SQLiteMemoryBioRAG
from middleware.auto_guardado import registrar_accion, analizar_y_autoguardar

logger = logging.getLogger("BioRAG.MCP")

_sesiones_activas: dict[str, float] = {}  # agente → timestamp de contexto_inicio

LIMITE_MCP = int(os.environ.get('BIORAG_LIMITE_MCP', '10'))
"""Límite de resultados por defecto en búsquedas MCP."""

THRESHOLD_RAFTAGA_MCP = float(os.environ.get('BIORAG_THRESHOLD_RAFTAGA', '0.5'))
"""Score mínimo para activar ráfaga automáticamente en MCP."""

STALE_DAYS = int(os.environ.get('BIORAG_STALE_DAYS', '90'))
"""Días después de los cuales un nodo se marca como 'stale' (obsoleto).
Resultados stale no se entregan como información vigente.
Protegidos: categories Principle, Profile, Personal, Relation no se marcan stale."""

STALE_HARD_CUTOFF_DAYS = int(os.environ.get('BIORAG_STALE_HARD_CUTOFF', '365'))
"""Días después de los cuales un nodo se excluye de resultados (a menos que
esté en categoría protegida). 0 = sin cutoff."""

MAX_ASOCIACIONES_FLAT = int(os.environ.get('BIORAG_MAX_ASOCIACIONES_FLAT', '12'))
"""Máximo de nombres de asociaciones planas expuestos por nodo en la respuesta de
recordar/buscar. El campo `asociaciones` de cada resultado se devuelve como objeto
{total, items, truncada}: total es el conteo REAL de conexiones del nodo (nunca se
pierde información), items es la lista acotada a este límite, y truncada indica si
hay más que no se muestran. Con asociaciones_max=0 el agente pide la lista completa
del nodo que le interesa (consulta dirigida), evitando que hubs de 130-167 conexiones
inflen el JSON y disparen el truncado del cliente MCP. La tabla `sinapsis` (fuente
canónica) y la columna `largo_plazo.asociaciones` quedan intactas — es decisión de
serialización. Ver mcp_server.py _serializar_asociaciones.
"""

VENTANA_CORRECCION = int(os.environ.get('BIORAG_VENTANA_CORRECCION_SEGUNDOS', '900'))
"""Ventana de corrección en caliente (default 900s = 15min). Nodos más jóvenes se pueden actualizar directamente; más viejos requieren nodo nuevo + vincular."""

ORACULO_MAX_CHARS = int(os.environ.get('BIORAG_ORACULO_MAX_CHARS', '12000'))
"""Máximo de caracteres devueltos por el oráculo NotebookLM.

Si la respuesta de NotebookLM excede este límite, se trunca y se agrega una
nota indicando que el contenido fue recortado. Esto evita que el output de la
tool sea truncado por el cliente MCP por exceso de tamaño.
"""

PROMPT_INICIO_NOTEBOOKLM = os.environ.get("BIORAG_PROMPT_INICIO", "").strip()
"""Prompt base enviado al oráculo NotebookLM al iniciar sesión.

Obligatorio si se desea generar el query para NotebookLM. Se configura mediante
la variable de entorno BIORAG_PROMPT_INICIO. El nombre del agente se concatena
al inicio con el formato 'Agente: prompt'. Si no esta seteada, la tool no
armara el query para NotebookLM.
"""

NOTEBOOK_ID_ORACULO = os.environ.get("BIORAG_NOTEBOOK_ID", "").strip()
"""Notebook ID del oráculo NotebookLM.

Obligatorio si se desea generar el query para NotebookLM. Se configura mediante
la variable de entorno BIORAG_NOTEBOOK_ID. Si no esta seteada, la tool no
incluira el notebooklm_query.
"""

QUERIES_BIORAG_INICIO = [
    "reglas comportamiento agentes OEC",
    "pilares inmutables agente",
    "protocolo pre-acción",
    "reglas código anti-overengineering",
    "lecciones clave programación",
    "perfil profesional usuario stack",
    "mapa almacenamiento memoria",
]
"""Búsquedas predefinidas que el oráculo de BioRAG ejecuta al arrancar."""

AGENTES_VALIDOS = set()
"""Agentes reconocidos por el sistema (vacío = permite cualquier agente)."""


def _get_cerebro() -> SQLiteMemoryBioRAG:
    """Reusa la corteza (singleton). No reconstruir 6–11s por tool."""
    return _svc_get_cerebro(os.environ.get("BIORAG_PATH") or None)


def _interceptar(accion: str, texto: str, cerebro) -> Optional[dict]:
    registrar_accion(accion, texto)
    resultado = analizar_y_autoguardar(cerebro)
    if resultado:
        logger.info("auto-guardado: %s (%s)", resultado["concepto"], resultado["categoria"])
    return resultado


_HINT_LISTAR_DIMENSIONES = (
    "💡 Consultá `listar_dimensiones` o `listar_dimensiones_por_tipo` para ver "
    "los valores disponibles por eje antes de guardar."
)


def _resolver_dimensiones(cerebro, dimensiones):
    """Parsea JSON de dimensiones, resuelve IDs y retorna una 4-tupla:

        (dimensiones_dict, dimensiones_ids, error_json, meta)

    Contratos de cada elemento:
      - dimensiones_dict : {eje: [id, ...]} con los IDs resueltos (vacío si error fatal).
      - dimensiones_ids  : lista plana de IDs (vacía si error fatal).
      - error_json       : str JSON listo para retornar al cliente, o None si no hay error fatal.
      - meta             : dict con claves opcionales:
          · "advertencias"         → lista de strings (nombres innormalizables, no bloqueante).
          · "dimensiones_creadas"  → lista de strings "eje/nombre" auto-creados (info positiva).

    Comportamiento por caso:
      · JSON inválido o no-dict       → error fatal  (error_json != None, resto vacío).
      · Eje no existe en DB           → error fatal  (ejes son CERRADOS e invariantes).
      · Valor no es string/lista      → error fatal  (tipo incorrecto, programador error).
      · Nombre innormalizable         → advertencia  (no bloquea; el valor se ignora).
      · Nombre existente              → reutiliza ID (silencioso, anti-duplicado).
      · Nombre nuevo y normalizable   → auto-crea en catálogo; reporta en meta.
    """
    if not dimensiones:
        return None, [], None, {}

    # ── 1. Parsear el JSON ─────────────────────────────────────────────────────
    try:
        dim_raw = json.loads(dimensiones) if isinstance(dimensiones, str) else dimensiones
    except json.JSONDecodeError:
        return None, [], json.dumps({
            "status": "error",
            "mensaje": (
                "dimensiones debe ser un JSON válido con comillas dobles. "
                f"Ejemplo: {json.dumps({'emocion': ['afecto'], 'entidad': ['identidad_artificial']})}. "
                f"{_HINT_LISTAR_DIMENSIONES}"
            ),
        }, ensure_ascii=False), {}

    if not isinstance(dim_raw, dict):
        return None, [], json.dumps({
            "status": "error",
            "mensaje": (
                'dimensiones debe ser un objeto JSON (dict). Ejemplo: {"emocion": ["afecto"]}. '
                f"{_HINT_LISTAR_DIMENSIONES}"
            ),
        }, ensure_ascii=False), {}

    # ── 2. Procesar cada eje ───────────────────────────────────────────────────
    dimensiones_dict: dict = {}
    dimensiones_ids: list = []
    ejes_invalidos: list = []      # error fatal — ejes cerrados
    advertencias: list = []        # nombres innormalizables — no bloquea
    dimensiones_creadas: list = [] # nuevas dimensiones auto-creadas — info positiva

    for eje, valores in dim_raw.items():
        # Validación de tipo de la lista de valores
        if not isinstance(valores, list):
            ejes_invalidos.append(
                f"'{eje}': el valor debe ser una lista de strings, recibido {type(valores).__name__}"
            )
            continue

        valores_filtrados = []
        tipo_invalido = None
        for val in valores:
            if isinstance(val, str):
                valores_filtrados.append(val)
            else:
                tipo_invalido = type(val).__name__
        if tipo_invalido:
            ejes_invalidos.append(
                f"'{eje}': elemento de tipo {tipo_invalido} en la lista (deben ser strings)"
            )
            continue

        # Resolución de IDs — _resolver_dimension_ids ya valida que el eje exista
        ids, invalidos, creadas = cerebro._resolver_dimension_ids(
            eje, ",".join(valores_filtrados)
        )

        # Si el eje no existe, _resolver_dimension_ids retorna invalidos=todos los valores
        # y ids=[]. Lo detectamos consultando directamente el tipo.
        if not ids and invalidos and not valores_filtrados:
            # lista vacía enviada — no es error, simplemente no hay nada que resolver
            continue

        # Detectar si el eje en sí no existe (el helper lo reporta retornando los nombres
        # originales como invalidos cuando tipo_row es None)
        cerebro.cursor.execute(
            "SELECT 1 FROM tipos_dimension WHERE nombre = ?", (eje,)
        )
        if not cerebro.cursor.fetchone():
            ejes_invalidos.append(eje)
            continue

        # Nombres que no pudieron normalizarse → advertencia (no bloquea)
        for nombre_inv in invalidos:
            advertencias.append(
                f"Nombre '{nombre_inv}' en eje '{eje}' no pudo normalizarse y fue ignorado. "
                f"Usá solo letras, números y guión bajo (snake_case, sin tildes). "
                f"{_HINT_LISTAR_DIMENSIONES}"
            )

        # Nuevas dimensiones auto-creadas → info positiva
        for nombre_creado in creadas:
            dimensiones_creadas.append(f"{eje}/{nombre_creado}")

        if ids:
            dimensiones_dict[eje] = ids
            dimensiones_ids.extend(ids)

    # ── 3. Error fatal si hay ejes inválidos ───────────────────────────────────
    if ejes_invalidos:
        return None, [], json.dumps({
            "status": "error",
            "codigo": "EJES_INVALIDOS",
            "mensaje": (
                f"Eje(s) inválido(s): {ejes_invalidos}. "
                "Los ejes son un sistema cerrado e invariante. "
                f"{_HINT_LISTAR_DIMENSIONES}"
            ),
            "ejes_invalidos": ejes_invalidos,
        }, ensure_ascii=False), {}

    # ── 4. Construir meta (advertencias + confirmaciones) ──────────────────────
    meta: dict = {}
    if advertencias:
        meta["advertencias"] = advertencias
    if dimensiones_creadas:
        meta["dimensiones_creadas"] = dimensiones_creadas

    return dimensiones_dict, dimensiones_ids, None, meta
