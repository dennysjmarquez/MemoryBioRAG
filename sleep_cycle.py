#!/usr/bin/env python3
import sys
import os

# Asegurar que el path incluya el directorio actual
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.memory_store import SQLiteMemoryBioRAG

def ejecutar_sueño():
    db_path = "/mnt/recursos_compartidos_y_otros/MemoryBioRAG/MemoryBioRAG_Data/memory_biorag.db"
    
    print("====================================================")
    print("🌙 BIORAG: INICIANDO CICLO DE CONSOLIDACIÓN Y SUEÑO")
    print("====================================================")
    
    if not os.path.exists(db_path):
        print(f"[-] Base de datos no encontrada en {db_path}.")
        print("[*] Inicializando base de datos cerebral limpia...")
        
    cerebro = SQLiteMemoryBioRAG(db_path=db_path)
    
    # 1. Mostrar estado previo a la consolidación
    cerebro.cursor.execute("SELECT COUNT(*) FROM corto_plazo")
    en_corto = cerebro.cursor.fetchone()[0]
    
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'")
    activos_previos = cerebro.cursor.fetchone()[0]
    
    print(f"[i] Percepciones en Corto Plazo a consolidar: {en_corto}")
    print(f"[i] Nodos corticales activos previos: {activos_previos}")
    
    # 2. Ejecutar Consolidación y Poda Sináptica
    cerebro.ciclo_sueno_consolidacion(limite_energia=12.0)
    
    # 3. Mostrar estado post-consolidación
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'")
    activos_post = cerebro.cursor.fetchone()[0]
    
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido'")
    dormidos_post = cerebro.cursor.fetchone()[0]
    
    print("\n----------------------------------------------------")
    print("📋 REPORTE DE SALUD CORTICAL:")
    print("----------------------------------------------------")
    print(f"[+] Nodos corticales Activos: {activos_post}")
    print(f"[+] Nodos corticales Dormidos (Deep Memory): {dormidos_post}")
    print("[+] Memoria de Trabajo (Corto Plazo) vaciada y limpia.")
    print("====================================================")
    
    cerebro.cerrar_sistema()

if __name__ == "__main__":
    ejecutar_sueño()
