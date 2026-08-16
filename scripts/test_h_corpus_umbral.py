#!/usr/bin/env python3
"""test_h_corpus_umbral.py — ¿El umbral de FP no escala con el tamaño del corpus?

CONTEXTO
========
FP en snapshot (~800 nodos): 25% con umbral 0.25
FP en live DB (mayor):       80% con umbral 0.25
Daemon OFF: sigue 80%.  Umbral 0.1866: sigue 80%.

El reporte que detectó esto observó que "los scores de negativos en live son
altos (0.3-0.5)" y concluyó que la fusión lineal está rota, proponiendo RRF.

HIPÓTESIS ALTERNATIVA (H-corpus)
--------------------------------
El umbral 0.25 es una constante ABSOLUTA elegida cuando el corpus tenía ~800
nodos. Al crecer el corpus hay más candidatos y más colisiones léxicas, así que
el score del mejor candidato sube para CUALQUIER consulta — incluidas las que no
tienen respuesta. El umbral se queda corto sin que nada esté roto.

Si H-corpus es cierta, RRF no cambia nada: el problema es que el umbral debe
derivarse de los datos, no ser una constante.

CÓMO SE DISTINGUE DE "FUSIÓN ROTA"
----------------------------------
  H-corpus  : la distribución ENTERA de scores se desplaza hacia arriba al crecer
              el corpus. Los positivos también suben. La SEPARACIÓN entre
              positivos y negativos se mantiene razonable.
  Fusión rota: los negativos suben pero los positivos no, o suben menos. La
               separación se colapsa: el sistema deja de distinguir.

La métrica que los separa es el SOLAPAMIENTO entre ambas distribuciones (AUC).
  - AUC alta (>0.85) + FP alto  => H-corpus: hay señal, el umbral está mal puesto.
                                     Solución: calibrar el umbral. RRF no ayuda.
  - AUC baja (<0.70)            => discriminación realmente rota.
                                     Ahí sí hay que rehacer el scoring.

USO
    python3 scripts/test_h_corpus_umbral.py <db_snapshot> <db_live>
    python3 scripts/test_h_corpus_umbral.py <una_sola_db>     # solo esa

Ejecuta las consultas del benchmark y compara distribuciones. No modifica nada.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import math
import random

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)


def _cargar_casos(ruta_jsonl: str):
    """Separa los casos en positivos (con concepto esperado) y negativos."""
    if not os.path.exists(ruta_jsonl):
        raise SystemExit(f"ERROR: no existe {ruta_jsonl}")
    pos, neg = [], []
    with open(ruta_jsonl, encoding="utf-8") as fh:
        for linea in fh:
            if not linea.strip():
                continue
            d = json.loads(linea)
            if d.get("categoria") == "negativo" or d.get("concepto_esperado") is None:
                neg.append(d)
            else:
                pos.append(d)
    return pos, neg


def _auc(pos: list[float], neg: list[float]) -> float:
    """AUC por el estadístico de Mann-Whitney (probabilidad de que un positivo
    puntúe por encima de un negativo tomado al azar). 0.5 = azar, 1.0 = perfecto.

    Se calcula por conteo directo con corrección de empates: n_pos*n_neg es
    pequeño aquí (cientos x decenas) y así se evita depender de scipy.
    """
    if not pos or not neg:
        return float("nan")
    mayor = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                mayor += 1.0
            elif p == n:
                mayor += 0.5
    return mayor / (len(pos) * len(neg))


def _scores_top1(db_path: str, casos: list, limite_casos: int = 0) -> list[float]:
    """Devuelve el score del top-1 para cada consulta. Falla ruidosamente."""
    if not os.path.exists(db_path):
        raise SystemExit(f"ERROR: no existe la DB '{db_path}'")
    from core.memory_store import SQLiteMemoryBioRAG

    cerebro = SQLiteMemoryBioRAG(db_path)
    scores = []
    try:
        for caso in casos[:limite_casos] if limite_casos else casos:
            try:
                res = cerebro.buscar_por_frase(caso["query"], limite=5)
                # buscar_por_frase puede devolver (pagina, contextos) o solo la página
                pagina = res[0] if isinstance(res, tuple) else res
                if pagina:
                    # el score híbrido es el índice 4 de la tupla de resultado
                    scores.append(float(pagina[0][4]))
                else:
                    scores.append(0.0)
            except Exception as e:
                print(f"  aviso: fallo en '{caso.get('id','?')}': {e}")
    finally:
        try:
            cerebro.conn.close()
        except Exception:
            pass
    return scores


def analizar(db_path: str, etiqueta: str, pos_casos, neg_casos, umbral: float) -> dict:
    print(f"\n--- {etiqueta} ---")
    print(f"  DB: {db_path}")

    s_pos = _scores_top1(db_path, pos_casos)
    s_neg = _scores_top1(db_path, neg_casos)

    if not s_pos or not s_neg:
        raise SystemExit("ERROR: no se obtuvieron scores. Revisa la DB y los casos.")

    fp = sum(1 for s in s_neg if s >= umbral) / len(s_neg)
    auc = _auc(s_pos, s_neg)

    print(f"  positivos (n={len(s_pos)}): media={statistics.mean(s_pos):.3f}  "
          f"mediana={statistics.median(s_pos):.3f}  max={max(s_pos):.3f}")
    print(f"  negativos (n={len(s_neg)}): media={statistics.median(s_neg):.3f}  "
          f"mediana={statistics.median(s_neg):.3f}  max={max(s_neg):.3f}")
    print(f"  FP con umbral {umbral}: {100*fp:.1f}%")
    print(f"  AUC (separación pos vs neg): {auc:.3f}")

    # Barrido de umbrales para ver la curva completa
    print(f"\n  --- Barrido de umbrales (optimizando ganancia neta) ---")
    s_neg_sorted = sorted(s_neg)
    s_pos_sorted = sorted(s_pos)
    mejores = []
    # Barrer desde 0.0 a 1.0 en pasos de 0.01
    for u in [i/1000 for i in range(0, 1001, 5)]:
        fp = sum(1 for s in s_neg if s >= u) / len(s_neg) if s_neg else 0
        recall = sum(1 for s in s_pos if s >= u) / len(s_pos) if s_pos else 0
        ganancia_neta = len(s_pos) * (sum(1 for s in s_pos if s >= u) / len(s_pos)) - len(s_neg) * (sum(1 for s in s_neg if s >= u) / len(s_neg))
        mejores.append((u, fp, recall, ganancia_neta))
    # Buscar óptimo: maximizar ganancia neta
    best_u, best_fp, best_recall, best_ganancia = max(mejores, key=lambda x: x[3])

    # Umbral conforme con hold-out (split 50/50)
    s_neg_mezcla = list(s_neg)
    random.Random(20260815).shuffle(s_neg)
    corte = len(s_neg) // 2
    cal_neg = s_neg[:len(s_neg)//2]
    val_neg = s_neg[len(s_neg)//2:]

    print(f"\n  --- Barrido de umbrales (optimizando ganancia neta) ---")
    print(f"  Mejor umbral: {best_u:.3f} -> FP={100*best_fp:.1f}%, Recall={100*best_recall:.1f}%, Ganancia neta={best_ganancia:.1f}")

    if len(s_neg) >= 10:
        s_neg_mezcla = list(s_neg)
        random.Random(20260815).shuffle(s_neg)
        corte = len(s_neg) // 2
        cal_neg = s_neg[:len(s_neg)//2]
        val_neg = s_neg[len(s_neg)//2:]

        s_ord = sorted(cal_neg)
        k = math.ceil((len(s_ord) + 1) * 0.90)
        umbral_conforme = s_ord[min(k, len(s_ord)) - 1]
        fp_conf = sum(1 for s in val_neg if s > umbral_conforme) / len(val_neg)
        recall_conf = sum(1 for s in s_pos if s > umbral_conforme) / len(s_pos)
        print(f"  Umbral conforme (hold-out, alpha=0.10): {umbral_conforme:.3f} -> FP held-out={100*fp_conf:.1f}%, Recall held-out={100*recall_conf:.1f}%")

        # Análisis de coste-beneficio
        perdidos = (1.0 - recall_conf) * len(s_pos)
        evitados = (1.0 - fp_conf) * len(s_neg)
        print(f"     -> COSTE: perderías ~{perdidos:.0f} de {len(s_pos)} positivos "
              f"para evitar ~{evitados:.0f} de {len(s_neg)} falsos positivos")
        if perdidos > evitados:
            print(f"     *** AVISO: el umbral destruye más aciertos ({perdidos:.0f}) "
                  f"de los que protege ({evitados:.0f}). ***")
            print("         Revisa alpha, o el ratio real positivos:negativos de "
                  "tu carga de producción.")
    else:
        print(f"  Umbral conforme: NO CALCULADO — se necesitan >=10 negativos para "
              f"partir en calibración/validación (hay {len(s_neg)}).")
        print("  Calibrar y medir sobre los mismos datos daría un FP tautológico.")

    # Barrido completo para mostrar curva
    print(f"\n  --- Curva FP vs Recall ---")
    for u in [0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]:
        fp = sum(1 for s in s_neg if s >= u) / len(s_neg) if s_neg else 0
        recall = sum(1 for s in s_pos if s >= u) / len(s_pos) if s_pos else 0
        tp = sum(1 for s in s_pos if s >= u)
        fp_val = sum(1 for s in s_neg if s >= u)
        net = tp - fp_val
        print(f"  @ {u:.2f}: FP={100*fp:.1f}%, Recall={100*recall:.1f}%, Net={tp - fp_val}")

    return {"etiqueta": etiqueta, "auc": auc, "fp": fp,
            "media_pos": statistics.mean(s_pos), "media_neg": statistics.mean(s_neg),
            "umbral_conforme": umbral_conforme if 'umbral_conforme' in locals() else float("nan"),
            "recall_conforme": recall_conf if 'recall_conf' in locals() else float("nan")}


def main() -> None:
    import sys
    import os
    import math
    import random
    import statistics

    if len(sys.argv) < 2:
        raise SystemExit(
            "Uso: python3 scripts/test_h_corpus_umbral.py <db1> [db2]\n"
            "  db1 = snapshot, db2 = live (opcional)"
        )
    umbral = float(os.environ.get("BIORAG_FP_THRESHOLD", "0.25"))
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    casos_path = os.path.join(BASE, "scripts", "casos_qa.jsonl")
    pos, neg = _cargar_casos(casos_path)

    print("=" * 70)
    print("  H-corpus: ¿el umbral no escala, o la discriminación está rota?")
    print("=" * 70)
    print(f"casos: {len(pos)} positivos, {len(neg)} negativos | umbral FP = {umbral}")

    resultados = [analizar(sys.argv[1], "DB 1", pos, neg, umbral)]
    if len(sys.argv) > 2:
        resultados.append(analizar(sys.argv[2], "DB 2", pos, neg, umbral))

    print("\n" + "=" * 70)
    print("VEREDICTO")
    print("=" * 70)
    for r in resultados:
        if r["auc"] != r["auc"]:  # NaN
            continue
        if r["auc"] >= 0.85 and r["fp"] > 0.30:
            print(f"{r['etiqueta']}: H-CORPUS. AUC={r['auc']:.3f} alta pero "
                  f"FP={100*r['fp']:.0f}%.")
            print("  Hay señal de sobra; el umbral absoluto está mal puesto para")
            print("  este corpus. Solución: umbral calibrado. RRF NO ayuda aquí.")
        elif r["auc"] < 0.70:
            print(f"{r['etiqueta']}: DISCRIMINACIÓN ROTA. AUC={r['auc']:.3f}.")
            print("  Los positivos y negativos se solapan de verdad. Aquí sí hay")
            print("  que rehacer el scoring (fusión, señales).")
        else:
            print(f"{r['etiqueta']}: zona intermedia. AUC={r['auc']:.3f}, "
                  f"FP={100*r['fp']:.0f}%. Calibrar primero y volver a medir.")

    if len(resultados) == 2:
        d_neg = resultados[1]["media_neg"] - resultados[0]["media_neg"]
        d_pos = resultados[1]["media_pos"] - resultados[0]["media_pos"]
        print(f"\nDesplazamiento DB1 -> DB2:  negativos {d_neg:+.3f}   positivos {d_pos:+.3f}")
        if d_neg > 0.05 and abs(d_neg - d_pos) < 0.10:
            print("  Ambas distribuciones se desplazan juntas => H-corpus confirmada:")
            print("  es un efecto de escala del corpus, no una pérdida de señal.")
        elif d_neg > d_pos + 0.10:
            print("  Los negativos suben MÁS que los positivos => la separación se")
            print("  degrada de verdad con el tamaño del corpus.")


if __name__ == "__main__":
    main()
