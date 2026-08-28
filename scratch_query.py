import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MemoryBioRAG_Data", "memory_biorag.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

conceptos = [
    'cv_dennys_secciones_ab_finales_2026',
    'cv_click_result_arquitectura_frontend_decodificada',
    'cv_seccion_d_test_vinculacion',
    'cv_seccion_d_test_vinculacion2',
    'cv_bondarea_arquitectura_frontend_decodificada',
    'cv_seccion_d_estado_final_julio_2026',
    'cv_epidata_credit_agile_propuestas',
    'cv_seccion_d_arquitectura_frontend_estado',
    'cv_adevcom_arquitectura_frontend_decodificada'
]

for conc in conceptos:
    print(f"\n=== NODO: {conc} ===")
    
    # Dimensiones
    c.execute('''
        SELECT t.nombre as eje, d.name as valor
        FROM largo_plazo_dimensiones lpd
        JOIN dimensiones_semanticas d ON lpd.dimension_id = d.id
        JOIN tipos_dimension t ON d.tipo_id = t.id
        WHERE lpd.concepto = ?
    ''', (conc,))
    dims = c.fetchall()
    print("DIMENSIONES:")
    if dims:
        for r in dims:
            print(f"  - {r['eje']}: {r['valor']}")
    else:
        print("  - (Ninguna dimensión explícita registrada)")
        
    # Sinapsis
    c.execute('''
        SELECT 
            CASE WHEN origen = ? THEN destino ELSE origen END as asociado,
            peso
        FROM sinapsis
        WHERE origen = ? OR destino = ?
        ORDER BY peso DESC
    ''', (conc, conc, conc))
    syns = c.fetchall()
    print("SINAPSIS ASOCIATIVAS (Top más fuertes):")
    if syns:
        for r in syns[:7]:
            print(f"  - {r['asociado']} (Peso: {r['peso']})")
    else:
        print("  - (Ninguna conexión sináptica)")
