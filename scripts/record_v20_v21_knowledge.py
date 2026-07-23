#!/usr/bin/env python3
"""
Script para registrar en la corteza permanente de BioRAG el conocimiento
arquitectónico fundamental de las versiones v20.0 y v21.0.
"""

import os
import sys
import time

# Agregar directorio del proyecto al path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core.memory_store import SQLiteMemoryBioRAG

def registrar_memoria_arquitectura():
    db_path = os.path.join(project_root, "MemoryBioRAG_Data", "memory_biorag.db")
    print(f"🧠 Conectando a BioRAG DB en: {db_path}")
    cerebro = SQLiteMemoryBioRAG(db_path=db_path)

    # 1. Registrar Nodos de v20.0
    cerebro.percibir_corto_plazo(
        concepto="biorag_v20_gaba_inhibition",
        contenido="BioRAG v20.0 Inhibición Lateral GABA en Vivo durante evocación: El candidato Top-1 atenuá x0.60 a competidores secundarios cuando domina (score >= 0.80), eliminando el ruido semántico.",
        sinonimos="gaba inhibicion lateral,evocacion atractor,edelman 1987,biorag v20 v21 arquitectura",
        categoria="Principle",
        valencia_somatica=1.0
    )

    cerebro.percibir_corto_plazo(
        concepto="biorag_v20_rpe_dopamina",
        contenido="BioRAG v20.0 Error de Predicción de Recompensa Dopaminérgica (Dopamina RPE - Schultz 1997) con factor de inercia sináptica. biorag_feedback modula pesos: delta_W = +0.15 en éxitos, depresión en fallos atenuada por historial.",
        sinonimos="dopamina rpe,biorag feedback,inercia sinaptica,recompensa,biorag v20 v21 arquitectura",
        categoria="Principle",
        valencia_somatica=1.0
    )

    cerebro.percibir_corto_plazo(
        concepto="biorag_v20_valencia_somatica",
        contenido="BioRAG v20.0 Marcadores Somáticos y Valencia Cortical (Damasio 1994). Nodos con valencia somática >= 0.80 o categorías axiomáticas (Principle, Protocol) poseen Inmunidad Cortical Total contra LTD pasivo (-0.05) y poda.",
        sinonimos="valencia somatica,inmunidad cortical,marcadores somaticos,damasio,biorag v20 v21 arquitectura",
        categoria="Principle",
        valencia_somatica=1.0
    )

    cerebro.percibir_corto_plazo(
        concepto="biorag_v20_homeostatic_scaling",
        contenido="BioRAG v20.0 Escalado Sináptico Homeostático (Turrigiano 2008). Durante el sueño, si la energía promedio de la corteza excede 0.70, aplica normalización multiplicativa (x0.98) a nodos no inmunes para evitar saturación.",
        sinonimos="escalado homeostatico,synaptic scaling,turrigiano 2008,normalizacion,biorag v20 v21 arquitectura",
        categoria="Principle",
        valencia_somatica=1.0
    )

    # 2. Registrar Nodos de v21.0
    cerebro.percibir_corto_plazo(
        concepto="biorag_v21_dmn_engine",
        contenido="BioRAG v21.0 Red por Defecto (Default Mode Network - DMN) & Curiosidad Espontánea (core/dmn_engine.py). Hilo autónomo daemon en segundo plano para ideación espontánea (mind-wandering) durante inactividad del usuario (idle_seconds >= 300). Multiplataforma en Linux/Windows con 0 dependencias externas.",
        sinonimos="default mode network,dmn engine,curiosidad espontanea,mind wandering,biorag v20 v21 arquitectura",
        categoria="Principle",
        valencia_somatica=1.0
    )

    cerebro.percibir_corto_plazo(
        concepto="biorag_v21_zero_latency_interrupt",
        contenido="BioRAG v21.0 Interrupción Instantánea de Latencia Cero mediante threading.Event(). Cualquier interacción o prompt del usuario notifica al evento de inmediato, congelando la ideación DMN para dedicar el 100% de los recursos a la consulta.",
        sinonimos="interrupcion latencia cero,threading event,prioridad usuario,biorag v20 v21 arquitectura",
        categoria="Protocol",
        valencia_somatica=1.0
    )

    cerebro.percibir_corto_plazo(
        concepto="biorag_v21_spindles_resonant_replay",
        contenido="BioRAG v21.0 Muestreo Resonante Cortical (Spindles Replay). El motor DMN elige un Nodo Ancla de alta valencia (Vs >= 0.3) o peso (W >= 0.5) y explora nodos resonantes distantes sin conexión previa fuerte, sintetizando un Insight autónomo.",
        sinonimos="muestreo resonante,spindles replay,nodo ancla,insight autonomo,biorag v20 v21 arquitectura",
        categoria="Principle",
        valencia_somatica=1.0
    )

    cerebro.percibir_corto_plazo(
        concepto="biorag_v21_hypothesis_natural_selection",
        contenido="BioRAG v21.0 Selección Natural de Hipótesis DMN. Los Insights nacen con peso moderado (W=0.50) y valencia somática protegida (Vs=0.85). Si el usuario no los evoca ni refuerza, sufrirán decaimiento pasivo LTD por sueño en el futuro.",
        sinonimos="seleccion natural hipotesis,decaimiento ltd insight,dormancia,biorag v20 v21 arquitectura",
        categoria="Principle",
        valencia_somatica=1.0
    )

    # 3. Consolidar inmediatamente a Largo Plazo mediante el Ciclo de Sueño
    cerebro.ciclo_sueno_consolidacion()

    # 4. Verificar nodos grabados en largo_plazo
    rows = cerebro.cursor.execute("SELECT concepto, valencia_somatica, peso_sinaptico FROM largo_plazo WHERE concepto LIKE 'biorag_v2%'").fetchall()
    print("\n🔍 Nodos de Arquitectura Grabados y Consolidados en Largo Plazo:")
    for r in rows:
        print(f"  - Concepto: {r[0]} | Valencia: {r[1]} | Peso: {r[2]}")

    cerebro.cerrar_sistema()
    print("\n✨ Todo el conocimiento de BioRAG v20.0 y v21.0 ha sido grabado y consolidado exitosamente en la corteza de largo plazo.")

if __name__ == "__main__":
    registrar_memoria_arquitectura()
