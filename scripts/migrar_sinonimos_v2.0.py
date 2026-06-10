"""
Enriquecer nodos legacy de BioRAG con sinonimos.
Solo actualiza nodos reales (no test_*).
No toca contenido, peso ni estado.
"""

import os, sys

_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _SCRIPT_DIR)
from core.memory_store import SQLiteMemoryBioRAG as CortezaBioRAG

db_path = os.environ.get(
    "BIORAG_PATH",
    os.path.join(_SCRIPT_DIR, "MemoryBioRAG_Data", "memory_biorag.db")
)

SYNONIMOS = {
    "caso_formularios_anidados_angular": "nested forms,angular forms,tabs,formularios dinamicos,ngx-nested-forms",
    "caso_conflicto_liderazgo_sin_autoridad": "liderazgo,conflicto,deadline,proyecto,autoridad formal",
    "principio_naturaleza_agente": "naturaleza agente,criterio humano,agente vs humano,mentalidad",
    "ref_analisis_deepseek_biorag": "deepseek,analisis biorag,memoria agente,evaluacion externa",
    "aforismo_criterio_agente": "criterio,aforismo,ejecutor,agente,fundacional",
    "principio_pragmatismo_contextual": "pragmatismo,anti dogmatismo,framework,simplicidad",
    "principio_liderazgo_accion": "liderazgo,accion,cargo,jerarquia,presion",
    "caso_criterio_artificial_agente": "criterio artificial,agente,decision,construccion",
    "docker_infrastructure_rog": "docker,rog,g731gt,docker desktop,vm,ram,linux",
    "ref_formularios_anidados": "formularios anidados,referencia,archivos fuente,adevco",
    "guardado_automatico_caso_b": "regla 2 caso b,guardado automatico,alto impacto,autonomo",
    "comunicacion_entre_agentes": "comunicacion,agentes oec,canal,mensajes",
    "flag_deep_busqueda": "deep,flag,despertar nodos,dormidos",
    "ref_conversacion_criterio": "criterio,conversacion,naturaleza agente,referencia",
    "artisan_artis_dsl_paths": "artisan,artis,dsl,system prompt,path,legacy",
    "arquitectura_memoria_biorag": "arquitectura,memoria,niveles,corteza,persistencia",
    "hermes_orchestration_status": "hermes,orquestacion,gateway,kanban,estado",
    "agent_orchestrator_status": "agent orchestrator,pospuesto,hermes,skill",
}

cerebro = CortezaBioRAG(db_path=db_path)
conn = cerebro.conn
actualizados = 0

for concepto, syn_str in SYNONIMOS.items():
    cur = conn.execute(
        "SELECT sinonimos FROM largo_plazo WHERE concepto = ?", (concepto,)
    )
    row = cur.fetchone()
    if row is None:
        print(f"  [SKIP] {concepto} -- no existe")
        continue
    if row[0] and row[0].strip():
        print(f"  [SALTAR] {concepto} -- ya tiene sinonimos: '{row[0]}'")
        continue
    conn.execute(
        "UPDATE largo_plazo SET sinonimos = ? WHERE concepto = ?",
        (syn_str, concepto),
    )
    print(f"  [OK] {concepto} <- '{syn_str}'")
    actualizados += 1

conn.commit()

print(f"\nTotal: {actualizados} nodos enriquecidos.")

# Verificacion: buscar por sinonimo
print("\n--- Verificacion ---")
errores = 0
for concepto, syn_str in SYNONIMOS.items():
    primer_syn = syn_str.split(",")[0].strip()
    resultados, _ = cerebro.buscar_por_frase(primer_syn, profundidad="profundo")
    if resultados:
        match = resultados[0][0]
        ok = "[OK]" if match == concepto else "[RELACIONADO]"
        print(f"  '{primer_syn}' -> {match} {ok}")
    else:
        print(f"  '{primer_syn}' -> SIN RESULTADOS [FALLO]")
        errores += 1

conn.close()

if errores:
    print(f"\nERRORES: {errores} sinonimos no encontraron match")
    sys.exit(1)
else:
    print("\nTodos los sinonimos verificados. Cero errores.")
