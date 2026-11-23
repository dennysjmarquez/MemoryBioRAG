#!/usr/bin/env python3
"""
scripts/test_ablacion_invarianza.py
Experimento de Ablación Controlada de Invarianza:
Compara Base A (851 nodos) vs Base B (10,851 nodos: +10,000 irrelevantes)
sobre los 61 casos de prueba 'sinonimo' de scripts/casos_qa_baseline_v1.jsonl.

Ablaciones evaluadas:
  - Modo 0: Baseline (+10k sin fijar nada)
  - Modo 1: Semillas Dims fijadas desde Base A
  - Modo 2: Semillas Cadena fijadas desde Base A
  - Modo 3: Dual (Dims + Cadena fijadas)
  - Modo 4: BM25_norm fijado desde Base A
  - Modo 5: Total (Dims + Cadena + BM25_norm fijados)

Garantías:
- Opera exclusivamente sobre copias en /tmp/.
- Snapshot canónica 100% de solo lectura.
- Guarda trazabilidad completa en docs/invarianza_ablacion_resultados_crudos.json.
"""

import sys
import os
import json
import shutil
import sqlite3
import hashlib
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

DEFAULT_SNAP = str(BASE_DIR / "snapshots" / "qa_escape_qcr_20260811.db")
DEFAULT_CASOS = str(BASE_DIR / "scripts" / "casos_qa_baseline_v1.jsonl")
OUTPUT_JSON = str(BASE_DIR / "docs" / "invarianza_ablacion_resultados_crudos.json")

TMP_A = "/tmp/ablacion_A.db"
TMP_B = "/tmp/ablacion_B.db"


def sha256_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def cargar_casos_sinonimo(ruta_jsonl):
    casos = []
    with open(ruta_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("categoria") == "sinonimo":
                casos.append({
                    "id": item.get("id"),
                    "query": item["query"],
                    "expected": item.get("concepto_esperado") or item.get("expected"),
                    "raw": item
                })
    return casos


def preparar_bases(snap_src, n_irrelevantes=10000):
    for f in [TMP_A, TMP_B]:
        if os.path.exists(f):
            os.remove(f)

    # Copia limpia sin tocar jamás la original
    shutil.copyfile(snap_src, TMP_A)
    shutil.copyfile(snap_src, TMP_B)

    conB = sqlite3.connect(TMP_B)
    # Lote de ruido 100% sintético y query-term-disjoint (sin palabras comunes del español)
    batch = [
        (
            f"nodo_ruido_hex_{i:05d}",
            f"ruido_rnd_block_{i:05d} hash_hex_{i*37%99991:05x} kterm_{i*13%88883:05x}",
            0.5,
            "activo"
        )
        for i in range(n_irrelevantes)
    ]
    conB.executemany(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado) VALUES (?, ?, ?, ?)",
        batch
    )
    conB.commit()
    conB.close()

    cA = sqlite3.connect(TMP_A)
    cB = sqlite3.connect(TMP_B)
    cntA = cA.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado='activo'").fetchone()[0]
    cntB = cB.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado='activo'").fetchone()[0]
    cA.close()
    cB.close()
    return cntA, cntB


class CursorProxy:
    """Wrapper para interceptar llamadas execute sobre cursor SQLite."""

    def __init__(self, orig_cursor, hook_fn):
        self._orig = orig_cursor
        self._hook = hook_fn

    def execute(self, sql, *args):
        return self._hook(self._orig, sql, *args)

    def executemany(self, sql, *args):
        return self._orig.executemany(sql, *args)

    def executescript(self, sql):
        return self._orig.executescript(sql)

    def fetchone(self):
        return self._orig.fetchone()

    def fetchall(self):
        return self._orig.fetchall()

    def fetchmany(self, size=None):
        return self._orig.fetchmany(size) if size is not None else self._orig.fetchmany()

    @property
    def rowcount(self):
        return self._orig.rowcount

    @property
    def lastrowid(self):
        return self._orig.lastrowid

    @property
    def description(self):
        return self._orig.description

    def __iter__(self):
        return iter(self._orig)

    def __getattr__(self, name):
        return getattr(self._orig, name)


