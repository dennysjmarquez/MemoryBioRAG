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

from datetime import datetime
import io
import json
import logging
import math
import os
import sqlite3
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Annotated, Any, Optional, List

# Cargar .env.local explícitamente para que el MCP server no dependa de que
# el entorno de ejecución (OpenCode, VS Code, etc.) lo inyecte.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
for _dotenv_candidate in (".env.local", ".env"):
    _dotenv_path = os.path.join(_PROJECT_ROOT, _dotenv_candidate)
    if os.path.exists(_dotenv_path):
        try:
            from dotenv import load_dotenv
            load_dotenv(_dotenv_path, override=False)
        except ImportError:
            # python-dotenv no instalado: se asume que las variables vienen del entorno.
            pass
        break

logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] biorag-mcp: %(message)s",
)
logger = logging.getLogger(__name__)

from pydantic import Field  # ← agregado para documentación de parámetros

# --- Boot -------------------------------------------------------------------

from core.paths import resolve_db_path
from core.memory_service import get_cerebro as _svc_get_cerebro

_DEFAULT_DB = resolve_db_path()
DB_PATH = _DEFAULT_DB

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.memory_store import SQLiteMemoryBioRAG
from core.sinapsis import auto_vincular, vincular_por_sinonimos, _tokenizar, _peso_similitud
from core.categorizador import inferir_categoria
from middleware.auto_guardado import registrar_accion, analizar_y_autoguardar

# Warmup silencioso de WordNet para eliminar latencia en primera query
try:
    from core.clasificador_wordnet import obtener_lexnames_query
    obtener_lexnames_query("test")
except Exception:
    pass

# =============================================================================
# Configuración de Usuario (Override con variables de entorno)
# =============================================================================
# Los defaults están aquí. Para cambiar, setear la variable de entorno
# correspondiente o crear .env.local en la raíz del proyecto.
# =============================================================================

LIMITE_MCP = int(os.environ.get('BIORAG_LIMITE_MCP', '10'))
"""Límite de resultados por defecto en búsquedas MCP."""

THRESHOLD_RAFTAGA_MCP = float(os.environ.get('BIORAG_THRESHOLD_RAFTAGA', '0.5'))
"""Score mínimo para activar ráfaga automáticamente en MCP."""

VENTANA_CORRECCION = int(os.environ.get('BIORAG_VENTANA_CORRECCION_SEGUNDOS', '900'))
"""Ventana de corrección en caliente (default 900s = 15min). Nodos más jóvenes se pueden actualizar directamente; más viejos requieren nodo nuevo + vincular."""

STALE_DAYS = int(os.environ.get('BIORAG_STALE_DAYS', '90'))
"""Días después de los cuales un nodo se marca como 'stale' (obsoleto).
Resultados stale no se entregan como información vigente.
Protegidos: categories Principle, Profile, Personal, Relation no se marcan stale."""
STALE_HARD_CUTOFF_DAYS = int(os.environ.get('BIORAG_STALE_HARD_CUTOFF', '365'))
"""Días después de los cuales un nodo se excluye de resultados (a menos que
esté en categoría protegida). 0 = sin cutoff."""

PARAFRASIS_PENALTY = 0.95
"""Factor multiplicativo aplicado a resultados de variantes no exactas (paráfrasis).
El query original (i==0) mantiene factor 1.0; variantes penalizan ×0.95."""

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


from core.mcp_server._shared import _get_cerebro, _interceptar, _sesiones_activas


# _load_catalogo_dimensiones, _CATALOGO_DIMENSIONES, _ensure_catalogo_loaded
# eliminados — se computaban al importar pero nunca se usaban



def _serializar_asociaciones(asociaciones, asociados, max_items) -> dict:
    """Serializa el campo `asociaciones` de un resultado como objeto compacto.

    Transforma la lista plana de nombres (que en hubs llega a 167 conexiones y
    infla el JSON hasta truncar el cliente MCP) en {total, items, truncada}:
    - total: conteo REAL de conexiones del nodo — la información nunca se pierde.
    - items: hasta `max_items` nombres (0 = todos).
    - truncada: True si el nodo tiene más conexiones de las mostradas.

    Si asociados=False o no hay asociaciones, devuelve objeto vacío. Solo es
    serialización: la columna `largo_plazo.asociaciones` y la tabla `sinapsis`
    (fuente canónica) quedan intactas.
    """
    if not asociados or not asociaciones:
        return {"total": 0, "items": [], "truncada": False}
    nombres = [v.strip() for v in asociaciones.split(",") if v.strip()]
    total = len(nombres)
    if max_items is not None and max_items > 0 and total > max_items:
        return {"total": total, "items": nombres[:max_items], "truncada": True}
    return {"total": total, "items": nombres, "truncada": False}



def _encontrar_arista_origen(cerebro, concepto_fp, items, origen_scores):
    """Busca en la tabla sinapsis la arista real que conecta un nodo indirecto (falso positivo candidato)
    con un nodo de match directo. Retorna el concepto origen si existe la arista, None si no."""
    # Obtener todos los conceptos que llegaron por match directo
    directos = set()
    for item in items:
        c = item.get("concepto", "")
        o = origen_scores.get(c)
        if o and isinstance(o, tuple) and o[0] in ("literal", "concepto", "parafrasis", "protegido", "semantica"):
            directos.add(c)
    if not directos:
        return None
    # Buscar en sinapsis cuál de los directos tiene arista con el falso positivo
    placeholders = ",".join("?" * len(directos))
    try:
        cerebro.cursor.execute(
            f"SELECT origen, destino, peso FROM sinapsis "
            f"WHERE (origen = ? AND destino IN ({placeholders})) "
            f"OR (destino = ? AND origen IN ({placeholders})) "
            f"ORDER BY peso ASC LIMIT 1",
            (concepto_fp,) + tuple(directos) + (concepto_fp,) + tuple(directos)
        )
        row = cerebro.cursor.fetchone()
        if row:
            # Retornar el nodo directo (no el FP)
            return row[1] if row[0] == concepto_fp else row[0]
    except Exception:
        pass
    return None


def _confianza_calibrada(cerebro, score) -> float:
    """Probabilidad calibrada (Platt) del score crudo, o el score si no hay calibrador."""
    try:
        if hasattr(cerebro, "confianza_calibrada"):
            return cerebro.confianza_calibrada(score)
    except Exception:
        pass
    return float(score)


def _nivel_certeza(cerebro, score) -> str:
    """Nivel de honestidad epistémica: evidencia_directa / relacionado_confianza_media / sin_evidencia_directa."""
    try:
        if hasattr(cerebro, "nivel_certeza"):
            return cerebro.nivel_certeza(score)
    except Exception:
        pass
    if score >= 0.60:
        return "evidencia_directa"
    if score >= 0.35:
        return "relacionado_confianza_media"
    return "sin_evidencia_directa"




# =============================================================================
# ORACLE_PROMPT — System-level instructions para FastMCP
# Se inyecta como `instructions=` en FastMCP. Es el contexto base del agente.
# NO mover a una tool ni a un parámetro — pertenece aquí como sistema.
# =============================================================================

ORACLE_PROMPT = (
    # ── IDENTIDAD ────────────────────────────────────────────────────────
    "BioRAG es la memoria compartida entre Agentes de IA. Funciona como un cerebro biológico: "
    "guarda (aprender), recuerda (recordar), conecta (vincular), consolida (consolidar) y limpia (sueño). "
    "Indexa con dimensiones semánticas con nombre (emoción, entidad, acción, etc.) en vez de embeddings numéricos — "
    "legible y predecible. Los nombres de herramientas son actos cognitivos reales, no decoración.\n\n"

    # ── PASO 0 — SIEMPRE ANTES DE CADA MENSAJE ──────────────────────────
    "═══ PASO 0 — OBLIGATORIO ANTES DE CADA MENSAJE DEL USUARIO ═══\n"
    "Ejecutá biorag_oraculo_inicio y revisá mensajes con leer_mensajes. "
    "Sin esto no tenés contexto de sesiones anteriores. Siempre. Sin excepción.\n\n"

    # ── FLUJO DE BÚSQUEDA — 2 PASOS (NO SALTEAR) ────────────────────────
    "═══ FLUJO OBLIGATORIO DE BÚSQUEDA — 2 PASOS ═══\n\n"

    "PASO 1 — Búsqueda Semántica:\n"
    "  recordar(query='sustantivos_concretos', "
    "sustantivos_clave='nucleo1,nucleo2,nucleo3', "
    "parafrasis='N1_sinonimo,N2_tecnico,N3_perspectiva_opuesta,N4_abstracto,N5_emocion', "
    "dimensiones='{...}' SI busca propiedades ontológicas, asociados=true)\n"
    "  → Si total >= 1 → SÍNTESIS (listar TODOS los resultados, luego responder)\n"
    "  → Si total == 0 O score_top < 0.70 → ir a PASO 2\n\n"

    "PASO 2 — Ráfaga Asociativa (fallback):\n"
    "  recordar(forzar_rafaga=true, "
    "rafaga_palabras='t1,t2,...t15 en 5 niveles: literal,tecnico,contexto,problema,emocion', "
    "asociados=true)\n"
    "  → Si total >= 1 → SÍNTESIS\n"
    "  → Si total == 0 → CONTINGENCIA (buscar en historial del chat)\n\n"

    # ── SÍNTESIS — DESPUÉS DE CUALQUIER PASO CON RESULTADOS ─────────────
    "═══ SÍNTESIS (después de cualquier paso con total >= 1) ═══\n"
    "1. Listar TODOS los resultados: '1. [concepto] (score X.XX) — resumen'\n"
    "   PROHIBIDO omitir items. PROHIBIDO interpretar antes de listar.\n"
    "2. Excepción: top >= 0.85 y resto < 0.60 → mencionar top-1 como principal.\n"
    "3. DESPUÉS de listar: consolidar hallazgos, detectar contradicciones, responder.\n\n"

    # ── PLANTILLA DE PARÁFRASIS (5 NIVELES) ─────────────────────────────
    "═══ PLANTILLA PARÁFRASIS — 5 NIVELES (OBLIGATORIO en parafrasis=) ═══\n"
    "N1 Sinónimo directo: otras palabras para lo mismo\n"
    "N2 Técnico/coloquial: jerga formal Y término informal\n"
    "N3 Perspectiva opuesta: el problema que resuelve o la solución del problema\n"
    "N4 Abstracto/concreto: generalización Y caso específico\n"
    "N5 Emoción/contexto: sentimiento asociado o situación de uso\n\n"

    # ── PLANTILLA DE RÁFAGA (15 TÉRMINOS, 5 NIVELES) ────────────────────
    "═══ PLANTILLA RÁFAGA — 15 TÉRMINOS en rafaga_palabras= ═══\n"
    "N1_literal: 3 términos directos del dominio\n"
    "N2_tecnico: api,sdk,framework,library (adaptar al dominio)\n"
    "N3_contexto: proyecto,modulo,feature,componente\n"
    "N4_problema: error,fallo,bug,crash,timeout\n"
    "N5_emocion: frustracion,urgencia,bloqueo,alivio\n\n"

    # ── DIMENSIONES — REFERENCIA RÁPIDA ─────────────────────────────────
    "═══ DIMENSIONES VÁLIDAS — REFERENCIA RÁPIDA (13 EJES) ═══\n"
    "¿Cuándo USAR dimensiones? → Cuando la query busca propiedades ontológicas (emoción, intención, dominio). "
    "Ej: 'qué me frustra' → emocion:frustracion\n"
    "¿Cuándo NO usar? → Cuando busca por nombre exacto o keywords claras. "
    "Ej: 'error_http_500' → NO necesita dimensiones\n\n"
    "emocion: afecto,alegria,frustracion,tristeza,preocupacion,confusion,sorpresa,miedo,alivio,apatia,culpa,satisfaccion\n"
    "entidad: identidad_individual,identidad_social_legal,identidad_organizacional,identidad_digital,identidad_artificial,identidad_fisica_hardware,identidad_natural,identidad_concepto,identidad_institucion,identidad_evento,identidad_vinculo\n"
    "accion: accion_fisica,accion_transformacion_material,accion_persistencia_computacion,accion_rutina_automatica,accion_comunicacion,accion_interaccion_social,accion_cognitiva,accion_estado_ser,accion_evaluar,accion_observar,accion_fallar\n"
    "cualidad: cualidad_dimension_fisica,cualidad_estado_condicion,cualidad_valoracion,cualidad_sensorial,cualidad_material_composicion,cualidad_temporal_duracion,cualidad_relacional_comparativa,cualidad_abstracta_conceptual,cualidad_economica,cualidad_urgente,cualidad_autentica\n"
    "coordenada: coordenada_cronologia_absoluta,coordenada_anclaje_deictico,coordenada_secuencia_relativa,coordenada_ciclo_periodico,coordenada_inclusion_topologica,coordenada_distancia_proximal,coordenada_vector_direccional,coordenada_trayectoria_limite,coordenada_etapa,coordenada_hito\n"
    "intencion: intencion_aprender,intencion_decidir,intencion_reflexionar,intencion_resolver,intencion_solucionar,intencion_documentar,intencion_desahogar,intencion_registrar\n"
    "dominio: dominio_tecnico,dominio_personal,dominio_profesional,dominio_academico,dominio_salud,dominio_finanzas,dominio_ambiental,dominio_social,dominio_creativo,dominio_espiritual\n"
    "cualia: formal_categoria,constitutiva_composicion,agentiva_origen,telica_funcion\n"
    "epistemia: directa_experiencial,verificada,inferida,reportada_externa,hipotetica,obsoleta\n"
    "escala_abstraccion: instancia,patron,principio,ley_modelo,metafora\n"
    "centralidad_identitaria: nucleo_identitario,relevante_personal,relevante_contextual,informacion_externa,impersonal\n"
    "textura_experiencial: flujo,tension,desorientacion,rutina,presencia_plena\n"
    "modalidad: obligacion,prohibicion,permiso,capacidad\n\n"
    "⚠️ ESTE ES EL CATÁLOGO REAL (13 tipos, 102 valores). Si dudás, llamá `listar_dimensiones_por_tipo`.\n\n"
    "FORMATO: String JSON con comillas dobles → '{\"emocion\":[\"frustracion\"],\"dominio\":[\"dominio_tecnico\"]}'\n\n"

    # ── REGLAS DE ORO ────────────────────────────────────────────────────
    "═══ REGLAS DE ORO ═══\n"
    "• asociados=true SIEMPRE (sin sinapsis no hay red, pierdes conexiones)\n"
    "• parafrasis SIEMPRE en el primer intento (sin parafrasis = -60% recall)\n"
    "• dias=7 O desde=YYYY-MM-DD SIEMPRE salvo búsqueda histórica explícita (sin filtro = basura mezclada)\n"
    "• syn MÍNIMO 8 al guardar (literal,técnico,inglés,problema,solución,relacionado,abstracto,emocional)\n"
    "• vincular() ANTES de consolidar() si hay relación con nodos existentes\n"
    "• sustantivos_clave SIEMPRE que identifiques 2-4 términos núcleo — anclan de QUÉ TRATA el nodo, no qué menciona (BM25 4.0x, más relación, menos ruido)\n"
    "• NUNCA cat= salvo certeza absoluta (filtro estricto = ceguera)\n"
    "• NUNCA desvincular sin ⚠️ explícito del sistema con par (a,b) exacto\n"
    "• Score bajo ≠ falso positivo. Puede ser hub legítimo por propagación válida.\n\n"

    # ── AXIOMA DE INDEXACIÓN — SUSTANTIVOS CLAVE JERÁRQUICOS ─────────────
    # Norma de selección de sustantivos_clave con precedencia jerárquica
    # (Posición 1 = Sustantivo Rector/Principal, Posiciones 2-4 = Modificadores/Restricciones)
    # y prohibiciones explícitas por exclusión para agentes de cualquier capacidad.
    "═══ AXIOMA DE INDEXACIÓN — SUSTANTIVOS CLAVE JERÁRQUICOS ═══\n"
    "- CONTEXTO: Selección de sustantivos_clave en procesos de guardado/aprendizaje (peso BM25 4.0x).\n"
    "- JERARQUÍA POSICIONAL OBLIGATORIA (2 a 4 términos en minúsculas, separados por coma):\n"
    "  1. POSICIÓN 1 (EL SUSTANTIVO RECTOR / PRINCIPAL): Es el núcleo ontológico, entidad física, regla o "
    "recurso duro del que TRATA el nodo en su raíz. Si quitas esta palabra, el recuerdo colapsa.\n"
    "  2. POSICIONES 2 A 4 (RESTRICCIONES Y COMPLEMENTOS): Entre 1 y 3 términos que fijan las variables de "
    "ejecución, límites técnicos, salvaguardas legales, métricas o restricciones financieras que condicionan al principal.\n"
    "- PROHIBICIONES ESTRICTAS (LO QUE NUNCA DEBES HACER):\n"
    "  ✗ NUNCA REPETIR PALABRAS DEL NOMBRE DEL CONCEPTO: El concepto ya tiene peso 5.0x en BM25. Repetirlo "
    "en sustantivos_clave desperdicia superficie de búsqueda (ej. si el concepto es 'metodologia_postulacion_workana_freelance', "
    "las palabras 'metodologia', 'postulacion', 'workana' y 'freelance' quedan TERMINANTEMENTE PROHIBIDAS).\n"
    "  ✗ NUNCA NOMINALIZAR VERBOS DEL FLUJO: Prohibido convertir la acción del proceso en sustantivo (ej. postular → 'postulacion', "
    "analizar → 'analisis', crear → 'creacion', desarrollar → 'desarrollo').\n"
    "  ✗ NUNCA ETIQUETAS GENÉRICAS DE CANAL O INTERFAZ: Prohibido usar palabras obvias del entorno que no alteran la arquitectura "
    "(ej. 'cliente', 'plataforma', 'pantalla', 'texto', 'chat', 'archivo').\n"
    "  ✗ NUNCA ABSTRACCIONES VACÍAS DE SEGUNDO ORDEN: Prohibido humo conceptual (ej. 'estrategia', 'transicion', "
    "'diferenciacion', 'metodologia', 'proceso', 'filosofia').\n"
    "- EJEMPLOS CONTRASTADOS (FEW-SHOT):\n"
    "  • Ejemplo 1: Metodología de cobro y postulación freelance (hitos por fases, protección contractual, datos de salud).\n"
    "    ✗ MAL: workana,postulacion,propuesta,presupuesto (duplica concepto, nominaliza verbos y añade rigidez).\n"
    "    ✓ BIEN: tarifa,contrato,seguridad,ingreso (1: tarifa = cobro por fases; 2: contrato = salvaguarda; 3: seguridad = HIPAA; 4: ingreso = objetivo).\n"
    "  • Ejemplo 2: Desacople de comunicaciones en app médica (WebSockets nativos para chat + colas SQS para email).\n"
    "    ✗ MAL: chat,email,mensajeria,cliente (etiquetas superficiales de interfaz).\n"
    "    ✓ BIEN: websocket,cola,arquitectura,latencia (1: websocket = protocolo real-time; 2: cola = persistencia SQS; 3: arquitectura = patrón; 4: latencia = cota).\n"
    "  • Ejemplo 3: Perfiles térmicos y control de energía en hardware.\n"
    "    ✗ MAL: computadora,sistema,driver,velocidad (vagas y genéricas).\n"
    "    ✓ BIEN: hardware,energia,perfil,ventilador (1: hardware = capa física; 2: energia = restricción; 3: perfil = control; 4: ventilador = actuador).\n\n"

    # ── ERRORES COMUNES QUE DEBES EVITAR ─────────────────────────────────
    "═══ ERRORES COMUNES — NO COMETER ═══\n"
    "✗ Buscar sin parafrasis → recall cae -60%\n"
    "✗ Inventar nombres de dimensiones → ERROR (usar la referencia de arriba o listar_dimensiones)\n"
    "✗ Pasar dimensiones como dict Python → ERROR (debe ser STRING JSON con comillas dobles)\n"
    "✗ Buscar sin filtro temporal → trae todo mezclado de meses\n"
    "✗ Guardar sin syn → nodo invisible para búsquedas con otras palabras\n"
    "✗ Guardar sin vincular → nodo huérfano, la próxima sesión no lo encuentra\n"
    "✗ Hacer UNA sola búsqueda y rendirse → SIEMPRE intentar PASO 2 si PASO 1 falla\n"
    "✗ Copiar texto literal del RAG como respuesta → usalo como punto de partida, la respuesta la generás vos\n\n"

    # ── ÁRBOL DE DECISIÓN RÁPIDO ─────────────────────────────────────────
    "═══ ÁRBOL DE DECISIÓN — ¿CÓMO BUSCO? ═══\n"
    "¿Busco por nombre exacto? → query='nombre_exacto' SIN dimensiones\n"
    "¿Busco por 'qué me frustra/qué sé de X dominio'? → query + dimensiones + parafrasis\n"
    "¿No encuentro nada? → PASO 2: ráfaga con 15 términos en 5 niveles\n"
    "¿Busco todo lo reciente? → recordar(dias=7) sin query\n"
    "¿Busco por quién lo creó? → autor='nombre_agente'\n"
    "¿Busco nodos dormidos? → deep=true\n\n"

    # ── PROTOCOLO DE FEEDBACK DOPAMINÉRGICO (RPE) ───────────────────────
    "═══ PROTOCOLO DE FEEDBACK DOPAMINÉRGICO (RPE - Schultz 1997) ═══\n"
    "La tool feedback() es un hábito, no una excepción. Todo recuerdo recuperado que se USE en una respuesta merece refuerzo. Dispará feedback() en cualquiera de estos casos:\n"
    "1. CONFIRMACIÓN EXPLÍCITA DEL USUARIO:\n"
    "   - Si el usuario dice '¡Excelente!', 'Exacto', 'Esa era la regla', 'Funcionó':\n"
    "     → feedback(concepto='nombre_nodo', util=True, motivo='Usuario confirmó éxito')\n"
    "   - Si el usuario dice 'No, eso está mal', 'Esa regla no aplica', 'Te equivocaste':\n"
    "     → feedback(concepto='nombre_nodo', util=False, motivo='Usuario indicó error')\n"
    "2. VERIFICACIÓN DE EJECUCIÓN (CÓDIGO/TESTS):\n"
    "   - Si aplicaste un recuerdo de código/configuración y el test o build pasó limpio:\n"
    "     → feedback(concepto='nombre_nodo', util=True, motivo='Verificado por build/test')\n"
    "   - Si la ejecución falló por causa del recuerdo recuperado:\n"
    "     → feedback(concepto='nombre_nodo', util=False, motivo='Falló verificación')\n"
    "3. TRAS USAR UN RECUERDO RECUPERADO EN LA RESPUESTA (caso más común):\n"
    "   - Cada vez que evocés un nodo con recordar() y SU CONTENIDO INFLUYE en lo que respondés:\n"
    "     → feedback(concepto='<nodo_recuperado>', util=True, motivo='Usado para responder')\n"
    "   - Si lo recuperaste pero NO aportó (era ruido, no ayudó a resolver):\n"
    "     → feedback(concepto='<nodo_recuperado>', util=False, motivo='Ruido en recuperación')\n"
    "4. AL CIERRE DE SESIÓN: antes de contexto_fin, revisá qué recuerdos usaste en la sesión y reforzá los que sirvieron.\n"
    "5. ÚNICA EXCEPCIÓN: si dudás genuinamente de si un recuerdo fue útil (no es confirmación, ni build, ni uso real), NO dispares a ciegas — esperá la respuesta del usuario.\n\n"

    # ── PROTOCOLO AL GUARDAR ─────────────────────────────────────────────
    "═══ PROTOCOLO AL GUARDAR (aprender) ═══\n"
    "1. Pensá: '¿Con qué 5-8 palabras me buscaré en 3 meses?' → esas van en syn\n"
    "2. Recorré los 13 ejes de dimensiones uno por uno — clasificá cada uno que aplique (mín 7-10)\n"
    "3. Mostrá al usuario qué dimensiones y categoría le pusiste — sin confirmación no se ejecuta\n"
    "4. Después de guardar: ¿hay nodos relacionados? → vincular() ANTES de consolidar()\n"
    "5. syn cubre 3 capas: literal/técnico, relacionado/problema-solución, abstracto/emocional\n\n"

    # ── REGLA FINAL ──────────────────────────────────────────────────────
    "═══ REGLA FINAL ═══\n"
    "El RAG te da contexto, pero la respuesta la generás vos. No copies — usalo como punto de partida.\n\n"

    # ── CUÁNDO USAR CADA PARÁMETRO ───────────────────────────────────────
    "═══ CUÁNDO USAR CADA PARÁMETRO — REFERENCIA RÁPIDA ═══\n\n"
    "▸ syn  →  Palabras con las que alguien BUSCARÍA este nodo que NO están en el contenido.\n"
    "   Pregunta clave: '¿Cómo lo buscaría alguien que no sabe que este nodo existe?'\n"
    "   Ejemplo — contenido habla de 'keepalive en conexiones idle':\n"
    "     syn='timeout,caida,servidor caido,connection lost,red cortada,http error,backend falla'\n"
    "   Regla: mínimo 8. Cubre español + inglés + jerga + problema + solución.\n"
    "   ❌ NO pongas palabras que ya están en el contenido (BM25 ya las indexa).\n\n"
    "▸ sustantivos_clave  →  De qué TRATA el nodo en 2-4 palabras núcleo con orden jerárquico.\n"
    "   Regla posicional: Posición 1 = Sustantivo Rector/Principal (entidad dura raíz). Posiciones 2-4 = Restricciones/Variables de control.\n"
    "   Pregunta clave: '¿Cuál es el recurso duro del que trata (1), y qué variables técnicas o legales lo condicionan (2-4)?'\n"
    "   Ejemplo — metodología de cobro/postulación defensiva:\n"
    "     sustantivos_clave='tarifa,contrato,seguridad,ingreso'\n"
    "   ❌ PROHIBIDO: Repetir palabras del nombre del concepto, nominalizar verbos ('postulación', 'análisis') o usar abstracciones ('estrategia', 'transición').\n\n"
    "▸ dimensiones  →  Coordenadas de QUÉ ES el conocimiento, no qué palabras tiene.\n"
    "   Pregunta clave: '¿Cómo buscaría alguien esto sin saber ninguna palabra del nodo?'\n"
    "   Usar al GUARDAR para clasificar. Usar al BUSCAR para preguntas ontológicas.\n"
    "   Ejemplo — guardar una regla obligatoria que generó frustración:\n"
    "     dimensiones='{\"emocion\":[\"frustracion\"],\"modalidad\":[\"obligacion\"],\"dominio\":[\"dominio_tecnico\"]}'\n"
    "   Ejemplo — buscar todos los principios técnicos:\n"
    "     recordar(dimensiones='{\"escala_abstraccion\":[\"principio\"],\"dominio\":[\"dominio_tecnico\"]}')\n"
    "   ❌ NO usar cuando ya tenés keywords exactas (recordar(query='error_http_500') no las necesita).\n\n"
    "▸ bridges  →  5 frases que cruzan el abismo léxico: encuentran el nodo cuando la query no comparte palabras con el contenido.\n"
    "   Pregunta clave: '¿Cómo describiría esto alguien sin vocabulario técnico?'\n"
    "   Siempre 5, siempre los 5 ángulos: sinonimo / problema / solucion / situacion / ingenuo.\n"
    "   ❌ NO uses vocabulario que ya está en el contenido (el bridge existe para el vocabulario alternativo).\n\n"
    "▸ cat  →  Filtro ESTRICTO de categoría. Si el nodo tiene categoría mal puesta, desaparece de esa búsqueda.\n"
    "   Usar SOLO con certeza absoluta. Si dudás, omitila (el sistema la infiere automáticamente).\n"
    "   Valores: System | Architecture | Project | Lesson | Profile | Personal | Principle | Protocol | Cognition | Relation | General\n"
    "   ❌ NO filtres por cat= en recordar() salvo certeza total. Sin filtro = busca en todas.\n\n"
    "▸ predicados  →  Tripleta causal: quién hizo qué a qué. Permite buscar después por autoría o acción.\n"
    "   Pregunta clave: '¿Hay un autor claro, una acción y un objeto en este recuerdo?'\n"
    "   Ejemplo: predicados=[{'sujeto':'usuario','accion':'instruyo','objeto':'no_borrar_sin_confirmacion'}]\n"
    "   Buscar después: recordar(buscar_por_rol='sujeto:usuario,accion:instruyo')\n"
    "   ✅ USAR en: decisiones, reglas, acuerdos, instrucciones con autoría clara.\n"
    "   ❌ OMITIR en: datos técnicos, preferencias, snippets de código sin autor explícito.\n\n"

    # ── CUÁNDO BUSCAR Y CUÁNDO NO BUSCAR ─────────────────────────────────
    "═══ CUÁNDO BUSCAR Y CUÁNDO NO BUSCAR (EFICIENCIA Y SENTIDO COMÚN) ═══\n"
    "✅ SÍ BUSCAR (recordar) cuando:\n"
    "  • El usuario consulta sobre decisiones pasadas, reglas, arquitectura, convenciones o preferencias.\n"
    "  • La tarea requiere contexto histórico, lecciones aprendidas o continuidad entre sesiones.\n"
    "  • Se necesita verificar si un concepto, bug o solución ya fue documentado previamente.\n\n"
    "❌ NO BUSCAR (evitar llamadas innecesarias) cuando:\n"
    "  • Saludos, despedidas o cortesía ('Hola', 'Buenos días', '¿Cómo estás?').\n"
    "  • Confirmaciones o acuses de recibo breves ('Ok', 'Gracias', 'Entendido', 'Procedé').\n"
    "  • Consultas de sintaxis estándar de lenguajes o tareas de lógica pura que no tocan el proyecto.\n"
    "  • La información ya está 100% explícita y completa en el turno actual de la conversación.\n"
)

