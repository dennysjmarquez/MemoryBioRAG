#!/usr/bin/env python3
"""
Análisis forense A/B — Convergencia Multi-Campo (Spec-006) v2
==============================================================
REGLA OPERATIVA:
  - NO modifica ningún archivo de producción ni la DB de snapshot.
  - Crea copia SQLite INDEPENDIENTE por cada caso (OFF y ON simulado).
  - Desactiva DMN antes de importar el motor.
  - Registra por candidato del top-10:
      · score_base      → r[4] de buscar_por_frase (sin multiplicador)
      · canales         → {concepto, sinonimos, sustantivos, contenido}
      · bypass_v1       → match_exacto OR origen no-literal
      · multiplicador_v1→ valor que aplicaría la v1
      · score_v1_efect  → score_base * mult (simulado)
      · origen_tipo     → via store.last_origen_scores
      · score_capa      → score de la capa de recuperación
      · match_exacto    → detección léxica
      · qcr             → ratio, umbral, decisión
      · es_gold         → True si == concepto_esperado

Uso:
    BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/forense_convergencia_v2.py
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json, os, re, sqlite3, tempfile, logging

# ── 0. Desactivar DMN ANTES de importar el motor ─────────────────────────────
os.environ["BIORAG_DMN_SINTESIS_ACTIVA"] = "0"
os.environ["BIORAG_NO_LOG"]              = "1"
os.environ["BIORAG_CONVERGENCIA_ACTIVA"] = "0"
os.environ["BIORAG_CONVERGENCIA_ALPHA"]  = "0.5"

logging.basicConfig(level=logging.WARNING)

SNAPSHOT_PATH = os.environ.get("BIORAG_PATH", "snapshots/qa_escape_qcr_20260811.db")
ALPHA_V1      = 0.5
QA_REPORTE    = "scripts/forense_convergencia_v2_reporte.json"

CASOS = [
    {"id":"0516","cat":"por_tema",           "query":"real más sistemas",
     "gold":"dennys-identidad-profunda"},
    {"id":"0514","cat":"sinonimo",            "query":"perfil",
     "gold":"dennys-identidad-profunda"},
    {"id":"0489","cat":"typo",               "query":"oracle custom prompt arsitecura que fuciona",
     "gold":"oracle_custom_prompt_arsitecura_que_funciona"},
    {"id":"0518","cat":"variante_gramatical", "query":"cuando usado dimensione biorags",
     "gold":"cuando_usar_dimensiones_biorag"},
    {"id":"0564","cat":"pregunta_natural",    "query":"¿Dónde encuentro la info de memoria v5 1 optimizaciones?",
     "gold":"memoria_v5_1_optimizaciones"},
]

_ORIGENES_NO_LITERALES = {
    "typo","expansion","latente","cadena","simbolico",
    "dimensional_fallback","semantica","unicode","lexico_aprendido","sdm"
}

def _campo_activo(q_set, texto):
    if not texto or not q_set:
        return 0
    from core.fallback_simbolico import _tokenizar_normalizado as _tn
    return 1 if q_set & set(_tn(texto)) else 0

def calcular_canales(q_set, concepto, sinonimos, sustantivos, contenido):
    c = [_campo_activo(q_set, x) for x in [concepto, sinonimos, sustantivos, contenido]]
    return {"concepto":c[0], "sinonimos":c[1], "sustantivos":c[2], "contenido":c[3],
            "total": sum(c), "mascara": "".join(str(x) for x in c)}

def mult_v1(total, alpha=ALPHA_V1):
    return alpha + (1.0 - alpha) * (total / 4.0)

# Formato de tupla: (concepto, contenido, peso_sinaptico, estado, score_hibrido, asociaciones)
IDX = {"concepto":0, "contenido":1, "peso":2, "estado":3, "score":4, "asoc":5}

def analizar_caso(caso, snapshot_path):
    query = caso["query"]
    gold  = caso["gold"]

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        tmp_path = tf.name
    try:
        src = sqlite3.connect(snapshot_path)
        dst = sqlite3.connect(tmp_path)
        src.backup(dst); src.close(); dst.close()

        os.environ["BIORAG_PATH"] = tmp_path

        import importlib
        import core.memory.constants as _c
        importlib.reload(_c)
        from core.memory_store import SQLiteMemoryBioRAG
        store = SQLiteMemoryBioRAG(tmp_path)

        raw = store.buscar_por_frase(query, limite=10)
        # retorna (lista_tuplas, total_int)
        lista = raw[0] if isinstance(raw, tuple) else raw
        lista = lista[:10]

        origenes = getattr(store, "last_origen_scores", {}) or {}

        from core.fallback_simbolico import _tokenizar_normalizado as _tn
        q_set = set(_tn(query))

        # Batch-fetch sinonimos + sustantivos
        conceptos = [r[IDX["concepto"]] for r in lista]
        meta_map = {}
        if conceptos:
            ph = ",".join("?" * len(conceptos))
            store.cursor.execute(
                f"SELECT concepto, sinonimos, sustantivos_clave FROM largo_plazo WHERE concepto IN ({ph})",
                conceptos
            )
            for row in store.cursor.fetchall():
                meta_map[row[0]] = {"sinonimos": row[1] or "", "sustantivos": row[2] or ""}

        # QCR helpers
        q_tokens_qcr = [t.lower() for t in re.findall(r'\w{3,}', query)]
        qcr_activo   = len(q_tokens_qcr) >= 2
        try:
            idf_map = store._idf_tokens_qcr(q_tokens_qcr) if qcr_activo else {}
        except Exception:
            idf_map = {}
        idf_den  = sum(idf_map.get(t, 1.0) for t in q_tokens_qcr) if idf_map else float(max(1, len(q_tokens_qcr)))
        qcr_umbral = _c.QCR_IDF_UMBRAL if (idf_map and _c.QCR_IDF_ACTIVO) else 0.50
        QCR_ESCAPE_MIN = float(os.getenv("BIORAG_QCR_ESCAPE_CAPA_MIN", "0.60"))

        def qcr_check(conc, contenido_r, score_r, origen_tipo, sc_capa):
            sin  = meta_map.get(conc, {}).get("sinonimos", "")
            text = f"{conc} {contenido_r} {sin}".lower()
            if idf_map:
                ratio = sum(idf_map.get(t,1.0) for t in q_tokens_qcr if t in text) / idf_den
            else:
                ratio = sum(1 for t in q_tokens_qcr if t in text) / max(1, len(q_tokens_qcr))
            pr = ratio >= qcr_umbral
            pe = origen_tipo in _ORIGENES_NO_LITERALES and sc_capa >= QCR_ESCAPE_MIN
            pt = False
            if _c.QCR_TYPO_ACTIVA and score_r >= _c.QCR_TYPO_PISO:
                from core.memory.constants import _qcr_todos_cercanos
                pt = _qcr_todos_cercanos(q_tokens_qcr, text, _c.QCR_TYPO_DIST)
            return {"ratio": round(ratio, 4), "umbral": qcr_umbral,
                    "pasa_ratio": pr, "pasa_escape": pe, "pasa_typo": pt,
                    "pasa": not qcr_activo or pr or pe or pt}

        # Match exacto: mismos tokens que la query
        _q_norm = " ".join(sorted(q_set)) if q_set else ""

        filas = []
        for pos, r in enumerate(lista, 1):
            conc    = r[IDX["concepto"]]
            cnt     = r[IDX["contenido"]] or ""
            score_b = r[IDX["score"]]
            sin     = meta_map.get(conc, {}).get("sinonimos", "")
            sus     = meta_map.get(conc, {}).get("sustantivos", "")

            origen_info = origenes.get(conc, ("literal", 0.0))
            origen_tipo = origen_info[0] if isinstance(origen_info, (tuple,list)) else "desconocido"
            sc_capa     = origen_info[1] if isinstance(origen_info, (tuple,list)) else 0.0

            _c_norm = " ".join(sorted(set(_tn(conc)))) if q_set else ""
            me = (_q_norm == _c_norm) or (bool(q_set) and q_set == set(_tn(conc)))

            canales = calcular_canales(q_set, conc, sin, sus, cnt)
            bypass  = me or (origen_tipo in _ORIGENES_NO_LITERALES)
            m       = 1.0 if bypass else mult_v1(canales["total"])
            sc_v1   = round(min(1.0, score_b * m), 6)
            qcr     = qcr_check(conc, cnt, score_b, origen_tipo, sc_capa)

            filas.append({
                "pos_off": pos,
                "concepto": conc,
                "es_gold": conc == gold,
                "score_base": score_b,
                "canales": canales,
                "origen_tipo": origen_tipo,
                "origen_score_capa": round(sc_capa, 4),
                "match_exacto": me,
                "bypass_v1": bypass,
                "multiplicador_v1": round(m, 4),
                "score_v1_efectivo": sc_v1,
                "delta_v1": round(sc_v1 - score_b, 6),
                "qcr": qcr,
            })

        # Simular reordenamiento v1
        sorted_v1 = sorted(filas, key=lambda x: x["score_v1_efectivo"], reverse=True)
        for i, f in enumerate(sorted_v1, 1):
            f["pos_v1"] = i

        store.conn.close()
        os.unlink(tmp_path)

        goff = next((f["pos_off"] for f in filas    if f["es_gold"]), None)
        gv1  = next((f["pos_v1"]  for f in sorted_v1 if f["es_gold"]), None)

        return {
            "id": caso["id"], "cat": caso["cat"], "query": query, "gold": gold,
            "tokens_query": sorted(q_set),
            "candidatos": filas,
            "gold_pos_off": goff,
            "gold_pos_v1":  gv1,
            "gold_encontrado_off": goff is not None,
            "regresion_v1": (gv1 or 999) > (goff or 999),
            "mejora_v1":    (gv1 or 999) < (goff or 999),
        }

    except Exception as exc:
        import traceback
        try: os.unlink(tmp_path)
        except: pass
        return {"id": caso["id"], "error": str(exc), "tb": traceback.format_exc()}


def main():
    if not os.path.exists(SNAPSHOT_PATH):
        print(f"[ERROR] Snapshot no encontrado: {SNAPSHOT_PATH}"); sys.exit(1)

    print(f"[Forense v2] Snapshot: {SNAPSHOT_PATH}  Alpha_v1={ALPHA_V1}  DMN=OFF")
    print()

    resultados = []
    for caso in CASOS:
        print(f"── Caso {caso['id']} [{caso['cat']}]  '{caso['query']}'")
        r = analizar_caso(caso, SNAPSHOT_PATH)
        resultados.append(r)
        if "error" in r:
            print(f"   [ERROR] {r['error']}\n{r.get('tb','')}"); continue

        goff = r["gold_pos_off"]; gv1 = r["gold_pos_v1"]
        tag  = "⚠ REGRESIÓN" if r["regresion_v1"] else ("✓ MEJORA" if r["mejora_v1"] else "= SIN CAMBIO")
        print(f"   gold='{r['gold']}'  pos_OFF={goff}  pos_V1={gv1}  → {tag}")

        hdr = f"   {'P':>3} {'G':>2} {'CONCEPTO':<42} {'BASE':>7} {'CH':>6} {'MV1':>6} {'SV1':>7} {'ORIGEN':<20} QCR"
        print(hdr)
        print("   " + "-"*(len(hdr)-3))
        for f in r["candidatos"][:7]:
            gm  = "★" if f["es_gold"] else " "
            c   = f["canales"]
            ch  = f"{c['total']}/4[{c['mascara']}]"
            qcr_s = f"OK(r={f['qcr']['ratio']:.2f})" if f["qcr"]["pasa"] else f"FAIL(r={f['qcr']['ratio']:.2f})"
            print(f"   {f['pos_off']:>3} {gm:>2} {f['concepto']:<42.42} "
                  f"{f['score_base']:>7.4f} {ch:>10} {f['multiplicador_v1']:>6.3f} "
                  f"{f['score_v1_efectivo']:>7.4f} {f['origen_tipo']:<20} {qcr_s}")
        print()

    # Guardar JSON
    reporte = {
        "config": {"snapshot": SNAPSHOT_PATH, "alpha_v1": ALPHA_V1, "dmn": "OFF"},
        "casos": resultados,
        "resumen": {
            "total": len(CASOS),
            "regresiones_v1": sum(1 for r in resultados if r.get("regresion_v1")),
            "mejoras_v1":     sum(1 for r in resultados if r.get("mejora_v1")),
            "sin_cambio_v1":  sum(1 for r in resultados if not r.get("regresion_v1") and not r.get("mejora_v1")),
        }
    }
    with open(QA_REPORTE, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)
    print(f"\n[Forense v2] Reporte → {QA_REPORTE}")
    print(f"[Forense v2] Resumen: {reporte['resumen']}")

    # ── Diagnóstico extendido ─────────────────────────────────────────────────
    print("\n" + "="*72)
    print("DIAGNÓSTICO: causas raíz de regresión por caso")
    print("="*72)
    for r in resultados:
        if "error" in r: continue
        print(f"\n[{r['id']} {r['cat']}] '{r['query']}'")
        gold_f = next((f for f in r["candidatos"] if f["es_gold"]), None)
        if not gold_f:
            print("  ⚠ Gold NO encontrado en top-10  → problema de RECUPERACIÓN, no de re-ranking")
            continue
        g = gold_f
        print(f"  GOLD '{r['gold']}':")
        print(f"    score_base={g['score_base']:.4f}  canales={g['canales']['total']}/4[{g['canales']['mascara']}]"
              f"  origen={g['origen_tipo']}(capa={g['origen_score_capa']:.3f})"
              f"  bypass={g['bypass_v1']}  mult_v1={g['multiplicador_v1']:.3f}"
              f"  sv1={g['score_v1_efectivo']:.4f}  qcr={'OK' if g['qcr']['pasa'] else 'FAIL'}")

        desplazan = sorted(
            [f for f in r["candidatos"] if not f["es_gold"] and f["score_v1_efectivo"] >= g["score_v1_efectivo"]],
            key=lambda x: x["score_v1_efectivo"], reverse=True
        )
        if desplazan:
            print(f"  Competidores que igualan/superan al gold con v1 ({len(desplazan)}):")
            for d in desplazan[:4]:
                causas = []
                if d["score_base"] > g["score_base"]:
                    causas.append(f"score_base_mayor(+{d['score_base']-g['score_base']:.4f})")
                if d["canales"]["total"] > g["canales"]["total"]:
                    causas.append(f"mas_canales({d['canales']['total']}>{g['canales']['total']})")
                if d["multiplicador_v1"] > g["multiplicador_v1"]:
                    causas.append(f"mult_mayor({d['multiplicador_v1']:.3f}>{g['multiplicador_v1']:.3f})")
                if d["bypass_v1"]:
                    causas.append("bypass(origen_no_literal)")
                print(f"    [{d['pos_off']}→{d.get('pos_v1','?')}] '{d['concepto'][:44]}'"
                      f"  ch={d['canales']['total']}/4  mult={d['multiplicador_v1']:.3f}"
                      f"  sv1={d['score_v1_efectivo']:.4f}  [{', '.join(causas) or 'mismo_score'}]")
        else:
            print(f"  ✓ Gold no desplazado con v1  →  pos_v1={r['gold_pos_v1']}")

    print("\n" + "="*72)
    print("FIN DEL ANÁLISIS FORENSE — producción intacta")
    print("="*72)


if __name__ == "__main__":
    main()