class InterceptorBusqueda:
    """Envuelve e intercepta semillas y scores híbridos en una instancia SQLiteMemoryBioRAG."""

    def __init__(self, semillas_dims=None, semillas_cadena=None, scores_bm25=None):
        self.semillas_dims = semillas_dims or {}         # query -> [conceptos]
        self.semillas_cadena = semillas_cadena or {}     # query -> [conceptos]
        self.scores_bm25 = scores_bm25 or {}             # query -> {concepto: bm25_norm}
        self.capturadas_dims = {}                        # query -> [conceptos]
        self.capturadas_cadena = {}                      # query -> [conceptos]
        self.capturadas_hibrido = {}                     # query -> {concepto: componentes}
        self.query_actual = None
        self.concepto_actual = None
        self.cerebro = None

    def instalar(self, cerebro):
        self.cerebro = cerebro
        orig_cursor = cerebro.cursor
        orig_evocacion = cerebro._evocacion_por_cadena
        orig_hibrido = cerebro._calcular_score_hibrido

        import core.fallback_simbolico as fb_mod
        orig_ssc = fb_mod.score_simbolico_concepto

        # Hook en score_simbolico_concepto para saber qué concepto se está evaluando
        def hooked_ssc(tokens, concepto):
            self.concepto_actual = concepto
            return orig_ssc(tokens, concepto)

        fb_mod.score_simbolico_concepto = hooked_ssc

        def patched_execute(cur, sql, *params):
            if isinstance(sql, str) and "SELECT DISTINCT dimension_id" in sql and "FROM largo_plazo_dimensiones" in sql:
                if self.query_actual:
                    conceptos_peticion = list(params[0]) if params else []
                    if not self.capturadas_dims.get(self.query_actual):
                        self.capturadas_dims[self.query_actual] = conceptos_peticion

                    if self.query_actual in self.semillas_dims:
                        dims_fijas = self.semillas_dims[self.query_actual]
                        if dims_fijas:
                            placeholders = ",".join(["?" for _ in dims_fijas])
                            sql = f"""
                                SELECT DISTINCT dimension_id
                                FROM largo_plazo_dimensiones
                                WHERE concepto IN ({placeholders})
                            """
                            params = (dims_fijas,)

            return cur.execute(sql, *params)

        cerebro.cursor = CursorProxy(orig_cursor, patched_execute)

        def patched_evocacion(semillas, *args, **kwargs):
            if self.query_actual:
                if not self.capturadas_cadena.get(self.query_actual):
                    self.capturadas_cadena[self.query_actual] = list(semillas)

                if self.query_actual in self.semillas_cadena:
                    semillas_fijas = self.semillas_cadena[self.query_actual]
                    if semillas_fijas:
                        semillas = semillas_fijas

            return orig_evocacion(semillas, *args, **kwargs)

        cerebro._evocacion_por_cadena = patched_evocacion

        def patched_hibrido(**kwargs):
            conc = self.concepto_actual
            bm25_previo = kwargs.get("bm25_norm", 0.0)
            imputado = False
            bm25_inyectado = bm25_previo

            if self.query_actual and conc:
                if self.query_actual not in self.capturadas_hibrido:
                    self.capturadas_hibrido[self.query_actual] = {}

                # Inyección real de BM25_norm si está activa en Modo 4 / Modo 5
                if self.query_actual in self.scores_bm25:
                    if conc in self.scores_bm25[self.query_actual]:
                        bm25_inyectado = self.scores_bm25[self.query_actual][conc]
                    else:
                        bm25_inyectado = 0.0
                        imputado = True
                    kwargs["bm25_norm"] = bm25_inyectado

            sc_final = orig_hibrido(**kwargs)

            if self.query_actual and conc:
                self.capturadas_hibrido[self.query_actual][conc] = {
                    "bm25_norm": kwargs.get("bm25_norm", 0.0),
                    "bm25_previo_dinamico": bm25_previo,
                    "bm25_inyectado": bm25_inyectado,
                    "imputado_ausente_en_A": imputado,
                    "dim_score": kwargs.get("dim_score", 0.0),
                    "peso_sinaptico": kwargs.get("peso_sinaptico", 0.0),
                    "concepto_ratio": kwargs.get("concepto_ratio", 0.0),
                    "sinonimos_ratio": kwargs.get("sinonimos_ratio", 0.0),
                    "score_latente": kwargs.get("score_latente", 0.0),
                    "score_cadena": kwargs.get("score_cadena", 0.0),
                    "tematico_score": kwargs.get("tematico_score", 0.0),
                    "score_hibrido_pre_rerank": sc_final
                }

            return sc_final

        cerebro._calcular_score_hibrido = patched_hibrido


