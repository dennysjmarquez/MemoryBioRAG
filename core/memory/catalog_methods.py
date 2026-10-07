"""
Módulo de métodos de catálogo (categorías, dimensiones y sincronización).

Extraído de SQLiteMemoryBioRAG (Paso 3.4d - T17).
"""

import logging
import re
import time
import unicodedata

logger = logging.getLogger("BioRAG.MemoryStore")


def _normalizar_nombre_dimension(nombre: str):
    """Normaliza un nombre de dimensión a snake_case ASCII válido.

    Aplica las siguientes transformaciones en orden:
      1. Strip de espacios al inicio/fin.
      2. NFD + eliminación de diacríticos (tildes, cedillas, etc.).
      3. Minúsculas.
      4. Espacios, guiones y puntos → guión bajo.
      5. Elimina caracteres que no sean [a-z0-9_].
      6. Colapsa múltiples guiones bajos consecutivos a uno solo.
      7. Elimina guiones bajos al inicio/fin.
      8. Trunca a 80 caracteres (borde del campo TEXT de SQLite).

    Retorna el nombre normalizado (str) si es válido, o None si el resultado
    es innormalizable (vacío, menor a 2 chars, o empieza con dígito).
    """
    if not nombre or not isinstance(nombre, str):
        return None
    s = nombre.strip()
    # Paso 2: descomponer NFD y eliminar marcas de combinación (diacríticos)
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    # Paso 3: minúsculas
    s = s.lower()
    # Paso 4: separadores legibles → guión bajo
    s = re.sub(r'[\s\-\.]+', '_', s)
    # Paso 5: eliminar todo lo que no sea alphanumerico o guión bajo
    s = re.sub(r'[^a-z0-9_]', '', s)
    # Paso 6: colapsar guiones bajos múltiples
    s = re.sub(r'_+', '_', s)
    # Paso 7: trim de guiones bajos
    s = s.strip('_')
    # Paso 8: truncar
    if len(s) > 80:
        s = s[:80].rstrip('_')

    # Validaciones de integridad
    if not s:
        return None
    if len(s) < 2:
        return None
    if not s[0].isalpha():  # debe comenzar con letra, no con número ni _
        return None
    return s


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
    """Convierte nombres de dimensiones de un eje a lista de IDs.

    Comportamiento (mundo abierto para valores, cerrado para ejes):
      - Normaliza cada nombre automáticamente (NFD, snake_case, lowercase).
      - Si el nombre normalizado YA EXISTE en el catálogo → reutiliza su ID.
        (No importa el eje: `name` es globalmente UNIQUE — anti-duplicado garantizado.)
      - Si NO EXISTE → crea una nueva entrada con auto_generada=1, confianza=0.7.
      - Si el nombre es innormalizable (emojis, vacío, etc.) → lo agrega a `invalidos`.

    Retorna (ids_validos: list[int], invalidos: list[str], creadas: list[str]).
      - invalidos : nombres que no pudieron normalizarse.
      - creadas   : nombres de dimensiones que fueron auto-creadas en esta llamada.
    """
    nombres_raw = [v.strip() for v in valores_str.split(",") if v.strip()]
    if not nombres_raw:
        return [], [], []

    # Obtener tipo_id del eje — si no existe, el eje es inválido (manejo en _resolver_dimensiones)
    self.cursor.execute(
        "SELECT id FROM tipos_dimension WHERE nombre = ?", (tipo_nombre,)
    )
    tipo_row = self.cursor.fetchone()
    if not tipo_row:
        # El eje no existe: retornamos todos como inválidos para que el caller lo maneje
        return [], nombres_raw, []
    tipo_id = tipo_row[0]

    ids_validos = []
    invalidos = []
    creadas = []

    for nombre_raw in nombres_raw:
        nombre_norm = _normalizar_nombre_dimension(nombre_raw)

        if nombre_norm is None:
            # Nombre imposible de normalizar — ej: emoji, string numérico puro, vacío
            invalidos.append(nombre_raw)
            continue

        # Búsqueda global por nombre normalizado (UNIQUE en toda la tabla)
        self.cursor.execute(
            "SELECT id FROM dimensiones_semanticas WHERE name = ?",
            (nombre_norm,)
        )
        row = self.cursor.fetchone()

        if row:
            # Ya existe — reutilizar ID. Sin inserción. Anti-duplicado absoluto.
            ids_validos.append(row[0])
        else:
            # No existe — auto-crear con marcadores de confianza reducida
            try:
                self.cursor.execute(
                    """
                    INSERT OR IGNORE INTO dimensiones_semanticas
                        (name, description, tipo_id, auto_generada, confianza, generado_en)
                    VALUES (?, '', ?, 1, 0.7, ?)
                    """,
                    (nombre_norm, tipo_id, time.time())
                )
                # SELECT incondicional: captura tanto inserción nueva como race-condition
                self.cursor.execute(
                    "SELECT id FROM dimensiones_semanticas WHERE name = ?",
                    (nombre_norm,)
                )
                new_row = self.cursor.fetchone()
                if new_row:
                    ids_validos.append(new_row[0])
                    creadas.append(nombre_norm)
                    logger.info(
                        "[DimensionHub] Auto-creada: '%s' en eje '%s' (auto_generada=1, confianza=0.7)",
                        nombre_norm, tipo_nombre
                    )
            except Exception as exc:
                logger.warning(
                    "[DimensionHub] Error al auto-crear '%s' en eje '%s': %s",
                    nombre_norm, tipo_nombre, exc
                )
                invalidos.append(nombre_raw)

    return ids_validos, invalidos, creadas


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
