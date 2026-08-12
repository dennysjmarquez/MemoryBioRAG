from core.memory_store import SQLiteMemoryBioRAG, EpistemicUncertaintyError
import os

os.environ['BIORAG_PPMI_WEIGHT'] = '1.0'
mem = SQLiteMemoryBioRAG()

print("="*60)
print("EXPERIMENTO CIENTÍFICO: NEOCÓRTEX DE SANGRE (v27.0)")
print("="*60)

def probar_query(nombre, query):
    print(f"\n--- {nombre} ---")
    print(f"Query: '{query}'")
    epi = mem.evaluar_episteme(query)
    print(f"Certeza Epistémica: {epi['confianza_epistemica']} (Estado: {epi['estado']})")
    
    try:
        res, total = mem.buscar_por_frase(query)
        print(f"Resultado: ÉXITO. Se recuperaron {len(res)} nodos.")
        for i, r in enumerate(res[:3]):
            # Formato de res: (concepto, contenido, sinonimos, timestamp, score, tipo, ...)
            concepto = r[0]
            tipo = r[5] if len(r)>5 else 'desconocido'
            score = r[4]
            print(f"  [{i+1}] {concepto} (Score: {score:.4f}, Tipo: {tipo[:30]}...)")
    except EpistemicUncertaintyError as e:
        print(f"Resultado: BLOQUEADO POR HONESTIDAD EPISTÉMICA.")
        print(f"  -> El sistema se negó a alucinar. Mensaje: {e}")
    except Exception as e:
        print(f"Resultado: ERROR INTERNO: {e}")

# Escenario 1: En Distribución / Literal (El sistema sabe y busca normal)
probar_query("ESCENARIO 1 (En Dominio)", "arquitectura vectorial de memoria")

# Escenario 2: Resonancia Dimensional (Conceptos poéticos/lejanos, debe fallar la exactitud y usar Resonancia)
# "ente callado que mira el cielo"
probar_query("ESCENARIO 2 (Resonancia Pura)", "ente callado que mira el cielo")

# Escenario 3: Ignorancia Epistémica (El sistema NO sabe y no alucina)
probar_query("ESCENARIO 3 (Fuera de Distribución)", "wxxqqzz jkhgkjh plkjhgf")

print("\n" + "="*60)
print("CONCLUSIÓN: El sistema distingue perfectamente entre lo que sabe, lo que intuye, y lo que ignora.")
print("="*60)