def ejecutar_evaluacion(db_path, casos, interceptor=None, ignore_peso=True):
    for mod in list(sys.modules.keys()):
        if mod.startswith("core.") or mod == "core":
            del sys.modules[mod]

    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path)

    if interceptor:
        interceptor.instalar(cerebro)

    resultados_casos = []
    resultados_por_query = {}

    for c in casos:
        q = c["query"]
        gold = c["expected"]

        if interceptor:
            interceptor.query_actual = q
            if q not in interceptor.capturadas_dims:
                interceptor.capturadas_dims[q] = []
            if q not in interceptor.capturadas_cadena:
                interceptor.capturadas_cadena[q] = []
            if q not in interceptor.capturadas_hibrido:
                interceptor.capturadas_hibrido[q] = {}

        pagina, _ = cerebro.buscar_por_frase(
            q,
            profundidad="activos",
            limite=5,
            ignore_peso_sinaptico=ignore_peso
        )

        top5 = [row[0] for row in pagina[:5]] if pagina else []
        top5_scores = [(row[0], round(row[4], 6)) for row in pagina[:5]] if pagina else []
        en_r5 = (gold in top5)
        en_r1 = (top5[0] == gold) if top5 else False

        if interceptor and pagina:
            for row in pagina:
                conc = row[0]
                sc_post = round(row[4], 6)
                if conc in interceptor.capturadas_hibrido.get(q, {}):
                    interceptor.capturadas_hibrido[q][conc]["score_postprocesado"] = sc_post

        res_caso = {
            "id": c["id"],
            "query": q,
            "gold": gold,
            "top5": top5,
            "top5_scores_postprocesados": top5_scores,
            "r5": en_r5,
            "r1": en_r1
        }
        resultados_casos.append(res_caso)

        if q not in resultados_por_query:
            resultados_por_query[q] = top5

    cerebro.cerrar_sistema()
    return resultados_casos, resultados_por_query


