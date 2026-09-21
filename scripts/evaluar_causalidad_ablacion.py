#!/usr/bin/env python3
"""
Evaluación de Causalidad y Ablación Formal — BioRAG v32.0.

Responde directamente al escrutinio científico y a la auditoría metodológica:
¿Cuál es el impacto causal individual y conjunto de cada mecanismo cognitivo?

Condiciones experimentales evaluadas:
  [A] Motor base sin Hub ni boost de sustantivos
  [B] Motor base + Concept Hub
  [C] Motor base + Sustantivos Clave
  [D] Motor base + Hub + Sustantivos (v32.0)

Métricas reportadas por condición:
  - Recall@1, Recall@5, MRR
  - Rescates netos (Casos que fallaban en A y son resueltos en B/C/D)
  - Daños/Regresiones netas (Casos que pasaban en A y fallan en B/C/D)
  - Casos neutros (Sin cambio de resultado)
  - Desglose de procedencia de candidato ganador (Candidate Provenance)
"""

import os
import sys
import json
import time
import shutil
import tempfile
import argparse
import unicodedata
import re
from collections import defaultdict

# Raíz del workspace
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from core.memory_store import SQLiteMemoryBioRAG


def _normalizar(txt):
    if not txt:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFKD", txt)
        if not unicodedata.combining(c)
    ).lower().strip()


def _clave_normalizada(txt):
    return re.sub(r"[^a-z0-9]+", "", _normalizar(txt))


