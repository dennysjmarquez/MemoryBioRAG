#!/usr/bin/env python3
import sys
import os
import time
import re

# Asegurar que el path incluya el directorio actual
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.memory_store import SQLiteMemoryBioRAG
from middleware.interceptor import escanear_familiaridad, procesar_comandos_ocultos, inyectar_contexto_familiaridad
from config.prompts import SYSTEM_PROMPT_BIORAG

def banner():
    print(r"""
======================================================================
  🧠 BioRAG CLI: Simulador de Memoria Cognitiva Biomimética
  [SQLite B-Tree] [Plasticidad LTP/LTD] [Jaccard Difuso] [Sinapsis]
======================================================================
    """)

def ejecutar_simulacion():
    _default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MemoryBioRAG_Data", "memory_biorag.db")
    db_path = os.environ.get('BIORAG_PATH') or _default
    cerebro = SQLiteMemoryBioRAG(db_path=db_path)
    banner()

    print("[*] Escribe tu mensaje para interactuar con el agente.")
    print("[*] Comandos especiales en la consola:")
    print("    - '/sueno'   -> Forzar ciclo de sueño (Consolidación y Poda).")
    print("    - '/corteza' -> Listar todos los recuerdos guardados en SQLite.")
    print("    - '/salir'   -> Salir del simulador.")
    print("----------------------------------------------------------------------")

    while True:
        try:
            entrada = input("\nCreador (Dennys) > ").strip()
            if not entrada:
                continue

            if entrada.lower() == "/salir":
                print("[-] Cerrando BioRAG. Cuidando el hardware...")
                break

            elif entrada.lower() == "/sueno":
                cerebro.ciclo_sueno_consolidacion(limite_energia=10.0)
                continue

            elif entrada.lower() == "/corteza":
                print("\n================== 👁️ CORTEZA CEREBRAL (SQLite) ==================")
                cerebro.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo")
                filas = cerebro.cursor.fetchall()
                if not filas:
                    print("[i] La corteza está vacía. Consolida recuerdos usando /sueno.")
                for c, cont, peso, estado, asoc in filas:
                    print(f"[{estado.upper()}] Clave: '{c}' | Peso: {peso} | Asoc: [{asoc}]")
                    if cont:
                        print(f"      Detalle: {cont[:100]}...")
                print("==================================================================")
                continue

            # 1. PASO 1: Inyección de Familiaridad (Familiarity Scan)
            inicio_scan = time.perf_counter()
            prompt_inyectado = inyectar_contexto_familiaridad(entrada, cerebro)
            fin_scan = time.perf_counter()

            print(f"\n[Microsegundos: {(fin_scan - inicio_scan)*1000000:.2f} us] - Escaneo de Familiaridad Completado.")
            if prompt_inyectado != entrada:
                print("\n--- 📥 PROMPT INYECTADO AL CONTEXTO DEL AGENTE ---")
                print(prompt_inyectado)
                print("-------------------------------------------------")
            else:
                print("[i] Sin coincidencia de familiaridad. La mente del agente está limpia.")

            # 2. PASO 2: Simular la respuesta del Agente según su System Prompt
            print("\n--- 🤖 SIMULACIÓN DE RESPUESTA DEL AGENTE ---")
            
            # Lógica simulada basada en palabras clave del Creador para mostrar el uso de comandos secretos
            concepto_detectado = re.search(r'(cayetano|empleo|velas|diseño|flexbox|css)', entrada.lower())
            
            if "recuerda que" in entrada.lower() or "guarda que" in entrada.lower():
                # Simular guardado
                partes = entrada.lower().split("recuerda que")
                dato = partes[1].strip() if len(partes) > 1 else "hecho importante"
                # Extraer un concepto para la clave
                clave = re.findall(r'\b\w{3,}\b', dato)
                key = clave[0] if clave else "percepcion"
                
                respuesta_agente = (
                    f"<pensamiento>\n"
                    f"El creador me esta dando una instruccion persistente. Debo consolidar este hecho.\n"
                    f"[GUARDAR: {key} = {dato}]\n"
                    f"</pensamiento>\n"
                    f"Entendido, Dennys. He registrado la percepción sobre '{key}' en mi memoria inmediata. "
                    f"Se consolidará en mi corteza permanente cuando ejecutes el ciclo de sueño (/sueno)."
                )
            elif "asocia" in entrada.lower():
                # Simular asociacion
                palabras = re.findall(r'\b\w{3,}\b', entrada.lower())
                a = palabras[1] if len(palabras) > 1 else "concepto_a"
                b = palabras[2] if len(palabras) > 2 else "concepto_b"
                respuesta_agente = (
                    f"<pensamiento>\n"
                    f"El usuario me pide explícitamente enlazar {a} con {b}.\n"
                    f"[ASOCIAR: {a} = {b}]\n"
                    f"</pensamiento>\n"
                    f"He establecido una sinapsis bidireccional entre '{a}' y '{b}' en el grafo permanente."
                )
            elif prompt_inyectado != entrada:
                # Si hubo inyección de familiaridad, simular evocación y respuesta
                conceptos = escanear_familiaridad(entrada, cerebro)
                clave_evocar = conceptos[0]
                
                respuesta_agente = (
                    f"<pensamiento>\n"
                    f"El escaner de familiaridad inyectó una nota sobre '{clave_evocar}'.\n"
                    f"Evocaré los detalles específicos del SQLite para responder con precisión.\n"
                    f"[BUSCAR: {clave_evocar}]\n"
                    f"</pensamiento>\n"
                )
                
                # Ejecutar intercepción parcial para que el agente "tenga" la información antes de hablar
                resultados = procesar_comandos_ocultos(respuesta_agente, cerebro)
                memoria = resultados["buscar"][0]["resultado"] if resultados["buscar"] else None
                
                respuesta_agente += (
                    f"¡Hola Dennys! Sí, mi meta-índice de familiaridad me trajo la intuición de '{clave_evocar}'. "
                    f"Al evocar mi corteza profunda, he recordado el siguiente detalle:\n\n"
                    f"👉 \"{memoria}\"\n\n"
                    f"¿Qué deseas que hagamos con esta información?"
                )
            else:
                respuesta_agente = (
                    f"<pensamiento>\n"
                    f"El usuario me saluda o habla de un tema nuevo sin coincidencia en la corteza.\n"
                    f"</pensamiento>\n"
                    f"Hola Dennys. Estoy listo. Si deseas que guarde algo persistente para mis hermanas, "
                    f"dime: 'Recuerda que...'"
                )

            # Imprimir salida cruda del Agente
            print(respuesta_agente)
            print("---------------------------------------------")

            # 3. PASO 3: Intercepción del Middleware en segundo plano
            resultados_middleware = procesar_comandos_ocultos(respuesta_agente, cerebro)
            if resultados_middleware["guardar"] or resultados_middleware["asociar"]:
                print("\n[🧠 MIDDLEWARE INTERCEPTOR - OPERACIONES:")
                for g in resultados_middleware["guardar"]:
                    print(f"   -> [GUARDADO] '{g['clave']}' guardado temporalmente en corto plazo.")
                for a in resultados_middleware["asociar"]:
                    print(f"   -> [SINAPSIS] '{a['concepto_a']}' <--> '{a['concepto_b']}' enlazados.")
                print("]")

        except KeyboardInterrupt:
            print("\n[-] Saliendo del simulador de forma segura...")
            break
        except Exception as e:
            print(f"[!] Error: {e}")

    cerebro.cerrar_sistema()

if __name__ == "__main__":
    ejecutar_simulacion()
