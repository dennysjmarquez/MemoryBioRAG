"""Deuda técnica trasladada intacta: submódulo de búsqueda MCP.

Expone tools de búsqueda y recuperación en BioRAG:
- recordar
- buscar
"""

from datetime import datetime
import json
import logging
import math
import os
import re
import sqlite3
import time
from typing import Annotated, Any, Optional, List

from pydantic import Field

from core.mcp_server._shared import (
    LIMITE_MCP,
    MAX_ASOCIACIONES_FLAT,
    STALE_DAYS,
    STALE_HARD_CUTOFF_DAYS,
    THRESHOLD_RAFTAGA_MCP,
    _get_cerebro,
    _interceptar,
    _resolver_dimensiones,
)
from core.sinapsis import _tokenizar

logger = logging.getLogger("mcp_server")


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


def register(mcp: Any) -> None:
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
            "  Mínimo 3 paráfrasis. Ideal 5.\n"
            "  Resultado esperado: 1-5 recuerdos con score >= 0.50.\n"
            "  Si encontraste lo que buscabas → FIN. No pases a PASO 2.\n\n"
            "PASO 2 — Ráfaga de Rescate (SOLO si PASO 1 devolvió 0 resultados o score < 0.50):\n"
            "  rafaga_palabras: 10-15 términos separados por coma cubriendo:\n"
            "    (1) Literal (2) Técnico (3) Contexto (4) Problema (5) Emoción/Prioridad\n"
            "  forzar_rafaga=True\n"
            "  El motor busca por FTS en abanico amplio y re-rankea.\n"
            "  Evaluá los resultados en tu síntesis (la ráfaga trae más candidatos, filtrá vos).\n\n"
            "═══════════════════════════════════════════════════════\n"
            "EJEMPLO COMPLETO — PASO 1 (búsqueda recomendada):\n"
            "═══════════════════════════════════════════════════════\n"
            "recordar(\n"
            "  query='timeout base de datos',\n"
            "  parafrasis='error conexion postgres,db connection lost,fallo pool conexiones,base de datos no responde',\n"
            "  dimensiones='{\"dominio\":[\"dominio_tecnico\"],\"emocion\":[\"frustracion\"]}',\n"
            "  sustantivos_clave='servidor,backend,timeout,conexion',\n"
            ")\n\n"
            "═══════════════════════════════════════════════════════\n"
            "EJEMPLO COMPLETO — PASO 2 (rescate si PASO 1 no encontró):\n"
            "═══════════════════════════════════════════════════════\n"
            "recordar(\n"
            "  query='timeout base de datos',\n"
            "  forzar_rafaga=True,\n"
            "  rafaga_palabras='timeout,db,database,postgres,conexion,connection,pool,leak,socket,reset,refused,caida,error',\n"
            "  sustantivos_clave='servidor,backend,timeout,conexion',\n"
            ")\n\n"
            "Parámetros: query (str), dimensiones (str JSON opcional), parafrasis (str opcional),\n"
            "dias (int opcional), desde/hasta (str YYYY-MM-DD opcional), autor (str opcional),\n"
            "modo_estricto (bool opcional), forzar_rafaga (bool opcional), rafaga_palabras (str opcional),\n"
            "asociados (bool default True), limite (int default 10), deep (bool default False),\n"
            "context_window (int 0-2 default 0), completo (bool default False), preview_chars (int default 1500),\n"
            "pagina (int default 1), ordenar_por (str: 'relevancia'|'recencia'|'antiguedad', default 'relevancia'),\n"
            "asociaciones_max (int opcional, default 12, 0=todas),\n"
            "sustantivos_clave (str opcional: 2-4 sustantivos separados por coma para boost temático BM25 4.0x).\n\n"
            "Retorna: {total, pagina_actual, paginas_totales, resultados[], contexto_expandido[], sinapsis_creadas[], profundidad, trazabilidad, advertencia_temporal}"
        ),
    )
    def biorag_recordar(
        query: Annotated[Optional[str], Field(
            description=(
                "Frase o palabras clave a buscar. Dejar None o vacío para ver log cronológico puro (filtrable por días/fechas/autor).\n"
                "Para búsquedas dirigidas, usar frase corta (2-5 palabras). OBLIGATORIO incluir paráfrasis en el parámetro `parafrasis` para evitar falsos negativos."
            )
        )] = None,
        dimensiones: Annotated[Optional[Any], Field(
            description=(
                "Filtro ontológico dimensional. Coordenadas semánticas para buscar por la NATURALEZA del recuerdo, no por sus palabras.\n\n"
                "FORMATO OBLIGATORIO — STRING JSON con comillas dobles:\n"
                'dimensiones=\'{"dominio":["dominio_tecnico"],"emocion":["frustracion"]}\'\n\n'
                "CUÁNDO USARLO:\n"
                "- Cuando busques recuerdos por tipo de experiencia (ej: frustraciones técnicas, decisiones personales, aprendizajes).\n"
                "- Cuando la búsqueda textual sea ambigua y quieras restringir el significado.\n"
                "- OBLIGATORIO evaluar si el contexto de búsqueda justifica dimensiones antes de llamar.\n\n"
                "LOS 13 EJES:\n"
                "emocion (afecto, alegria, frustracion, tristeza, preocupacion, confusion, sorpresa, miedo, alivio, apatia, culpa, satisfaccion) | "
                "entidad (identidad_individual, identidad_social_legal, identidad_organizacional, identidad_digital, identidad_artificial, identidad_fisica_hardware, identidad_natural, identidad_concepto, identidad_institucion, identidad_evento, identidad_vinculo) | "
                "accion (accion_fisica, accion_transformacion_material, accion_persistencia_computacion, accion_rutina_automatica, accion_comunicacion, accion_interaccion_social, accion_cognitiva, accion_estado_ser, accion_evaluar, accion_observar, accion_fallar) | "
                "cualidad (cualidad_dimension_fisica, cualidad_estado_condicion, cualidad_valoracion, cualidad_sensorial, cualidad_material_composicion, cualidad_temporal_duracion, cualidad_relacional_comparativa, cualidad_abstracta_conceptual, cualidad_economica, cualidad_urgente, cualidad_autentica) | "
                "coordenada (coordenada_cronologia_absoluta, coordenada_anclaje_deictico, coordenada_secuencia_relativa, coordenada_ciclo_periodico, coordenada_inclusion_topologica, coordenada_distancia_proximal, coordenada_vector_direccional, coordenada_trayectoria_limite, coordenada_etapa, coordenada_hito) | "
                "intencion (intencion_aprender, intencion_decidir, intencion_reflexionar, intencion_resolver, intencion_solucionar, intencion_documentar, intencion_desahogar, intencion_registrar) | "
                "dominio (dominio_tecnico, dominio_personal, dominio_profesional, dominio_academico, dominio_salud, dominio_finanzas, dominio_ambiental, dominio_social, dominio_creativo, dominio_espiritual) | "
                "cualia (formal_categoria, constitutiva_composicion, agentiva_origen, telica_funcion) | "
                "epistemia (directa_experiencial, verificada, inferida, reportada_externa, hipotetica, obsoleta) | "
                "escala_abstraccion (instancia, patron, principio, ley_modelo, metafora) | "
                "centralidad_identitaria (nucleo_identitario, relevante_personal, relevante_contextual, informacion_externa, impersonal) | "
                "textura_experiencial (flujo, tension, desorientacion, rutina, presencia_plena) | "
                "modalidad (obligacion, prohibicion, permiso, capacidad)\n\n"
                "Para ver todos los valores válidos: llamar `listar_dimensiones` o `listar_dimensiones_por_tipo`."
            )
        )] = None,
        parafrasis: Annotated[Optional[str], Field(
            description=(
                "Reformulaciones alternativas de la query separadas por coma. OBLIGATORIO en toda búsqueda conceptual.\n"
                "Sin paráfrasis, el recall cae ~60%. Generar 3-5 variantes cubriendo diferentes ángulos:\n"
                "- Sinónimos directos\n"
                "- Términos técnicos equivalentes\n"
                "- Perspectiva funcional (qué hace vs cómo se llama)\n"
                "- Vocabulario coloquial vs formal\n"
                "Ejemplo: query='error de red', parafrasis='timeout conexion,fallo socket,caida servidor,problema conectividad'"
            )
        )] = None,
        dias: Annotated[Optional[int], Field(
            description=(
                "Filtrar recuerdos de los últimos N días (ej: dias=7 para la última semana, dias=1 para hoy). "
                "Filtro temporal pre-hoc: solo busca dentro de la ventana de tiempo especificada. "
                "Combinable con query (busca solo en ese período) o sin query (log cronológico de los últimos N días)."
            )
        )] = None,
        desde: Annotated[Optional[str], Field(
            description=(
                "Fecha de inicio en formato YYYY-MM-DD (ej: '2026-01-15'). "
                "Solo devuelve recuerdos creados a partir de esta fecha (inclusive). "
                "Se ignora si se especifica `dias`."
            )
        )] = None,
        hasta: Annotated[Optional[str], Field(
            description=(
                "Fecha de fin en formato YYYY-MM-DD (ej: '2026-02-01'). "
                "Solo devuelve recuerdos creados hasta el final de este día (23:59:59). "
                "Combinable con `desde` para definir un rango cerrado, o con `dias`."
            )
        )] = None,
        autor: Annotated[Optional[str], Field(
            description=(
                "Filtrar por agente creador o mencionado (ej: 'athena', 'claudia', 'usuario'). "
                "Busca coincidencias del nombre en el contenido o concepto del recuerdo. "
                "Combinable con filtros de fecha, categoría y query."
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
            description="Si True, utiliza inferencia transitiva sobre sinapsis latentes."
        )] = True,
        ordenar_por: Annotated[str, Field(
            description=(
                "Criterio de ordenamiento de resultados:\n"
                "- 'relevancia' (default): orden estándar por score híbrido multiseñal (BM25 + PPMI + dimensiones + Hebbiano).\n"
                "- 'recencia': del más nuevo al más viejo (CREATED DESC). Útil para ver qué pasó recién.\n"
                "- 'antiguedad': del más viejo al más nuevo (CREATED ASC). Útil para reconstruir historia/origen de un tema.\n\n"
                "⚠️ WARNER TEMPORAL: cuando ordenar_por es 'recencia' o 'antiguedad', el orden NO refleja relevancia semántica. "
                "El JSON devuelto incluye 'advertencia_temporal: true' y un aviso explícito para que el agente no confunda "
                "recencia con importancia."
            )
        )] = "relevancia",
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
        deep: Annotated[bool, Field(
            description="Si True, busca también en recuerdos dormidos (memoria profunda). Usar si no se encuentra en memoria activa."
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
            description="Número de página para resultados paginados (base 1). Default: 1.",
            ge=1,
        )] = 1,
        sustantivos_clave: Annotated[Optional[str], Field(
            description=(
                "Opcional — 2-4 sustantivos clave del tema a buscar (boost BM25 4.0x).\n"
                "Formato: minúsculas, separados por coma, sin espacios (ej: 'servidor,backend,timeout').\n"
                "CUÁNDO USARLO: cuando query es genérica pero sabés los términos técnicos exactos.\n"
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
