"""
Módulo de métodos de catálogo (categorías, dimensiones y sincronización).

Extraído de SQLiteMemoryBioRAG (Paso 3.4d - T17).
"""

import logging

logger = logging.getLogger("BioRAG.MemoryStore")


def _resolver_categoria_id(self, nombre):
    if not self._cat_cache:
        cur = self.conn.execute("SELECT id, name FROM categories")
        for row in cur.fetchall():
            self._cat_cache[row[1]] = row[0]
    if nombre in self._cat_cache:
        return self._cat_cache[nombre]

    # Mapeo insensible a mayúsculas y alias español/inglés
    norm_map = {
        'proyecto': 'Project', 'project': 'Project',
        'leccion': 'Lesson', 'lección': 'Lesson', 'lesson': 'Lesson',
        'sistema': 'System', 'system': 'System',
        'arquitectura': 'Architecture', 'architecture': 'Architecture',
        'perfil': 'Profile', 'profile': 'Profile',
        'personal': 'Personal',
        'principio': 'Principle', 'principle': 'Principle',
        'protocolo': 'Protocol', 'protocol': 'Protocol',
        'cognicion': 'Cognition', 'cognición': 'Cognition', 'cognition': 'Cognition',
        'metacognicion': 'Cognition', 'metacognición': 'Cognition',
        'relacion': 'Relation', 'relación': 'Relation', 'relation': 'Relation',
        'general': 'General', 'solucion': 'Lesson', 'solución': 'Lesson'
    }
    n_clean = str(nombre).strip().lower()
    if n_clean in norm_map and norm_map[n_clean] in self._cat_cache:
        return self._cat_cache[norm_map[n_clean]]

    for k, v in self._cat_cache.items():
        if k.lower() == n_clean:
            return v

    validas = ", ".join(sorted(self._cat_cache.keys()))
    raise ValueError(f"Categoria '{nombre}' no existe. Validas: {validas}")


def listar_categorias(self):
    self.cursor.execute("SELECT id, name, description FROM categories ORDER BY id")
    return self.cursor.fetchall()


def _resolver_dimension_ids(self, tipo_nombre, valores_str):
    """Convierte nombres de dimensiones de un eje específico a lista de IDs.
    Retorna (ids_validos, nombres_invalidos)."""
    nombres = [v.strip().lower() for v in valores_str.split(",") if v.strip()]
    if not nombres:
        return [], []
    ph = ",".join("?" * len(nombres))
    self.cursor.execute(
        f"SELECT id, name FROM dimensiones_semanticas "
        f"WHERE tipo_id = (SELECT id FROM tipos_dimension WHERE nombre = ?) "
        f"AND name IN ({ph})",
        [tipo_nombre] + nombres,
    )
    rows = self.cursor.fetchall()
    encontrados = {row[1]: row[0] for row in rows}
    ids_validos = [encontrados[n] for n in nombres if n in encontrados]
    invalidos = [n for n in nombres if n not in encontrados]
    return ids_validos, invalidos


def _obtener_arbol_dimensiones(self):
    """Retorna el catálogo completo de dimensiones formateado como string.
    Se usa para inyectar el catálogo vivo en la descripción de la tool aprender."""
    self.cursor.execute("""
        SELECT t.nombre, t.description, d.name, d.description
        FROM tipos_dimension t
        LEFT JOIN dimensiones_semanticas d ON d.tipo_id = t.id
        ORDER BY t.id, d.id
    """)
    filas = self.cursor.fetchall()
    arbol = {}
    for tipo_nombre, tipo_desc, dim_nombre, dim_desc in filas:
        if tipo_nombre not in arbol:
            arbol[tipo_nombre] = {"desc": tipo_desc, "dims": []}
        if dim_nombre:
            arbol[tipo_nombre]["dims"].append(f"{dim_nombre}: {dim_desc or '(sin descripción)'}")

    lineas = []
    for tipo_nombre, data in arbol.items():
        dims_str = "; ".join(data["dims"]) if data["dims"] else "(vacío)"
        lineas.append(f"  {tipo_nombre}: {dims_str}")
    return "\n".join(lineas)


def sync_status(self):
    """Retorna categorías pendientes de sincronizar."""
    self.cursor.execute("""
        SELECT c.id, c.name, COUNT(sl.id) as cambios
        FROM sync_log sl
        JOIN categories c ON sl.categoria_id = c.id
        WHERE sl.sincronizado = 0
        GROUP BY c.id, c.name
        ORDER BY c.name
    """)
    return self.cursor.fetchall()


def sync_marcado(self, categoria_ids):
    """Marca categorías como sincronizadas."""
    if not categoria_ids:
        return
    placeholders = ",".join("?" * len(categoria_ids))
    self.cursor.execute(
        f"UPDATE sync_log SET sincronizado = 1 WHERE categoria_id IN ({placeholders}) AND sincronizado = 0",
        categoria_ids
    )
    self.conn.commit()


def sync_limpiar(self):
    """Limpia el log de sincronización ya procesado."""
    self.cursor.execute("DELETE FROM sync_log WHERE sincronizado = 1")
    self.conn.commit()
