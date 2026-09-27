"""core/memory/ingest.py - Módulo de percepción e ingestión de recuerdos.

Extraído de SQLiteMemoryBioRAG siguiendo el patrón A1:
- Funciones con `self` como primer parámetro.
- Mantiene cuerpos intactos e imports internos dentro de las funciones.
"""

import time


def percibir_corto_plazo(
    self,
    concepto,
    contenido,
    sinonimos="",
    categoria="General",
    dimensiones=None,
    predicados=None,
    valencia_somatica=0.0,
    sustantivos_clave="",
):
    """Almacena temporalmente una percepción o hecho en la memoria de trabajo (Corto Plazo).
    Si el concepto ya existe en corto plazo, concatena contenido y mergea sinónimos.
    dimensiones: dict {tipo_nombre: [valores]} para indexación de 5 ejes.
    predicados: list[dict] con {sujeto, accion, objeto, contexto} para SRL v16.0.
    valencia_somatica: float [0.0, 1.0] para marcadores somáticos (v20.0).
    sustantivos_clave: str (v25 spec 001) — centro de gravedad temático, ya normalizado por
    la tool (aprender/guardar). Sobrescribe el valor previo (no merge): si el tema cambió,
    los sustantivos se reemplazan (Decisión 2 del plan 001). Aditivo: default '' = nodos
    legacy sin sustantivos, el comportamiento previo no cambia."""
    key = concepto.lower().strip()
    cat_id = self._resolver_categoria_id(categoria)

    # Auto-asignar valencia somática máxima si la categoría es Principle o Protocol
    if isinstance(categoria, str) and categoria.lower() in ("principle", "protocol"):
        valencia_somatica = 1.0

    self.cursor.execute(
        "SELECT contenido, sinonimos, categoria FROM corto_plazo WHERE concepto = ?",
        (key,),
    )
    existente = self.cursor.fetchone()
    if existente:
        contenido_final = existente[0] + f" | Actualización: {contenido}"
        sinonimos_exist = [
            s.strip() for s in (existente[1] or "").split(",") if s.strip()
        ]
        sinonimos_nuevos = [
            s.strip()
            for s in (sinonimos or "").split(",")
            if s.strip() and s.strip() not in sinonimos_exist
        ]
        sinonimos_final = ",".join(sinonimos_exist + sinonimos_nuevos)
        cat_id = existente[2] or cat_id
    else:
        contenido_final = contenido
        sinonimos_final = sinonimos

    self.cursor.execute(
        """
        INSERT OR REPLACE INTO corto_plazo (concepto, contenido, timestamp, sinonimos, categoria, valencia_somatica, sustantivos_clave)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            key,
            contenido_final,
            time.time(),
            sinonimos_final,
            cat_id,
            float(valencia_somatica or 0.0),
            sustantivos_clave or "",
        ),
    )

    # SRL v16.0: Almacenar predicados en corto_plazo_predicados (se propagan al consolidar)
    if predicados:
        ahora = time.time()
        for pred in predicados:
            if not isinstance(pred, dict):
                continue
            self.cursor.execute(
                "INSERT INTO corto_plazo_predicados (concepto, sujeto, accion, objeto, contexto, creado_en) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    key,
                    pred.get("sujeto"),
                    pred.get("accion"),
                    pred.get("objeto"),
                    pred.get("contexto"),
                    ahora,
                ),
            )

    # Insertar dimensiones en tabla puente
    # Si dimensiones ya es dict de IDs (de _resolver_dimensiones), usar directamente
    # Si es dict de nombres (legacy), resolver IDs
    dim_dict = dimensiones or {}
    for tipo_nombre, valores in dim_dict.items():
        if not valores:
            continue
        # Si los valores son ints, ya son IDs resueltos
        if isinstance(valores[0], int):
            ids_validos = valores
        else:
            ids_validos, _ = self._resolver_dimension_ids(
                tipo_nombre,
                ",".join(valores) if isinstance(valores, list) else valores,
            )
        for eid in ids_validos:
            self.cursor.execute(
                "INSERT OR IGNORE INTO corto_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)",
                (key, eid),
            )

    self.conn.commit()

    # ponytail: removed semantic table expansion — agent passes synonyms directly


def consolidar_concepto(self, concepto):
    """Mueve un concepto de corto a largo plazo directamente.
    No ejecuta LTD, inhibición lateral ni toca otros nodos.
    El trigger FTS5 se encarga del índice automáticamente."""
    key = concepto.lower().strip()
    self.cursor.execute(
        "SELECT contenido, sinonimos, categoria FROM corto_plazo WHERE concepto = ?",
        (key,),
    )
    fila = self.cursor.fetchone()
    if not fila:
        return False
    contenido, sinonimos, cat_id = fila

    self.cursor.execute(
        "INSERT OR REPLACE INTO largo_plazo "
        "(concepto, categoria, contenido, peso_sinaptico, estado, sinonimos, creado_en) "
        "VALUES (?, ?, ?, 1.0, 'activo', ?, ?)",
        (key, cat_id, contenido, sinonimos or "", time.time()),
    )
    # ponytail: ultimo_acceso se actualiza en cada acceso, creado_en es el timestamp de consolidación
    # Propagar dimensiones de corto → largo plazo
    self.cursor.execute(
        """
        INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id)
        SELECT concepto, dimension_id FROM corto_plazo_dimensiones WHERE concepto = ?
    """,
        (key,),
    )
    self.cursor.execute(
        "DELETE FROM corto_plazo_dimensiones WHERE concepto = ?", (key,)
    )
    self.cursor.execute("DELETE FROM corto_plazo WHERE concepto = ?", (key,))
    self.conn.commit()
    from core.sinapsis import auto_vincular

    auto_vincular(self, key, contenido)
    # Clasificación simbólica: WordNet lexnames
    self._clasificar_nodo_wordnet(key, contenido, sinonimos or "")
    # v29: el recuerdo se marca como cambio estructural. El ADN y los vecinos
    # se reconstruyen de forma batch en el siguiente ciclo de sueño DMN; no hay
    # inferencia vectorial ni recorrido del corpus en el camino de escritura.
    self._adn_pendiente_recalculo = True
    # SDM v19.0: Indexar vector binario para recuperación por similitud estructural
    try:
        from core.sdm import indexar_nodo_sdm

        indexar_nodo_sdm(self, key)
    except Exception:
        pass
    # SRL v16.0: Propagar predicados de corto → largo plazo
    self.cursor.execute(
        """
        INSERT INTO predicados (concepto, sujeto, accion, objeto, contexto, creado_en)
        SELECT concepto, sujeto, accion, objeto, contexto, creado_en FROM corto_plazo_predicados WHERE concepto = ?
    """,
        (key,),
    )
    self.cursor.execute(
        "DELETE FROM corto_plazo_predicados WHERE concepto = ?", (key,)
    )
    return True