def comparar_con_base(res_base_casos, res_base_q, res_test_casos, res_test_q, marcas_ambiguedad):
    total_q = len(res_base_q)
    cambios_orden = 0
    detalles_cambio = []

    for q, top5_base in res_base_q.items():
        top5_test = res_test_q.get(q, [])
        if top5_base != top5_test:
            cambios_orden += 1
            detalles_cambio.append({
                "query": q,
                "top5_base": top5_base,
                "top5_test": top5_test
            })

    total_bruto = len(res_base_casos)
    aciertos_base_bruto = sum(1 for c in res_base_casos if c["r5"])
    aciertos_test_bruto = sum(1 for c in res_test_casos if c["r5"])

    perdidos_bruto = []
    ganados_bruto = []

    casos_filtrados_base = []
    casos_filtrados_test = []

    for c_base, c_test in zip(res_base_casos, res_test_casos):
        cid = c_base["id"]
        marca = marcas_ambiguedad.get(cid, {})
        es_ambiguo = marca.get("ambigua_r5", False)

        if c_base["r5"] and not c_test["r5"]:
            perdidos_bruto.append({**c_base, "top5_test": c_test["top5"], "ambiguo": es_ambiguo})
        elif not c_base["r5"] and c_test["r5"]:
            ganados_bruto.append({**c_test, "top5_base": c_base["top5"], "ambiguo": es_ambiguo})

        if not es_ambiguo:
            casos_filtrados_base.append(c_base)
            casos_filtrados_test.append(c_test)

    total_filtrado = len(casos_filtrados_base)
    aciertos_base_filt = sum(1 for c in casos_filtrados_base if c["r5"])
    aciertos_test_filt = sum(1 for c in casos_filtrados_test if c["r5"])

    # Cálculo independiente de cambios de orden para el subconjunto filtrado
    queries_filtradas = set(c["query"] for c in casos_filtrados_base)
    cambios_orden_filt = 0
    for q in queries_filtradas:
        if res_base_q.get(q) != res_test_q.get(q):
            cambios_orden_filt += 1

    perdidos_filt = [c for c in perdidos_bruto if not c.get("ambiguo")]
    ganados_filt = [c for c in ganados_bruto if not c.get("ambiguo")]

    return {
        "total_queries": total_q,
        "cambios_orden": cambios_orden,
        "bruto": {
            "total": total_bruto,
            "aciertos_base": aciertos_base_bruto,
            "aciertos_test": aciertos_test_bruto,
            "perdidos": len(perdidos_bruto),
            "ganados": len(ganados_bruto),
            "detalles_perdidos": perdidos_bruto,
            "detalles_ganados": ganados_bruto,
        },
        "filtrado": {
            "total": total_filtrado,
            "total_queries": len(queries_filtradas),
            "cambios_orden": cambios_orden_filt,
            "aciertos_base": aciertos_base_filt,
            "aciertos_test": aciertos_test_filt,
            "perdidos": len(perdidos_filt),
            "ganados": len(ganados_filt),
            "detalles_perdidos": perdidos_filt,
            "detalles_ganados": ganados_filt,
        },
        "detalles_cambio": detalles_cambio,
    }


