"""core/memory/quarantine.py - Módulo de cuarentena y evicción de recuerdos.

Extraído de SQLiteMemoryBioRAG siguiendo el patrón A1:
- Funciones con `self` como primer parámetro.
- Mantiene cuerpos intactos.
"""

import time


def _candidatos_eviccion(self, limite=5):
    """Identifica nodos candidatos para eviccion (dormant — no ejecuta borrado).

    Retorna lista de (concepto, peso, ultimo_acceso, dias_sin_acceso)
    """
    now = time.time()
    self.cursor.execute("""
        SELECT concepto, peso_sinaptico, ultimo_acceso,
               ROUND((? - ultimo_acceso) / 86400.0, 1) as dias_sin_acceso
        FROM largo_plazo
        WHERE estado = 'dormido'
          AND peso_sinaptico <= 0.1
        ORDER BY ultimo_acceso ASC
        LIMIT ?
    """, (now, limite))
    return self.cursor.fetchall()


def _ejecutar_eviccion(self, max_borrar=10):
    """Borra nodos dormidos abandonados para liberar espacio en la corteza.

    Solo se activa cuando la env var BIORAG_PODAR=true.
    Elimina hasta `max_borrar` nodos que cumplan:
      - estado = 'dormido'
      - peso_sinaptico <= 0.01
    Ordenados por ultimo_acceso ASC (los mas viejos primero).

    USO (solo via env var, no hay flag CLI):
      export BIORAG_PODAR=true
      python3 biorag.py sueno

    Sin BIORAG_PODAR=true esto nunca se ejecuta.
    Los datos borrados no se pueden recuperar — usar con criterio.
    """
    self.cursor.execute("""
        SELECT concepto FROM largo_plazo
        WHERE estado = 'dormido'
          AND peso_sinaptico <= 0.01
        ORDER BY ultimo_acceso ASC
        LIMIT ?
    """, (max_borrar,))
    candidatos = [row[0] for row in self.cursor.fetchall()]
    if not candidatos:
        return 0
    placeholders = ",".join("?" for _ in candidatos)
    self.cursor.execute(
        f"DELETE FROM largo_plazo WHERE concepto IN ({placeholders})", candidatos
    )
    # FTS cleanup via trigger largo_plazo_ad (no manual DELETE needed)
    self.conn.commit()
    return len(candidatos)


def purgar_cuarentena_vencida(self) -> int:
    """Elimina definitivamente nodos en cuarentena con fecha_expiracion vencida.
    Corre automáticamente al inicio de cada recordar (path caliente).
    Retorna cantidad de nodos eliminados."""
    ahora = time.time()
    self.cursor.execute(
        "DELETE FROM largo_plazo WHERE estado = 'cuarentena' AND fecha_expiracion IS NOT NULL AND fecha_expiracion < ?",
        (ahora,)
    )
    n = self.cursor.rowcount
    if n > 0:
        self.conn.commit()
    return n


def mover_a_cuarentena(self, concepto: str, dias_expiracion: int = 30) -> bool:
    """Mueve un nodo a estado 'cuarentena' con fecha de expiración.
    Reversible: si el nodo se referencia antes de expirar, vuelve a activo.
    El purge definitivo corre automáticamente en cada recordar."""
    self.cursor.execute("SELECT estado FROM largo_plazo WHERE concepto = ?", (concepto,))
    row = self.cursor.fetchone()
    if not row:
        return False
    ahora = time.time()
    expiracion = ahora + (dias_expiracion * 86400)
    self.cursor.execute(
        "UPDATE largo_plazo SET estado = 'cuarentena', fecha_expiracion = ? WHERE concepto = ?",
        (expiracion, concepto)
    )
    self.conn.commit()
    return True


def rescatar_de_cuarentena(self, concepto: str) -> bool:
    """Rescata un nodo de cuarentena antes de que expire.
    Vuelve a estado activo. Se gatilla automáticamente si el nodo
    aparece en resultados de recordar con score > 0."""
    self.cursor.execute(
        "UPDATE largo_plazo SET estado = 'activo', fecha_expiracion = NULL WHERE concepto = ? AND estado = 'cuarentena'",
        (concepto,)
    )
    n = self.cursor.rowcount
    if n > 0:
        self.conn.commit()
    return n > 0


def buscar_en_cuarentena(self, frase: str, limite: int = 3):
    """Busca nodos en estado 'cuarentena' que matcheen la frase via FTS.

    Independiente del 'profundidad' de la búsqueda principal: el filtro
    l.estado = 'activo' de buscar_por_frase excluye la cuarentena, así que
    el auto-rescate del camino normal de recordar necesita su propia query.
    Sin esto, un nodo en cuarentena solo podía salir por purge o por
    rescate manual con deep=True (cuarentena de una sola vía en la práctica).

    Retorna lista de (concepto, contenido, peso_sinaptico, bm25)."""
    if not frase or not frase.strip():
        return []
    import re as _re

    def _fts_safe_term(term):
        partes = _re.split(r'[-]+', term)
        return " ".join(p for p in partes if p)

    tokens = [t for t in frase.split() if len(t) >= 2]
    if not tokens:
        return []
    fts_match = " OR ".join(f'"{_fts_safe_term(t)}"' for t in tokens)
    self.cursor.execute(
        """
        SELECT l.concepto, l.contenido, l.peso_sinaptico,
               bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) AS bm25_val
        FROM largo_plazo_fts f
        CROSS JOIN largo_plazo l ON l.rowid = f.rowid
        WHERE largo_plazo_fts MATCH ? AND l.estado = 'cuarentena'
        ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0)
        LIMIT ?
        """,
        (fts_match, limite)
    )
    return self.cursor.fetchall()
