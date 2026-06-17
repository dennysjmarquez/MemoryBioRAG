"""
Semántica: expansión de queries por equivalencias léxicas.

Permite que "auto" encuentre "vehículo" sin embeddings externos.
Tabla semantica bidireccional con peso y límite de expansión.
"""

import json
import os


def init_semantica_table(cursor):
    """Crea la tabla semantica si no existe."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semantica (
            termino TEXT NOT NULL,
            equivalente TEXT NOT NULL,
            peso REAL DEFAULT 0.8,
            PRIMARY KEY (termino, equivalente)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sem_term ON semantica(termino)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sem_equiv ON semantica(equivalente)")
    cursor.connection.commit()


def expandir_query(cursor, termino, max_equivalentes=5):
    """
    Expande un término a sus equivalentes semánticos.
    Busca en ambas direcciones: auto→vehículo y vehículo→auto.
    Retorna lista de equivalentes ordenados por peso.
    """
    init_semantica_table(cursor)
    termino = termino.lower().strip()
    cursor.execute(
        "SELECT equivalente, peso FROM semantica WHERE termino = ? "
        "UNION "
        "SELECT termino, peso FROM semantica WHERE equivalente = ? "
        "ORDER BY peso DESC LIMIT ?",
        (termino, termino, max_equivalentes)
    )
    return [row[0] for row in cursor.fetchall()]


def agregar_equivalencia(cursor, termino, equivalente, peso=0.8):
    """
    Agrega una equivalencia semántica bidireccional.
    Inserta ambos sentidos: termino→equivalente y equivalente→termino.
    """
    init_semantica_table(cursor)
    termino = termino.lower().strip()
    equivalente = equivalente.lower().strip()
    if termino == equivalente:
        return
    cursor.execute(
        "INSERT OR REPLACE INTO semantica (termino, equivalente, peso) VALUES (?, ?, ?)",
        (termino, equivalente, peso)
    )
    cursor.execute(
        "INSERT OR REPLACE INTO semantica (termino, equivalente, peso) VALUES (?, ?, ?)",
        (equivalente, termino, peso)
    )
    cursor.connection.commit()


def eliminar_equivalencia(cursor, termino, equivalente):
    """Elimina una equivalencia semántica (ambos sentidos)."""
    init_semantica_table(cursor)
    termino = termino.lower().strip()
    equivalente = equivalente.lower().strip()
    cursor.execute(
        "DELETE FROM semantica WHERE (termino = ? AND equivalente = ?) OR (termino = ? AND equivalente = ?)",
        (termino, equivalente, equivalente, termino)
    )
    cursor.connection.commit()


def listar_equivalencias(cursor, termino=None):
    """
    Lista equivalencias semánticas.
    Si termino es None, retorna todas.
    """
    init_semantica_table(cursor)
    if termino:
        termino = termino.lower().strip()
        cursor.execute(
            "SELECT termino, equivalente, peso FROM semantica WHERE termino = ? OR equivalente = ? ORDER BY peso DESC",
            (termino, termino)
        )
    else:
        cursor.execute("SELECT termino, equivalente, peso FROM semantica ORDER BY peso DESC")
    return cursor.fetchall()


def tabla_vacia(cursor):
    """Verifica si la tabla semántica está vacía."""
    init_semantica_table(cursor)
    cursor.execute("SELECT COUNT(*) FROM semantica")
    return cursor.fetchone()[0] == 0


def cargar_vocabulario(cursor, vocabulario_dict):
    """
    Carga vocabulario desde un diccionario.
    Estructura: {"categoria": {"term": ["equiv1", "equiv2"], ...}}
    Inserta bidireccionalmente.
    """
    init_semantica_table(cursor)
    count = 0
    for categoria, terminos in vocabulario_dict.items():
        for term, equivalentes in terminos.items():
            for equiv in equivalentes:
                agregar_equivalencia(cursor, term, equiv, 0.85)
                count += 1
    return count


def cargar_vocabulario_desde_archivo(cursor, ruta_archivo):
    """Carga vocabulario desde un archivo JSON."""
    if not os.path.exists(ruta_archivo):
        return 0
    with open(ruta_archivo, 'r', encoding='utf-8') as f:
        vocabulario = json.load(f)
    return cargar_vocabulario(cursor, vocabulario)


def auto_aprender_desde_sononimos(cursor, concepto, sinonimos):
    """
    Aprende equivalencias semánticas desde los sinónimos de un nodo.
    Llamar cuando se guarda un nodo con sinónimos explícitos.
    """
    if not sinonimos:
        return 0
    init_semantica_table(cursor)
    concepto = concepto.lower().strip()
    sinonimos_list = [s.strip().lower() for s in sinonimos.split(",") if s.strip()]
    count = 0
    for sinonimo in sinonimos_list:
        if sinonimo != concepto and len(sinonimo) >= 2:
            agregar_equivalencia(cursor, concepto, sinonimo, 0.85)
            count += 1
    return count