def main():
    parser = argparse.ArgumentParser(description="Ablación controlada de invarianza de corpus.")
    parser.add_argument("--snap", default=DEFAULT_SNAP, help="Ruta al snapshot de referencia")
    parser.add_argument("--casos", default=DEFAULT_CASOS, help="Ruta al dataset de casos JSONL")
    parser.add_argument("--n-nodos", type=int, default=10000, help="Nodos irrelevantes en base B")
    parser.add_argument("--out-json", default=OUTPUT_JSON, help="Ruta para exportar resultados crudos JSON")
    parser.add_argument("--ignore-peso", action="store_true", default=True, help="ignore_peso_sinaptico (default: True)")
    args = parser.parse_args()

    print("=" * 80)
    print("BIORAG: EXPERIMENTO DE ABLACIÓN CONTROLADA DE INVARIANZA (REPORTE FORENSE EXHAUSTIVO)")
    print("=" * 80)

    hash_snap = sha256_archivo(args.snap)
    hash_casos = sha256_archivo(args.casos)

    print(f"Snapshot canónica: {args.snap}")
    print(f"  SHA-256: {hash_snap}")
    print(f"Dataset casos:    {args.casos}")
    print(f"  SHA-256: {hash_casos}")

    casos = cargar_casos_sinonimo(args.casos)
    queries_unicas = sorted(list(set(c["query"] for c in casos)))
    print(f"Casos 'sinonimo': {len(casos)} (Consultas únicas: {len(queries_unicas)})")

    print(f"Preparando bases temporales (B = A + {args.n_nodos} nodos en /tmp)...")
    cntA, cntB = preparar_bases(args.snap, args.n_nodos)
    print(f"Base A activos: {cntA} | Base B activos: {cntB}")

    # Clasificación de ambigüedad abierta desde la copia temporal TMP_A para no tocar jamás la snapshot original
    from core.memory_store import SQLiteMemoryBioRAG
    from scripts.evaluar_qa import clasificar_casos_sinonimo
    cerebro_temp = SQLiteMemoryBioRAG(TMP_A)
    raw_casos_para_clasif = [c["raw"] for c in casos]
    marcas_ambiguedad = clasificar_casos_sinonimo(cerebro_temp, raw_casos_para_clasif)
    cerebro_temp.cerrar_sistema()

    ambiguos_r5 = {cid: m for cid, m in marcas_ambiguedad.items() if m.get("ambigua_r5")}
    print(f"Casos clasificados ambigua_r5 (>5 reclamantes): {len(ambiguos_r5)}")
    print("-" * 80)

    # 1. Base A (Referencia canónica)
    print("1/7: Evaluando Base A (referencia canónica)...")
    interceptor_A = InterceptorBusqueda()
    res_A_casos, res_A_q = ejecutar_evaluacion(TMP_A, casos, interceptor_A, ignore_peso=args.ignore_peso)

    # Extraer mapa de bm25_norm de Base A
    mapa_bm25_A = {}
    for q, candidatos in interceptor_A.capturadas_hibrido.items():
        mapa_bm25_A[q] = {c: comp["bm25_norm"] for c, comp in candidatos.items()}

    # 2. Modo 0: Baseline en Base B
    print("2/7: Evaluando Modo 0: Baseline en Base B...")
    interceptor_M0 = InterceptorBusqueda()
    res_B0_casos, res_B0_q = ejecutar_evaluacion(TMP_B, casos, interceptor_M0, ignore_peso=args.ignore_peso)
    comp_M0 = comparar_con_base(res_A_casos, res_A_q, res_B0_casos, res_B0_q, marcas_ambiguedad)

    # 3. Modo 1: Semillas Dimensionales fijadas
    print("3/7: Evaluando Modo 1: Semillas Dimensionales FIJADAS...")
    interceptor_M1 = InterceptorBusqueda(semillas_dims=interceptor_A.capturadas_dims)
    res_B1_casos, res_B1_q = ejecutar_evaluacion(TMP_B, casos, interceptor_M1, ignore_peso=args.ignore_peso)
    comp_M1 = comparar_con_base(res_A_casos, res_A_q, res_B1_casos, res_B1_q, marcas_ambiguedad)

    # 4. Modo 2: Semillas Cadena fijadas
    print("4/7: Evaluando Modo 2: Semillas Cadena FIJADAS...")
    interceptor_M2 = InterceptorBusqueda(semillas_cadena=interceptor_A.capturadas_cadena)
    res_B2_casos, res_B2_q = ejecutar_evaluacion(TMP_B, casos, interceptor_M2, ignore_peso=args.ignore_peso)
    comp_M2 = comparar_con_base(res_A_casos, res_A_q, res_B2_casos, res_B2_q, marcas_ambiguedad)

    # 5. Modo 3: Dual (Dims + Cadena)
    print("5/7: Evaluando Modo 3: DUAL (Dims + Cadena FIJADAS)...")
    interceptor_M3 = InterceptorBusqueda(
        semillas_dims=interceptor_A.capturadas_dims,
        semillas_cadena=interceptor_A.capturadas_cadena
    )
    res_B3_casos, res_B3_q = ejecutar_evaluacion(TMP_B, casos, interceptor_M3, ignore_peso=args.ignore_peso)
    comp_M3 = comparar_con_base(res_A_casos, res_A_q, res_B3_casos, res_B3_q, marcas_ambiguedad)

    # 6. Modo 4: Intervención aislada en BM25_norm
    print("6/7: Evaluando Modo 4: BM25_NORM FIJADO desde Base A...")
    interceptor_M4 = InterceptorBusqueda(scores_bm25=mapa_bm25_A)
    res_B4_casos, res_B4_q = ejecutar_evaluacion(TMP_B, casos, interceptor_M4, ignore_peso=args.ignore_peso)
    comp_M4 = comparar_con_base(res_A_casos, res_A_q, res_B4_casos, res_B4_q, marcas_ambiguedad)

    # 7. Modo 5: Intervención Total (Dims + Cadena + BM25_norm)
    print("7/7: Evaluando Modo 5: TOTAL (Dims + Cadena + BM25_norm FIJADOS)...")
    interceptor_M5 = InterceptorBusqueda(
        semillas_dims=interceptor_A.capturadas_dims,
        semillas_cadena=interceptor_A.capturadas_cadena,
        scores_bm25=mapa_bm25_A
    )
    res_B5_casos, res_B5_q = ejecutar_evaluacion(TMP_B, casos, interceptor_M5, ignore_peso=args.ignore_peso)
    comp_M5 = comparar_con_base(res_A_casos, res_A_q, res_B5_casos, res_B5_q, marcas_ambiguedad)

    # Reporte JSON Crudo Completo
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    reporte_crudo = {
        "metadata": {
            "snapshot_path": args.snap,
            "snapshot_sha256": hash_snap,
            "dataset_path": args.casos,
            "dataset_sha256": hash_casos,
            "n_nodos_irrelevantes": args.n_nodos,
            "activos_base_A": cntA,
            "activos_base_B": cntB,
            "total_casos_sinonimo": len(casos),
            "total_consultas_unicas": len(queries_unicas),
            "eval_params": {
                "profundidad": "activos",
                "limite": 5,
                "ignore_peso_sinaptico": args.ignore_peso,
                "context_window": 0,
                "usar_inferencia": True
            }
        },
        "semillas_referencia_base_A": {
            "dims": interceptor_A.capturadas_dims,
            "cadena": interceptor_A.capturadas_cadena,
            "scores_hibrido_detalle": interceptor_A.capturadas_hibrido
        },
        "marcas_ambiguedad": marcas_ambiguedad,
        "condiciones": {
            "Base_A": {
                "casos": res_A_casos,
                "top5_por_query": res_A_q,
                "semillas_dims": interceptor_A.capturadas_dims,
                "semillas_cadena": interceptor_A.capturadas_cadena,
                "scores_hibrido_detalle": interceptor_A.capturadas_hibrido,
            },
            "Modo_0_Baseline": {
                "comp": comp_M0,
                "casos": res_B0_casos,
                "top5_por_query": res_B0_q,
                "semillas_dims": interceptor_M0.capturadas_dims,
                "semillas_cadena": interceptor_M0.capturadas_cadena,
                "scores_hibrido_detalle": interceptor_M0.capturadas_hibrido,
            },
            "Modo_1_DimsFijadas": {
                "comp": comp_M1,
                "casos": res_B1_casos,
                "top5_por_query": res_B1_q,
                "semillas_dims": interceptor_M1.capturadas_dims,
                "semillas_cadena": interceptor_M1.capturadas_cadena,
                "scores_hibrido_detalle": interceptor_M1.capturadas_hibrido,
            },
            "Modo_2_CadenaFijada": {
                "comp": comp_M2,
                "casos": res_B2_casos,
                "top5_por_query": res_B2_q,
                "semillas_dims": interceptor_M2.capturadas_dims,
                "semillas_cadena": interceptor_M2.capturadas_cadena,
                "scores_hibrido_detalle": interceptor_M2.capturadas_hibrido,
            },
            "Modo_3_DualFijada": {
                "comp": comp_M3,
                "casos": res_B3_casos,
                "top5_por_query": res_B3_q,
                "semillas_dims": interceptor_M3.capturadas_dims,
                "semillas_cadena": interceptor_M3.capturadas_cadena,
                "scores_hibrido_detalle": interceptor_M3.capturadas_hibrido,
            },
            "Modo_4_BM25Fijado": {
                "comp": comp_M4,
                "casos": res_B4_casos,
                "top5_por_query": res_B4_q,
                "semillas_dims": interceptor_M4.capturadas_dims,
                "semillas_cadena": interceptor_M4.capturadas_cadena,
                "scores_hibrido_detalle": interceptor_M4.capturadas_hibrido,
            },
            "Modo_5_TotalFijado": {
                "comp": comp_M5,
                "casos": res_B5_casos,
                "top5_por_query": res_B5_q,
                "semillas_dims": interceptor_M5.capturadas_dims,
                "semillas_cadena": interceptor_M5.capturadas_cadena,
                "scores_hibrido_detalle": interceptor_M5.capturadas_hibrido,
            },
        }
    }

    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(reporte_crudo, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("CONSOLIDADO 1: EVALUACIÓN SIN FILTRAR (TOTAL = 61 CASOS)")
    print("=" * 80)
    print(f"{'Condición':<34} | {'Top-5 Alterado':<16} | {'R@5 Aciertos':<12} | {'Perdidos / Ganados'}")
    print("-" * 80)
    print(f"{'Base A (Referencia canónica)':<34} | {'0/58 (0.0%)':<16} | {comp_M0['bruto']['aciertos_base']}/61      | 0 / 0")

    condiciones_print = [
        ("Modo 0: Baseline (+10k sin fijar)", comp_M0),
        ("Modo 1: Semillas Dims fijadas", comp_M1),
        ("Modo 2: Semillas Cadena fijadas", comp_M2),
        ("Modo 3: Dual (Dims + Cadena)", comp_M3),
        ("Modo 4: BM25_norm fijado", comp_M4),
        ("Modo 5: Total (Dims + Cad + BM25)", comp_M5),
    ]

    for nombre, comp in condiciones_print:
        s_alt = f"{comp['cambios_orden']}/58"
        s_r5 = f"{comp['bruto']['aciertos_test']}/61"
        s_pg = f"{comp['bruto']['perdidos']} / {comp['bruto']['ganados']}"
        print(f"{nombre:<34} | {s_alt:<16} | {s_r5:<12} | {s_pg}")

    print("\n" + "=" * 80)
    print(f"CONSOLIDADO 2: EVALUACIÓN HONESTA / FILTRADA (TOTAL = {comp_M0['filtrado']['total']} CASOS NO AMBIGUOS)")
    print("=" * 80)
    print(f"{'Condición':<34} | {'Top-5 Alterado':<16} | {'R@5 Aciertos':<12} | {'Perdidos / Ganados'}")
    print("-" * 80)
    s_alt_base = f"0/{comp_M0['filtrado']['total_queries']} (0.0%)"
    print(f"{'Base A (Referencia canónica)':<34} | {s_alt_base:<16} | {comp_M0['filtrado']['aciertos_base']}/{comp_M0['filtrado']['total']}      | 0 / 0")

    for nombre, comp in condiciones_print:
        s_alt = f"{comp['filtrado']['cambios_orden']}/{comp['filtrado']['total_queries']}"
        s_r5 = f"{comp['filtrado']['aciertos_test']}/{comp['filtrado']['total']}"
        s_pg = f"{comp['filtrado']['perdidos']} / {comp['filtrado']['ganados']}"
        print(f"{nombre:<34} | {s_alt:<16} | {s_r5:<12} | {s_pg}")

    print("=" * 80)
    print(f"\nReporte JSON crudo guardado en: {args.out_json}")

    for f in [TMP_A, TMP_B]:
        if os.path.exists(f):
            os.remove(f)
    print("Bases temporales eliminadas. Sistema limpio.\n")


if __name__ == "__main__":
    main()
