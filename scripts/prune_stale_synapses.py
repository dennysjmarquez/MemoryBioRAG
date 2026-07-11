#!/usr/bin/env python3
import sys
import os

# Agregar directorio raíz al path para importar core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from biorag import SQLiteMemoryBioRAG
from core.sinapsis import recalcular_similitud_sinapsis, calcular_idf_corpus, _sincronizar_asociaciones


def audit_and_prune_sinapsis(dry_run=False):
    cerebro = SQLiteMemoryBioRAG()
    try:
        # Obtener todas las sinapsis automáticas
        cerebro.cursor.execute(
            "SELECT origen, destino, peso, tipo FROM sinapsis WHERE tipo IN ('co_ocurrencia', 'co_nombre', 'co_semantica')"
        )
        sinapsis = cerebro.cursor.fetchall()

        print(f"Total sinapsis automáticas encontradas para auditar: {len(sinapsis)}")
        
        idf_map = calcular_idf_corpus(cerebro)
        
        eliminadas = 0
        actualizadas = 0
        mantienen = 0
        conceptos_afectados = set()

        # Para evitar procesar la misma pareja bidireccional dos veces de forma redundante
        parejas_procesadas = set()

        for origen, destino, peso, tipo in sinapsis:
            # Crear una clave única de la pareja ordenada
            pareja = tuple(sorted([origen, destino]))
            if pareja in parejas_procesadas:
                continue
            parejas_procesadas.add(pareja)

            # Recalcular similitud con la fórmula IDF actual
            nueva_sim = recalcular_similitud_sinapsis(cerebro, origen, destino, idf_map=idf_map)

            # Umbral actual en BioRAG es 0.4
            if nueva_sim < 0.4:
                print(f"[PODA] {origen} <-> {destino} | Peso viejo: {peso} | Nueva Sim: {nueva_sim} | Eliminando...")
                if not dry_run:
                    cerebro.cursor.execute(
                        "DELETE FROM sinapsis WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
                        (origen, destino, destino, origen)
                    )
                eliminadas += 1
                conceptos_afectados.add(origen)
                conceptos_afectados.add(destino)
            else:
                if peso != nueva_sim:
                    print(f"[UPDATE] {origen} <-> {destino} | Peso viejo: {peso} -> Nuevo Peso: {nueva_sim}")
                    if not dry_run:
                        cerebro.cursor.execute(
                            "UPDATE sinapsis SET peso = ? WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
                            (nueva_sim, origen, destino, destino, origen)
                        )
                    actualizadas += 1
                else:
                    mantienen += 1

        if not dry_run:
            # Sincronizar campo 'asociaciones' en la tabla largo_plazo para los conceptos modificados
            for concepto in conceptos_afectados:
                _sincronizar_asociaciones(cerebro, concepto)
            cerebro.conn.commit()
            print("\n[ÉXITO] Cambios guardados en la base de datos.")
        else:
            print("\n[DRY RUN] Ejecución de simulación. No se realizaron cambios permanentes.")

        print(f"Resumen:")
        print(f" - Sinapsis eliminadas (sim < 0.4): {eliminadas} (bidireccionales)")
        print(f" - Sinapsis actualizadas en peso: {actualizadas}")
        print(f" - Sinapsis que se mantienen iguales: {mantienen}")

    finally:
        cerebro.cerrar_sistema()


if __name__ == "__main__":
    dry_run = "--run" not in sys.argv
    if dry_run:
        print("Ejecutando en modo DRY RUN (Simulación). Usa '--run' para aplicar los cambios.")
    audit_and_prune_sinapsis(dry_run=dry_run)
