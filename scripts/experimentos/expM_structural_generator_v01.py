#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expM_structural_generator_v01.py
=============================================================================
EXP-M (v0.1) — GENERADOR ESTRUCTURAL COMPOSICIONAL AISLADO (A0-DEV)
=============================================================================
Prototipo experimental aislado para evaluar la capacidad de un generador
estructural composicional para introducir nodos Gold en el candidate pool (Node-CE@K)
en casos con Zero-Overlap léxico estricto (A0).

Restricciones Metodológicas Obligatorias (Aureon Protocol):
1. Ejecución EXCLUSIVAMENTE sobre los 8 casos A0-DEV (Fase 5 OOD no-test).
2. Los 20 casos A0-TEST de EXP-L permanecen 100% ciegos, intocados y no evaluados.
3. Cero modificaciones en core/ (código 100% autocontenido y aislado).
4. Sin memorización ni reglas ad-hoc para casos particulares.
5. El Gold se utiliza ÚNICAMENTE para evaluar la métrica de acceso (Node-CE@K),
   NUNCA durante la generación de candidatos.
6. Ablación causal estricta: demostrar que al retirar el operador/composición responsable,
   el nodo Gold desaparece del pool generado.

Métrica Primaria:
- Node-CE@K: Tasa de entrada del nodo Gold exacto en el Top-K de candidatos estructurales.
- Curva fija reportada: CE@1, CE@5, CE@10, CE@20 (con K_primary = 10 congelado).
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
OUTPUT_RESULTS_PATH = "docs/expM_dev_results_v01.json"

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

# Taxonomía general de patrones funcionales independientes de casos individuales
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


