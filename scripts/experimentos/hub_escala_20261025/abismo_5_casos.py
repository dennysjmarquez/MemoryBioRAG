import os, sys, sqlite3; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
import core.concept_hub as ch
C = [("qué hacía antes de ser programador","historia_tasajera_fumigador_rufino"),
     ("metí un cambio y todo se rompió","leccion_control_flujo_codigo_preexistente"),
     ("toqué algo que andaba bien y dejó de andar","leccion_control_flujo_codigo_preexistente"),
     ("cómo sobrevivía económicamente antes de la tecnología","historia_tasajera_fumigador_rufino"),
     ("dos modelos de IA que no están de acuerdo, ¿cómo resuelvo?","resolucion_de_contradicciones_entre_insights_sumatoria_mentalidad")]
for db in sys.argv[1:]:
    c = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
    for modo in ("0", "1"):
        os.environ["BIORAG_HUB_ESCALA"] = modo
        out = []
        for q, g in C:
            r = ch.expandir_query_con_hub(q, c, 0.40)
            out.append("✓" if r and r["canonical_nodes"][0] == g else ("✗" + (r["canonical_nodes"][0][:18] if r else "-")))
        print(f"{db.split('/')[-1]:12s} {'nuevo' if modo=='1' else 'viejo'}: {'  '.join(out)}")