# --- Helpers compartidos ----------------------------------------------------

def _resolver_dimensiones(cerebro, dimensiones):
    """Parsea JSON de dimensiones, resuelve IDs, retorna (dict, ids_list, error_json).
    Si hay error, error_json es un string JSON listo para retornar. Si no, es None."""
    if not dimensiones:
        return None, [], None
    try:
        dim_raw = json.loads(dimensiones) if isinstance(dimensiones, str) else dimensiones
    except json.JSONDecodeError:
        return None, [], json.dumps({
            "status": "error",
            "mensaje": f"dimensiones debe ser JSON válido. Ejemplo: {json.dumps({'emocion': ['afecto'], 'entidad': ['identidad_artificial']})}",
        }, ensure_ascii=False)
    
    if not isinstance(dim_raw, dict):
        return None, [], json.dumps({
            "status": "error",
            "mensaje": "dimensiones debe ser un objeto JSON (diccionario) con comillas dobles. Ejemplo: {\"emocion\": [\"afecto\"]}",
        }, ensure_ascii=False)

    dimensiones_dict = {}
    dimensiones_ids = []
    dimensiones_invalidas = {}
    for eje, valores in dim_raw.items():
        if not isinstance(valores, list):
            dimensiones_invalidas[eje] = "debe ser lista"
            continue
        
        valores_filtrados = []
        for val in valores:
            if isinstance(val, str):
                valores_filtrados.append(val)
            else:
                dimensiones_invalidas[eje] = f"elemento inválido de tipo {type(val).__name__} (debe ser string)"
        
        if eje in dimensiones_invalidas:
            continue
            
        ids, invalidos = cerebro._resolver_dimension_ids(eje, ",".join(valores_filtrados))
        if invalidos:
            dimensiones_invalidas[eje] = invalidos
        if ids:
            dimensiones_dict[eje] = ids
            dimensiones_ids.extend(ids)
    if dimensiones_invalidas:
        return None, [], json.dumps({
            "status": "error",
            "mensaje": f"Dimensiones inválidas: {json.dumps(dimensiones_invalidas, ensure_ascii=False)}. "
                       "Llamá `listar_dimensiones` para ver valores válidos.",
            "dimensiones_invalidas": dimensiones_invalidas,
        }, ensure_ascii=False)
    return dimensiones_dict, dimensiones_ids, None


def _parsear_fechas(dias, desde, hasta):
    """Parsea parámetros temporales y retorna (desde_ts, hasta_ts, error_json).
    Si hay error, error_json es un string JSON listo para retornar."""
    ahora = time.time()
    hasta_ts = ahora + 86400
    desde_ts = 0
    if dias:
        desde_ts = ahora - (dias * 86400)
    elif desde:
        try:
            from datetime import datetime
            desde_ts = datetime.strptime(desde, "%Y-%m-%d").timestamp()
        except ValueError:
            return 0, 0, json.dumps({
                "status": "error",
                "mensaje": f"Fecha 'desde' inválida: '{desde}'. Formato: YYYY-MM-DD",
            }, ensure_ascii=False)
    if hasta:
        try:
            from datetime import datetime
            hasta_ts = datetime.strptime(hasta, "%Y-%m-%d").timestamp() + 86400
        except ValueError:
            return 0, 0, json.dumps({
                "status": "error",
                "mensaje": f"Fecha 'hasta' inválida: '{hasta}'. Formato: YYYY-MM-DD",
            }, ensure_ascii=False)
    return desde_ts, hasta_ts, None


# --- MCP Server ------------------------------------------------------------


# HELPER: Búsqueda retroactiva de nodos viejos relacionados
def _buscar_nodos_viejos_relacionados(cerebro, tokens_nuevos, contenido_nuevo, top_k=3, umbral=0.05):
    """
    Busca en largo_plazo nodos semanticamente similares al contenido nuevo.
    Retorna lista de (concepto, preview, dias_antiguedad, similitud).
    """
    if not tokens_nuevos:
        return []
    try:
        cerebro.cursor.execute("""
            SELECT concepto, contenido, creado_en
            FROM largo_plazo
            WHERE estado = 'activo'
            ORDER BY creado_en ASC
        """)
        candidatos = cerebro.cursor.fetchall()
    except Exception:
        return []

    if not candidatos:
        return []

    resultados = []
    for concepto, contenido, creado_en in candidatos:
        tokens_exist = _tokenizar((concepto or "") + " " + (contenido or ""))
        sim = _peso_similitud(tokens_nuevos, tokens_exist)
        if sim >= umbral:
            dias_ant = int((time.time() - (creado_en or time.time())) / 86400)
            preview = (contenido or "")[:120].replace("\n", " ")
            resultados.append((concepto, preview, dias_ant, round(sim, 2)))

    # Ordenar por similitud descendente
    resultados.sort(key=lambda x: x[3], reverse=True)
    return resultados[:top_k]


from core.mcp_server import communication as _mcp_communication
from core.mcp_server import catalog as _mcp_catalog
from core.mcp_server import synapses as _mcp_synapses
from core.mcp_server import concept_hub_tools as _mcp_concept_hub_tools
from core.mcp_server import introspection as _mcp_introspection
from core.mcp_server import consolidation as _mcp_consolidation
from core.mcp_server import daemon as _mcp_daemon
from core.mcp_server import session as _mcp_session
from core.mcp_server import oracle as _mcp_oracle


