"""
Módulo de integración con ADN Conceptual.

Extraído de SQLiteMemoryBioRAG (Paso 3.4e - T17).
"""

import json
import time
import logging

from core.memory import constants

logger = logging.getLogger("BioRAG.MemoryStore")


def _cargar_firmas_adn(self):
    """Carga las firmas de ADN persistidas en la DB al motor en RAM."""
    if not self.adn_engine:
        return
    self.cursor.execute("SELECT concepto, firma_json FROM adn_firmas")
    for concepto, firma_json in self.cursor.fetchall():
        try:
            firma = json.loads(firma_json)
            self.adn_engine.registrar_concepto(concepto, firma)
        except Exception:
            continue


def _persistir_firma_adn(self, concepto: str, firma: dict):
    """Persiste una firma genética en la base de datos."""
    try:
        firma_json = json.dumps(firma)
        self.cursor.execute("""
            INSERT OR REPLACE INTO adn_firmas (concepto, firma_json, actualizado_en)
            VALUES (?, ?, ?)
        """, (concepto, firma_json, time.time()))
        self.conn.commit()
    except Exception as e:
        logger.warning(f"Error al persistir ADN para {concepto}: {e}")


def _enriquecer_con_adn(self, query, resultados_base, limite=None):
    """Signal #14 (v29): fusión ADN Conceptual con los resultados base (Política A).

    Implementa el contrato de degradación asociativa del plan (§3 y §4.2):
    - NUNCA silencio vacío: si no hay base ni señal ADN, devuelve la lista
      interna vacía pero con metadatos explícitos de `sin_evidencia_local`.
    - Escala S_base y S_adn a [0,1] dentro del pool de candidatos antes de
      combinar (§4.1). No suma cosenos crudos.
    - Fusión versionada (§4.2):
        S_final_directo    = 0.85*S_base + 0.15*S_adn
        S_final_asociativo = min(0.49, 0.70*S_base + 0.30*S_adn)
      La cota 0.49 impide que una asociación de baja confianza adelante a
      una coincidencia directa fiable.
    - Expansión ADN SOLO desde anclajes (mejores 2 resultados base), nunca
      un barrido global de `indices.vecs` (§2.3). `buscar_por_esencia` usa
      `adn_vecinos_v29` persistido o el pool de sus 2 cromosomas dominantes.
    - Preserva la estructura de tupla de 6 campos que los consumidores ya
      esperan: (concepto, contenido, peso, estado, score, asociaciones).
      El score final ocupa la posición 4; los metadatos de procedencia se
      devuelven por separado para no romper el contrato público.

    Returns:
        (pagina_resultados, metadatos_epistemicos)
    """
    base = list(resultados_base)
    metadatos = {
        "estado": "sin_evidencia_local",
        "confianza_epistemica": 0.0,
        "indice_adn_listo": bool(self.adn_engine is not None and self.adn_engine.indice_listo),
        "tipo_relacion_por_concepto": {},
        "genes_compartidos_por_concepto": {},
    }

    # Guarda de degradación: sin índice ADN no hay señal complementaria,
    # pero si ya hay base (evidencia directa), NO se etiqueta como sin_evidencia.
    if self.adn_engine is None or not self.adn_engine.indice_listo:
        metadatos["estado"] = "conocido" if base else "sin_evidencia_local"
        return base, metadatos

    # Evaluación epistémica C_e (calibra visibilidad, NUNCA silencia: §4.2)
    ce = 0.0
    if self.neocortex is not None:
        try:
            ce = float(self.neocortex.evaluar_episteme(query).get("confianza_epistemica", 0.0))
        except Exception:
            ce = 0.0
    metadatos["confianza_epistemica"] = ce

    # 1) S_base normalizado en [0,1] dentro del pool (max del pool, no global).
    max_base = max((float(r[4]) for r in base), default=0.0)
    pool = {}  # concepto -> dict con campos base + señal ADN
    for r in base:
        s_base = float(r[4])
        s_base_norm = s_base / max_base if max_base > 0 else 0.0
        pool[r[0]] = {
            "concepto": r[0], "contenido": r[1], "peso": r[2], "estado": r[3],
            "s_base": s_base_norm, "s_adn": 0.0, "asociaciones": r[5],
            "genes": [], "procedencia": "directa",
        }

    # 2) Expansión ADN desde los 2 mejores anclajes de la base (§3.1.2/3).
    anclajes = sorted(base, key=lambda r: float(r[4]), reverse=True)[:2]
    n_adn_consultados = 0
    for ancla in anclajes:
        try:
            vecinos = self.adn_engine.buscar_por_esencia(ancla[0], top_k=constants.ADN_MAX_EXPANSION)
        except Exception:
            vecinos = []
        for v in vecinos:
            n_adn_consultados += 1
            concepto_adn = v.get("concepto")
            if not concepto_adn or concepto_adn in pool:
                continue
            s_adn = float(v.get("afinidad_genetica", 0.0))
            if s_adn < constants.ADN_UMBRAL_ASOCIACION:
                continue
            pool[concepto_adn] = {
                "concepto": concepto_adn, "contenido": "", "peso": 0.0, "estado": "activo",
                "s_base": 0.0, "s_adn": s_adn, "asociaciones": [],
                "genes": v.get("genes_compartidos", []), "procedencia": "asociacion",
            }
    metadatos["candidatos_adn_consultados"] = n_adn_consultados

    # 3) S_adn para los candidatos directos: afinidad persistida del nodo
    #    en adn_vecinos_v29 (primer vecino), o firma del concepto en firma ADN.
    for concepto, info in pool.items():
        if info["procedencia"] != "directa":
            continue
        try:
            vecinos_nodo = self.adn_engine.vecinos.get(concepto, [])
            if vecinos_nodo:
                info["s_adn"] = float(vecinos_nodo[0].get("afinidad_genetica", 0.0))
                info["genes"] = vecinos_nodo[0].get("genes_compartidos", [])
        except Exception:
            info["s_adn"] = 0.0

    # 4) Fusión versionada (§4.2) + etiquetado de procedencia (§3.1.5).
    resultado = []
    for info in pool.values():
        s_base, s_adn = info["s_base"], info["s_adn"]
        if info["procedencia"] == "directa":
            s_final = 0.85 * s_base + 0.15 * s_adn
            tipo_relacion = "evidencia_directa"
        else:
            s_final = min(0.49, 0.70 * s_base + 0.30 * s_adn)
            tipo_relacion = "asociacion"
        metadatos["tipo_relacion_por_concepto"][info["concepto"]] = tipo_relacion
        metadatos["genes_compartidos_por_concepto"][info["concepto"]] = info["genes"]
        resultado.append((
            info["concepto"], info["contenido"], info["peso"], info["estado"],
            round(min(1.0, max(0.0, s_final)), 4), info["asociaciones"],
        ))

    resultado.sort(key=lambda r: r[4], reverse=True)
    if limite:
        resultado = resultado[:limite]

    # 5) Contrato §3.1.6: sin ancla → lista interna vacía + metadatos explícitos.
    metadatos["estado"] = (
        "conocido" if ce >= 0.60 else
        ("relacionado" if ce >= 0.20 else "asociativo_baja_confianza")
    )
    if not resultado:
        metadatos["estado"] = "sin_evidencia_local"
    return resultado, metadatos