def cargar_casos(ruta_jsonl, limite=None, estratificado=False):
    casos = []
    with open(ruta_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            # Omitir negativos en evaluación de ranking retrieval
            if item.get("categoria") == "negativo":
                continue
            casos.append(item)

    if estratificado and limite:
        por_cat = defaultdict(list)
        for c in casos:
            por_cat[c["categoria"]].append(c)
        seleccionados = []
        cuota = max(1, limite // len(por_cat))
        for cat, items in por_cat.items():
            seleccionados.extend(items[:cuota])
        return seleccionados[:limite]

    if limite:
        return casos[:limite]
    return casos


def ejecutar_evaluacion_causal(db_path, casos, verbose=False):
    # Crear copia de base de datos para aislamiento experimental total
    temp_dir = tempfile.mkdtemp(prefix="biorag_ablacion_")
    isolated_db = os.path.join(temp_dir, "eval_ablacion.db")
    shutil.copyfile(db_path, isolated_db)
    os.environ["BIORAG_PATH"] = isolated_db
    os.environ["BIORAG_NO_LOG"] = "1"

    bio = SQLiteMemoryBioRAG(isolated_db)

    # Captura estado inicial para aislar queries entre sí
    estado_inicial_nodos = {
        r[0]: (r[1], r[2])
        for r in bio.cursor.execute("SELECT concepto, estado, peso_sinaptico FROM largo_plazo").fetchall()
    }

    condiciones = [
        {"id": "A", "nombre": "Motor base sin Hub ni boost de sustantivos", "hub": "0", "boost": None},
        {"id": "B", "nombre": "Motor base + Concept Hub",                  "hub": "1", "boost": None},
        {"id": "C", "nombre": "Motor base + Sustantivos Clave",            "hub": "0", "boost": 1.5},
        {"id": "D", "nombre": "Motor base + Hub + Sustantivos (v32.0)",    "hub": "1", "boost": 1.5},
    ]

    resultados_condicion = {c["id"]: {"hits_1": 0, "hits_5": 0, "mrr_sum": 0.0, "total": 0, "ranks": {}} for c in condiciones}
    provenance_top1 = {c["id"]: defaultdict(int) for c in condiciones}

    def restaurar_estado_nodos():
        actual = bio.cursor.execute(
            "SELECT concepto, estado, peso_sinaptico FROM largo_plazo"
        ).fetchall()
        cambias = []
        for concepto, estado, peso in actual:
            original = estado_inicial_nodos.get(concepto)
            if original and (original[0] != estado or original[1] != peso):
                cambias.append((original[0], original[1], concepto))
        if cambias:
            bio.cursor.executemany(
                "UPDATE largo_plazo SET estado = ?, peso_sinaptico = ? WHERE concepto = ?",
                cambias,
            )
            bio.conn.commit()

    total_casos = len(casos)
    print(f"\n[INFO] Iniciando evaluación causal A/B/C/D sobre {total_casos} casos...")

    for idx, c in enumerate(casos, 1):
        case_id = str(c.get("id", idx))
        query = c["query"]
        expected = c.get("concepto_esperado")
        expected_clave = _clave_normalizada(expected) if expected else ""

        if verbose or idx % 10 == 0 or idx == total_casos:
            print(f"  Progreso: {idx}/{total_casos} (Caso {case_id}: {query[:35]}...)")

        for cond in condiciones:
            cid = cond["id"]
            os.environ["BIORAG_HUB_ENABLED"] = cond["hub"]
            boost_val = cond["boost"]

            # Restaurar nodos solo si fueron mutados
            restaurar_estado_nodos()

            res, _ = bio.buscar_por_frase(query, limite=5, sustantivos_clave_boost=boost_val)
            prov = bio.obtener_provenance_ultimo_resultado()

            # Determinar rank del esperado
            rank = None
            for r_idx, r in enumerate(res, 1):
                conc_name = r[0] if isinstance(r, (tuple, list)) else r.get("concepto", "")
                if _clave_normalizada(conc_name) == expected_clave or conc_name == expected:
                    rank = r_idx
                    break

            # Registrar stats
            resultados_condicion[cid]["total"] += 1
            resultados_condicion[cid]["ranks"][case_id] = rank

            if rank == 1:
                resultados_condicion[cid]["hits_1"] += 1
            if rank is not None and rank <= 5:
                resultados_condicion[cid]["hits_5"] += 1
                resultados_condicion[cid]["mrr_sum"] += 1.0 / rank

            # Provenance del ganador Top-1
            if prov and prov.get("candidatos"):
                top_cand = prov["candidatos"][0]
                orig = top_cand.get("origen_candidato", "desconocido")
                provenance_top1[cid][orig] += 1

    # Cleanup temp
    try:
        bio.cerrar_sistema()
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    # Calcular Causalidad (Rescates, Daños, Neutros frente a Baseline A)
    analisis_causal = {}
    ranks_A = resultados_condicion["A"]["ranks"]

    for cid in ["B", "C", "D"]:
        rescates = []
        danos = []
        neutros = 0
        ranks_exp = resultados_condicion[cid]["ranks"]

        for case_id, rank_a in ranks_A.items():
            rank_x = ranks_exp.get(case_id)
            pass_a = (rank_a is not None and rank_a <= 5)
            pass_x = (rank_x is not None and rank_x <= 5)

            if not pass_a and pass_x:
                rescates.append({"id": case_id, "rank_baseline": rank_a, "rank_experimental": rank_x})
            elif pass_a and not pass_x:
                danos.append({"id": case_id, "rank_baseline": rank_a, "rank_experimental": rank_x})
            else:
                neutros += 1

        analisis_causal[cid] = {
            "rescates_count": len(rescates),
            "danos_count": len(danos),
            "neutros_count": neutros,
            "balance_neto": len(rescates) - len(danos),
            "detalles_rescates": rescates,
            "detalles_danos": danos
        }

    return {
        "total_casos": total_casos,
        "condiciones": resultados_condicion,
        "causalidad": analisis_causal,
        "provenance": {k: dict(v) for k, v in provenance_top1.items()}
    }


def imprimir_reporte(resultados, salida_md=None, salida_json=None):
    total = resultados["total_casos"]
    conds = resultados["condiciones"]
    causal = resultados["causalidad"]
    prov = resultados["provenance"]

    lineas = []
    lineas.append("# INFORME DE CAUSALIDAD Y ABLACIÓN EXPERIMENTAL — BioRAG v32.0\n")
    lineas.append(f"**Fecha:** {time.strftime('%Y-%m-%d %H:%M:%S')}  ")
    lineas.append(f"**Total Casos Evaluados:** {total} consultas  \n")

    lineas.append("## 1. Rendimiento Comparativo por Condición Experimental\n")
    lineas.append("| Condición | R@1 (%) | R@5 (%) | MRR | Rescates vs A | Daños vs A | Balance Neto |")
    lineas.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")

    nombres = {
        "A": "Motor base sin Hub ni boost de sustantivos",
        "B": "Motor base + Concept Hub",
        "C": "Motor base + Sustantivos Clave",
        "D": "Motor base + Hub + Sustantivos (v32.0)"
    }

    for cid in ["A", "B", "C", "D"]:
        c_stat = conds[cid]
        r1 = (c_stat["hits_1"] / total) * 100
        r5 = (c_stat["hits_5"] / total) * 100
        mrr = c_stat["mrr_sum"] / total
        if cid == "A":
            rescates = "-"
            danos = "-"
            neto = "Línea Base"
        else:
            c_info = causal[cid]
            rescates = str(c_info["rescates_count"])
            danos = str(c_info["danos_count"])
            neto = f"+{c_info['balance_neto']}" if c_info['balance_neto'] >= 0 else str(c_info['balance_neto'])
        lineas.append(f"| **[{cid}] {nombres[cid]}** | {r1:.2f}% | {r5:.2f}% | {mrr:.4f} | {rescates} | {danos} | **{neto}** |")

    lineas.append("\n## 2. Atribución Causal de Mecanismos (Veredicto de Rescates y Regresiones)\n")
    for cid in ["B", "C", "D"]:
        c_info = causal[cid]
        lineas.append(f"### Condición [{cid}] {nombres[cid]}")
        lineas.append(f"- **Casos Rescatados:** {c_info['rescates_count']} consultas (que fallaban sin este mecanismo y ahora se recuperan en Top-5)")
        lineas.append(f"- **Casos Perjudicados (Daños/Regresiones):** {c_info['danos_count']} consultas")
        lineas.append(f"- **Casos Neutros:** {c_info['neutros_count']} consultas")
        lineas.append(f"- **Impacto Neto:** {'+' if c_info['balance_neto'] >= 0 else ''}{c_info['balance_neto']} casos ganados netos\n")

    lineas.append("## 3. Desglose de Procedencia de Candidatos Ganadores (Top-1 Provenance)\n")
    lineas.append("Distribución del subsistema que generó el candidato ganador en la Condición D (v32.0):\n")
    lineas.append("| Subsistema de Origen | Casos Top-1 | Porcentaje (%) |")
    lineas.append("| :--- | :---: | :---: |")
    for orig, cnt in sorted(prov["D"].items(), key=lambda x: x[1], reverse=True):
        pct = (cnt / total) * 100
        lineas.append(f"| `{orig}` | {cnt} | {pct:.1f}% |")

    lineas.append("\n## 4. Conclusión Científica y Delimitación Metodológica\n")
    d_info = causal["D"]
    lineas.append(f"1. **Balance Causal Cuantificado:** En la condición integrada [D], se registraron {d_info['rescates_count']} rescates y {d_info['danos_count']} regresión(es) frente a la condición base [A], resultando en un balance neto de {'+' if d_info['balance_neto'] >= 0 else ''}{d_info['balance_neto']} casos ganados sobre la muestra evaluada (n={total}).")
    if d_info['danos_count'] > 0:
        lineas.append(f"   - Casos con regresión identificados: {', '.join(d['id'] for d in d_info['detalles_danos'])}. La telemetría de procedencia permite aislar el factor (p. ej. inyección de términos con solapamiento parcial / vocabulary drift) para guiar la optimización de guards.")
    lineas.append("2. **Diferenciación Epistemológica:** Se distingue formalmente entre Candidate Provenance (subsistema que integró el candidato al pool) y Contribución Causal (demostrada mediante la diferencia experimental entre condiciones con el mecanismo activo vs inactivo).")
    lineas.append("3. **Fundamentación vs. Calibración:** La jerarquía cualitativa de los 5 ángulos se apoya en la teoría de prototipos (Rosch, 1975) y redes semánticas (Collins & Quillian, 1969), mientras que sus multiplicadores escalares exactos corresponden a una calibración empírica en el corpus que debe validarse en pruebas de generalización continua.")

    texto_reporte = "\n".join(lineas)
    print("\n" + texto_reporte + "\n")

    if salida_md:
        os.makedirs(os.path.dirname(salida_md), exist_ok=True)
        with open(salida_md, "w", encoding="utf-8") as f:
            f.write(texto_reporte)
        print(f"[OK] Reporte markdown guardado en: {salida_md}")

    if salida_json:
        os.makedirs(os.path.dirname(salida_json), exist_ok=True)
        with open(salida_json, "w", encoding="utf-8") as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False)
        print(f"[OK] Métricas JSON guardadas en: {salida_json}")


def main():
    parser = argparse.ArgumentParser(description="Evaluación Causal y Ablación BioRAG v32.0")
    parser.add_argument("--db", default=None, help="Ruta a base de datos (por defecto snapshot oficial o producción)")
    parser.add_argument("--casos", default="scripts/casos_qa_baseline_v1.jsonl", help="Ruta al dataset jsonl")
    parser.add_argument("--limite", type=int, default=None, help="Límite de casos a evaluar")
    parser.add_argument("--estratificado", action="store_true", help="Muestreo estratificado por categorías")
    parser.add_argument("--verbose", action="store_true", help="Logging detallado por caso")
    parser.add_argument("--out-md", default="docs/informe_causalidad_ablacion_v32.md", help="Salida markdown")
    parser.add_argument("--out-json", default="docs/informe_causalidad_ablacion_v32.json", help="Salida JSON")
    args = parser.parse_args()

    db_path = args.db
    if not db_path:
        snap = os.path.join(ROOT_DIR, "snapshots", "qa_escape_qcr_20260811.db")
        prod = os.path.join(ROOT_DIR, "MemoryBioRAG_Data", "memory_biorag.db")
        db_path = prod if os.path.exists(prod) else snap

    print(f"[CONFIG] DB seleccionada: {db_path}")
    print(f"[CONFIG] Casos dataset:   {args.casos}")

    casos = cargar_casos(args.casos, limite=args.limite, estratificado=args.estratificado)
    resultados = ejecutar_evaluacion_causal(db_path, casos, verbose=args.verbose)
    imprimir_reporte(resultados, salida_md=args.out_md, salida_json=args.out_json)


if __name__ == "__main__":
    main()