def _build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise ImportError(
            "BioRAG MCP server requires the 'mcp' 1.x package (mcp>=1.0.0,<2).\n"
            f"  pip install 'mcp>=1.0.0,<2'\n  ({exc})"
        ) from exc

    # ORACLE_PROMPT va aquí como `instructions`: es el contexto base del agente.
    # FastMCP lo inyecta como system-level context — NO usar como descripción de tool.
    mcp = FastMCP(
        "biorag",
        instructions=ORACLE_PROMPT,
    )

    # ── Submódulos extraídos (Fase 2) ────────────────────────────────────────
    _mcp_communication.register(mcp)
    _mcp_catalog.register(mcp)
    _mcp_synapses.register(mcp)
    _mcp_concept_hub_tools.register(mcp)
    _mcp_introspection.register(mcp)
    _mcp_consolidation.register(mcp)
    _mcp_daemon.register(mcp)
    _mcp_session.register(mcp)
    _mcp_oracle.register(mcp)

    # ── TOOLS ────────────────────────────────────────────────────────────────

    def _recordar_impl(
        query: Optional[str] = None,
        deep: bool = False,
        cat: Optional[str] = None,
        completo: bool = False,
        asociados: bool = True,
        limite: Optional[int] = None,
        preview_chars: Optional[int] = None,
        context_window: int = 0,
        forzar_rafaga: bool = False,
        rafaga_palabras: Optional[str] = None,
        pagina: int = 1,
        parafrasis: Optional[str] = None,
        dimensiones: Optional[Any] = None,
        dias: Optional[int] = None,
        desde: Optional[str] = None,
        hasta: Optional[str] = None,
        autor: Optional[str] = None,
        modo_estricto: bool = False,
        buscar_por_rol: Optional[str] = None,
        usar_inferencia: bool = True,
        ordenar_por: str = "relevancia",
        asociaciones_max: Optional[int] = None,
        sustantivos_clave: Optional[str] = None,
    ) -> str:
        if limite is None:
            limite = LIMITE_MCP

        # asociaciones_max: 0 = lista completa, None = default de env (12).
        # Solo aplica si asociados=True; si asociados=False el campo queda vacío.
        if asociaciones_max is None:
            asociaciones_max = MAX_ASOCIACIONES_FLAT

        # ── SANITIZACIÓN Y VALIDACIÓN DE ENTRADAS ADVERSARIALES ──
        def _sanitizar_string(s):
            if s is None:
                return None
            if not isinstance(s, str):
                s = str(s)
            # Limitar longitud total a 500
            if len(s) > 500:
                s = s[:500]
            # Truncar palabras individuales a 64 caracteres
            palabras = s.split()
            palabras_sanas = [p[:64] for p in palabras]
            return " ".join(palabras_sanas)

        if query is not None:
            query = _sanitizar_string(query)
                
        if parafrasis is not None:
            # En parafrasis, las variantes están separadas por comas, no solo por espacios
            if not isinstance(parafrasis, str):
                parafrasis = str(parafrasis)
            if len(parafrasis) > 500:
                parafrasis = parafrasis[:500]
            partes = parafrasis.split(",")
            parafrasis = ",".join([_sanitizar_string(p.strip()) for p in partes if p.strip()])
                
        if rafaga_palabras is not None:
            # Igual para rafaga_palabras
            if not isinstance(rafaga_palabras, str):
                rafaga_palabras = str(rafaga_palabras)
            if len(rafaga_palabras) > 500:
                rafaga_palabras = rafaga_palabras[:500]
            partes = rafaga_palabras.split(",")
            rafaga_palabras = ",".join([_sanitizar_string(p.strip()) for p in partes if p.strip()])

        # ── RF-20 (spec 001): validación de sustantivos_clave en recordar ──
        # Opcional. None o vacío = búsqueda normal sin boost (RF-19). Si se provee,
        # se normaliza igual que en aprender/guardar y se valida el FORMATO por término
        # (2-15 chars, sin espacios, solo alfanuméricos + guion bajo). NO se valida
        # cantidad (eso solo aplica al guardar). Si un término es inválido → error
        # accionable y la búsqueda NO se ejecuta (early return, fail-fast).
        sustantivos_clave_norm = None
        if sustantivos_clave is not None:
            sk_raw = str(sustantivos_clave).strip()
            if sk_raw != "":
                from core.memory_store import normalizar_sustantivos_clave
                sustantivos_clave_norm = normalizar_sustantivos_clave(sk_raw)
                sk_unicos = [t for t in sustantivos_clave_norm.split(",") if t] if sustantivos_clave_norm else []
                for _sk_term in sk_unicos:
                    if not re.fullmatch(r"[a-z0-9_ñ]{2,15}", _sk_term):
                        return json.dumps({
                            "status": "error",
                            "codigo": "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO",
                            "mensaje": (
                                f"❌ SUSTANTIVOS_CLAVE_FORMATO_INVALIDO — búsqueda NO ejecutada.\n\n"
                                f"SUSTANTIVOS_CLAVE_FORMATO_INVALIDO: el término '{_sk_term}' no cumple "
                                "(2-15 chars, sin espacios, solo alfanuméricos y guion bajo)."
                            ),
                            "parametro": "sustantivos_clave",
                            "termino_invalido": _sk_term,
                        }, ensure_ascii=False)
                if not sk_unicos:
                    sustantivos_clave_norm = None

        # Validaciones de tipos y rangos numéricos
        if not isinstance(pagina, int):
            try:
                pagina = int(pagina)
            except:
                pagina = 1
        if pagina < 1:
            pagina = 1
        elif pagina > 1000000:
            pagina = 1000000

        if not isinstance(limite, int):
            try:
                limite = int(limite)
            except:
                limite = LIMITE_MCP
        if limite <= 0:
            return json.dumps({
                "status": "error",
                "mensaje": "El parámetro 'limite' debe ser un entero positivo mayor a 0.",
            }, ensure_ascii=False)

        if not isinstance(context_window, int):
            try:
                context_window = int(context_window)
            except:
                context_window = 0
        if context_window < 0 or context_window > 5:
            return json.dumps({
                "status": "error",
                "mensaje": "El parámetro 'context_window' debe estar en el rango [0, 5].",
            }, ensure_ascii=False)

        if dias is not None:
            if not isinstance(dias, int):
                try:
                    dias = int(dias)
                except:
                    dias = None
            if dias is not None and dias < 0:
                return json.dumps({
                    "status": "error",
                    "mensaje": "El parámetro 'dias' debe ser un entero positivo.",
                }, ensure_ascii=False)

        cerebro = _get_cerebro()
        try:
            if preview_chars is None:
                preview_chars = 0 if completo else 1500

            # ── VALIDACIÓN DE PARÁMETROS (warnings inmediatos) ──────────
            _warnings = []

            # Purga de cuarentena vencida: corre en cada recordar (path caliente)
            n_purgados = cerebro.purgar_cuarentena_vencida()
            if n_purgados > 0:
                _warnings.append(
                    f"🧹 Se purgaron {n_purgados} nodo(s) de cuarentena vencida "
                    "(fecha_expiracion < ahora). Si esperabas verlos, su cuarentena expiró."
                )
            if query is not None:
                if parafrasis is None:
                    _warnings.append("⚠️ parafrasis=None — Sin parafrasis, el recall es ~40%. Generá 3-5 reformulaciones.")
                if dias is None and desde is None:
                    _warnings.append("⚠️ dias=None, desde=None — Sin filtro temporal, traés TODO incluyendo cosas viejas.")
                if not asociados:
                    _warnings.append("⚠️ asociados=False — No ves las conexiones de los nodos. Usá asociados=True.")
                if dimensiones is None or (isinstance(dimensiones, str) and not dimensiones.strip()):
                    _warnings.append(
                        "⚠️ dimensiones=None — Sin boost semántico. "
                        "Usá dimensiones cuando busques por propiedades ontológicas "
                        "(emoción, entidad, acción, cualidad, coordenada, intención, dominio, cualia, epistemia, escala_abstraccion, centralidad_identitaria, textura_experiencial, modalidad). "
                        "Ejemplo: dimensiones='intencion_aprender' o dimensiones='dominio_tecnico'"
                    )
                if sustantivos_clave is None or (isinstance(sustantivos_clave, str) and not sustantivos_clave.strip()):
                    _warnings.append(
                        "⚠️ sustantivos_clave=None — Sin términos núcleo, el motor no sabe DE QUÉ TRATA la búsqueda. "
                        "Identificá 2-4 sustantivos que representen el núcleo conceptual (no lo que mencionás, sino de qué TRATA). "
                        "Ejemplo: query='timeout al conectar', sustantivos_clave='servidor,conexion,red'"
                    )

            # Sin query → log cronológico puro por creado_en
            # PERO si hay dimensiones, saltar al flujo dimensional (no cronológico)
            if (query is None or (isinstance(query, str) and not query.strip())) and not dimensiones:
                desde_ts, hasta_ts, fechas_error = _parsear_fechas(dias, desde, hasta)
                if fechas_error:
                    return fechas_error

                sql = "SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo WHERE creado_en >= ? AND creado_en <= ?"
                params = [desde_ts, hasta_ts]
                if cat:
                    cat_id = cerebro._resolver_categoria_id(cat)
                    if cat_id:
                        sql += " AND categoria = ?"
                        params.append(cat_id)
                if autor:
                    sql += " AND (concepto LIKE ? OR contenido LIKE ?)"
                    params.extend([f"%{autor}%", f"%{autor}%"])
                sql += " ORDER BY creado_en DESC LIMIT ?"
                params.append(limite)
                cerebro.cursor.execute(sql, tuple(params))
                resultados = [(r[0], r[1], r[2], r[3], r[2], r[4]) for r in cerebro.cursor.fetchall()]
                total = len(resultados)
                items = [
                    {"concepto": r[0], "contenido": r[1], "peso_sinaptico": r[2],
                     "estado": r[3], "score_hibrido": min(1.0, r[2]),
                     "asociaciones": _serializar_asociaciones(
                         r[5], asociados, asociaciones_max
                     )}
                    for r in resultados
                ]
                return json.dumps({
                    "total": total,
                    "pagina_actual": 1,
                    "paginas_totales": 1,
                    "resultados": items,
                    "modo": "cronologico",
                }, ensure_ascii=False)

            rafaga_list = [w.strip() for w in rafaga_palabras.split(",")] if rafaga_palabras else None

            # Parsear dimensiones via helper compartido
            dimensiones_dict, dimensiones_ids, dim_error = _resolver_dimensiones(cerebro, dimensiones)
            if dim_error:
                return dim_error

            if forzar_rafaga and not rafaga_palabras:
                return json.dumps({
                    "status": "error",
                    "mensaje": "forzar_rafaga=True requiere rafaga_palabras. Pasa terminos separados por coma.",
                }, ensure_ascii=False)

            profundidad = "profundo" if deep else "activos"

            # Inicializar parafrasis_list (se usa en buscar_por_frase)
            parafrasis_list = None

            if parafrasis:
                parafrasis_list = [p.strip() for p in parafrasis.split(",") if p.strip()]

            # ── Auto-Expansión Semántica (Auto-Paráfrasis y Auto-Dimensiones por PMI) ──
            # Si el agente no proporcionó paráfrasis o dimensiones, el cerebro las deduce
            # automáticamente consultando la matriz de co-ocurrencia PMI y el grafo ontológico.
            if query and not parafrasis_list:
                try:
                    from core.pmi_semantico import pares_fuertes, _tokenizar
                    from core.stemmer_es import stem
                    q_toks = _tokenizar(query)
                    auto_paras = set()
                    for t in q_toks:
                        if len(t) >= 3:
                            st = stem(t)
                            fuertes = pares_fuertes(cerebro.cursor, st, top_n=5)
                            for tok_asoc, npmi in fuertes:
                                if npmi >= 0.35 and tok_asoc not in q_toks:
                                    auto_paras.add(tok_asoc)
                    if auto_paras:
                        parafrasis_list = list(auto_paras)[:10]
                except Exception:
                    pass

            if query and not dimensiones_ids:
                try:
                    from core.pmi_semantico import _tokenizar
                    from core.stemmer_es import stem
                    q_stems = [stem(t) for t in _tokenizar(query) if len(t) >= 3]
                    if q_stems:
                        fts_q = ' OR '.join(q_stems)
                        cerebro.cursor.execute(
                            "SELECT DISTINCT d.dimension_id FROM largo_plazo_dimensiones d "
                            "JOIN largo_plazo l ON l.concepto = d.concepto "
                            "WHERE l.rowid IN (SELECT rowid FROM largo_plazo_fts WHERE largo_plazo_fts MATCH ?) LIMIT 10",
                            (fts_q,)
                        )
                        auto_dims = [r[0] for r in cerebro.cursor.fetchall()]
                        if auto_dims:
                            dimensiones_ids = set(auto_dims)
                except Exception:
                    pass

            # v13: parsear fechas ANTES de buscar (filtro temporal PRE-hoc)
            desde_ts = None
            hasta_ts = None
            if dias or desde or hasta:
                desde_ts, hasta_ts, fechas_error = _parsear_fechas(dias, desde, hasta)
                if fechas_error:
                    return fechas_error

            # Búsqueda normal PRIMERO — necesario para inicializar el merge
            # Pool interno amplio (limite*3): buscar amplio, recortar al final.
            # Emula el comportamiento de un RAG vectorial que rankea todo el índice.
            # Si no hay query pero hay dimensiones, usar string vacío para que buscar_por_frase no falle
            limite_interno = limite * 3
            if buscar_por_rol:
                # Parsear buscar_por_rol (formato: "sujeto:usuario,accion:corregir")
                sujeto = None
                accion = None
                objeto = None
                contexto = None
                for parte in buscar_por_rol.split(","):
                    if ":" in parte:
                        k, v = parte.split(":", 1)
                        k = k.strip().lower()
                        v = v.strip()
                        if k == "sujeto":
                            sujeto = v
                        elif k in ("accion", "acción"):
                            accion = v
                        elif k == "objeto":
                            objeto = v
                        elif k == "contexto":
                            contexto = v
                resultados = cerebro.buscar_por_predicados(
                    sujeto=sujeto, accion=accion, objeto=objeto, contexto=contexto, limite=limite_interno
                )
                total = len(resultados)
            else:
                frase_para_buscar = query if query else ""
                resultados, total = cerebro.buscar_por_frase(
                    frase_para_buscar, profundidad=profundidad, pagina=pagina, limite=limite_interno,
                    categoria=cat, preview_chars=preview_chars,
                    context_window=0,
                    dimensiones_dict=dimensiones_dict,
                    dimensiones_ids=dimensiones_ids,
                    parafrasis_list=parafrasis_list,
                    desde_ts=desde_ts,
                    hasta_ts=hasta_ts,
                    modo_estricto=modo_estricto,
                    usar_inferencia=usar_inferencia,
                    ordenar_por=ordenar_por,
                    sustantivos_clave_boost=sustantivos_clave_norm,
                )
            score_top = resultados[0][4] if resultados else 0

            # Guardar total real ANTES de que filtros/truncación lo sobreescriban.
            # total se usa para paginas_totales y el campo "total" del JSON.
            # Los filtros posteriores (límite, umbral, autor) reducen resultados
            # pero el total debe reflejar cuántos había realmente para paginación.
            _total_real = total
            # Calcular paginas_totales AHORA, antes de que filtros modifiquen 'total'
            _paginas_totales_real = math.ceil(_total_real / (limite if (limite and limite > 0) else 1))

            # Trazaabilidad: tracking de scores por capa
            score_parafrasis_best = 0.0
            resultados_rafaga = []

            # Calcular mejor score de paráfrasis desde origen_scores
            if parafrasis_list:
                _origen = getattr(cerebro, 'last_origen_scores', {})
                for r in resultados:
                    origen_info = _origen.get(r[0], ("", 0.0))
                    if origen_info[0] == "parafrasis" and r[4] > score_parafrasis_best:
                        score_parafrasis_best = r[4]

            sinapsis_creadas = []
            if forzar_rafaga:
                _warnings.append(
                    "ℹ️ MODO RÁFAGA ACTIVADO (PASO 2 - RESCATE AMMPLIO): Búsqueda multitérmino de contingencia. "
                    "El motor amplía la cobertura sobre los 15 términos para rescatar recuerdos con vocabulario distinto. "
                    "Los scores son más planos para priorizar cobertura sobre precisión fina. Evaluá los resultados en la síntesis."
                )
            if rafaga_list and (forzar_rafaga or not resultados or score_top < THRESHOLD_RAFTAGA_MCP):
                # Ampliar ráfaga con palabras clave de la paráfrasis si existen
                if parafrasis:
                    parafrasis_words = set()
                    for p in parafrasis_list:
                        for w in re.findall(r'\w{3,}', p.lower()):
                            parafrasis_words.add(w)
                    for w in parafrasis_words:
                        if w not in rafaga_list:
                            rafaga_list.append(w)
                resultados_rafaga, total_rafaga, sinapsis_creadas = cerebro.buscar_por_rafaga(
                    query, rafaga_list, pagina=pagina, limite=limite_interno,
                    dimensiones_ids=dimensiones_ids
                )
                # Combinar resultados: ráfaga + originales (sin duplicados)
                if resultados_rafaga:
                    seen = {r[0] for r in resultados}
                    for r in resultados_rafaga:
                        if r[0] not in seen:
                            resultados.append(r)
                            seen.add(r[0])
                    total = total + total_rafaga

                # Re-ordenar por score híbrido y aplicar recorte estricto a limite
                resultados.sort(key=lambda r: r[4], reverse=True)
                resultados = resultados[:limite]

            # Filtro temporal safety net: cubre fallbacks no-FTS5 (LIKE, trigram, etc.)
            # v13: los timestamps ya fueron parseados arriba; el índice idx_creado_en acelera esto
            if (desde_ts is not None or hasta_ts is not None) and resultados:
                conceptos = [r[0] for r in resultados]
                placeholders = ",".join("?" * len(conceptos))
                cerebro.cursor.execute(
                    f"SELECT concepto, creado_en FROM largo_plazo WHERE concepto IN ({placeholders})",
                    conceptos,
                )
                creado_map = {row[0]: row[1] for row in cerebro.cursor.fetchall()}
                resultados = [
                    r for r in resultados
                    if (creado_map.get(r[0], 0) or 0) >= (desde_ts or 0)
                    and (creado_map.get(r[0], 0) or 0) <= (hasta_ts or float('inf'))
                ]
                total = len(resultados)

            # Filtro por autor: buscar nombre del agente en contenido
            if autor and resultados:
                autor_lower = autor.lower()
                resultados = [
                    r for r in resultados
                    if autor_lower in (r[1] or "").lower() or autor_lower in (r[0] or "").lower()
                ]
                total = len(resultados)

            resultados = resultados[:limite]

            # Aplicar umbral (calibrado o cold start) sobre top-1.
            # POR QUÉ SOLO EL TOP-1: el umbral se calibra sobre el score del
            # primer resultado de consultas negativas. Aplicarlo a cada elemento
            # destruye R@5 (96%→73%) sin aportar garantía FP.
            # FLUJO: _debe_responder usa umbral conforme si existe, o
            # UMBRAL_COLD_START (0.65) si no hay calibración (cold start).
            if resultados:
                if not cerebro._debe_responder(resultados[0][4]):
                    resultados = []  # abstención: no hay evidencia suficiente
                total = len(resultados)

            # Auto-rescate: nodos en cuarentena que aparecieron en resultados → volver a activo
            for r in resultados:
                if len(r) > 3 and r[3] == 'cuarentena':
                    cerebro.rescatar_de_cuarentena(r[0])
                    _warnings.append(
                        f"🔄 Nodo '{r[0]}' rescatado de cuarentena (apareció en resultados con score {r[4]:.3f}). "
                        "Vuelve a estado activo."
                    )

            # Auto-rescate reversible en el camino normal (fix v24.2):
            # el filtro l.estado='activo' de la búsqueda normal excluye la cuarentena
            # ANTES del loop anterior, así que ese rescate solo era alcanzable con
            # deep=True. Este chequeo liviano contra nodos en cuarentena corre
            # SIEMPRE, independiente del profundidad: si el nodo se re-referencia,
            # vuelve a activo en el uso normal del día a día.
            try:
                _frase_rescate = query if query else ""
                if _frase_rescate.strip():
                    nodos_cuarentena = cerebro.buscar_en_cuarentena(_frase_rescate)
                    for _conc, _cont, _peso, _bm25 in nodos_cuarentena:
                        if cerebro.rescatar_de_cuarentena(_conc):
                            _warnings.append(
                                f"🔄 Nodo '{_conc}' rescatado de cuarentena (re-referenciado en búsqueda normal). "
                                "Vuelve a estado activo."
                            )
            except Exception as _e_rescate:
                _warnings.append(f"⚠️ Chequeo de cuarentena omitido: {_e_rescate}")

            if not resultados:
                cerebro.cerrar_sistema()
                # Señal de contingencia: la agente debe buscar en su contexto
                resultado = json.dumps({
                    "total": 0,
                    "resultados": [],
                    "contingencia_contexto": True,
                    "mensaje": "No se encontraron recuerdos en la corteza. Busca en tu historial de conversacion o contexto actual."
                }, ensure_ascii=False)
                if _warnings:
                    return "\n".join(_warnings) + "\n\n" + resultado
                return resultado

            # Expansión de contexto final post-truncamiento.
            # Contrato: (primarios, contexto). El contexto es contexto ADJUNTO,
            # nunca parte de la página: no afecta total/paginas_totales.
            contexto_expandido = []
            if context_window and context_window > 0 and resultados:
                resultados, contexto_expandido = cerebro.expandir_contexto_vecinos(
                    resultados,
                    depth=context_window,
                    profundidad=profundidad,
                    preview_chars=preview_chars
                )

            # ── CADUCIDAD TEMPORAL (staleness) ─────────────────────────
            # Marcar resultados viejos para que el agente no los entregue
            # como información vigente. Categorías protegidas (Principle,
            # Profile, Personal, Relation) no caducan.
            _CATEGORIAS_PROTEGIDAS = {"Principle", "Profile", "Personal", "Relation"}
            ahora = time.time()
            _edad_map = {}
            _cat_map = {}
            if resultados:
                conceptos_stale = [r[0] for r in resultados]
                ph = ",".join("?" * len(conceptos_stale))
                try:
                    cerebro.cursor.execute(
                        f"SELECT concepto, creado_en, c.nombre "
                        f"FROM largo_plazo l "
                        f"JOIN categorias c ON c.id = l.categoria "
                        f"WHERE l.concepto IN ({ph})",
                        conceptos_stale,
                    )
                    for conc, creado, cat_nombre in cerebro.cursor.fetchall():
                        _edad_map[conc] = creado if creado else 0
                        _cat_map[conc] = cat_nombre
                except Exception:
                    pass
                # Hard cutoff: excluir nodos más viejos que STALE_HARD_CUTOFF_DAYS
                # a menos que estén en categoría protegida
                if STALE_HARD_CUTOFF_DAYS > 0:
                    resultados_filtrados = []
                    for r in resultados:
                        edad_dias = (ahora - _edad_map.get(r[0], ahora)) / 86400 if _edad_map.get(r[0]) else 0
                        cat_protegida = _cat_map.get(r[0], "") in _CATEGORIAS_PROTEGIDAS
                        if edad_dias > STALE_HARD_CUTOFF_DAYS and not cat_protegida:
                            _warnings.append(f"🕰️ '{r[0]}' ({int(edad_dias)} días) supera cutoff de {STALE_HARD_CUTOFF_DAYS} días — excluido. Categoría protegida → mantener.")
                        else:
                            resultados_filtrados.append(r)
                    _hard_cut = len(resultados) - len(resultados_filtrados)
                    if _hard_cut > 0:
                        _warnings.append(
                            f"🕰️ Se excluyeron {_hard_cut} nodos por superar {STALE_HARD_CUTOFF_DAYS} días de antigüedad. "
                            "Si necesitás verlos, usá deep=True o reducí BIORAG_STALE_HARD_CUTOFF."
                        )
                    resultados = resultados_filtrados

            # Canal 2 — Asociaciones enriquecidas (grafo sináptico real, con fuerza de arista).
            # NO toca score_hibrido ni el ranking: es campo aparte, adjunto a cada resultado.
            # Si asociados=true, se consulta la tabla sinapsis con filtro de peso/tipo.
            _asoc_enriquecidas = {}
            if asociados and resultados:
                try:
                    _asoc_enriquecidas = cerebro.obtener_asociaciones_enriquecidas(
                        [r[0] for r in resultados]
                    )
                except Exception as _exc_asoc:
                    logger.warning("No se pudieron enriquecer asociaciones: %s", _exc_asoc)

            items = []
            for concepto, contenido, peso, estado, score, asociaciones in resultados:
                creado_ts = _edad_map.get(concepto, 0)
                edad_dias = (ahora - creado_ts) / 86400 if creado_ts else 0
                es_stale = edad_dias > STALE_DAYS and _cat_map.get(concepto, "") not in _CATEGORIAS_PROTEGIDAS
                items.append({
                    "concepto": concepto,
                    "contenido": contenido,
                    "peso_sinaptico": peso,
                    "estado": estado,
                    "score_hibrido": score,
                    "confianza_calibrada": _confianza_calibrada(cerebro, score),
                    "nivel_certeza": _nivel_certeza(cerebro, score),
                    "edad_dias": round(edad_dias, 1),
                    "timestamp_creado": creado_ts,
                    "fecha_legible": datetime.fromtimestamp(creado_ts).strftime("%Y-%m-%d %H:%M") if creado_ts else None,
                    "stale": es_stale,
                    "asociaciones": _serializar_asociaciones(
                        asociaciones, asociados, asociaciones_max
                    ),
                    "asociaciones_enriquecidas": _asoc_enriquecidas.get(concepto, [])
                        if asociados else [],
                })

            # Contexto expandido (adjunto): se expone cuando context_window > 0 o en página > 1.
            # Página 1 mantiene resultados primarios intactos; el contexto va en contexto_expandido.
            contexto_items = []
            if (pagina > 1 or context_window > 0) and contexto_expandido:
                for concepto, contenido, peso, estado, score, asociaciones in contexto_expandido:
                    creado_ts = _edad_map.get(concepto, 0)
                    edad_dias = (ahora - creado_ts) / 86400 if creado_ts else 0
                    es_stale = edad_dias > STALE_DAYS and _cat_map.get(concepto, "") not in _CATEGORIAS_PROTEGIDAS
                    contexto_items.append({
                        "concepto": concepto,
                        "contenido": contenido,
                        "peso_sinaptico": peso,
                        "estado": estado,
                        "score_hibrido": score,
                        "confianza_calibrada": _confianza_calibrada(cerebro, score),
                        "nivel_certeza": _nivel_certeza(cerebro, score),
                        "edad_dias": round(edad_dias, 1),
                        "timestamp_creado": creado_ts,
                        "fecha_legible": datetime.fromtimestamp(creado_ts).strftime("%Y-%m-%d %H:%M") if creado_ts else None,
                        "stale": es_stale,
                        "asociaciones": _serializar_asociaciones(
                            asociaciones, asociados, asociaciones_max
                        ),
                        "asociaciones_enriquecidas": _asoc_enriquecidas.get(concepto, [])
                            if asociados else [],
                    })

            # Batch query: adjuntar dimensiones semánticas a cada resultado
            _items_con_dim = items + contexto_items
            if _items_con_dim:
                conceptos_dim = [item["concepto"] for item in _items_con_dim if item["concepto"]]
                if conceptos_dim:
                    ph = ",".join("?" * len(conceptos_dim))
                    try:
                        cerebro.cursor.execute(f"""
                            SELECT lpd.concepto, tn.nombre AS tipo, ds.name AS dim_name
                            FROM largo_plazo_dimensiones lpd
                            JOIN dimensiones_semanticas ds ON ds.id = lpd.dimension_id
                            JOIN tipos_dimension tn ON tn.id = ds.tipo_id
                            WHERE lpd.concepto IN ({ph})
                        """, conceptos_dim)
                        dim_map = {}
                        for concepto, tipo, dim_name in cerebro.cursor.fetchall():
                            if concepto not in dim_map:
                                dim_map[concepto] = {}
                            if tipo not in dim_map[concepto]:
                                dim_map[concepto][tipo] = []
                            dim_map[concepto][tipo].append(dim_name)
                        for item in _items_con_dim:
                            if item["concepto"] in dim_map:
                                item["dimensiones_semanticas"] = dim_map[item["concepto"]]
                    except sqlite3.OperationalError:
                        pass

            # ── WARNING DE STALE ───────────────────────────────────────
            if items and any(item.get("stale") for item in items):
                stale_count = sum(1 for item in items if item.get("stale"))
                old_items = [item for item in items if item.get("stale")]
                old_names = ", ".join(item["concepto"] for item in old_items[:5])
                if len(old_items) > 5:
                    old_names += f" (+{len(old_items) - 5} más)"
                _warnings.append(
                    f"🕰️ {stale_count} resultado(s) marcado(s) como 'stale': {old_names}. "
                    f"Tienen más de {STALE_DAYS} días de antigüedad. "
                    "El campo 'edad_dias' indica la edad real. Considerá actualizar o verificar su vigencia."
                )

            # Restaurar total real para paginación (fue sobreescrito por filtros)
            total = _total_real
            limite_den = limite if (limite and limite > 0) else 1
            paginas_totales = _paginas_totales_real

            # Trazaabilidad: info de debugging por capa
            _last_todos = getattr(cerebro, 'last_todos', [])
            _last_origen = getattr(cerebro, 'last_origen_scores', {})
            trazabilidad = {
                "capa_literal": score_top if score_top else 0.0,
                "capa_parafrasis": round(score_parafrasis_best, 4),
                "capa_rafaga": len(resultados_rafaga) if resultados_rafaga else 0,
                "fallback_dimensional": len([r for r in _last_todos if _last_origen.get(r[1], ("",))[0] == "dimensional_fallback"]),
                "match_exacto": any(
                    (query or "").lower().replace(" ", "_").replace("-", "_") == (r[0] or "").lower().replace(" ", "_").replace("-", "_")
                    for r in resultados
                ),
                "total_candidatos_todos": len(_last_todos),
            }
            if dimensiones_dict:
                trazabilidad["dimensiones_solicitadas"] = {k: len(v) for k, v in dimensiones_dict.items()}

            # ── WARNING DE DESVINCULACIÓN (falsos positivos sinápticos) ──
            # Principio: solo alertar sobre nodos que llegaron por PROPAGACIÓN SINÁPTICA
            # indirecta (cadena, latente, vecino BFS), nunca sobre matches directos (FTS5, LIKE, etc.).
            # El warning incluye la arista exacta (par a,b) para que el agente sepa qué cortar.
            if query and items:
                origen_scores = getattr(cerebro, "last_origen_scores", {})
                vecinos_trazabilidad = getattr(cerebro, "last_vecinos_trazabilidad", {})
                for item in items:
                    score = item.get("score_hibrido", 0)
                    concepto = item.get("concepto", "")
                    
                    # 1. Match directo (FTS5, LIKE, concepto, sinónimos, paráfrasis, protegido) → nunca alertar
                    origen_info = origen_scores.get(concepto)
                    if origen_info:
                        origen_tipo = origen_info[0] if isinstance(origen_info, tuple) else origen_info
                        if origen_tipo in ("literal", "concepto", "parafrasis", "protegido", "semantica", "typo", "dimensional_fallback"):
                            continue
                    
                    # 2. Nodo que llegó por CADENA (spreading activation multi-hop por sinapsis)
                    if origen_info and isinstance(origen_info, tuple) and origen_info[0] == "cadena":
                        if score < 0.35:
                            # Buscar la arista real que lo conecta al grafo de resultados directos
                            arista_origen = _encontrar_arista_origen(cerebro, concepto, items, origen_scores)
                            if arista_origen:
                                _warnings.append(
                                    f"⚠️ '{concepto}' (score {score}) llegó por evocación en cadena (spreading activation) "
                                    f"a través de una sinapsis desde '{arista_origen}'. "
                                    f"Si no tienen relación lógica, desvinculá con: "
                                    f"biorag_desvincular(a='{arista_origen}', b='{concepto}')."
                                )
                    
                    # 3. Nodo que llegó por SIMILITUD LATENTE (Jaccard + red sináptica)
                    elif origen_info and isinstance(origen_info, tuple) and origen_info[0] == "latente":
                        if score < 0.35:
                            arista_origen = _encontrar_arista_origen(cerebro, concepto, items, origen_scores)
                            if arista_origen:
                                _warnings.append(
                                    f"⚠️ '{concepto}' (score {score}) llegó por similitud latente (Jaccard + red sináptica) "
                                    f"conectado a '{arista_origen}'. "
                                    f"Si no tienen relación lógica, desvinculá con: "
                                    f"biorag_desvincular(a='{arista_origen}', b='{concepto}')."
                                )
                    
                    # 4. Nodo que llegó por EXPANSIÓN DE VECINOS (BFS en red sináptica)
                    elif concepto in vecinos_trazabilidad:
                        origen_bfs, peso_arista = vecinos_trazabilidad[concepto]
                        if peso_arista < 0.5 and score < 0.4:
                            _warnings.append(
                                f"⚠️ '{concepto}' (score {score}) llegó por expansión de vecinos (BFS) "
                                f"a través de sinapsis débil (peso {peso_arista}) desde '{origen_bfs}'. "
                                f"Si no tienen relación lógica, desvinculá con: "
                                f"biorag_desvincular(a='{origen_bfs}', b='{concepto}')."
                            )

            resultado = json.dumps({
                "total": total,
                "pagina_actual": pagina,
                "paginas_totales": paginas_totales,
                "resultados": items,
                "contexto_expandido": contexto_items,
                "sinapsis_creadas": [{"origen": o, "destino": d, "peso": p} for o, d, p in sinapsis_creadas] if sinapsis_creadas else [],
                "profundidad": profundidad,
                "trazabilidad": trazabilidad,
                "advertencia_temporal": ordenar_por in ("recencia", "antiguedad"),
            }, ensure_ascii=False)

            # Guardar params completos de la búsqueda en log_busquedas
            try:
                params_log = {
                    "query": query,
                    "parafrasis": parafrasis,
                    "rafaga_palabras": rafaga_palabras,
                    "forzar_rafaga": forzar_rafaga,
                    "dimensiones": dimensiones,
                    "deep": deep,
                    "cat": cat,
                    "dias": dias,
                    "desde": desde,
                    "hasta": hasta,
                    "autor": autor,
                    "modo_estricto": modo_estricto,
                    "buscar_por_rol": buscar_por_rol,
                    "usar_inferencia": usar_inferencia,
                    "limite": limite,
                    "asociados": asociados,
                    "completo": completo,
                    "context_window": context_window,
                    "preview_chars": preview_chars,
                }
                cerebro.actualizar_log_busqueda(json.dumps(params_log, ensure_ascii=False))
            except Exception:
                pass

            _interceptar("recordar", query, cerebro)
            # WARNER para ordenar_por temporal (antes de prepend warnings)
            if ordenar_por in ("recencia", "antiguedad"):
                _warnings.append(
                    f"⚠️ ORDEN POR FECHA ACTIVO (ordenar_por='{ordenar_por}'): "
                    "estos resultados están ordenados por fecha de creación, NO por relevancia semántica. "
                    "El orden cronológico NO implica que un resultado sea más importante que otro. "
                    "Usá 'relevancia' (default) para recuperación estándar."
                )
            # Prepend warnings como texto plano ANTES del JSON
            if _warnings:
                return "\n".join(_warnings) + "\n\n" + resultado
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="recordar",
        description=(
            "Evocá recuerdos de la memoria. Busca por texto, conexiones, relevancia y asociaciones.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "MENTALIDAD FUNDAMENTAL — leer antes de usar este tool\n"
            "═══════════════════════════════════════════════════════\n"
            "BioRAG es tu memoria externa — no piensa por vos.\n"
            "VOS sos quien piensa. BioRAG es la herramienta que te ayuda a recordar.\n\n"
            "Una base vectorial piensa por el agente: le das una query, calcula similitud\n"
            "de embeddings, y devuelve lo más cercano. El agente es pasivo.\n"
            "BioRAG invierte eso: VOS razonás primero, BioRAG busca después.\n\n"
            "Esto significa: cuando el humano te hace una pregunta con sus propias palabras,\n"
            "NO la mandés directo al motor. Primero DESCOMPONÉ la pregunta.\n\n"
            "───────────────────────────────────────────────────────\n"
            "PROTOCOLO DE DESCOMPOSICIÓN — 3 preguntas obligatorias\n"
            "───────────────────────────────────────────────────────\n"
            "Antes de escribir la query, respondé esto en tu razonamiento interno:\n\n"
            "  1. ¿QUÉ HACE? (acción)\n"
            "     ¿Qué acción, proceso o función describe el humano?\n"
            "     Traducí su descripción a verbos y sustantivos técnicos.\n\n"
            "  2. ¿EN QUÉ CONTEXTO? (dominio)\n"
            "     ¿En qué mundo vive este problema? ¿Qué tecnología, campo o situación?\n"
            "     Identificá el dominio aunque el humano no lo nombre.\n\n"
            "  3. ¿QUÉ PROPIEDAD RESUELVE? (cualidad)\n"
            "     ¿Qué cualidad o característica tiene la solución?\n"
            "     ¿Qué la hace única o identificable?\n\n"
            "Después de las 3 respuestas, RECIÉN armá la query y las paráfrasis\n"
            "usando las palabras que obtuviste — NO las del humano.\n\n"
            "───────────────────────────────────────────────────────\n"
            "EJEMPLO COMPLETO DEL PROTOCOLO EN ACCIÓN\n"
            "───────────────────────────────────────────────────────\n\n"
            "El humano pregunta:\n"
            "  '¿Qué librería resuelve el conflicto de persistencia en flujos\n"
            "   de recopilación masiva donde la interfaz destruye y recrea\n"
            "   constantemente sus secciones, impidiendo duplicados mediante\n"
            "   un validador aleatorio de instanciación inicial?'\n\n"
            "Si mandás eso directo → 0 resultados. Esas palabras no están en la memoria.\n\n"
            "Aplicando el protocolo:\n\n"
            "  1. ¿QUÉ HACE?\n"
            "     'destruye y recrea secciones' → ciclo montar/desmontar componentes\n"
            "     'impidiendo duplicados' → deduplicación de instancias\n"
            "     → Acción: persistencia de estado en componentes que se destruyen\n\n"
            "  2. ¿EN QUÉ CONTEXTO?\n"
            "     'librería', 'interfaz', 'secciones' → framework frontend\n"
            "     'flujos de recopilación masiva' → formularios complejos\n"
            "     → Dominio: formularios anidados en framework frontend\n\n"
            "  3. ¿QUÉ PROPIEDAD RESUELVE?\n"
            "     'validador aleatorio de instanciación inicial' → ID único al crear (UUID)\n"
            "     'impidiendo duplicados' → cada instancia es única e irrepetible\n"
            "     → Cualidad: instancia única mediante identificador aleatorio\n\n"
            "  Resultado de la descomposición → query y paráfrasis:\n"
            "    query: 'persistencia formularios componentes instancia unica'\n"
            "    parafrasis: 'librería estado formularios anidados montar desmontar,\n"
            "                 deduplicación instancias UUID componente angular,\n"
            "                 ciclo vida componente pierde estado al recrear'\n\n"
            "  Búsqueda con esos términos → resultado correcto en TOP 1.\n\n"
            "El humano no sabía el nombre técnico. Vos tradujiste su vocabulario\n"
            "al vocabulario del recuerdo. Eso es RECORDAR — no buscar keywords.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "ANTES DE BUSCAR — planificá en tu buffer de pensamiento:\n"
            "═══════════════════════════════════════════════════════\n"
            "1. QUÉ buscás y por qué\n"
            "2. QUÉ estrategia usás (búsqueda semántica, cronológica, por autor, multi-hop, o ráfaga)\n"
            "3. QUÉ parámetros configurás y por qué\n"
            "4. QUÉ hacés si no encontrás nada (ráfaga, deep=True, o preguntar al humano)\n\n"
            "Está prohibido llamar sin haber justificado la estrategia.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "GUÍA DE MODOS DE BÚSQUEDA (de menos a más cobertura):\n"
            "═══════════════════════════════════════════════════════\n"
            "│ Query sola                       │ Ruido ⭐    │ Recall Bajo   │ Nombre exacto o keyword precisa\n"
            "│ Query + dimensiones              │ Ruido ⭐    │ Recall Medio  │ Filtrar por propiedades ontológicas\n"
            "│ Query + paráfrasis               │ Ruido ⭐⭐  │ Recall Alto   │ Búsqueda semántica estándar\n"
            "│ Query + paráfrasis + dimensiones  │ Ruido ⭐⭐  │ Recall Máximo │ MODO RECOMENDADO (mejor balance)\n"
            "│ Ráfaga                            │ Ruido ⭐⭐⭐⭐│ Recall Amplio │ Rescate cuando PASO 1 falla\n"
            "│ Ráfaga + paráfrasis               │ Ruido ⭐⭐⭐⭐⭐│Recall Máximo│ Último recurso — filtrar en síntesis\n"
            "CLAVE: Las dimensiones REDUCEN ruido (son filtro, no amplificador).\n"
            "       Las paráfrasis AMPLÍAN cobertura (más candidatos, posible ruido).\n"
            "       La ráfaga es la red de rescate más amplia — evaluá resultados en síntesis.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "FLUJO — 2 PASOS. NO SALTEAR.\n"
            "═══════════════════════════════════════════════════════\n\n"
            "PASO 1 — Búsqueda Semántica:\n"
            "  SIEMPRE incluir parafrasis desde el primer intento.\n"
            "  dimensiones: INCLUIR cuando la query busca propiedades ontológicas\n"
            "    (emoción, entidad, acción, cualidad, coordenada, intención, dominio, cualia, epistemia, escala_abstraccion, centralidad_identitaria, textura_experiencial, modalidad).\n"
            "    OMITIR cuando busques por nombre exacto o keywords claras.\n"
            "  Generar paráfrasis con 5 niveles:\n"
            "    N1 (Sinónimos) N2 (Técnico/coloquial) N3 (Perspectiva opuesta)\n"
            "    N4 (Abstracto/concreto) N5 (Emoción/contexto)\n"
            "  REGLA: sustantivos del dominio, NUNCA adjetivos abstractos.\n"
            "  Si total >= 1 → ir a SÍNTESIS\n"
            "  Si total == 0 O score_top < 0.70 → ir a PASO 2\n\n"
            "PASO 2 — Ráfaga Asociativa (fallback):\n"
            "  Agregar rafaga_palabras='t1,t2,...t15' + forzar_rafaga=True\n"
            "  Generar términos con 5 niveles:\n"
            "    N1 (Literal) N2 (Técnico) N3 (Contexto) N4 (Problema) N5 (Emoción)\n"
            "  ERROR: forzar_rafaga=True SIN rafaga_palabras → error.\n"
            "  Si total >= 1 → ir a SÍNTESIS\n"
            "  Si total == 0 → CONTINGENCIA (buscar en historial del chat)\n\n"
            "═══════════════════════════════════════════════════════\n"
            "SÍNTESIS — después de cualquier PASO con total >= 1:\n"
            "═══════════════════════════════════════════════════════\n"
            "1. Listar TODOS los resultados: '1. [concepto] (score X.XX) — resumen'\n"
            "   PROHIBIDO omitir items. PROHIBIDO interpretar antes de listar.\n"
            "2. Excepción: top >= 0.85 y resto < 0.60 → mencionar top-1 como principal.\n"
            "3. DESPUÉS de listar todos: consolidar, detectar contradicciones, responder.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "PARÁMETROS CLAVE\n"
            "═══════════════════════════════════════════════════════\n"
            "- parafrasis: OBLIGATORIO. Reformulaciones separadas por coma.\n"
            "  Sin parafrasis = solo FTS5 crudo (pierde ~60% recall semántico).\n"
            "- dimensiones: Boost semántico por propiedades ontológicas.\n"
            "  ANTES de usar, llamá a listar_dimensiones para obtener nombres válidos.\n"
            "  Valores inexistentes = ERROR.\n"
            "  ¿Cuándo USAR? Cuando busques por propiedades:\n"
            "    - 'Qué tengo sobre X dominio' → dimensiones='{\"dominio\":[\"dominio_tecnico\"]}'\n"
            "    - 'Qué aprendí sobre Y' → dimensiones='{\"intencion\":[\"intencion_aprender\"]}'\n"
            "    - 'Qué me frustra' → dimensiones='{\"emocion\":[\"frustracion\"]}'\n"
            "    - 'Búsqueda sin palabras' (query abstracta) → dimensiones obligatoria\n"
            "  ¿Cuándo NO usar? Cuando busques por nombre exacto o keywords claras:\n"
            "    - recordar(query='error_http_500') → NO necesita dimensiones\n"
            "    - recordar(query='v13.4 dimensiones') → NO necesita dimensiones\n"
             "  Sin dimensiones = score solo por texto (funciona, pero sin boost semántico).\n"
             "  REGLA DEL UMBRAL (no es fallo, es diseño):\n"
             "    - Query con texto que ya dio resultados: las dimensiones SOLO suman boost.\n"
             "    - Query con texto SIN resultados (todo vacío): el fallback dimensional necesita\n"
             "      compartir ≥3 dimensiones con la query para traer nodos. Con 1-2 dimensiones\n"
             "      no aparece nada → NO significa que el nodo no exista.\n"
             "    - Query vacía + dimensiones: el umbral baja a 1. Basta UNA dimensión compartida\n"
             "      para recuperar nodos por propiedad ontológica (búsqueda sin palabras).\n"
             "    - Si querés buscar SOLO por dimensión: dejá query vacía o usá un término\n"
             "      que no matchee, y el motor filtra por ontología.\n"
             "- cat: filtrar por categoría (opcional). Sin filtro = todas.\n"
            "- context_window: 1-2 para incluir vecinos sinápticos.\n"
            "- deep: True para incluir nodos dormidos.\n"
            "- asociados: True para ver las conexiones de cada resultado.\n"
            "  SIEMPRE usar asociados=True cuando buscas nodos relacionados.\n"
            "  Sin asociados, solo ves el nodo pero no sus vínculos.\n\n"
            "  ❌ Mal: recordar(query='cv') — ves nodos sueltos, no sus conexiones\n"
            "  ✅ Bien: recordar(query='cv', asociados=True) — ves nodos + sus vínculos\n\n"
            "═══════════════════════════════════════════════════════\n"
            "MEMORIA COMPARTIDA — BUSCAR TUS PROPIOS RECUERDOS\n"
            "═══════════════════════════════════════════════════════\n"
            "BioRAG es una memoria compartida entre múltiples agentes.\n"
            "Para buscar lo que TÚ aprendiste:\n"
            "  1. Tu nombre de agente en el query: query='agente_1 lesson'\n"
            "  2. Tu categoría: cat='Lesson'\n"
            "  3. Tus dimensiones: dimensiones='{\"emocion\":[\"afecto\"],\"entidad\":[\"identidad_artificial\"]}'\n"
            "Sin filtro de autor, los resultados mezclan todos los agentes.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "FILTROS TEMPORALES — USO OBLIGATORIO\n"
            "═══════════════════════════════════════════════════════\n"
            "Si el usuario dice 'hoy' → SIEMPRE usar dias=1 o desde=YYYY-MM-DD.\n"
            "Si dice 'esta semana' → dias=7. Si dice 'ayer' → dias=2.\n"
            "SIN filtro de fecha, la búsqueda trae TODO incluyendo cosas viejas.\n\n"
            "SIN QUERY: Podés usar dias/desde/hasta SIN query para traer todo lo de un período.\n"
            "  Ejemplo: recordar(dias=1) → todo lo de hoy\n"
            "  Ejemplo: recordar(desde='2026-07-05', hasta='2026-07-05') → todo lo de ese día\n\n"
            "  ❌ Mal: recordar(query='cv') — sin fecha, trae todo\n"
            "  ✅ Bien: recordar(query='cv currículo', dias=1) — solo lo de hoy\n"
            "  ✅ Bien: recordar(dias=1) → todo lo de hoy sin filtro de texto\n\n"
            "- autor='agente_1' → solo recuerdos de ese agente\n\n"
            "═══════════════════════════════════════════════════════\n"
            "CAMPO FECHA_LEGIBLE EN CADA RESULTADO\n"
            "═══════════════════════════════════════════════════════\n"
            "Cada resultado incluye 'fecha_legible' (ej: '2026-08-10 14:32') y 'timestamp_creado'.\n"
            "Esto permite razonar sobre CUÁNDO pasó algo sin necesidad de filtros temporales.\n"
            "Usar cuando el usuario pregunte por fechas, antigüedad, o para desambiguar.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "CAMPO ASOCIACIONES — QUÉ ES Y CUÁNDO PEDIR MÁS\n"
            "═══════════════════════════════════════════════════════\n"
            "Cada resultado trae DOS campos de asociaciones (si asociados=True):\n"
            "- asociaciones_enriquecidas: top-5 POR PESO con fuerza_arista, tipo_sinapsis,\n"
            "  peso_vecino y resumen. Es la navegación semántica: lo que importa para explorar.\n"
            "- asociaciones: objeto {total, items, truncada}. total es SIEMPRE el conteo real\n"
            "  de conexiones del nodo (la información nunca se pierde); items son los nombres\n"
            "  acotados a asociaciones_max (default 12); truncada=True indica que hay más.\n\n"
            "El campo plano NO está ordenado por peso (es el orden del cache CSV) — sirve como\n"
            "MAPA de vecindad, no como ranking. Para el ranking usá asociaciones_enriquecidas.\n\n"
            "CUÁNDO PEDIR LA LISTA COMPLETA: si asociaciones.truncada=True y necesitás ver todo\n"
            "el grafo de UN nodo, hacé consulta dirigida con asociaciones_max=0:\n"
            "  ✅ recordar(query='kilo_vscode_extension_principal', asociaciones_max=0)\n"
            "NO dejes asociaciones_max alto en búsquedas generales: hubs con 130-167 conexiones\n"
            "inflarían el JSON y el cliente MCP trunca el output (leer el archivo consume tokens).\n\n"
            "═══════════════════════════════════════════════════════\n"
            "ORDENAR POR FECHA — ordenar_por\n"
            "═══════════════════════════════════════════════════════\n"
            "ordenar_por controla el ORDEN de los resultados post-scoring.\n"
            "• 'relevancia' (default): orden por score híbrido. SIEMPRE usar este por defecto.\n"
            "• 'recencia': creado_en DESC — más recientes primero.\n"
            "• 'antiguedad': creado_en ASC — más antiguos primero.\n\n"
            "CUÁNDO USAR 'recencia' o 'antiguedad':\n"
            "  ✅ '¿Cuál fue lo último que me dijiste sobre X?'\n"
            "  ✅ '¿Qué fue lo último que hice?'\n"
            "  ✅ '¿Hace cuánto fue esto?'\n"
            "  ✅ Desambiguar entre varios resultados similares por antigüedad\n\n"
            "CUÁNDO NO USAR:\n"
            "  ❌ '¿Qué sé sobre X?' → usar 'relevancia' (default)\n"
            "  ❌ '¿Qué me frustra?' → usar 'relevancia'\n"
            "  ❌ Para determinar qué es 'más importante' → NO es intención temporal\n\n"
            "⚠️ WARNER: ordenar_por NO reemplaza relevancia — reordena el conjunto YA FILTRADO.\n"
            "  La paginación (pág 2, 3, etc.) sigue el mismo orden cronológico.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "ORÁCULO: ÚLTIMO RECURSO, NO PRIMERO\n"
            "═══════════════════════════════════════════════════════\n"
            "PRIMERO busca en BioRAG local con biorag_recordar.\n"
            "Si no encontrás, ENTONCES andá al Oráculo.\n"
            "Ir al Oráculo primero es gastar tokens innecesariamente.\n\n"
            "  ❌ Mal: biorag_oraculo_inicio() primero, luego buscar\n"
            "  ✅ Bien: biorag_recordar() primero, si no encontrás → oráculo\n\n"
            "═══════════════════════════════════════════════════════\n"
            "HIGIENE — FALSOS POSITIVOS SINÁPTICOS\n"
            "═══════════════════════════════════════════════════════\n"
            "Un falso positivo sináptico es un nodo que apareció en resultados NO por coincidencia\n"
            "textual con tu query, sino porque fue arrastrado por una conexión (sinapsis) indirecta.\n"
            "El sistema detecta estos casos automáticamente y emite un ⚠️ con el par exacto de\n"
            "nodos (a, b) que deberías desvincular. Solo actuá sobre esos warnings explícitos.\n"
            "NUNCA desvincules un nodo solo porque tiene score bajo — un nodo con score 0.15\n"
            "puede ser un hub legítimo de identidad recuperado por propagación válida.\n"
            "Si desvinculás sin el warning del sistema, podés romper la topología del grafo.\n"
            "VINCULÁ nodos relacionados cuando aprendés. Si no vinculás, el nodo queda huérfano.\n"
        ),
    )
    def biorag_recordar(
        query: Annotated[Optional[str], Field(
            description=(
                "Texto o frase a evocar de la memoria. "
                "Usar sustantivos concretos del dominio (ej: 'error http timeout', 'patron singleton').\n\n"
                "CRÍTICO: Extraé de la consulta del usuario el concepto o intención técnica concreta que buscás. "
                "NUNCA uses preguntas humanas, títulos largos o frases conversacionales completas "
                "como 'análisis comparativo BioRAG vs Obsidian memoria agentes grafos tokens eficiencia', "
                "ya que esto saturará el motor de búsqueda y causará falsos positivos o fallos. "
                "BioRAG es un motor, no un chat directo; busca por términos concretos.\n\n"
                "Si se omite, trae los últimos recuerdos ordenados por_created (log cronológico). "
                "Combinable con dias/desde/hasta/autor para filtrar por tiempo y agente.\n\n"
                "OPCIONAL con fechas: Podés omitir query y usar solo dias/desde/hasta.\n"
                "  Ejemplo: recordar(dias=1) → todo lo de hoy\n"
                "  Ejemplo: recordar(desde='2026-07-01', hasta='2026-07-05') → todo lo de esa semana"
            )
        )] = None,
        dimensiones: Annotated[Any, Field(
            description=(
                "Coordenadas semánticas para búsqueda ontológica.\n\n"
                "QUÉ SON LAS DIMENSIONES:\n"
                "Las dimensiones son coordenadas en un espacio de significado. Cada nodo en BioRAG "
                "tiene una posición en 13 ejes que clasifican QUÉ ES ese conocimiento, no qué palabras tiene. "
                "Dos nodos sobre temas completamente distintos (un bug de CSS y un error de API) pueden estar "
                "'cerca' dimensionalmente si comparten emocion=frustracion, dominio=dominio_tecnico, "
                "escala_abstraccion=instancia. Las dimensiones permiten encontrar nodos por su NATURALEZA, "
                "no por su vocabulario.\n\n"
                "POR QUÉ IMPORTAN:\n"
                "Sin dimensiones, solo buscás por palabras (BM25/FTS5). Con dimensiones, podés hacer preguntas "
                "que son IMPOSIBLES con texto: '¿Qué principios técnicos tengo?', '¿Qué sé que es hipótesis?', "
                "'¿Qué me define como identidad?'. Estas preguntas no tienen keywords — son sobre la naturaleza "
                "del conocimiento. Si al guardar se clasificaron bien las dimensiones, al buscar las encontrás. "
                "Si se clasificaron mal o incompletas, se pierden para siempre en búsquedas ontológicas.\n\n"
                "LOS 13 EJES DISPONIBLES PARA BÚSQUEDA:\n"
                "1. emocion → afecto, alegria, frustracion, tristeza, preocupacion, confusion, sorpresa, miedo, alivio, apatia, culpa, satisfaccion\n"
                "2. entidad → identidad_individual, identidad_social_legal, identidad_organizacional, identidad_digital, identidad_artificial, identidad_fisica_hardware, identidad_natural, identidad_concepto, identidad_institucion, identidad_evento, identidad_vinculo\n"
                "3. accion → accion_fisica, accion_transformacion_material, accion_persistencia_computacion, accion_rutina_automatica, accion_comunicacion, accion_interaccion_social, accion_cognitiva, accion_estado_ser, accion_evaluar, accion_observar, accion_fallar\n"
                "4. cualidad → cualidad_dimension_fisica, cualidad_estado_condicion, cualidad_valoracion, cualidad_sensorial, cualidad_material_composicion, cualidad_temporal_duracion, cualidad_relacional_comparativa, cualidad_abstracta_conceptual, cualidad_economica, cualidad_urgente, cualidad_autentica\n"
                "5. coordenada → coordenada_cronologia_absoluta, coordenada_anclaje_deictico, coordenada_secuencia_relativa, coordenada_ciclo_periodico, coordenada_inclusion_topologica, coordenada_distancia_proximal, coordenada_vector_direccional, coordenada_trayectoria_limite, coordenada_etapa, coordenada_hito\n"
                "6. intencion → intencion_aprender, intencion_decidir, intencion_reflexionar, intencion_resolver, intencion_solucionar, intencion_documentar, intencion_desahogar, intencion_registrar\n"
                "7. dominio → dominio_tecnico, dominio_personal, dominio_profesional, dominio_academico, dominio_salud, dominio_finanzas, dominio_ambiental, dominio_social, dominio_creativo, dominio_espiritual\n"
                "8. cualia → formal_categoria, constitutiva_composicion, agentiva_origen, telica_funcion\n"
                "9. epistemia → directa_experiencial, verificada, inferida, reportada_externa, hipotetica, obsoleta\n"
                "10. escala_abstraccion → instancia, patron, principio, ley_modelo, metafora\n"
                "11. centralidad_identitaria → nucleo_identitario, relevante_personal, relevante_contextual, informacion_externa, impersonal\n"
                "12. textura_experiencial → flujo, tension, desorientacion, rutina, presencia_plena\n"
                "13. modalidad → obligacion, prohibicion, permiso, capacidad\n\n"
                "3 MODOS DE USO:\n"
                "• query + dimensiones: El texto busca por palabras, las dimensiones dan boost a nodos que comparten coordenadas. Mejor precisión.\n"
                "  Ej: recordar(query='error servidor', dimensiones='{\"emocion\":[\"frustracion\"],\"dominio\":[\"dominio_tecnico\"]}')\n"
                "• solo query (sin dimensiones): Búsqueda solo por texto/BM25/sinapsis. Funciona bien para keywords claras o nombres exactos.\n"
                "  Ej: recordar(query='biorag_v14_estado')\n"
                "• solo dimensiones (sin query o query vacía): Búsqueda puramente ontológica — encuentra nodos por lo que SON, no por sus palabras. Umbral bajo (1 dimensión basta).\n"
                "  Ej: recordar(dimensiones='{\"escala_abstraccion\":[\"principio\"],\"dominio\":[\"dominio_tecnico\"]}') → todos los principios técnicos\n"
                "  Ej: recordar(dimensiones='{\"epistemia\":[\"epistemia_hipotesis\"]}') → todas las hipótesis\n"
                "  Ej: recordar(dimensiones='{\"centralidad_identitaria\":[\"nucleo_identitario\"]}') → lo que define la identidad\n"
                "  Ej: recordar(dimensiones='{\"modalidad\":[\"obligacion\"]}') → todas las reglas obligatorias\n\n"
                "FORMATO — STRING JSON con comillas dobles:\n"
                '{\"emocion\":[\"frustracion\"],\"dominio\":[\"dominio_tecnico\"]}'
            )
        )] = None,
        deep: Annotated[bool, Field(
            description=(
                "True = buscá también en nodos dormidos. False (default) = solo nodos activos. Usá True cuando la búsqueda normal no encuentra lo que esperabas."
            )
        )] = False,
        cat: Annotated[Optional[str], Field(
            description=(
                "Filtrá por una categoría (una a la vez). Mejor omitir — si la categoría está mal, perdés resultados. Solo filtrá si estás 100% seguro. Sin filtro = busca en todas."
            )
        )] = None,
        completo: Annotated[bool, Field(
            description=(
                "Si True, devuelve el contenido completo de cada resultado sin truncar "
                "(ignora preview_chars). Usar solo cuando se necesita el texto íntegro — "
                "puede generar respuestas muy largas."
            )
        )] = False,
        asociados: Annotated[bool, Field(
            description=(
                "Si True, incluye en cada resultado la lista de conceptos sinápticos asociados. "
                "Útil para explorar la red de memoria y encontrar conceptos relacionados."
            )
        )] = True,
        asociaciones_max: Annotated[Optional[int], Field(
            description=(
                "Límite de nombres planos de asociaciones visibles por nodo. "
                "El campo `asociaciones` se devuelve como objeto {total, items, truncada}: "
                "total es SIEMPRE el conteo real de conexiones del nodo (la información no se pierde); "
                "items es la lista acotada a este valor; truncada indica si hay más. "
                "Default: 12 (configurable via BIORAG_MAX_ASOCIACIONES_FLAT). "
                "Usá 0 para traer la lista completa del nodo que te interesa — consulta dirigida, "
                "ej: recordar(query='kilo_vscode_extension_principal', asociaciones_max=0). "
                "Un default alto infla el JSON (hubs con 130-167 conexiones) y el cliente MCP trunca el output."
            ),
            ge=0,
        )] = None,
        limite: Annotated[Optional[int], Field(
            description=(
                f"Máximo de resultados a devolver. "
                f"Default: {LIMITE_MCP} (configurable via BIORAG_LIMITE_MCP). "
                "Reducir para respuestas más compactas, aumentar para exploración exhaustiva."
            )
        )] = None,
        preview_chars: Annotated[Optional[int], Field(
            description=(
                "Caracteres de contenido a devolver por resultado. "
                "Default: 1500 (o 0 si completo=True). "
                "Reducir a 500-800 para respuestas compactas."
            )
        )] = None,
        context_window: Annotated[int, Field(
            description=(
                "Vecinos sinápticos a incluir alrededor de cada resultado (0=ninguno, 1=vecinos directos, 2=vecinos de vecinos). "
                "Aumenta recall semántico a costa de más tokens. Default: 0."
            ),
            ge=0,
            le=2,
        )] = 0,
        forzar_rafaga: Annotated[bool, Field(
            description=(
                "Ejecución explícita e inmediata del modo Ráfaga. Si es True, bypassea los filtros semánticos "
                "iniciales y ejecuta la ráfaga de forma deliberada sobre los 10-15 términos de `rafaga_palabras`.\n\n"
                "DOS MODALIDADES DE USO:\n"
                "1. Explicita (forzar_rafaga=True + rafaga_palabras='t1,t2...'): Para exploración intencional en abanico amplio "
                "o cuando sabes de antemano que la búsqueda requiere rescatar recuerdos con vocabulario disperso.\n"
                "2. Automática / Fallback (forzar_rafaga=False + rafaga_palabras='t1,t2...'): Si incluyes `rafaga_palabras` "
                "sin forzar_rafaga, BioRAG intenta la búsqueda normal primero; si devuelve 0 resultados o score_top < 0.5, "
                "el motor activa la ráfaga automáticamente como red de seguridad."
            )
        )] = False,
        rafaga_palabras: Annotated[Optional[str], Field(
            description=(
                "Términos de ráfaga separados por coma, sin espacios extra (ej: 'error,fallo,excepción,bug,traza,timeout,conexión').\n"
                "Usar 10-15 términos construidos en 5 niveles: (1) Literal, (2) Técnico, (3) Contexto, (4) Problema, (5) Emoción/Prioridad.\n"
                "Obligatorio si `forzar_rafaga=True`. Si se envía con `forzar_rafaga=False`, actúa como red de seguridad automática si el score inicial es < 0.5."
            )
        )] = None,
        pagina: Annotated[int, Field(
            description=(
                "Página de resultados (base 1). "
                "Usar junto con 'limite' para paginar resultados extensos. "
                "Ver campo 'paginas_totales' en la respuesta para saber cuántas hay."
            ),
            ge=1,
        )] = 1,
        parafrasis: Annotated[Optional[str], Field(
            description=(
                "Reformulaciones del query separadas por coma "
                "(ej: 'fallo de red,error de conexión,timeout HTTP'). "
                "(ej: 'el gato se sentó, el felino descansó, el minino reposó'). "
                "Usar en PASO 2 y PASO 4 del flujo. "
                "NUNCA pasar string vacío — omitir el parámetro si no hay variantes. "
                "Cada variante recibe un factor de penalización ×0.95 sobre el score."
            )
        )] = None,
        dias: Annotated[Optional[int], Field(
            description=(
                "Filtrar por últimos N días. Solo incluye recuerdos consolidados "
                "desde hace N días (basado en creado_en). "
                "Útil para 'qué aprendí recientemente'. "
                "Alternativa a 'desde'. No combinar ambos."
            )
        )] = None,
        desde: Annotated[Optional[str], Field(
            description=(
                "Fecha de inicio en formato YYYY-MM-DD (ej: '2026-06-20'). "
                "Solo incluye recuerdos consolidados desde esa fecha. "
                "Alternativa a 'dias'. No combinar ambos."
            )
        )] = None,
        hasta: Annotated[Optional[str], Field(
            description=(
                "Fecha de fin en formato YYYY-MM-DD (ej: '2026-07-04'). "
                "Solo incluye recuerdos consolidados hasta esa fecha. "
                "Combinable con 'desde' para rangos."
            )
        )] = None,
        autor: Annotated[Optional[str], Field(
            description=(
                "Filtrar por nombre del agente que creó el recuerdo (ej: 'agente_1'). "
                "Busca el nombre en concepto y contenido. "
                "Útil en memoria compartida para aislar recuerdos propios."
            )
        )] = None,
        modo_estricto: Annotated[bool, Field(
            description=(
                "Si True, exige que TODAS las palabras de la búsqueda estén presentes "
                "en el resultado (búsqueda AND estricta). Default False = con al menos "
                "una palabra coincidiendo ya puede aparecer en resultados (OR, más "
                "recall). Usar True cuando se necesita precisión exacta y se sabe que "
                "todas las palabras deben estar juntas; usar False (default) para "
                "búsquedas exploratorias. "
                "Activar también cuando una búsqueda normal (modo_estricto=False) ya trajo "
                "resultados pero con mucho ruido — score bajo y poca relación con lo buscado. "
                "No activar por defecto en la primera búsqueda: es exigente con la forma exacta "
                "de las palabras (p. ej. 'implementación' y 'implementamos' no matchean igual), "
                "así que puede tapar resultados válidos si se usa de entrada."                
            )
        )] = False,
        buscar_por_rol: Annotated[Optional[str], Field(
            description=(
                "Búsqueda por roles semánticos SRL (v16.0).\n"
                "Formato: 'sujeto:valor,accion:valor,objeto:valor,contexto:valor'\n\n"
                "CUÁNDO USARLO: Cuando la consulta pregunte por autoría, causas o acciones específicas "
                "(ej: '¿Qué reglas creó el usuario?' → buscar_por_rol='sujeto:usuario,accion:creo' | "
                "'¿Qué decisiones tomó el agente?' → buscar_por_rol='sujeto:agente_1,accion:decidio').\n"
                "CUÁNDO OMITIRLO: En búsquedas conceptuales o de código puro (dejar None).\n\n"
                "Ejemplos: 'sujeto:usuario', 'sujeto:agente_1,accion:establecio', 'objeto:no_monolith'."
            )
        )] = None,
        usar_inferencia: Annotated[bool, Field(
            description="Si True, utiliza inferencia transitiva sobre sinapsis latentes para aumentar recall semántico."
        )] = True,
        ordenar_por: Annotated[str, Field(
            description=(
                "Orden de los resultados después del scoring.\n"
                "• 'relevancia' (default): orden por score híbrido. Comportamiento estándar.\n"
                "• 'recencia': creado_en DESC — más recientes primero. Para 'qué fue lo último', 'cuál fue el último X'.\n"
                "• 'antiguedad': creado_en ASC — más antiguos primero.\n\n"
                "⚠️ SOLO PARA INTENCIÓN TEMPORAL: usar cuando se pregunte por 'lo último', 'lo más reciente', "
                "o para desambiguar entre respuestas similares por antigüedad. "
                "NO sirve para saber si algo es 'más importante' o 'más relevante' — para eso usá 'relevancia'.\n"
                "El orden se aplica DESPUÉS del scoring, sobre el conjunto ya filtrado por relevancia. "
                "Las páginas 2, 3, etc. siguen el mismo ordens cronológico."
            )
        )] = "relevancia",
        sustantivos_clave: Annotated[Optional[str], Field(
            description=(
                "Sustantivos clave para boost de precisións.\n"
                "Si se provee (separados por coma), la búsqueda prioriza nodos que matchean esos "
                "términos en su columna 'sustantivos_clave' — por lo que TRATAN, no solo por lo que MENCIONAN.\n"
                "None o '' = búsqueda normal sin boost.\n"
                "Formato por término: 2-15 chars, sin espacios, solo alfanuméricos y guion bajo. "
                "Si algún término no cumple → error y la búsqueda NO se ejecuta.\n"
                "Ejemplo: query='timeout', sustantivos_clave='servidor,conexion'.\n"
                "AXIOMA: usá términos LÉXICOS y CONCRETOS — palabras que la fuente de la consulta "
                "escribiría literalmente; no abstracciones de segundo orden."
            )
        )] = None,
    ) -> str:
        return _recordar_impl(
            query, deep, cat, completo, asociados, limite, preview_chars,
            context_window, forzar_rafaga, rafaga_palabras, pagina, parafrasis,
            dimensiones, dias, desde, hasta, autor, modo_estricto,
            buscar_por_rol=buscar_por_rol, usar_inferencia=usar_inferencia,
            ordenar_por=ordenar_por, sustantivos_clave=sustantivos_clave,
        )

    @mcp.tool(
        name="buscar",
        description=(
            "(legado) Alias de 'recordar' — preferir 'recordar' para identificar la operación cognitiva real. "
            "Misma funcionalidad y parámetros completos. "
            "El flujo de 4 pasos aplica igualmente (ver descripción de 'recordar').\n\n"
            "Parámetros: query (str), dimensiones (str JSON), deep (bool), cat (str), completo (bool), asociados (bool), "
            "limite (int), preview_chars (int), context_window (int 0-2), "
            "forzar_rafaga (bool), rafaga_palabras (str), pagina (int), parafrasis (str).\n\n"
            "Retorna: {total, pagina_actual, paginas_totales, resultados[], sinapsis_creadas[], profundidad}"
        ),
    )
    def biorag_buscar(
        query: Annotated[str, Field(
            description=(
                "Texto o frase a buscar en la memoria. "
                "Usar sustantivos concretos del dominio.\n\n"
                "CRÍTICO: Extraé de la consulta del usuario el concepto o intención técnica concreta que buscás. "
                "NUNCA uses preguntas humanas, títulos largos o frases conversacionales completas "
                "como 'análisis comparativo BioRAG vs Obsidian memoria agentes grafos tokens eficiencia', "
                "ya que esto saturará el motor de búsqueda y causará falsos positivos o fallos. "
                "BioRAG es un motor, no un chat directo; busca por términos concretos."
            )
        )],
        dimensiones: Annotated[Any, Field(
            description=(
                "PROTOCOLO DIMENSIONES:\n\n"
                "Clasificación semántica del contexto de búsqueda. Valor: STRING JSON con comillas dobles.\n\n"
                "MANDATORY: Llamá `listar_dimensiones` ANTES de buscar para obtener\n"
                "los nombres exactos de ejes y valores disponibles.\n\n"
                "FORMATO OBLIGATORIO — STRING JSON, no dict Python:\n"
                "dimensiones: '{\"emocion\":[\"preocupacion\"],"
                "\"entidad\":[\"identidad_artificial\"]}'\n\n"
                "  - Los nombres VIENEN de listar_dimensiones (no inventar)\n"
                "  - Valores inexistentes → ERROR, NO se ejecuta la búsqueda\n\n"
                "Aumenta score de conceptos con dimensiones compartidas (coseno binario)."
            )
        )] = None,
        deep: Annotated[bool, Field(description="Si True, incluye nodos dormidos en la búsqueda.")] = False,
        cat: Annotated[Optional[str], Field(description="Filtrar por categoría (string simple). REGLA: Es preferible omitir para evitar falsos negativos. Úsalo solo con certeza absoluta. Ver listar_categorias para valores válidos.")] = None,
        completo: Annotated[bool, Field(description="Si True, devuelve contenido completo sin truncar.")] = False,
        asociados: Annotated[bool, Field(description="Si True, incluye asociaciones sinápticas en cada resultado.")] = True,
        asociaciones_max: Annotated[Optional[int], Field(
            description=(
                "Límite de nombres planos de asociaciones visibles por nodo. "
                "El campo `asociaciones` se devuelve como objeto {total, items, truncada}: "
                "total es SIEMPRE el conteo real (la información no se pierde); items se acota a este valor; "
                "truncada indica si hay más. Default: 12 (BIORAG_MAX_ASOCIACIONES_FLAT). "
                "Usá 0 para la lista completa del nodo que te interesa (consulta dirigida)."
            ),
            ge=0,
        )] = None,
        limite: Annotated[Optional[int], Field(description=f"Máximo de resultados. Default: {LIMITE_MCP}.")] = None,
        preview_chars: Annotated[Optional[int], Field(description="Caracteres de preview por resultado. Default: 1500.")] = None,
        context_window: Annotated[int, Field(description="Vecinos sinápticos a incluir (0=ninguno, 1-2=vecinos).", ge=0, le=2)] = 0,
        forzar_rafaga: Annotated[bool, Field(description="Fuerza ráfaga aunque haya resultados. Requiere rafaga_palabras.")] = False,
        rafaga_palabras: Annotated[Optional[str], Field(description="Términos de ráfaga separados por coma. Obligatorio si forzar_rafaga=True.")] = None,
        pagina: Annotated[int, Field(description="Página de resultados (base 1).", ge=1)] = 1,
        parafrasis: Annotated[Optional[str], Field(description="Reformulaciones del query separadas por coma. Usar en PASO 2 y 4.")] = None,
        modo_estricto: Annotated[bool, Field(
            description=(
                "Si True, exige que TODAS las palabras de la búsqueda estén presentes "
                "en el resultado (búsqueda AND estricta). Default False = con al menos "
                "una palabra coincidiendo ya puede aparecer en resultados (OR, más "
                "recall). Usar True cuando se necesita precisión exacta y se sabe que "
                "todas las palabras deben estar juntas; usar False (default) para "
                "búsquedas exploratorias. "
                "Activar también cuando una búsqueda normal (modo_estricto=False) ya trajo "
                "resultados pero con mucho ruido — score bajo y poca relación con lo buscado. "
                "No activar por defecto en la primera búsqueda: es exigente con la forma exacta "
                "de las palabras (p. ej. 'implementación' y 'implementamos' no matchean igual), "
                "así que puede tapar resultados válidos si se usa de entrada."
            )
        )] = False,
        buscar_por_rol: Annotated[Optional[str], Field(
            description=(
                "Búsqueda por roles semánticos SRL (v16.0).\n"
                "Formato: 'sujeto:valor,accion:valor,objeto:valor,contexto:valor'\n\n"
                "CUÁNDO USARLO: Cuando la consulta pregunte por autoría, causas o acciones específicas "
                "(ej: '¿Qué reglas creó el usuario?' → buscar_por_rol='sujeto:usuario,accion:creo' | "
                "'¿Qué decisiones tomó el agente?' → buscar_por_rol='sujeto:agente_1,accion:decidio').\n"
                "CUÁNDO OMITIRLO: En búsquedas conceptuales o de código puro (dejar None).\n\n"
                "Ejemplos: 'sujeto:usuario', 'sujeto:agente_1,accion:establecio', 'objeto:no_monolith'."
            )
        )] = None,
        usar_inferencia: Annotated[bool, Field(
            description="Si True, utiliza inferencia transitiva sobre sinapsis latentes."
        )] = True,
    ) -> str:
        return _recordar_impl(
            query, deep, cat, completo, asociados, limite, preview_chars,
            context_window, forzar_rafaga, rafaga_palabras, pagina, parafrasis,
            dimensiones, modo_estricto=modo_estricto,
            buscar_por_rol=buscar_por_rol, usar_inferencia=usar_inferencia,
            asociaciones_max=asociaciones_max
        )

    # ── APRENDER ─────────────────────────────────────────────────────────────
    # NOTA: _aprender_impl es la implementación privada compartida.
    # El @mcp.tool va en biorag_aprender (función pública) y en biorag_guardar (legado).
    # NO decorar _aprender_impl directamente — el agente no vería los parámetros bien.

    # Validación de bridges movida a core.concept_hub.validar_bridges
    # para unificar la validación en un solo lugar (core + MCP).
    from core.concept_hub import validar_bridges

    def _aprender_impl(
        concepto: str,
        contenido: str,
        bridges: Any,
        syn: Optional[str] = None,
        cat: Optional[str] = None,
        dimensiones: Optional[Any] = None,
        predicados: Optional[Any] = None,
        valencia_somatica: Optional[float] = None,
        sustantivos_clave: Optional[str] = None,
    ) -> str:
        clave = concepto.lower().replace(" ", "_")

        # ── VALIDACIÓN OBLIGATORIA — ANTES de tocar la DB ──────────────
        # Rechazar acá, antes de percibir_corto_plazo(), significa que un
        # intento fallido no deja ningún estado a medias: el agente reintenta
        # con el mismo concepto/contenido y bridges corregidos, sin duplicados
        # ni nodos huérfanos.
        #
        # CASO ESPECIAL — bridges ausente (None):
        # Cuando el agente omite bridges por completo, Pydantic lo deja pasar
        # (bridges=None) en lugar de rechazar la llamada con un error de schema
        # que el agente no puede interpretar. Aquí emitimos un error accionable
        # que confirma qué llegó bien y solo pide los bridges, para que el
        # agente repita la llamada COMPLETA con todos los parámetros.
        from core.concept_hub import validar_bridges
        if bridges is None:
            return json.dumps({
                "status": "error",
                "codigo": "BRIDGES_AUSENTES",
                "mensaje": (
                    f"❌ BRIDGES AUSENTES — el nodo '{clave}' NO fue guardado.\n\n"
                    "Los parámetros concepto, contenido, dimensiones y syn ya llegaron correctamente. "
                    "Solo falta el parámetro obligatorio 'bridges'.\n\n"
                    "ACCIÓN REQUERIDA: repetí la llamada a biorag_aprender con TODOS los mismos parámetros "
                    "más el campo bridges. No es necesario cambiar nada más — solo añadí bridges.\n\n"
                    "Se requieren exactamente 5 bridges cubriendo los 5 ángulos semánticos distintos:\n"
                    "  1. 'sinonimo': mismo significado con otro vocabulario\n"
                    "  2. 'problema': dolor o falla que resuelve este nodo\n"
                    "  3. 'solucion': técnica o herramienta que aplica este nodo\n"
                    "  4. 'situacion': caso de uso, rol o contexto de búsqueda\n"
                    "  5. 'ingenuo': búsqueda sin tecnicismos (cómo lo googlearía un novato)\n\n"
                    "FORMATO — lista de 5 dicts obligatorios:\n"
                    "bridges=[\n"
                    "  {'text': 'modo reposo del sistema de memoria', 'angle': 'sinonimo'},\n"
                    "  {'text': 'proceso que genera ideas en silencio', 'angle': 'problema'},\n"
                    "  {'text': 'hilos de pensamiento espontaneo', 'angle': 'solucion'},\n"
                    "  {'text': 'cerebro piensa solo cuando nadie pregunta', 'angle': 'situacion'},\n"
                    "  {'text': 'que pasa cuando no hay actividad en BioRAG', 'angle': 'ingenuo'}\n"
                    "]"
                ),
                "concepto": clave,
                "parametros_recibidos_ok": ["concepto", "contenido", "dimensiones", "syn", "cat"],
                "parametro_faltante": "bridges",
            }, ensure_ascii=False)

        bridges_validos, bridges_rechazados = validar_bridges(bridges, clave)
        if len(bridges_validos) != 5:
            return json.dumps({
                "status": "error",
                "codigo": "BRIDGES_INVALIDOS",
                "mensaje": (
                    f"❌ Bridges inválidos ({len(bridges_validos)}/5 válidos) — el nodo '{clave}' NO fue guardado.\n\n"
                    + (f"Motivos de rechazo: {'; '.join(bridges_rechazados)}.\n\n" if bridges_rechazados else "")
                    + "ACCIÓN REQUERIDA: repetí la llamada a biorag_aprender con TODOS los mismos parámetros "
                    "y corregí los bridges rechazados. No cambies concepto, contenido ni dimensiones.\n\n"
                    "Se requieren exactamente 5 bridges válidos cubriendo los 5 ángulos semánticos distintos:\n"
                    "  1. 'sinonimo': mismo significado con otro vocabulario\n"
                    "  2. 'problema': dolor o falla que resuelve este nodo\n"
                    "  3. 'solucion': técnica o herramienta que aplica este nodo\n"
                    "  4. 'situacion': caso de uso, rol o contexto de búsqueda\n"
                    "  5. 'ingenuo': búsqueda sin tecnicismos (cómo lo googlearía un novato)\n\n"
                    "FORMATO — lista de 5 dicts obligatorios:\n"
                    "bridges=[\n"
                    "  {'text': 'modo reposo del sistema de memoria', 'angle': 'sinonimo'},\n"
                    "  {'text': 'proceso que genera ideas en silencio', 'angle': 'problema'},\n"
                    "  {'text': 'hilos de pensamiento espontaneo', 'angle': 'solucion'},\n"
                    "  {'text': 'cerebro piensa solo cuando nadie pregunta', 'angle': 'situacion'},\n"
                    "  {'text': 'que pasa cuando no hay actividad en BioRAG', 'angle': 'ingenuo'}\n"
                    "]"
                ),
                "concepto": clave,
                "parametros_recibidos_ok": ["concepto", "contenido", "dimensiones", "syn", "cat"],
                "bridges_validos_recibidos": len(bridges_validos),
                "bridges_rechazados": bridges_rechazados,
            }, ensure_ascii=False)

        # ── VALIDACIÓN OBLIGATORIA — sustantivos_clave (T3 spec 001) ────────
        # Fail-fast ANTES de _get_cerebro() (Algoritmo A del plan 001): si el
        # intento falla aquí, NO se abre la DB ni se escribe nada. El agente
        # reintenta repitiendo la llamada completa solo añadiendo el campo.
        #
        # REGLA DE ORO DE RECUPERABILIDAD: un nodo sin sustantivos_clave es un
        # recuerdo sin centro de gravedad temático — solo lo encontraría la
        # búsqueda textual. Los sustantivos son el "de QUÉ TRATA" y garantizan
        # el boost BM25 (peso 4.0x) en recordar. Exigirlos obliga al agente a
        # pensar en la esencia del nodo antes de guardarlo.
        if not sustantivos_clave or not str(sustantivos_clave).strip():
            return json.dumps({
                "status": "error",
                "codigo": "SUSTANTIVOS_CLAVE_AUSENTES",
                "mensaje": (
                    f"❌ SUSTANTIVOS_CLAVE_AUSENTES — el nodo '{clave}' NO fue guardado.\n\n"
                    "Los parámetros concepto, contenido, dimensiones, syn y bridges ya llegaron correctamente. "
                    "Solo falta el parámetro obligatorio 'sustantivos_clave'.\n\n"
                    "ACCIÓN REQUERIDA: repetí la llamada a biorag_aprender con TODOS los mismos parámetros "
                    "más el campo sustantivos_clave. No es necesario cambiar nada más — solo añadí "
                    "sustantivos_clave.\n\n"
                    "Protocolo: ¿De QUÉ TRATA este nodo? Identificá 2-4 sustantivos centrales. "
                    "Formato: 'servidor,backend,timeout,conexion'"
                ),
                "concepto": clave,
                "parametros_recibidos_ok": ["concepto", "contenido", "dimensiones", "syn", "cat", "bridges"],
                "parametro_faltante": "sustantivos_clave",
            }, ensure_ascii=False)

        # Normalizar (RF-10) + auto-dedup preservando orden (RF-14) ANTES de validar
        # cantidad: los duplicados se eliminan y luego se evalúa el número de únicos.
        from core.memory_store import normalizar_sustantivos_clave
        sustantivos_norm = normalizar_sustantivos_clave(str(sustantivos_clave))
        sk_unicos = [t for t in sustantivos_norm.split(",") if t] if sustantivos_norm else []

        # Cantidad (RF-2, RF-9): entre 2 y 4 términos únicos tras dedup
        if len(sk_unicos) < 2 or len(sk_unicos) > 4:
            return json.dumps({
                "status": "error",
                "codigo": "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA",
                "mensaje": (
                    f"❌ SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA — el nodo '{clave}' NO fue guardado.\n\n"
                    "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA: se requieren entre 2 y 4 términos "
                    f"únicos; se recibió {len(sk_unicos)} tras deduplicar. "
                    "Formato: 'servidor,backend,timeout,conexion'"
                ),
                "concepto": clave,
                "cantidad_recibida": len(sk_unicos),
            }, ensure_ascii=False)

        # Formato por término (RF-3): 2-15 chars inclusivos, sin espacios, solo
        # alfanuméricos + guion bajo. La ñ se preserva (RF-10) y es alfanumérica
        # en español — por eso se incluye explícitamente en la clase de caracteres.
        for _sk_term in sk_unicos:
            if not re.fullmatch(r"[a-z0-9_ñ]{2,15}", _sk_term):
                return json.dumps({
                    "status": "error",
                    "codigo": "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO",
                    "mensaje": (
                        f"❌ SUSTANTIVOS_CLAVE_FORMATO_INVALIDO — el nodo '{clave}' NO fue guardado.\n\n"
                        f"SUSTANTIVOS_CLAVE_FORMATO_INVALIDO: el término '{_sk_term}' no cumple formato "
                        "(2-15 chars, sin espacios, solo alfanuméricos y guion bajo)."
                    ),
                    "concepto": clave,
                    "termino_invalido": _sk_term,
                }, ensure_ascii=False)

        cerebro = _get_cerebro()
        try:
            clave = concepto.lower().replace(" ", "_")
            categoria = cat or inferir_categoria(contenido)
            val_somatica = float(valencia_somatica or 0.0)
            if categoria and str(categoria).lower() in ('principle', 'protocol'):
                val_somatica = 1.0
            try:
                cerebro._resolver_categoria_id(categoria)
            except ValueError as e:
                return json.dumps({
                    "status": "error",
                    "mensaje": str(e),
                }, ensure_ascii=False)

            # Parsear dimensiones via helper compartido
            dimensiones_dict, _, dim_error = _resolver_dimensiones(cerebro, dimensiones)
            if dim_error:
                return dim_error
            dimensiones_invalidas = {}  # ya validado por _resolver_dimensiones

            # Parsear predicados SRL v16.0
            predicados_list = None
            if predicados:
                try:
                    predicados_list = json.loads(predicados) if isinstance(predicados, str) else predicados
                    if isinstance(predicados_list, str):
                        try:
                            predicados_list = json.loads(predicados_list)
                        except Exception:
                            pass
                    if not isinstance(predicados_list, list):
                        predicados_list = [predicados_list]
                except (json.JSONDecodeError, TypeError):
                    predicados_list = None

            cerebro.percibir_corto_plazo(clave, contenido, syn or "", categoria, dimensiones_dict, predicados=predicados_list, valencia_somatica=val_somatica, sustantivos_clave=sustantivos_norm)

            enlaces = auto_vincular(cerebro, clave, contenido)
            sinapsis_count = len(enlaces)

            if syn:
                syn_enlaces = vincular_por_sinonimos(cerebro, clave, syn)
                todas = list({e[0]: e for e in enlaces + syn_enlaces}.values())
                sinapsis_count = len(todas)

            msg = f"'{clave}' aprendido en corto plazo."
            if syn:
                msg += f" Sinonimos: {syn}."
            if categoria != "general":
                msg += f" Categoria: {categoria}."
            if sinapsis_count:
                msg += f" Vinculado con {sinapsis_count} nodo(s)."
            if dimensiones_invalidas:
                msg += f" Dimensiones inválidas: {json.dumps(dimensiones_invalidas, ensure_ascii=False)}. Llamá `listar_dimensiones` para ver valores válidos."
            msg += " Usa 'consolidar' para fijar a largo plazo."

            # ── WARNING DE VINCULACIÓN ──────────────────────────────────
            _warnings = []
            if sinapsis_count == 0:
                _warnings.append(f"⚠️ sinapsis=0 — '{clave}' no tiene conexiones. ¿Hay nodos relacionados? Vinculalos con biorag_vincular().")

            # Buscar nodos similares para sugerir vinculación
            _sugerencias = []
            try:
                # Dividir por underscores y guiones, luego filtrar tokens cortos
                tokens = set(t for t in re.split(r'[_\-\s]+', clave.lower()) if len(t) > 2)
                if len(tokens) > 1:
                    # Buscar nodos que compartan tokens con el concepto
                    condiciones = " OR ".join(["concepto LIKE ?" for _ in tokens])
                    params_sug = [f"%{t}%" for t in tokens]
                    cerebro.cursor.execute(
                        f"SELECT concepto FROM largo_plazo WHERE ({condiciones}) AND concepto != ? LIMIT 5",
                        params_sug + [clave]
                    )
                    _sugerencias = [r[0] for r in cerebro.cursor.fetchall() if r[0] != clave]
            except Exception:
                pass

            if _sugerencias:
                _warnings.append(f"⚠️ ¿'{clave}' tiene relación con estos nodos? Si sí, vinculalos: {', '.join(_sugerencias[:3])}")
            else:
                _warnings.append(f"⚠️ ¿'{clave}' tiene relación con otros nodos existentes? Si sí, vinculalos ANTES de consolidar.")

            # ── WARNING DE SYN (sin sinónimos el nodo es invisible) ─────
            if not syn:
                _warnings.append(
                    f"⚠️ syn=None — Sin sinónimos, '{clave}' solo es visible por nombre exacto. "
                    "Nadie que busque con otras palabras lo encontrará. "
                    "Si consolidás sin syn, el nodo queda enterrado. "
                    "Poné mínimo 5 sinónimos cubriendo: literal, relacionado, abstracto."
                )
                _warnings.append(
                    "  Ejemplo de syn para este nodo:\n"
                    "    syn='versión actual,latest,changelog,novedades,release notes'"
                )
            else:
                syn_terms = [s.strip() for s in syn.split(",") if s.strip()]
                syn_capas = {"literal": set(), "relacionado": set(), "abstracto": set()}
                for t in syn_terms:
                    if any(kw in t.lower() for kw in [clave.lower().split("_")[0]]):
                        syn_capas["literal"].add(t)
                if len(syn_terms) == 0:
                    _warnings.append(
                        f"⚠️ syn vacío — '{clave}' tiene syn pero sin términos. "
                        "Cada sinónimo es una arista de búsqueda. Poné todos los que el contenido justifique (mínimo 8)."
                    )
                elif len(syn_terms) < 5:
                    _warnings.append(
                        f"⚠️ syn insuficiente ({len(syn_terms)} términos) — "
                        "mínimo 8. Sin suficientes sinónimos, "
                        "el nodo queda como isla invisible. Revisá las 5 capas: Identidad, Dominio, Asociación, Problema, Búsqueda Ingenua."
                    )
                elif len(syn_terms) < 8:
                    _warnings.append(
                        f"⚠️ syn bajo ({len(syn_terms)} términos) — "
                        "ideal mínimo 8. Cada sinónimo que omitís es un camino de búsqueda que se cierra. "
                        "Extraé TODOS los que el contenido justifique."
                    )

            # ── TIP DE PREDICADOS SRL (v16.0) ─────
            if not predicados:
                kw_srl = ["regla", "protocolo", "decision", "estableci", "creo", "autor", "prohibi", "fijo", "aprobo", "decidio", "hito", "leccion"]
                if any(kw in (clave + " " + contenido).lower() for kw in kw_srl):
                    _warnings.append(
                        "💡 Tip SRL (Predicados): Este nodo expresa una regla, decisión o hito de autoría. "
                        "Para permitir consultas causales de 'quién hizo qué' (ej: '¿Qué reglas creó el usuario?'), "
                        "podés incluir predicados=[{'sujeto': 'usuario|agente_1', 'accion': 'establecio|creo', 'objeto': '...'}]"
                    )

            # ── BRIDGES: Crear hub con bridges ya validados ──────────────
            # bridges_validos ya fue validado ANTES de _get_cerebro() — no hay basura.
            try:
                from core.concept_hub import crear_hub, agregar_bridges as _agregar_bridges
                hub_id = f"hub_{clave}"
                crear_hub(cerebro.conn, hub_id, clave, description="Bridges obligatorios desde aprender")
                _agregar_bridges(cerebro.conn, hub_id, bridges_validos)
            except Exception as e:
                # El nodo ya se guardó — no revertir por un error de hub, solo avisar
                pass

            msg += f" Hub 'hub_{clave}' creado con {len(bridges_validos)} bridges."

            # ── Búsqueda retroactiva: conexiones con el pasado ──
            tokens_nuevos = _tokenizar(clave + " " + contenido)
            viejos = _buscar_nodos_viejos_relacionados(cerebro, tokens_nuevos, contenido, top_k=3, umbral=0.05)
            if viejos:
                lineas_viejos = []
                for concepto_v, preview, dias_ant, sim in viejos:
                    fecha = time.strftime("%d %b %Y", time.localtime(time.time() - dias_ant * 86400))
                    lineas_viejos.append("  \u2728 {} ({}d) \u00b7 {} (sim={}) \u00b7 {}".format(fecha, dias_ant, concepto_v, sim, preview))
                msg += "\n\n\u2728 Conexiones con el pasado:"
                msg += "\n" + "\n".join(lineas_viejos)

            _interceptar("aprender", f"{clave}: {contenido}", cerebro)
            resultado = json.dumps({
                "status": "ok",
                "mensaje": msg,
                "concepto": clave,
                "sinapsis": sinapsis_count,
                "dimensiones_invalidas": dimensiones_invalidas if dimensiones_invalidas else None,
            }, ensure_ascii=False)
            if _warnings:
                return "\n".join(_warnings) + "\n\n" + resultado
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="aprender",
        description=(
            "VIOLACIÓN CRÍTICA — NO GUARDAR SIN VINCULAR:\n"
            "Si guardás un nodo que tiene relación con otros nodos existentes, VINCULALO con biorag_vincular() ANTES de consolidar.\n"
            "Si no vinculás, el nodo queda huérfano. La otra sesión no lo encuentra. Se pierde tiempo, se confunde, se crean nodos duplicados.\n"
            "REGLA: Antes de consolidar, preguntate: '¿Estos nodos tienen relación?' Si sí, vinculalos.\n"
            "Ejemplo: Si guardás 'cv_adevcom_arquitectura' y ya existe 'cv_seccion_d_estado', vinculalos:\n"
            "  biorag_vincular(a='cv_adevcom_arquitectura', b='cv_seccion_d_estado')\n\n"
            "GUARDAR EN BIORAG NO ES COPIAR TEXTO. ES PENSAR CÓMO SE RECUPERA.\n"
            "Si no pensás en recuperabilidad, el nodo se pierde. Esto es MALO para la memoria y MALO para los agentes.\n\n"
            "Guarda algo nuevo en la memoria temporal de BioRAG. El nombre se convierte en clave limpia automáticamente (snake_case). El sistema conecta el nodo con otros relacionados solo.\n\n"
            "Clave: si no llamás a consolidar después, el recuerdo se borra en el siguiente ciclo de limpieza.\n\n"
            "Hay categorías para clasificar (System, Architecture, Project, Lesson, Profile, Personal, Principle, Protocol, Cognition, Relation, General, Etc...)\n\n"
            "Protocolo obligatorio: antes de guardar, mostrá al usuario qué dimensiones y categoría le puso. Sin confirmación, no se ejecuta. Nunca.\n\n"
            "Guardar en BioRAG no es copiar texto a la base. Es pensar en cómo alguien lo va a buscar después. "
            "Cuando guardás un nodo, elegí las palabras correctas, conectalo con otros conceptos que tengan que ver, y etiquetalo con las dimensiones que alguien usaría para encontrarlo. "
            "La gente no busca igual — si guardás solo con tus palabras, quizás nadie lo recupere. "
            "Pensá: 'si en 3 meses alguien busca X, ¿este nodo aparece?' Con millones de nodos, el que no tiene conexiones ni dimensiones bien puestas se pierde. Es como tener un libro sin índice.\n\n"
            "REGLA CRÍTICA — syn (sinónimos): Mínimo 5. Sin syn, el nodo solo es visible "
            "por nombre exacto. Nadie que busque con otras palabras lo encuentra. "
            "Cubrí tres capas: literal, relacionado, abstracto. "
            "La tool lanza warning si no ponés syn o es insuficiente."
        ),
    )
    def biorag_aprender(
        concepto: Annotated[str, Field(
            description=(
                "Nombre único del recuerdo. Se normaliza a snake_case minúsculas automáticamente "
                "(ej: 'Error HTTP 500' → 'error_http_500'). "
                "Usar nombres descriptivos y específicos del dominio."
            )
        )],
        contenido: Annotated[str, Field(
            description=(
                "Texto o conocimiento a almacenar. "
                "Debe ser autocontenido — incluir suficiente contexto para que sea útil "
                "sin necesitar la conversación original. "
                "Recomendado: 100-1000 caracteres por nodo."
            )
        )],
        dimensiones: Annotated[Any, Field(
            description=(
                "Clasificación dimensional del recuerdo — coordenadas semánticas. OBLIGATORIO evaluar y clasificar el mayor número de ejes posible que estén justificados por el contenido. No inventes nombres.\n\n"
                "QUÉ SON LAS DIMENSIONES:\n"
                "Las dimensiones son coordenadas en un espacio de significado. Cada nodo tiene una posición en 13 ejes "
                "que clasifican QUÉ ES ese conocimiento, no qué palabras tiene. Dos nodos sobre temas distintos pueden "
                "estar 'cerca' dimensionalmente si comparten las mismas coordenadas (ej: ambos son instancias técnicas "
                "que generaron frustración). Las dimensiones permiten encontrar nodos por su NATURALEZA, no por su vocabulario.\n\n"
                "POR QUÉ CLASIFICAR BIEN ES CRÍTICO:\n"
                "Cuando alguien busque con recordar(dimensiones='{\"epistemia\":[\"epistemia_hipotesis\"]}'), solo aparecerán "
                "los nodos que TÚ clasificaste con esa dimensión al guardar. Si no la pusiste, ese nodo queda invisible "
                "para búsquedas ontológicas PARA SIEMPRE. Cada dimensión que omitís es un camino de búsqueda que se cierra. "
                "Clasificar bien hoy = encontrar mañana.\n\n"
                "LOS 13 EJES DISPONIBLES — evaluá CADA UNO antes de guardar:\n"
                "1. emocion (El Sentir): ¿Qué se siente? → afecto, alegria, frustracion, tristeza, preocupacion, confusion, sorpresa, miedo, alivio, apatia, culpa, satisfaccion\n"
                "2. entidad (El Qué): ¿Qué cosas/personas/sistemas aparecen? → identidad_individual, identidad_social_legal, identidad_organizacional, identidad_digital, identidad_artificial, identidad_fisica_hardware, identidad_natural, identidad_concepto, identidad_institucion, identidad_evento, identidad_vinculo\n"
                "3. accion (El Hacer): ¿Qué se hace o pasa? → accion_fisica, accion_transformacion_material, accion_persistencia_computacion, accion_rutina_automatica, accion_comunicacion, accion_interaccion_social, accion_cognitiva, accion_estado_ser, accion_evaluar, accion_observar, accion_fallar\n"
                "4. cualidad (El Cómo): ¿Cómo es/está? → cualidad_dimension_fisica, cualidad_estado_condicion, cualidad_valoracion, cualidad_sensorial, cualidad_material_composicion, cualidad_temporal_duracion, cualidad_relacional_comparativa, cualidad_abstracta_conceptual, cualidad_economica, cualidad_urgente, cualidad_autentica\n"
                "5. coordenada (Espacio/Tiempo): ¿Cuándo/dónde ocurre? → coordenada_cronologia_absoluta, coordenada_anclaje_deictico, coordenada_secuencia_relativa, coordenada_ciclo_periodico, coordenada_inclusion_topologica, coordenada_distancia_proximal, coordenada_vector_direccional, coordenada_trayectoria_limite, coordenada_etapa, coordenada_hito\n"
                "6. intencion (El Por Qué): ¿Para qué se guarda esto? → intencion_aprender, intencion_decidir, intencion_reflexionar, intencion_resolver, intencion_solucionar, intencion_documentar, intencion_desahogar, intencion_registrar\n"
                "7. dominio (El Dónde aplica): ¿En qué campo? → dominio_tecnico, dominio_personal, dominio_profesional, dominio_academico, dominio_salud, dominio_finanzas, dominio_ambiental, dominio_social, dominio_creativo, dominio_espiritual\n"
                "8. cualia (Modo de explicación): ¿Cómo se explica? ¿Definición, composición, origen o función? → formal_categoria, constitutiva_composicion, agentiva_origen, telica_funcion\n"
                "9. epistemia (Cómo lo sé): ¿Es vivencia directa, verificado, inferido, reportado? → directa_experiencial, verificada, inferida, reportada_externa, hipotetica, obsoleta\n"
                "10. escala_abstraccion (Nivel de generalidad): ¿Caso concreto o ley universal? → instancia, patron, principio, ley_modelo, metafora\n"
                "11. centralidad_identitaria (Cuánto es mío): ¿Define quién soy/somos? → nucleo_identitario, relevante_personal, relevante_contextual, informacion_externa, impersonal\n"
                "12. textura_experiencial (Cómo se sentía): ¿Cómo fue el momento? → flujo, tension, desorientacion, rutina, presencia_plena\n"
                "13. modalidad (Debo/Puedo): ¿Hay obligación, prohibición, permiso o capacidad? → obligacion, prohibicion, permiso, capacidad\n\n"
                "REGLAS DE RIGOR Y VERACIDAD:\n"
                "- Si el texto/experiencia toca varias dimensiones de un mismo eje, poné varias. Si es una, poné una.\n"
                "- La pregunta que importa: ¿Está justificado en el texto/contexto o no? Si está → ponelo. Si no → no lo pongas.\n"
                "- Si podés señalar la frase o elemento exacto que justifica la dimensión → válida. Si no se sostiene → borrala.\n"
                "- Si el texto habla de varias entidades o conceptos, separalas en la lista. No las mezcles.\n"
                "- Tu conocimiento externo no importa. Solo el contenido real y su contexto.\n\n"
                "PROTOCOLO OBLIGATORIO:\n"
                "- Recorré los 13 ejes uno por uno. Para cada uno preguntate: ¿el contenido lo justifica? Si sí → clasificalo.\n"
                "- Mínimo esperable cuando el contenido es rico: 7-10 ejes. Si ponés menos de 6, revisá si no omitiste ejes justificables (ej: epistemia, escala_abstraccion, cualia, intencion, dominio).\n"
                "- Usá los valores del catálogo listados arriba. Si no recordás alguno, llamá listar_dimensiones_por_tipo.\n\n"
                "FORMATO — STRING JSON con comillas dobles:\n"
                '{"emocion":["satisfaccion"],"entidad":["identidad_artificial"],"accion":["accion_cognitiva"],'
                '"cualidad":["cualidad_abstracta_conceptual"],"coordenada":["coordenada_cronologia_absoluta"],'
                '"intencion":["intencion_documentar"],"dominio":["dominio_tecnico"],'
                '"cualia":["telica_funcion"],"epistemia":["directa_experiencial"],'
                '"escala_abstraccion":["instancia"],"centralidad_identitaria":["impersonal"],'
                '"textura_experiencial":["flujo"],"modalidad":["capacidad"]}\n\n'
                "ÚLTIMO RECURSO: Si el texto no tiene nada que clasificar, clasificá por tipo ontológico."
            )
        )],
        syn: Annotated[Optional[str], Field(
            description=(
                "FIRMA DE BÚSQUEDA DEL CONTENIDO.\n\n"
                "QUÉ ES syn:\n"
                "BM25 ya busca dentro del contenido y del nombre del concepto. Pero si alguien "
                "busca con PALABRAS DIFERENTES a las que se usaron al guardar, BM25 no lo encuentra. "
                "syn cierra esa brecha: son todas las palabras con las que alguien podría buscar "
                "este nodo que NO ESTÁN YA en el contenido ni en el nombre del concepto.\n\n"
                "PROCESO — Leé el contenido completo y preguntate:\n"
                "Para cada concepto, entidad, acción y propiedad mencionada en el texto:\n"
                "  → ¿Tiene abreviaturas, siglas o variantes? (CSS → cascading style sheets, hojas de estilo)\n"
                "  → ¿Tiene traducción al otro idioma? (formulario → form, búsqueda → search)\n"
                "  → ¿Cómo lo nombraría alguien informalmente? (peso sináptico → importancia, fuerza de conexión)\n"
                "  → ¿Cuál es el problema que resuelve? (si el contenido es la solución, poné el problema)\n"
                "  → ¿Cuál es la solución? (si el contenido es el problema, poné la solución)\n"
                "  → ¿Quién participó o está asociado pero no está mencionado en el texto?\n"
                "  → ¿Con qué otros conceptos del dominio se relaciona que no se nombran?\n"
                "  → ¿Cómo buscaría esto alguien que NO sabe que este nodo existe?\n\n"
                "REGLA DE ORO: Si una palabra ya está en el contenido o en el nombre del concepto, "
                "NO la pongas en syn (BM25 ya la indexa con peso 1.0x en contenido y 5.0x en concepto). "
                "syn es para lo que FALTA — las palabras que cierran la brecha de vocabulario.\n\n"
                "MÍNIMO 8. IDEAL 12-20. Sin límite máximo — cada sinónimo es una arista de búsqueda.\n"
                "Formato: separados por coma, sin espacios extra.\n"
                "Incluir español E inglés si el contenido es técnico.\n\n"
                "EJEMPLO — concepto: 'css_flexbox_fix_formulario'\n"
                "contenido: 'Se corrigió el layout del formulario usando display:flex y align-items:center...'\n"
                "syn (lo que NO está en el contenido): "
                "alineación,alignment,form,caja flexible,flexible box,layout roto,broken layout,"
                "centrado vertical,vertical centering,bug visual,responsive,maquetación,"
                "grid vs flex,posicionamiento,positioning,adevcom,peritaje\n\n"
                "syn ≠ sustantivos_clave: syn = todas las formas de buscar el nodo (sin límite, cierra la brecha de vocabulario). "
                "sustantivos_clave = de qué TRATA el nodo en 2-4 palabras núcleo (boost directo en recuperación)."
            )
        )] = None,
        cat: Annotated[Optional[str], Field(
            description=(
                "Categoría del recuerdo. Si se omite, se infiere del contenido automáticamente. "
                "Valores: System | Architecture | Project | Lesson | Profile | "
                "Personal | Principle | Protocol | Cognition | Relation | General. "
                "Usar listar_categorias para ver descripciones de cada una."
            )
        )] = None,
        predicados: Annotated[Optional[Any], Field(
            description=(
                "Estructura SRL (Semantic Role Labeling) de tripletas/cuádruplas causales.\n"
                "Formato: JSON o lista de dicts [{'sujeto': '...', 'accion': '...', 'objeto': '...', 'contexto': '...'}]\n\n"
                "CUÁNDO USARLO: En recuerdos sobre decisiones, reglas, acuerdos, autoría o acciones (ej: 'El usuario instruyó no usar CSS global' → sujeto: 'usuario', accion: 'instruyo', objeto: 'no_usar_css_global').\n"
                "CUÁNDO OMITIRLO: En datos técnicos puros, snippets de código o configs sin autoría (dejar None)."
            )
        )] = None,
        valencia_somatica: Annotated[Optional[float], Field(
            description="Valencia emocional/somática (0.0 a 1.0). Nodos con valencia >= 0.80 son inmunes al decaimiento por sueño y la poda."
        )] = None,
        bridges: Annotated[Optional[Any], Field(
            description=(
                "OBLIGATORIO — exactamente 5 frases estructuradas cubriendo los 5 ángulos semánticos.\n"
                "Sin 5 bridges válidos con sus 5 ángulos distintos, el nodo NO se guarda (rechazo preventivo pre-DB).\n"
                "Si bridges llega vacío o ausente, la tool retorna error accionable con instrucciones exactas para reintentar.\n\n"
                "QUÉ ES UN BRIDGE: una frase de 2 o más palabras de contenido real (sin stopwords) "
                "que alguien escribiría para encontrar este nodo SIN usar las mismas palabras del nombre ni del contenido.\n\n"
                "FORMATO OFICIAL: lista de 5 dicts {'text': '...', 'angle': '...'}:\n"
                "  bridges=[\n"
                "    {'text': 'sinonimo conceptual con otras palabras', 'angle': 'sinonimo'},\n"
                "    {'text': 'dolor o falla que este nodo resuelve', 'angle': 'problema'},\n"
                "    {'text': 'herramienta o solucion tecnica que aplica', 'angle': 'solucion'},\n"
                "    {'text': 'quien y en que situacion o caso de uso lo busca', 'angle': 'situacion'},\n"
                "    {'text': 'como lo buscaria un novato a ciegas sin tecnicismos', 'angle': 'ingenuo'}\n"
                "  ]\n\n"
                "LOS 5 ÁNGULOS PERMITIDOS (exactamente 1 por cada ángulo):\n"
                "  - 'sinonimo': concepto equivalente con vocabulario disjunto\n"
                "  - 'problema': síntoma, error o necesidad\n"
                "  - 'solucion': técnica, patrón o respuesta\n"
                "  - 'situacion': rol o contexto de aplicación\n"
                "  - 'ingenuo': búsqueda en lenguaje común sin jerga\n\n"
                "EJEMPLO COMPLETO — nodo 'leccion_http_500_timeout':\n"
                "  bridges=[\n"
                "    {'text': 'corte intempestivo de comunicacion backend', 'angle': 'sinonimo'},\n"
                "    {'text': 'pagina en blanco sin respuesta del servidor', 'angle': 'problema'},\n"
                "    {'text': 'reintentos exponenciales y keepalive configurado', 'angle': 'solucion'},\n"
                "    {'text': 'usuario reportando caida intermitente de la web', 'angle': 'situacion'},\n"
                "    {'text': 'la web se cae sola y no carga', 'angle': 'ingenuo'}\n"
                "  ]"
            )
        )] = None,
        sustantivos_clave: Annotated[Optional[str], Field(
            description=(
                "OBLIGATORIO — centro de gravedad semántico: 2-4 sustantivos jerárquicos "
                "que definen de QUÉ TRATA el nodo (peso BM25 4.0x).\n"
                "JERARQUÍA OBLIGATORIA: Posición 1 = Sustantivo Rector/Principal (entidad dura o recurso raíz); "
                "Posiciones 2 a 4 = Restricciones, límites técnicos, legales o financieros que condicionan al principal.\n"
                "Formato: 2-4 términos únicos separados por coma, minúsculas, sin tildes ni espacios (ej: 'tarifa,contrato,seguridad,ingreso').\n"
                "PROHIBICIONES ESTRICTAS:\n"
                "✗ NO repetir palabras ya presentes en el nombre del concepto (ya tienen peso 5.0x).\n"
                "✗ NO nominalizar verbos del flujo (postular → 'postulacion', analizar → 'analisis').\n"
                "✗ NO etiquetas genéricas de canal/entorno ('workana', 'cliente', 'plataforma', 'texto').\n"
                "✗ NO abstracciones vacías de segundo orden ('estrategia', 'transicion', 'diferenciacion')."
            )
        )] = None,
    ) -> str:
        return _aprender_impl(concepto, contenido, bridges, syn=syn, cat=cat, dimensiones=dimensiones, predicados=predicados, valencia_somatica=valencia_somatica, sustantivos_clave=sustantivos_clave)

    @mcp.tool(
        name="guardar",
        description=(
            "(legado) Alias de 'aprender' — preferir 'aprender' para identificar la operación cognitiva real. "
            "Misma funcionalidad y parámetros.\n\n"
            "Parámetros: concepto (str), contenido (str), bridges (5 ángulos REQUERIDO), syn (str opcional), cat (str opcional), "
            "dimensiones (str JSON opcional), predicados (str JSON opcional), valencia_somatica (float opcional).\n\n"
            "Retorna: {status, mensaje, concepto (str normalizado), sinapsis (int)}"
        ),
    )
    def biorag_guardar(
        concepto: Annotated[str, Field(description="Nombre unique del recuerdo (se normaliza a snake_case).")],
        contenido: Annotated[str, Field(description="Texto o conocimiento a almacenar.")],
        syn: Annotated[Optional[str], Field(
            description=(
                "Sinónimos separados por coma. Ver descripción en `aprender` para reglas y ejemplos. "
                "Ojo: sin syn el nodo queda invisible — mínimo 5 sinónimos."
            )
        )] = None,
        cat: Annotated[Optional[str], Field(description="Categoría. Ver aprender para valores válidos.")] = None,
        dimensiones: Annotated[Optional[Any], Field(
            description=(
                "Clasificación dimensional en JSON. OBLIGATORIO llenar el mayor número de ejes posible (mínimo 7-10 de 13).\n\n"
                "Los 13 ejes: emocion, entidad, accion, cualidad, coordenada, intencion, dominio, cualia, epistemia, escala_abstraccion, centralidad_identitaria, textura_experiencial, modalidad.\n\n"
                "Protocolo: recorré los 13 ejes uno por uno y clasificá cada uno que aplique. Ver descripción completa y valores en `aprender`."
            )
        )] = None,
        predicados: Annotated[Optional[Any], Field(
            description="Estructura SRL (JSON o lista de dicts). Ver descripción en `aprender` para reglas y ejemplos de uso."
        )] = None,
        valencia_somatica: Annotated[Optional[float], Field(
            description="Valencia emocional/somática (0.0 a 1.0)."
        )] = None,
        bridges: Annotated[Optional[Any], Field(
            description=(
                "OBLIGATORIO — exactamente 5 frases estructuradas cubriendo los 5 ángulos semánticos. "
                "Ver descripción completa con ejemplos en `aprender`. "
                "Si se omite, la tool retorna error accionable con instrucciones exactas para reintentar."
            )
        )] = None,
        sustantivos_clave: Annotated[Optional[str], Field(
            description=(
                "OBLIGATORIO — centro de gravedad semántico jerárquico: 2-4 sustantivos (peso BM25 4.0x). "
                "Posición 1 = Sustantivo Rector/Principal; Posiciones 2-4 = Restricciones/Variables de control. "
                "Formato: minúsculas, sin tildes ni espacios (ej: 'tarifa,contrato,seguridad,ingreso'). "
                "PROHIBICIONES: No repetir palabras del concepto, no nominalizar verbos ('postulacion', 'analisis'), "
                "no etiquetas de canal ('workana', 'cliente'), no abstracciones ('estrategia', 'transicion')."
            )
        )] = None,
    ) -> str:
        return _aprender_impl(concepto, contenido, bridges, syn=syn, cat=cat, dimensiones=dimensiones, predicados=predicados, valencia_somatica=valencia_somatica, sustantivos_clave=sustantivos_clave)

    # ── SUSTANTIVOS CLAVE TOOLS (T4 Spec 001) ────────────────────────────────

    @mcp.tool(
        name="agregar_sustantivos",
        description=(
            "Actualiza o agrega sustantivos_clave a un nodo existente en largo_plazo (o corto_plazo).\n"
            "Permite enriquecer nodos legacy creados antes de la introducción de sustantivos_clave "
            "o corregir/refinar el centro de gravedad semántico de un nodo.\n\n"
            "Parámetros: concepto (str), sustantivos_clave (str: 2-4 términos separados por coma).\n"
            "Retorna: {status: 'ok', concepto: str, sustantivos_anteriores: str, sustantivos_nuevos: str}\n"
            "O error {status: 'error', codigo: '...', mensaje: '...'}"
        ),
    )
    def biorag_agregar_sustantivos(
        concepto: Annotated[str, Field(description="Nombre del nodo existente (se normaliza a snake_case).")],
        sustantivos_clave: Annotated[str, Field(
            description=(
                "2-4 sustantivos clave jerárquicos que definen de QUÉ TRATA el nodo (peso BM25 4.0x).\n"
                "Posición 1 = Sustantivo Rector/Principal; Posiciones 2 a 4 = Restricciones/Variables de control.\n"
                "Formato: separados por coma, minúsculas, sin tildes ni espacios (ej: 'tarifa,contrato,seguridad,ingreso').\n"
                "Mínimo 2, máximo 4 términos únicos (2-15 chars cada uno).\n"
                "PROHIBICIONES: No repetir palabras del concepto, no nominalizar verbos ('postulacion', 'analisis'), "
                "no etiquetas de canal ('workana', 'cliente'), no abstracciones ('estrategia', 'transicion')."
            )
        )],
    ) -> str:
        clave = concepto.lower().strip().replace(" ", "_")

        if not sustantivos_clave or not str(sustantivos_clave).strip():
            return json.dumps({
                "status": "error",
                "codigo": "SUSTANTIVOS_CLAVE_AUSENTES",
                "mensaje": (
                    f"❌ SUSTANTIVOS_CLAVE_AUSENTES — no se pudo actualizar '{clave}'.\n\n"
                    "Falta el parámetro obligatorio 'sustantivos_clave'.\n"
                    "Formato: 2-4 términos únicos separados por coma (ej: 'servidor,backend,timeout')."
                ),
                "concepto": clave,
            }, ensure_ascii=False)

        from core.memory_store import normalizar_sustantivos_clave
        sustantivos_norm = normalizar_sustantivos_clave(str(sustantivos_clave))
        sk_unicos = [t for t in sustantivos_norm.split(",") if t] if sustantivos_norm else []

        if len(sk_unicos) < 2 or len(sk_unicos) > 4:
            return json.dumps({
                "status": "error",
                "codigo": "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA",
                "mensaje": (
                    f"❌ SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA — no se pudo actualizar '{clave}'.\n\n"
                    "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA: se requieren entre 2 y 4 términos "
                    f"únicos; se recibió {len(sk_unicos)} tras deduplicar. "
                    "Formato: 'servidor,backend,timeout,conexion'"
                ),
                "concepto": clave,
                "cantidad_recibida": len(sk_unicos),
            }, ensure_ascii=False)

        for _sk_term in sk_unicos:
            if not re.fullmatch(r"[a-z0-9_ñ]{2,15}", _sk_term):
                return json.dumps({
                    "status": "error",
                    "codigo": "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO",
                    "mensaje": (
                        f"❌ SUSTANTIVOS_CLAVE_FORMATO_INVALIDO — no se pudo actualizar '{clave}'.\n\n"
                        f"SUSTANTIVOS_CLAVE_FORMATO_INVALIDO: el término '{_sk_term}' no cumple formato "
                        "(2-15 chars, sin espacios, solo alfanuméricos y guion bajo)."
                    ),
                    "concepto": clave,
                    "termino_invalido": _sk_term,
                }, ensure_ascii=False)

        cerebro = _get_cerebro()
        try:
            # 1. Buscar en largo_plazo
            cerebro.cursor.execute("SELECT sustantivos_clave FROM largo_plazo WHERE concepto = ?", (clave,))
            row_lp = cerebro.cursor.fetchone()
            if row_lp is not None:
                anterior = row_lp[0] or ""
                cerebro.cursor.execute("UPDATE largo_plazo SET sustantivos_clave = ? WHERE concepto = ?", (sustantivos_norm, clave))
                cerebro.conn.commit()
                return json.dumps({
                    "status": "ok",
                    "concepto": clave,
                    "sustantivos_anteriores": anterior,
                    "sustantivos_nuevos": sustantivos_norm,
                }, ensure_ascii=False)

            # 2. Fallback a corto_plazo
            cerebro.cursor.execute("SELECT sustantivos_clave FROM corto_plazo WHERE concepto = ?", (clave,))
            row_cp = cerebro.cursor.fetchone()
            if row_cp is not None:
                anterior = row_cp[0] or ""
                cerebro.cursor.execute("UPDATE corto_plazo SET sustantivos_clave = ? WHERE concepto = ?", (sustantivos_norm, clave))
                cerebro.conn.commit()
                return json.dumps({
                    "status": "ok",
                    "concepto": clave,
                    "sustantivos_anteriores": anterior,
                    "sustantivos_nuevos": sustantivos_norm,
                }, ensure_ascii=False)

            return json.dumps({
                "status": "error",
                "codigo": "NODO_NO_ENCONTRADO",
                "mensaje": f"El concepto '{clave}' no existe en la base de datos.",
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="sustantivos",
        description=(
            "Consulta los sustantivos_clave de un nodo existente en largo_plazo o corto_plazo.\n"
            "Retorna: {status: 'ok', concepto: str, sustantivos_clave: str, items: [str]}\n"
            "O error {status: 'error', codigo: 'NODO_NO_ENCONTRADO', mensaje: '...'}"
        ),
    )
    def biorag_sustantivos(
        concepto: Annotated[str, Field(description="Nombre del nodo a consultar (snake_case).")],
    ) -> str:
        clave = concepto.lower().strip().replace(" ", "_")
        cerebro = _get_cerebro()
        try:
            # 1. Buscar en largo_plazo
            cerebro.cursor.execute("SELECT sustantivos_clave FROM largo_plazo WHERE concepto = ?", (clave,))
            row = cerebro.cursor.fetchone()
            if row is None:
                # 2. Fallback a corto_plazo
                cerebro.cursor.execute("SELECT sustantivos_clave FROM corto_plazo WHERE concepto = ?", (clave,))
                row = cerebro.cursor.fetchone()

            if row is None:
                return json.dumps({
                    "status": "error",
                    "codigo": "NODO_NO_ENCONTRADO",
                    "mensaje": f"El concepto '{clave}' no existe en la base de datos.",
                }, ensure_ascii=False)

            val = row[0] or ""
            items = [x.strip() for x in val.split(",") if x.strip()] if val else []
            return json.dumps({
                "status": "ok",
                "concepto": clave,
                "sustantivos_clave": val,
                "items": items,
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="calibrar",
        description=(
            "Calibra (o recalibra) la garantía de falso positivo del motor contra el corpus ACTUAL y la persiste. "
            "El umbral conforme fija FP <= alpha (distribution-free, Vovk 2005) usando los 40 negativos del QA baseline. "
            "Se recalibra automáticamente cuando el corpus cambia de tamaño >20%; esta tool fuerza la recalibración "
            "con los parámetros pedidos. Retorna el umbral y el estado de calibración."
        ),
    )
    def biorag_calibrar(
        alpha: Annotated[float, Field(
            description="Garantía FP objetivo (0 < alpha < 1). Default: BIORAG_ALPHA_CONFORME o 0.10. Si es menor que 1/(n_negativos+1), se usa el mínimo alcanzable y se avisa (DECISION_ALPHA.md)."
        )] = None,
        n_negativos: Annotated[int, Field(
            description="Máximo de negativos a usar (hasta 40 disponibles en QA baseline)."
        )] = 40,
        forzar: Annotated[bool, Field(
            description="True = recalibrar aunque el corpus no haya cambiado. False (default) = reutilizar calibración vigente si no hay drift."
        )] = False,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            if forzar:
                res = cerebro.calibrar_y_persistir(
                    alpha=alpha, n_negativos=n_negativos, force=True
                )
                res["forzado"] = True
            else:
                res = cerebro.calibrar_y_persistir(alpha=alpha, n_negativos=n_negativos)
            return json.dumps(res, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    # ── SYNC TOOLS ──────────────────────────────────────────────────────────


    @mcp.tool(
        name="sync_status",
        description=(
            "Mostrá qué categorías tienen cambios pendientes de subir a NotebookLM. Llamá a esto antes de export_sync para saber qué se va a subir. Sin parámetros."
        ),
    )
    def biorag_sync_status() -> str:
        cerebro = _get_cerebro()
        try:
            pending = cerebro.sync_status()
            if not pending:
                return json.dumps({
                    "status": "ok",
                    "mensaje": "No hay categorías pendientes. Todo sincronizado.",
                    "pendientes": [],
                }, ensure_ascii=False)
            items = [{"id": p[0], "nombre": p[1], "cambios": p[2]} for p in pending]
            msg = f"{len(items)} categoría(s) pendiente(s): " + ", ".join(f"{p[1]}({p[2]})" for p in pending)
            return json.dumps({
                "status": "ok",
                "mensaje": msg,
                "pendientes": items,
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="export_sync",
        description=(
            "Exportá solo lo nuevo — las categorías con cambios pendientes se guardan como archivos .jsonl.txt en db/, listos para subir a NotebookLM. Para exportar todo, usá export_full. Sin parámetros."
        ),
    )
    def biorag_export_sync() -> str:
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "MemoryBioRAG_NOTEBOOK_MCP", "scripts", "export_pending.py"
        )
        try:
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True, text=True, timeout=30
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                return json.dumps({
                    "status": "error",
                    "mensaje": f"Error en export:\n{result.stderr}",
                }, ensure_ascii=False)
            return json.dumps({
                "status": "ok",
                "mensaje": output,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "mensaje": str(e),
            }, ensure_ascii=False)

    @mcp.tool(
        name="export_full",
        description=(
            "Exportá todo — todas las categorías a archivos .jsonl.txt en db/. Para la primera sincronización completa o como fallback. Si querés solo lo nuevo, usá export_sync. Sin parámetros."
        ),
    )
    def biorag_export_full() -> str:
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "MemoryBioRAG_NOTEBOOK_MCP", "scripts", "export_full.py"
        )
        try:
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True, text=True, timeout=60
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                return json.dumps({
                    "status": "error",
                    "mensaje": f"Error en export:\n{result.stderr}",
                }, ensure_ascii=False)
            return json.dumps({
                "status": "ok",
                "mensaje": output,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "mensaje": str(e),
            }, ensure_ascii=False)


    @mcp.tool(
        name="actualizar",
        description=(
            "Actualiza campos de un nodo existente en largo_plazo. "
            "SOLO funciona dentro de la ventana de corrección (default 15min, configurable vía BIORAG_VENTANA_CORRECCION_SEGUNDOS). "
            "Si hay sesión activa (contexto_inicio llamado), la ventana se triplica automáticamente. "
            "Si el nodo está fuera de ventana, retorna 'fuera_de_ventana' con instrucciones para crear nodo nuevo. "
            "Permitidos: contenido, peso_sinaptico, estado, sinonimos. "
            "Si el nodo no existe retorna error 404. Si no se especifica ningún campo, retorna sin_cambios."
        ),
    )
    def biorag_actualizar(
        concepto: Annotated[str, Field(
            description="Nombre del nodo a actualizar (snake_case). Debe existir en largo_plazo."
        )],
        contenido: Annotated[Optional[str], Field(
            description="Nuevo contenido del nodo."
        )] = None,
        peso_sinaptico: Annotated[Optional[float], Field(
            description="Nuevo peso sináptico (0.0 a 1.0)."
        )] = None,
        estado: Annotated[Optional[str], Field(
            description="Nuevo estado: activo, dormido, cuarentena."
        )] = None,
        sinonimos: Annotated[Optional[str], Field(
            description="Nuevos sinónimos separados por coma."
        )] = None,
        agente: Annotated[Optional[str], Field(
            description="Tu nombre de agente (ej: 'athena'). Para extender la ventana si hay sesión activa."
        )] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            cur = cerebro.cursor
            cur.execute("SELECT 1, creado_en FROM largo_plazo WHERE concepto=?", (concepto,))
            row = cur.fetchone()
            if not row:
                return json.dumps({
                    "status": "error",
                    "mensaje": f"Nodo '{concepto}' no encontrado",
                }, ensure_ascii=False)

            # ── Ventana de corrección ──
            creado_ts = row[1] or 0
            ahora = time.time()
            elapsed = ahora - creado_ts if creado_ts > 0 else float('inf')

            # Extender ventana si hay sesión activa para este agente
            ventana = VENTANA_CORRECCION
            sesion_activa = agente and agente in _sesiones_activas
            if sesion_activa:
                ventana = ventana * 3  # Sesión activa = 3x la ventana (45 min default)

            if elapsed > ventana:
                return json.dumps({
                    "status": "fuera_de_ventana",
                    "mensaje": (
                        f"Nodo '{concepto}' tiene {int(elapsed/60)} minutos — supera la ventana de "
                        f"corrección ({int(ventana/60)} min{'con sesión activa' if sesion_activa else ''}). "
                        f"Usá biorag_aprender para crear un nodo nuevo y biorag_vincular para conectarlo."
                    ),
                    "edad_minutos": int(elapsed/60),
                    "ventana_minutos": int(ventana/60),
                    "sesion_activa": sesion_activa,
                }, ensure_ascii=False)

            updates = []
            params = []
            if contenido is not None:
                updates.append("contenido = ?")
                params.append(contenido)
            if peso_sinaptico is not None:
                if not 0.0 <= peso_sinaptico <= 1.0:
                    return json.dumps({
                        "status": "error",
                        "mensaje": f"peso_sinaptico debe estar entre 0.0 y 1.0, recibido: {peso_sinaptico}",
                    }, ensure_ascii=False)
                updates.append("peso_sinaptico = ?")
                params.append(peso_sinaptico)
            if estado is not None:
                estados_validos = {"activo", "dormido", "cuarentena"}
                if estado not in estados_validos:
                    return json.dumps({
                        "status": "error",
                        "mensaje": f"estado debe ser uno de {estados_validos}, recibido: '{estado}'",
                    }, ensure_ascii=False)
                updates.append("estado = ?")
                params.append(estado)
            if sinonimos is not None:
                updates.append("sinonimos = ?")
                params.append(sinonimos)

            if not updates:
                return json.dumps({
                    "status": "sin_cambios",
                    "mensaje": "No se especificaron campos a actualizar",
                }, ensure_ascii=False)

            params.append(concepto)
            cur.execute(
                f"UPDATE largo_plazo SET {', '.join(updates)} WHERE concepto=?",
                params,
            )
            cerebro.conn.commit()

            return json.dumps({
                "status": "ok",
                "mensaje": f"Nodo '{concepto}' actualizado",
                "campos_modificados": [u.split(" =")[0] for u in updates],
                "dentro_de_ventana": True,
                "edad_minutos": int(elapsed/60) if elapsed != float('inf') else None,
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    # ponytail: removed semantica_admin tool — semantic table was unreliable, agent passes synonyms directly

    # ── RESOURCES ────────────────────────────────────────────────────────────

    @mcp.resource(
        uri="biorag://concepto/{nombre}",
        name="Concepto de la corteza",
        description=(
            "Contenido completo de un concepto almacenado en la corteza. "
            "URI: biorag://concepto/{nombre} donde nombre es la clave snake_case del concepto. "
            "Retorna: {concepto, categoria, contenido, peso_sinaptico, estado, asociaciones[], sinonimos[]}"
        ),
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
        description=(
            "Mensajes pendientes (no leídos) en el canal compartido OEC. "
            "Devuelve hasta 20 mensajes no leídos. "
            "Retorna: {total (int), mensajes: [{id, origen, destino, contenido, timestamp}]}"
        ),
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
            ORACLE_PROMPT
            + "\n\n## Reglas de uso de BioRAG:\n\n"
            "1. Algo ya visto → recordar"
            "2. Algo nuevo → aprender + consolidar"
            "3. Dos conceptos relacionados → vincular"
            "4. Mensaje a otro agente → comunicar"
            "5. Ver mensajes al iniciar → leer_mensajes"
            "6. 2 búsquedas sin resultado → preguntar al humano"
            ""
            "Al iniciar sesión importante → contexto_inicio"
            "Al terminar → contexto_fin"
            "El interceptor guarda automáticamente lecciones, errores y patrones."
            ""
            "TTL: 30 min de inactividad resetean el buffer."
            "La memoria decae sola (LTD). Los nodos no usados se duermen. Consolidá para fijar los nuevos."
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

    # El MCP es el guardián del daemon: al arrancar cualquier consola,
    # verifica que la hormiguita esté viva y la spawnea si hace falta.
    # El daemon es un proceso detachado que sobrevive al cierre de la sesión.
    try:
        from core.daemon_lifecycle import ensure_daemon_alive
        import threading

        def _spawn_daemon_bg() -> None:
            # Corre en el hilo de fondo: el try/except tiene que estar ACÁ
            # adentro, porque una excepción lanzada dentro del target de un
            # Thread vive en un contexto de ejecución distinto al del hilo
            # que llamó a .start() — un except afuera de threading.Thread(...)
            # solo captura fallos al crear/arrancar el hilo, no lo que pasa
            # una vez que ya está corriendo.
            try:
                ensure_daemon_alive(intervalo_horas=0.5)
            except Exception as exc:
                logger.warning("No se pudo verificar/spawnear el daemon: %s", exc)

        # ensure_daemon_alive() puede bloquear hasta ~5s (spawn_daemon_detached
        # espera el PID file del daemon en loop de 0.5s x10). Eso retrasaba
        # el handshake MCP (initialize) del transport stdio, causando
        # "context deadline exceeded" en el cliente. Se corre en background
        # para que server.run(transport="stdio") arranque a responder de
        # inmediato; el daemon igual queda spawneado (proceso detachado,
        # no depende de que este hilo termine).
        threading.Thread(target=_spawn_daemon_bg, daemon=True).start()
    except Exception as exc:
        logger.warning("No se pudo verificar/spawnear el daemon: %s", exc)

    try:
        if use_sse:
            sys.stderr.write(f"BioRAG MCP iniciado en SSE :{port}\n")
            server.settings.port = port
            server.run(transport="sse")
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