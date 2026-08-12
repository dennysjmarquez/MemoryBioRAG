from core.memory_store import SQLiteMemoryBioRAG, EpistemicUncertaintyError
import os

os.environ['BIORAG_PPMI_WEIGHT'] = '1.0'  # Asegurar que el PPMI engine cargue
mem = SQLiteMemoryBioRAG()

print("Prueba 1: Ignorancia Epistémica (Sabe que no sabe)")
try:
    epi = mem.evaluar_episteme("zxdqweqw asdfasd fasdfasdf")
    print("Epi:", epi)
    res, total = mem.buscar_por_frase("zxdqweqw asdfasd fasdfasdf")
    print("FALLÓ: El sistema no levantó la excepción. Retornó:", len(res), "resultados")
except EpistemicUncertaintyError as e:
    print(f"ÉXITO: El sistema fue honesto. Mensaje: {e}")

print("\nPrueba 2: Resonancia Dimensional")
try:
    res, total = mem.buscar_por_frase("ser solitario pensador reflexion")
    print(f"Se encontraron {len(res)} resultados resonantes.")
    for i, r in enumerate(res[:3]):
        # r = (concepto, contenido, sinonimos, timestamp, score, tipo, ...otros)
        print(f"  [{i}] Concepto: {r[0]} | Tipo: {r[5] if len(r)>5 else 'desconocido'} | Score: {r[4]}")
except Exception as e:
    import traceback
    traceback.print_exc()
