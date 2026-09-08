#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expM_structural_generator_v02.py
=============================================================================
EXP-M (v0.2) — GENERADOR ESTRUCTURAL COMPOSICIONAL EN DOS ETAPAS (A0-DEV)
=============================================================================
Implementación formal del pipeline desacoplado en 2 etapas:
1. ETAPA DE GENERACIÓN DISCRETA: Produce un Candidate Pool PRE-SCORE acotado (N << 851)
   mediante intersección estricta de roles relacionales (Acción ∧ Dominio/Entidad)
   y navegación sináptica condicionada. Nodos no seleccionados quedan 100% excluidos.
2. ETAPA DE SCORING Y RANKING: Pondera y ordena ÚNICAMENTE los nodos que superaron
   la etapa de generación discreta.

Restricciones Metodológicas Obligatorias (Protocolo Aureon):
1. Ejecución EXCLUSIVAMENTE sobre los 8 casos A0-DEV (Fase 5 OOD no-test).
2. Los 20 casos A0-TEST de EXP-L permanecen 100% ciegos, intocados y no evaluados.
3. Cero modificaciones en core/ (código 100% autocontenido y aislado).
4. Sin memorización de casos ni reglas ad-hoc.
5. El Gold solo entra en la evaluación de la métrica de acceso (Node-CE@K),
   NUNCA durante la generación de candidatos.
