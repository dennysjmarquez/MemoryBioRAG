"""core/memory/ingest.py - Módulo de percepción e ingestión de recuerdos.

Extraído de SQLiteMemoryBioRAG siguiendo el patrón A1:
- Funciones con `self` como primer parámetro.
- Mantiene cuerpos intactos e imports internos dentro de las funciones.
"""

import time

from core.identidad_unicode import normalizar_identidad, _recortar_sin_perder_espacio_ideografico


def _comprobar_clave_legacy(self, original, normalizada):
    """Conserva la clave exacta si ya existe; en caso contrario usa la nueva."""
    if original == normalizada:
        return original
    self.cursor.execute(
        "SELECT concepto FROM corto_plazo WHERE concepto = ? "
        "UNION ALL SELECT concepto FROM largo_plazo WHERE concepto = ? LIMIT 1",
        (original, original),
    )
    return original if self.cursor.fetchone() is not None else normalizada


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
    sustantivos_clave_exactos=None,
):
    """Almacena temporalmente una percepción o hecho en la memoria de trabajo (Corto Plazo).
    Si el concepto ya existe en corto plazo, concatena contenido y mergea sinónimos.
    dimensiones: dict {tipo_nombre: [valores]} para indexación de 5 ejes.
    predicados: list[dict] con {sujeto, accion, objeto, contexto} para SRL v16.0.
    valencia_somatica: float [0.0, 1.0] para marcadores somáticos (v20.0).
    sustantivos_clave plegados y sustantivos_clave_exactos se sustituyen como un par
    cuando la percepción aporta sustantivos; no se fusionan etiquetas entre notas.
    Si la percepción no aporta sustantivos, conserva las etiquetas plegadas y exactas
    ya existentes en corto plazo; para un concepto nuevo, la etiqueta exacta queda NULL."""
    # Solo se transforman datos que entran en esta escritura; no filas antiguas.
    key_original = concepto.lower().strip()
    key_normalizada = normalizar_identidad(concepto).lower().strip()
    key = _comprobar_clave_legacy(self, key_original, key_normalizada)
    contenido = normalizar_identidad(contenido, ancho_solo_letras_numeros=True)
    sinonimos = normalizar_identidad(sinonimos or "", ancho_solo_letras_numeros=True)
    # Los sustantivos ya llegan normalizados por la herramienta. No recomponer
    # aquí su salida histórica NFKD: se comparte con la búsqueda actual.
    cat_id = self._resolver_categoria_id(categoria)

    # Auto-asignar valencia somática máxima si la categoría es Principle o Protocol
    if isinstance(categoria, str) and categoria.lower() in ("principle", "protocol"):
        valencia_somatica = 1.0

    self.cursor.execute(
        "SELECT contenido, sinonimos, categoria, COALESCE(sustantivos_clave, ''), sustantivos_clave_exactos "
        "FROM corto_plazo WHERE concepto = ?",
        (key,),
    )
    existente = self.cursor.fetchone()
    from core.memory_store import normalizar_sustantivos_clave_exactos_coherentes
    sk_entrante = sustantivos_clave or ""
    if existente:
        contenido_final = existente[0] + f" | Actualización: {contenido}"
        sinonimos_exist = [
            _recortar_sin_perder_espacio_ideografico(s)
            for s in (existente[1] or "").split(",") if s.strip()
        ]
        claves_exist = {s.strip() for s in sinonimos_exist}
        sinonimos_nuevos = [
            _recortar_sin_perder_espacio_ideografico(s)
            for s in (sinonimos or "").split(",")
            if s.strip() and s.strip() not in claves_exist
        ]
        sinonimos_final = ",".join(sinonimos_exist + sinonimos_nuevos)
        cat_id = existente[2] or cat_id
        if sk_entrante.strip():
            sk_final = sk_entrante
            sk_exactos_final = normalizar_sustantivos_clave_exactos_coherentes(
                sustantivos_clave_exactos, sk_final
            )
        else:
            # Una llamada sin sustantivos no borra ni el campo plegado ni su exacto.
            sk_final = existente[3] or ""
            sk_exactos_final = normalizar_sustantivos_clave_exactos_coherentes(
                existente[4], sk_final
            )
    else:
        contenido_final = contenido
        sinonimos_final = sinonimos
        sk_final = sk_entrante
        sk_exactos_final = normalizar_sustantivos_clave_exactos_coherentes(
            sustantivos_clave_exactos, sk_final
        )

    self.cursor.execute(
        """
        INSERT OR REPLACE INTO corto_plazo (concepto, contenido, timestamp, sinonimos, categoria, valencia_somatica, sustantivos_clave, sustantivos_clave_exactos)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            key,
            contenido_final,
            time.time(),
            sinonimos_final,
            cat_id,
            float(valencia_somatica or 0.0),
            sk_final,
            sk_exactos_final,
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
            ids_validos, _, _ = self._resolver_dimension_ids(
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

    Si el concepto ya existe en largo_plazo lo FUSIONA (UPDATE) con la misma
    regla que el ciclo de sueño (``consolidation.fusionar_en_largo_plazo``):
    conserva id, creado_en, dimensiones, métricas y grupos. Antes usaba
    ``INSERT OR REPLACE``, que borraba la fila vieja (cascadas, sin backup,
    contenido perdido y filas fantasma en FTS5)."""
    from core.memory.consolidation import fusionar_en_largo_plazo

    key_original = concepto.lower().strip()
    key_normalizada = normalizar_identidad(concepto).lower().strip()
    key = _comprobar_clave_legacy(self, key_original, key_normalizada)
    self.cursor.execute(
        "SELECT contenido, sinonimos, categoria, COALESCE(valencia_somatica, 0.0), "
        "COALESCE(sustantivos_clave, ''), sustantivos_clave_exactos FROM corto_plazo WHERE concepto = ?",
        (key,),
    )
    fila = self.cursor.fetchone()
    if not fila:
        return False
    contenido, sinonimos, cat_id, val_somatica, sk_corto, sk_exactos = fila

    fusionar_en_largo_plazo(self, key, contenido, sinonimos, cat_id, val_somatica, sk_corto, sk_exactos)
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
    # Neurona: este recuerdo se hace sus propias preguntas y la neurona aprende
    # en vivo (costo fijo, en silencio). Nunca rompe la escritura.
    try:
        from core.memory import neurona

        neurona.practicar(self, [key])
    except Exception:
        pass
    return True