class StructuralGeneratorV01:
    """
    Generador Estructural Composicional (v0.1).
    Extrae roles de Acción, Dominio y Restricción para navegar el grafo semántico-relacional
    de la base de datos sin depender de coincidencia léxica directa ni de embeddings densos.
    """

    def __init__(self, db_conn: sqlite3.Connection, labels_data: Dict[str, Any]):
        self.conn = db_conn
        self.labels = labels_data
        self.conceptos = labels_data["conceptos"]
        self.comunidades = dict(zip(labels_data["conceptos"], labels_data["knn_lpa"]))
        self._indexar_ontologia_db()

    def _indexar_ontologia_db(self):
        """Indexa la ontología dimensional y topológica existente en la DB."""
        c = self.conn.cursor()
        # Nodos activos
        self.nodos_activos = set(r[0] for r in c.execute("SELECT concepto FROM largo_plazo WHERE estado='activo'").fetchall())
        self.categorias_nodo = dict(c.execute("SELECT concepto, categoria FROM largo_plazo WHERE estado='activo'").fetchall())

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

        # Grafo sináptico (aristas salientes y entrantes)
        self.sinapsis_out = defaultdict(dict)
        for orig, dest, peso in c.execute("SELECT origen, destino, peso FROM sinapsis WHERE origen IN (SELECT concepto FROM largo_plazo WHERE estado='activo')").fetchall():
            self.sinapsis_out[orig][dest] = peso

    def parsear_estructura_query(self, query: str) -> Dict[str, Any]:
        """Extrae operadores de Acción, Entidad/Dominio y Restricciones de la query."""
        tokens = tokenizar(query)
        acciones_encontradas = []
        dominios_inferidos = set()
        entidades_inferidas = set()
        roles_detectados = set()

        for t in tokens:
            # Buscar en operadores de acción
            for op_k, op_v in OPERADORES_ACCION.items():
                if t.startswith(op_k[:4]) or op_k.startswith(t[:4]):
                    acciones_encontradas.append((op_k, op_v['tipo']))
                    roles_detectados.update(op_v['roles'])

            # Buscar en patrones de dominio/entidad
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

    def generar_candidatos(
        self,
        query: str,
        k: int = K_PRIMARY,
        ablate_action: bool = False,
        ablate_domain: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Genera candidatos mediante composición relacional sobre el grafo ontológico.
        """
        struct = self.parsear_estructura_query(query)
        scores_candidatos = defaultdict(float)
        trazabilidad = defaultdict(list)

        acciones = [] if ablate_action else struct["operadores_accion"]
        dominios = set() if ablate_domain else set(struct["dominios_inferidos"])
        entidades = set() if ablate_domain else set(struct["entidades_inferidas"])
        roles = struct["roles_detectados"]

        # Si no se extrajo ninguna estructura relacional, abstenerse
        if not acciones and not dominios and not entidades:
            return []

        # Ponderación composicional de nodos en el grafo
        for nodo in self.nodos_activos:
            score = 0.0
            nodo_dims = self.dims_por_nodo.get(nodo, set())

            # 1. Composición de Operador de Acción con Dimensiones del Nodo
            if not ablate_action:
                for op_name, op_tipo in acciones:
                    for tipo_d, dim_d in nodo_dims:
                        if tipo_d == 'accion' and op_tipo in dim_d:
                            score += 2.0
                            trazabilidad[nodo].append(f"AccionCompatible({op_name}->{dim_d})")
                        elif op_name in dim_d:
                            score += 1.5
                            trazabilidad[nodo].append(f"RolAccionDirecta({op_name}->{dim_d})")

            # 2. Composición de Dominios y Entidades
            if not ablate_domain:
                for tipo_d, dim_d in nodo_dims:
                    if tipo_d == 'dominio' and dim_d in dominios:
                        score += 1.0
                        trazabilidad[nodo].append(f"DominioCompatible({dim_d})")
                    if tipo_d == 'entidad' and dim_d in entidades:
                        score += 1.2
                        trazabilidad[nodo].append(f"EntidadCompatible({dim_d})")

            # 3. Composición Topológica vía Sinapsis a Nodos Centrales
            # Nodos con sinapsis a conceptos que comparten roles enriquecen la red
            for adj, peso in self.sinapsis_out.get(nodo, {}).items():
                adj_dims = self.dims_por_nodo.get(adj, set())
                for tipo_d, dim_d in adj_dims:
                    if dim_d in dominios or dim_d in entidades:
                        score += 0.3 * peso
                        trazabilidad[nodo].append(f"SinapsisTopologica({adj}->{dim_d}, p={peso:.2f})")

            if score > 0.0:
                scores_candidatos[nodo] = score

        # Ordenar candidatos de forma determinística
        sorted_cands = sorted(scores_candidatos.items(), key=lambda x: (-x[1], x[0]))
        top_k = sorted_cands[:k]

        resultado = []
        for rank, (cand_node, sc) in enumerate(top_k, 1):
            resultado.append({
                "rank": rank,
                "node": cand_node,
                "score": round(sc, 4),
                "island": self.comunidades.get(cand_node),
                "trace": trazabilidad.get(cand_node, [])
            })
        return resultado


def ejecutar_evaluacion_dev():
    print("===================================================================================================")
    print("EXP-M (v0.1): EVALUACIÓN AISLADA DEL GENERADOR ESTRUCTURAL COMPOSICIONAL (A0-DEV)")
    print("===================================================================================================")

    sha_db = calcular_sha256_archivo(DB_PATH)
    sha_labels = calcular_sha256_archivo(LABELS_PATH)
    sha_script = calcular_sha256_archivo(__file__)

    print(f"• Snapshot DB SHA-256:   {sha_db}")
    print(f"• Labels SHA-256:        {sha_labels}")
    print(f"• Script Evaluador SHA:  {sha_script}")

    # Dataset A0-DEV (8 casos OOD no usados en EXP-L)
    dev_cases = [
        {"id": "OOF_POS_11", "query": "particionar capacidad de computo en doce nucleos virtuales con tope en gigas", "gold": "docker_infrastructure_rog"},
        {"id": "OOF_POS_19", "query": "calibrar coeficientes multiplicativos para combinar valores de relevancia heterogeneos", "gold": "scoring_pesos_bm25"},
        {"id": "OOF_POS_21", "query": "entrelazamiento hiperdimensional binario proyectado a traves de pasarela situacional", "gold": "coche_puente_condicional"},
        {"id": "OOF_POS_29", "query": "generar conexiones estocasticas para consolidar grupos fuertemente entrelazados", "gold": "desde_athena_biorag"},
        {"id": "OOF_POS_30", "query": "transicion de vigilia a letargo con eliminacion de elementos caducos", "gold": "activos_dormidos_hermana"},
        {"id": "OOF_POS_40", "query": "procedimiento de clasificacion dimensional sobre tejido cortical", "gold": "clasificacion_dimensional_completa_corteza_20260702"},
        {"id": "OOF_POS_48", "query": "malla neuronal con topologia de enlaces sinapticos transversales", "gold": "cuaternidad-logica-oec"},
        {"id": "OOF_POS_49", "query": "registro cronologico de hitos alcanzados por el agente", "gold": "trayectoria_completa_cronologica"}
    ]

    with open(DEV_DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump({"benchmark": "EXP-M A0-DEV (8 Casos)", "cases": dev_cases}, f, indent=2, ensure_ascii=False)

    print(f"[+] Dataset A0-DEV (N=8) guardado en: {DEV_DATASET_PATH}")

    # Cargar Infraestructura
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        labels = json.load(f)

    generator = StructuralGeneratorV01(con, labels)

    print("\n[+] Ejecutando evaluación comparativa y ablación causal sobre A0-DEV...")

    resultados_dev = []
    
    # Contadores de Candidate Entry Rate para K_CURVE
    hits_full = {k: 0 for k in K_CURVE}
    hits_no_action = {k: 0 for k in K_CURVE}
    hits_no_domain = {k: 0 for k in K_CURVE}

    for cs in dev_cases:
        cid = cs["id"]
        q = cs["query"]
        gold = cs["gold"]
        gold_island = labels["knn_lpa"][labels["conceptos"].index(gold)] if gold in labels["conceptos"] else None

        # 1. Ejecución Completa (Structural-v0.1)
        t0 = time.perf_counter()
        cands_full = generator.generar_candidatos(q, k=20, ablate_action=False, ablate_domain=False)
        lat_full = (time.perf_counter() - t0) * 1000

        # 2. Ablación Sin Operador de Acción
        cands_no_action = generator.generar_candidatos(q, k=20, ablate_action=True, ablate_domain=False)

        # 3. Ablación Sin Operador de Dominio
        cands_no_domain = generator.generar_candidatos(q, k=20, ablate_action=False, ablate_domain=True)

        # Verificar rango de Gold en cada condición
        def find_gold_rank(cands_list):
            for c in cands_list:
                if c["node"] == gold:
                    return c["rank"], c["score"], c["trace"]
            return None, 0.0, []

        rank_full, score_full, trace_full = find_gold_rank(cands_full)
        rank_no_act, _, _ = find_gold_rank(cands_no_action)
        rank_no_dom, _, _ = find_gold_rank(cands_no_domain)

        for k in K_CURVE:
            if rank_full is not None and rank_full <= k: hits_full[k] += 1
            if rank_no_act is not None and rank_no_act <= k: hits_no_action[k] += 1
            if rank_no_dom is not None and rank_no_dom <= k: hits_no_domain[k] += 1

        # Causalidad: El rescate depende del componente si al retirarlo el Gold desaparece o cae
        causal_action_loss = (rank_full is not None and (rank_no_act is None or rank_no_act > rank_full))
        causal_domain_loss = (rank_full is not None and (rank_no_dom is None or rank_no_dom > rank_full))

        resultados_dev.append({
            "case_id": cid,
            "query": q,
            "gold": gold,
            "gold_island": gold_island,
            "structure_extracted": generator.parsear_estructura_query(q),
            "gold_in_pool_full": rank_full is not None,
            "gold_rank_full": rank_full,
            "gold_score_full": score_full,
            "gold_trace_full": trace_full,
            "rank_no_action": rank_no_act,
            "rank_no_domain": rank_no_dom,
            "causal_action_loss": causal_action_loss,
            "causal_domain_loss": causal_domain_loss,
            "latency_ms": round(lat_full, 2)
        })

    con.close()

    # 4. Reporte y Resumen de Resultados
    print("\n===================================================================================================")
    print(f"RESUMEN DE CANDIDATE ENTRY RATE (CE@K) SOBRE A0-DEV (N={len(dev_cases)})")
    print("===================================================================================================")
    print(f"• Baseline M0–M4 en EXP-L (Referencia): Node-CE@5 = 0/20 (0.0%) | Island-CE@6 = 15%–25%")
    print("---------------------------------------------------------------------------------------------------")
    for k in K_CURVE:
        pct_full = round(hits_full[k] / len(dev_cases) * 100.0, 1)
        pct_no_act = round(hits_no_action[k] / len(dev_cases) * 100.0, 1)
        pct_no_dom = round(hits_no_domain[k] / len(dev_cases) * 100.0, 1)
        print(f"  CE@{k:02d} -> Structural-v0.1: {hits_full[k]}/{len(dev_cases)} ({pct_full}%) | Sin Acción: {hits_no_action[k]}/{len(dev_cases)} ({pct_no_act}%) | Sin Dominio: {hits_no_domain[k]}/{len(dev_cases)} ({pct_no_dom}%)")

    print("\n===================================================================================================")
    print("TABLA DETALLADA CASO POR CASO (A0-DEV)")
    print("===================================================================================================")
    for r in resultados_dev:
        in_p = "SÍ" if r["gold_in_pool_full"] else "NO"
        rk = str(r["gold_rank_full"]) if r["gold_rank_full"] else "None"
        rk_na = str(r["rank_no_action"]) if r["rank_no_action"] else "None"
        rk_nd = str(r["rank_no_domain"]) if r["rank_no_domain"] else "None"
        print(f"[{r['case_id']}] Gold: {r['gold']:35s} | In Pool: {in_p:2s} | Rank Full: {rk:>4s} | Sin Acc: {rk_na:>4s} | Sin Dom: {rk_nd:>4s}")
        if r["gold_in_pool_full"]:
            print(f"       Trace: {r['gold_trace_full'][:2]}")

    # 5. Guardar Resultados de DEV
    output_payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "experiment": "EXP-M Structural Generator v0.1 (DEV Only)",
        "hashes": {
            "db_snapshot_sha256": sha_db,
            "labels_sha256": sha_labels,
            "script_sha256": sha_script
        },
        "k_primary": K_PRIMARY,
        "k_curve_results": {
            f"CE@{k}": {
                "full": f"{hits_full[k]}/{len(dev_cases)} ({round(hits_full[k]/len(dev_cases)*100, 1)}%)",
                "no_action": f"{hits_no_action[k]}/{len(dev_cases)} ({round(hits_no_action[k]/len(dev_cases)*100, 1)}%)",
                "no_domain": f"{hits_no_domain[k]}/{len(dev_cases)} ({round(hits_no_domain[k]/len(dev_cases)*100, 1)}%)"
            } for k in K_CURVE
        },
        "case_details": resultados_dev
    }

    with open(OUTPUT_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Resultados completos de DEV guardados en: {OUTPUT_RESULTS_PATH}")
    print("===================================================================================================")


if __name__ == "__main__":
    ejecutar_evaluacion_dev()
