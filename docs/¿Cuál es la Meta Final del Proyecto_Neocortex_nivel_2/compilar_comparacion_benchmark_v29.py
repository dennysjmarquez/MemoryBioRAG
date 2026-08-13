"""Compila las ejecuciones baseline y v29 en un único JSON verificable."""
import json
from pathlib import Path

base = Path(__file__).resolve().parent
antes = json.loads((base / "benchmark_921_baseline_v264.json").read_text(encoding="utf-8"))
despues = json.loads((base / "benchmark_921_v29.json").read_text(encoding="utf-8"))

metricas = ["recall_at_5", "recall_at_1", "mrr", "tasa_fp", "segundos"]
comparacion = {}
for metrica in metricas:
    valor_antes = antes["metricas_globales"][metrica]
    valor_despues = despues["metricas_globales"][metrica]
    comparacion[metrica] = {
        "antes_v264": valor_antes,
        "despues_v29": valor_despues,
        "delta": valor_despues - valor_antes,
    }

reporte = {
    "protocolo": {
        "suite": "casos_qa_baseline_v1.jsonl",
        "casos": despues["casos_total"],
        "snapshot_congelado": despues["snapshot"],
        "baseline_revision": "v26.4",
        "revision_evaluada": "v29",
        "condicion": "Mismo snapshot, misma suite y proceso aislado por ejecución."
    },
    "global": comparacion,
    "por_categoria": {
        categoria: {
            clave: {
                "antes_v264": antes["por_categoria"][categoria].get(clave),
                "despues_v29": despues["por_categoria"][categoria].get(clave),
            }
            for clave in sorted(set(antes["por_categoria"][categoria]) | set(despues["por_categoria"][categoria]))
            if clave != "total"
        }
        for categoria in sorted(antes["por_categoria"])
    },
    "interpretacion": {
        "regresion_retrieval": comparacion["recall_at_5"]["delta"] < 0,
        "observacion": "La suite de buscar_por_frase no utiliza todavía el ranking de ADN v29; por ello este resultado prueba ausencia de regresión en la ruta existente, no una mejora de recall atribuible al ADN."
    }
}
(base / "benchmark_921_comparacion_v264_vs_v29.json").write_text(
    json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(reporte["global"], ensure_ascii=False, indent=2))