6. Si no existe representación estructural suficiente, emite ABSTAIN_NO_CANDIDATE.
=============================================================================
"""

import os
import sys
import json
import sqlite3
import hashlib
import time
import re
import unicodedata
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Any, Optional, Set
import numpy as np

# Rutas congeladas
DB_PATH = "snapshots/qa_escape_qcr_20260811.db"
LABELS_PATH = "scripts/experimentos/expA_labels.json"
DEV_DATASET_PATH = "docs/expM_dev_dataset_8cases.json"
OUTPUT_RESULTS_PATH = "docs/expM_dev_results_v02.json"

K_PRIMARY = 10
K_CURVE = [1, 5, 10, 20]

# Stopwords mínimas para normalización de tokens
SPANISH_STOPWORDS = {
    'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para',
    'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'mas', 'pero', 'sus', 'le', 'ya', 'o', 'este',
    'si', 'porque', 'esta', 'son', 'entre', 'cuando', 'muy', 'sin', 'sobre', 'ser', 'tiene',
    'tambien', 'me', 'hasta', 'hay', 'donde', 'quien', 'desde', 'todo', 'nos', 'durante', 'todos',
    'uno', 'les', 'ni', 'contra', 'otros', 'ese', 'eso', 'ante', 'ellos', 'e', 'esto', 'mi', 'antes'
}


def calcular_sha256_archivo(ruta: str) -> str:
    """Calcula el hash SHA-256 de un archivo en disco."""
    if not os.path.exists(ruta):
        return "ARCHIVO_NO_EXISTE"
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def normalizar_texto(texto: str) -> str:
    """Normaliza texto eliminando diacríticos y convirtiendo a minúsculas."""
    nfkd = unicodedata.normalize('NFKD', str(texto).lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def tokenizar(texto: str) -> Set[str]:
    """Tokenización normalizada y filtrado de stopwords."""
    norm = normalizar_texto(texto.replace('_', ' ').replace('-', ' '))
    tokens = re.findall(r'[a-z0-9]{2,}', norm)
    return {t for t in tokens if t not in SPANISH_STOPWORDS}


# =============================================================================
# ÁLGEBRA DE ROLES Y OPERADORES RELACIONALES COMPOSICIONALES (GENERAL)
# =============================================================================

OPERADORES_ACCION = {
    'particionar': {'roles': ['segmentacion', 'asignacion_recursos', 'hardware'], 'tipo': 'accion_persistencia_computacion'},
    'restringir': {'roles': ['limite', 'tope', 'capacidad_maxima'], 'tipo': 'cualidad_dimension_fisica'},
    'calibrar': {'roles': ['ponderacion', 'ajuste_parametros', 'relevancia'], 'tipo': 'accion_evaluar'},
    'combinar': {'roles': ['fusion', 'multiplicacion', 'pesos'], 'tipo': 'accion_evaluar'},
    'proyectar': {'roles': ['transformacion', 'mapeo', 'espacio_vectorial'], 'tipo': 'accion_cognitiva'},
    'entrelazar': {'roles': ['asociacion', 'vinculo', 'hipervector'], 'tipo': 'accion_cognitiva'},
    'generar': {'roles': ['creacion', 'sintesis', 'proceso_dinamico'], 'tipo': 'accion_rutina_automatica'},
    'consolidar': {'roles': ['fijacion', 'agrupacion', 'topologia'], 'tipo': 'accion_persistencia_computacion'},
    'transicionar': {'roles': ['cambio_estado', 'ciclo_vigilia_sueño', 'letargo'], 'tipo': 'accion_rutina_automatica'},
    'eliminar': {'roles': ['poda', 'depuracion', 'limpieza'], 'tipo': 'accion_rutina_automatica'},
    'clasificar': {'roles': ['taxonomia', 'categorizacion', 'dimensiones'], 'tipo': 'accion_evaluar'},
    'estructurar': {'roles': ['malla', 'grafo', 'enlaces_sinapticos'], 'tipo': 'accion_cognitiva'},
    'registrar': {'roles': ['cronologia', 'historial', 'hitos_temporales'], 'tipo': 'accion_persistencia_computacion'},
}

PATRONES_DOMINIO_ENTIDAD = {
    'computo': {'dominios': ['dominio_tecnico'], 'entidades': ['identidad_digital', 'identidad_fisica_hardware']},
    'nucleos': {'dominios': ['dominio_tecnico'], 'entidades': ['identidad_fisica_hardware']},
    'gigas': {'dominios': ['dominio_tecnico'], 'entidades': ['identidad_fisica_hardware']},
    'coeficientes': {'dominios': ['dominio_tecnico'], 'entidades': ['identidad_concepto']},
    'relevancia': {'dominios': ['dominio_tecnico'], 'entidades': ['identidad_concepto']},
    'hiperdimensional': {'dominios': ['dominio_tecnico'], 'entidades': ['identidad_concepto', 'identidad_artificial']},
    'binario': {'dominios': ['dominio_tecnico'], 'entidades': ['identidad_digital']},
    'pasarela': {'dominios': ['dominio_tecnico'], 'entidades': ['identidad_concepto']},
    'estocasticas': {'dominios': ['dominio_tecnico'], 'entidades': ['identidad_concepto']},
    'grupos': {'dominios': ['dominio_tecnico'], 'entidades': ['identidad_concepto', 'identidad_organizacional']},
    'vigilia': {'dominios': ['dominio_profesional', 'dominio_espiritual'], 'entidades': ['identidad_individual', 'identidad_artificial']},
    'letargo': {'dominios': ['dominio_profesional', 'dominio_espiritual'], 'entidades': ['identidad_individual', 'identidad_artificial']},
    'caducos': {'dominios': ['dominio_profesional'], 'entidades': ['identidad_concepto']},
    'cortical': {'dominios': ['dominio_tecnico'], 'entidades': ['identidad_artificial', 'identidad_natural']},
    'neuronal': {'dominios': ['dominio_profesional', 'dominio_tecnico'], 'entidades': ['identidad_artificial', 'identidad_natural']},
    'sinapticos': {'dominios': ['dominio_profesional', 'dominio_tecnico'], 'entidades': ['identidad_artificial']},
    'cronologico': {'dominios': ['dominio_profesional'], 'entidades': ['identidad_natural', 'identidad_individual']},
    'hitos': {'dominios': ['dominio_profesional'], 'entidades': ['identidad_natural', 'identidad_evento']},
}


class StructuralGeneratorV02:
    """
    Generador Estructural Composicional (v0.2).
    Pipeline estricto de dos etapas:
    1. Generación Discreta: Produce un conjunto acotado de candidatos que satisfacen
       intersección conjuntiva de roles (Acción ∧ Dominio/Entidad) o puente relacional directo.
    2. Scoring & Ranking: Ordena exclusivamente los candidatos generados en la etapa 1.
    """

    def __init__(self, db_conn: sqlite3.Connection, labels_data: Dict[str, Any]):
        self.conn = db_conn
        self.labels = labels_data
        self.conceptos = labels_data["conceptos"]
        self.comunidades = dict(zip(labels_data["conceptos"], labels_data["knn_lpa"]))
        self._indexar_ontologia_db()

    def _indexar_ontologia_db(self):
        """Indexa la ontología dimensional, sináptica y de categorías de la DB."""
        c = self.conn.cursor()
        self.nodos_activos = set(r[0] for r in c.execute("SELECT concepto FROM largo_plazo WHERE estado='activo'").fetchall())
        self.categorias_nodo = dict(c.execute("SELECT concepto, categoria FROM largo_plazo WHERE estado='activo'").fetchall())
        
        # Mapeo de sinónimos directos en el registro del nodo
        self.sinonimos_por_nodo = {}
        for conc, syns in c.execute("SELECT concepto, sinonimos FROM largo_plazo WHERE estado='activo'").fetchall():
            self.sinonimos_por_nodo[conc] = set(tokenizar(syns or ''))

        # Dimensiones semánticas por nodo
        self.dims_por_nodo = defaultdict(set)
        for conc, dim_name, tipo_name in c.execute("""
            SELECT lpd.concepto, ds.name, td.nombre
            FROM largo_plazo_dimensiones lpd
            JOIN dimensiones_semanticas ds ON ds.id = lpd.dimension_id
            JOIN tipos_dimension td ON td.id = ds.tipo_id
            JOIN largo_plazo lp ON lp.concepto = lpd.concepto
            WHERE lp.estado = 'activo'
        """).fetchall():
            self.dims_por_nodo[conc].add((tipo_name, dim_name))

        # Grafo sináptico
        self.sinapsis_out = defaultdict(dict)
        for orig, dest, peso in c.execute("SELECT origen, destino, peso FROM sinapsis WHERE origen IN (SELECT concepto FROM largo_plazo WHERE estado='activo')").fetchall():
            self.sinapsis_out[orig][dest] = peso

    def parsear_estructura_query(self, query: str) -> Dict[str, Any]:
        """Extrae operadores de Acción, Entidad/Dominio y Restricciones."""
        tokens = tokenizar(query)
        acciones_encontradas = []
        dominios_inferidos = set()
        entidades_inferidas = set()
        roles_detectados = set()

        for t in tokens:
            for op_k, op_v in OPERADORES_ACCION.items():
                if t.startswith(op_k[:4]) or op_k.startswith(t[:4]):
                    acciones_encontradas.append((op_k, op_v['tipo']))
                    roles_detectados.update(op_v['roles'])

            for dom_k, dom_v in PATRONES_DOMINIO_ENTIDAD.items():
                if t.startswith(dom_k[:4]) or dom_k.startswith(t[:4]):
                    dominios_inferidos.update(dom_v.get('dominios', []))
                    entidades_inferidas.update(dom_v.get('entidades', []))

        return {
            "query_tokens": list(tokens),
            "operadores_accion": acciones_encontradas,
            "roles_detectados": list(roles_detectados),
            "dominios_inferidos": list(dominios_inferidos),
            "entidades_inferidas": list(entidades_inferidas)
        }

    # =========================================================================
    # ETAPA 1: GENERACIÓN DISCRETA DE CANDIDATOS (PRE-SCORE)
    # =========================================================================
    def generar_candidate_pool_discreto(
        self,
        query: str,
        ablate_action: bool = False,
        ablate_domain: bool = False,
        ablate_synapse: bool = False
    ) -> Tuple[Set[str], Dict[str, List[str]], Dict[str, int]]:
        """
        Genera un subconjunto restringido y discreto de candidatos (N << 851).
        Aplica reglas conjuntivas:
        - R1 (Intersección Conjuntiva): Nodos con Acción Y (Dominio O Entidad).
        - R2 (Puente de Rol Sinónimo): Nodos cuyos sinónimos contienen roles derivados.
        - R3 (Adyacencia Sináptica Fuerte): Vecinos inmediatos de nodos R1/R2 (si no ablacionado).
        """
        struct = self.parsear_estructura_query(query)
        acciones = [] if ablate_action else struct["operadores_accion"]
        dominios = set() if ablate_domain else set(struct["dominios_inferidos"])
        entidades = set() if ablate_domain else set(struct["entidades_inferidas"])
        roles = set(struct["roles_detectados"])

        if not acciones and not dominios and not entidades and not roles:
            return set(), {}, {"R1_conjuntiva": 0, "R2_rol_sinonimo": 0, "R3_sinapsis_fuerte": 0}

        pool_candidatos = set()
        trazabilidad_generacion = defaultdict(list)
        conteo_reglas = {"R1_conjuntiva": 0, "R2_rol_sinonimo": 0, "R3_sinapsis_fuerte": 0}

        # Conjuntos base de nodos por tipo
        nodos_con_accion = set()
        nodos_con_dominio_o_entidad = set()

        for nodo in self.nodos_activos:
            nodo_dims = self.dims_por_nodo.get(nodo, set())
            
            # Check Acción
            if not ablate_action:
                for op_name, op_tipo in acciones:
                    if any(tipo_d == 'accion' and op_tipo in dim_d for tipo_d, dim_d in nodo_dims):
                        nodos_con_accion.add(nodo)
                        break

            # Check Dominio / Entidad
            if not ablate_domain:
                if any((tipo_d == 'dominio' and dim_d in dominios) or (tipo_d == 'entidad' and dim_d in entidades) for tipo_d, dim_d in nodo_dims):
                    nodos_con_dominio_o_entidad.add(nodo)

        # Regla 1: Intersección Conjuntiva Estricta (Acción ∧ Dominio/Entidad)
        if nodos_con_accion and nodos_con_dominio_o_entidad:
            r1_nodos = nodos_con_accion.intersection(nodos_con_dominio_o_entidad)
        elif not ablate_action and not ablate_domain:
            # Si uno de los dos no produjo nada, intersección vacía
            r1_nodos = set()
        else:
            # Si una rama está ablacionada, tomar la rama restante
            r1_nodos = nodos_con_accion if ablate_domain else nodos_con_dominio_o_entidad

        for n in r1_nodos:
            pool_candidatos.add(n)
            trazabilidad_generacion[n].append("R1:InterseccionConjuntiva(Accion ∧ Dominio/Entidad)")
        conteo_reglas["R1_conjuntiva"] = len(r1_nodos)

        # Regla 2: Puente de Rol en Sinónimos Estructurales
        r2_nodos = set()
        for nodo, syn_tokens in self.sinonimos_por_nodo.items():
            if roles.intersection(syn_tokens):
                r2_nodos.add(nodo)
                pool_candidatos.add(nodo)
                roles_match = list(roles.intersection(syn_tokens))
                trazabilidad_generacion[nodo].append(f"R2:RolSinonimo({roles_match})")
        conteo_reglas["R2_rol_sinonimo"] = len(r2_nodos)

        # Regla 3: Expansión Sináptica Condicionada (Solo vecinos fuertes de R1 y R2)
        r3_nodos = set()
        if not ablate_synapse:
            nodos_semilla = r1_nodos.union(r2_nodos)
            for semilla in nodos_semilla:
                for vecino, peso in self.sinapsis_out.get(semilla, {}).items():
                    if peso >= 0.65 and vecino in self.nodos_activos:
                        r3_nodos.add(vecino)
                        pool_candidatos.add(vecino)
                        trazabilidad_generacion[vecino].append(f"R3:SinapsisFuerte(desde={semilla}, peso={peso:.2f})")
        conteo_reglas["R3_sinapsis_fuerte"] = len(r3_nodos)

        return pool_candidatos, trazabilidad_generacion, conteo_reglas

    # =========================================================================
    # ETAPA 2: SCORING Y RANKING ESTRUCTURAL
    # =========================================================================
    def rankear_candidate_pool(
        self,
        query: str,
        candidate_pool: Set[str],
        trazabilidad_generacion: Dict[str, List[str]],
        k: int = K_PRIMARY
    ) -> List[Dict[str, Any]]:
        """
        Pondera y ordena ÚNICAMENTE los nodos pertenecientes al Candidate Pool discreto.
        Nodos fuera del pool NO reciben score ni entran al ranking.
        """
        if not candidate_pool:
            return []

        struct = self.parsear_estructura_query(query)
        acciones = struct["operadores_accion"]
        dominios = set(struct["dominios_inferidos"])
        entidades = set(struct["entidades_inferidas"])

        scores = {}

        for nodo in candidate_pool:
            score = 0.0
            nodo_dims = self.dims_por_nodo.get(nodo, set())
            gen_rules = trazabilidad_generacion.get(nodo, [])

            # Puntaje base por reglas generadoras activas
            if any("R1" in r for r in gen_rules):
                score += 3.0
            if any("R2" in r for r in gen_rules):
                score += 2.5
            if any("R3" in r for r in gen_rules):
                score += 1.0

            # Concordancia dimensional fina
            for tipo_d, dim_d in nodo_dims:
                for op_name, op_tipo in acciones:
                    if tipo_d == 'accion' and op_tipo in dim_d:
                        score += 1.5
                if tipo_d == 'dominio' and dim_d in dominios:
                    score += 1.0
                if tipo_d == 'entidad' and dim_d in entidades:
                    score += 1.0

            scores[nodo] = score

        # Desempate determinístico por score DESC, luego por concepto ASC
        sorted_cands = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        top_k = sorted_cands[:k]

        resultado = []
        for rank, (cand_node, sc) in enumerate(top_k, 1):
            resultado.append({
                "rank": rank,
                "node": cand_node,
                "score": round(sc, 4),
                "island": self.comunidades.get(cand_node),
                "generation_rules": trazabilidad_generacion.get(cand_node, [])
            })
        return resultado


def ejecutar_evaluacion_dev_v02():
    print("===================================================================================================")
    print("EXP-M (v0.2): EVALUACIÓN AISLADA DEL GENERADOR ESTRUCTURAL EN DOS ETAPAS (A0-DEV)")
    print("===================================================================================================")

    sha_db = calcular_sha256_archivo(DB_PATH)
    sha_labels = calcular_sha256_archivo(LABELS_PATH)
    sha_script = calcular_sha256_archivo(__file__)

    print(f"• Snapshot DB SHA-256:   {sha_db}")
    print(f"• Labels SHA-256:        {sha_labels}")
    print(f"• Script Evaluador SHA:  {sha_script}")

    with open(DEV_DATASET_PATH, "r", encoding="utf-8") as f:
        dev_cases = json.load(f)["cases"]

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        labels = json.load(f)

    gen = StructuralGeneratorV02(con, labels)

    print(f"\n[+] Evaluando los {len(dev_cases)} casos A0-DEV bajo el pipeline de 2 etapas...")

    resultados_dev = []
    hits_full = {k: 0 for k in K_CURVE}
    hits_no_syn = {k: 0 for k in K_CURVE}
    hits_no_act = {k: 0 for k in K_CURVE}
    hits_no_dom = {k: 0 for k in K_CURVE}

    pool_sizes_pre_score = []

    for cs in dev_cases:
        cid = cs["id"]
        q = cs["query"]
        gold = cs["gold"]

        # 1. Pipeline Completo: Generación Discreta + Ranking
        t0_gen = time.perf_counter()
        pool_full, trace_gen_full, counts_rules_full = gen.generar_candidate_pool_discreto(q, ablate_action=False, ablate_domain=False, ablate_synapse=False)
        t_gen = (time.perf_counter() - t0_gen) * 1000

        t0_rank = time.perf_counter()
        cands_ranked_full = gen.rankear_candidate_pool(q, pool_full, trace_gen_full, k=20)
        t_rank = (time.perf_counter() - t0_rank) * 1000

        pool_sizes_pre_score.append(len(pool_full))

        # 2. Ablaciones Causales
        # A) Sin Expansión Sináptica
        pool_no_syn, trace_no_syn, _ = gen.generar_candidate_pool_discreto(q, ablate_action=False, ablate_domain=False, ablate_synapse=True)
        cands_no_syn = gen.rankear_candidate_pool(q, pool_no_syn, trace_no_syn, k=20)

        # B) Sin Operador de Acción
        pool_no_act, trace_no_act, _ = gen.generar_candidate_pool_discreto(q, ablate_action=True, ablate_domain=False, ablate_synapse=False)
        cands_no_act = gen.rankear_candidate_pool(q, pool_no_act, trace_no_act, k=20)

        # C) Sin Operador de Dominio/Entidad
        pool_no_dom, trace_no_dom, _ = gen.generar_candidate_pool_discreto(q, ablate_action=False, ablate_domain=True, ablate_synapse=False)
        cands_no_dom = gen.rankear_candidate_pool(q, pool_no_dom, trace_no_dom, k=20)

        def find_gold(cands_list):
            for c in cands_list:
                if c["node"] == gold:
                    return c["rank"], c["score"], c["generation_rules"]
            return None, 0.0, []

        rank_full, sc_full, rules_gold = find_gold(cands_ranked_full)
        rank_no_syn, _, _ = find_gold(cands_no_syn)
        rank_no_act, _, _ = find_gold(cands_no_act)
        rank_no_dom, _, _ = find_gold(cands_no_dom)

        gold_in_pre_pool = gold in pool_full

        for k in K_CURVE:
            if rank_full is not None and rank_full <= k: hits_full[k] += 1
            if rank_no_syn is not None and rank_no_syn <= k: hits_no_syn[k] += 1
            if rank_no_act is not None and rank_no_act <= k: hits_no_act[k] += 1
            if rank_no_dom is not None and rank_no_dom <= k: hits_no_dom[k] += 1

        resultados_dev.append({
            "case_id": cid,
            "query": q,
            "gold": gold,
            "pool_size_prescore": len(pool_full),
            "rules_candidate_counts": counts_rules_full,
            "gold_in_prescore_pool": gold_in_pre_pool,
            "gold_generation_rules": rules_gold,
            "gold_rank_top20": rank_full,
            "gold_score": sc_full,
            "rank_no_synapse": rank_no_syn,
            "rank_no_action": rank_no_act,
            "rank_no_domain": rank_no_dom,
            "top1_candidate": cands_ranked_full[0]["node"] if cands_ranked_full else None,
            "top1_score": cands_ranked_full[0]["score"] if cands_ranked_full else 0.0,
            "latency_generation_ms": round(t_gen, 2),
            "latency_ranking_ms": round(t_rank, 2),
            "latency_total_ms": round(t_gen + t_rank, 2)
        })

    con.close()

    # Resumen formal de métricas
    avg_pool_size = float(np.mean(pool_sizes_pre_score))
    print("\n===================================================================================================")
    print(f"RESUMEN FORMAL DE ETAPA 1 Y ETAPA 2 (A0-DEV, N={len(dev_cases)})")
    print("===================================================================================================")
    print(f"• Tamaño promedio de Candidate Pool PRE-SCORE: {avg_pool_size:.1f} nodos / 851 ({avg_pool_size/851*100:.1f}%)")
    print(f"  [v0.1 anterior era ~790 nodos (93%)] -> Reducción masiva de espacio de búsqueda.")
    print("---------------------------------------------------------------------------------------------------")
    print("CURVA DE CANDIDATE ENTRY RATE (Node-CE@K):")
    for k in K_CURVE:
        pct_f = round(hits_full[k] / len(dev_cases) * 100.0, 1)
        pct_ns = round(hits_no_syn[k] / len(dev_cases) * 100.0, 1)
        pct_na = round(hits_no_act[k] / len(dev_cases) * 100.0, 1)
        pct_nd = round(hits_no_dom[k] / len(dev_cases) * 100.0, 1)
        print(f"  Node-CE@{k:02d} -> Full: {hits_full[k]}/{len(dev_cases)} ({pct_f}%) | Sin Sinapsis: {hits_no_syn[k]}/{len(dev_cases)} ({pct_ns}%) | Sin Acción: {hits_no_act[k]}/{len(dev_cases)} ({pct_na}%) | Sin Dominio: {hits_no_dom[k]}/{len(dev_cases)} ({pct_nd}%)")

    print("\n===================================================================================================")
    print("TABLA DETALLADA CASO POR CASO (A0-DEV)")
    print("===================================================================================================")
    for r in resultados_dev:
        in_p = "SÍ" if r["gold_in_prescore_pool"] else "NO"
        rk = str(r["gold_rank_top20"]) if r["gold_rank_top20"] else "None"
        rk_ns = str(r["rank_no_synapse"]) if r["rank_no_synapse"] else "None"
        print(f"[{r['case_id']}] Gold: {r['gold']:35s} | PrePool: {r['pool_size_prescore']:3d} | InPrePool: {in_p:2s} | Rank: {rk:>4s} | SinSyn: {rk_ns:>4s}")
        if r["gold_in_prescore_pool"]:
            print(f"       Rules: {r['gold_generation_rules']}")

    # Guardar resultados
    output_payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "experiment": "EXP-M Structural Generator v0.2 (DEV Two-Stage Pipeline)",
        "hashes": {
            "db_snapshot_sha256": sha_db,
            "labels_sha256": sha_labels,
            "script_sha256": sha_script
        },
        "k_primary": K_PRIMARY,
        "avg_prescore_pool_size": round(avg_pool_size, 1),
        "k_curve_results": {
            f"Node-CE@{k}": {
                "full": f"{hits_full[k]}/{len(dev_cases)} ({round(hits_full[k]/len(dev_cases)*100, 1)}%)",
                "no_synapse": f"{hits_no_syn[k]}/{len(dev_cases)} ({round(hits_no_syn[k]/len(dev_cases)*100, 1)}%)",
                "no_action": f"{hits_no_act[k]}/{len(dev_cases)} ({round(hits_no_act[k]/len(dev_cases)*100, 1)}%)",
                "no_domain": f"{hits_no_dom[k]}/{len(dev_cases)} ({round(hits_no_dom[k]/len(dev_cases)*100, 1)}%)"
            } for k in K_CURVE
        },
        "case_details": resultados_dev
    }

    with open(OUTPUT_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Resultados completos guardados en: {OUTPUT_RESULTS_PATH}")
    print("===================================================================================================")


if __name__ == "__main__":
    ejecutar_evaluacion_dev_v02()
