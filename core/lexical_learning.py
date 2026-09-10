"""Lexical Learning Episode — puente simbólico A→B sin embeddings.

POR QUÉ (auditoría 2026-09-08): las señales no léxicas reordenan candidatos
que YA tienen ancla. Falta registrar la experiencia «expresión A, en este
contexto, refiere al concepto B» y usarla ANTES del ranking para GENERAR
candidatos. No es un diccionario global ni otro score.

Estados de evidencia (no fusionar nodos; R7):
  coocurrencia → latent
  coincidencia morfológica → candidate
  afirmación explícita → explicit
  confirmaciones repetidas → consolidated
  contradicción → quarantined

Solo `explicit` y `consolidated` expanden en búsqueda (confianza alta).
"""
from __future__ import annotations

import hashlib
import re
import time
import unicodedata
from typing import Iterable

# Relación tipada en sinapsis (canónica). No mutar `asociaciones` como fuente.
TIPO_SINAPSIS_LEXICO = "sinonimo_explicito"
ESTADOS_RECUPERABLES = frozenset({"explicit", "consolidated"})
CONF_MIN_EXPANSION = 0.7

_ACCENT_TABLE = str.maketrans(
    "áéíóúüñÁÉÍÓÚÜÑ",
    "aeiouunAEIOUUN",
)


def strip_accents(text: str) -> str:
    """Forma sin acentos para el índice invertido (simbólico, no embedding)."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_expresion(surface: str) -> str:
    """Forma canónica de una expresión: minúsculas, sin acentos, espacios colapsados.

    POR QUÉ: el índice invertido debe matchear «Panel de Control» y
    «panel de control» sin embeddings ni stemmers densos.
    """
    s = strip_accents((surface or "").strip().lower())
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def variantes_morfologicas(norm: str) -> list[str]:
    """Variantes superficiales baratas: plural -s/-es, sin espacios.

    POR QUÉ: el índice debe cubrir plural/género/compuestos sin red neuronal.
    Solo reglas locales; no WordNet aquí (WordNet ya vive en otro path).
    """
    out = {norm}
    if not norm:
        return list(out)
    out.add(norm.replace(" ", "_"))
    out.add(norm.replace(" ", ""))
    tokens = norm.split()
    if tokens:
        last = tokens[-1]
        if last.endswith("es") and len(last) > 4:
            out.add(" ".join(tokens[:-1] + [last[:-2]]).strip())
        elif last.endswith("s") and len(last) > 3:
            out.add(" ".join(tokens[:-1] + [last[:-1]]).strip())
        else:
            out.add(" ".join(tokens[:-1] + [last + "s"]).strip())
            if last.endswith(("n", "r", "l", "d", "z")):
                out.add(" ".join(tokens[:-1] + [last + "es"]).strip())
    return [v for v in out if v]


def context_hash(text: str | None) -> str:
    payload = (text or "").encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()[:16]


def inicializar_tablas_lexicas(cerebro) -> None:
    """Wrapper usado por memory_store: acepta cerebro o cursor."""
    cur = getattr(cerebro, "cursor", cerebro)
    init_lexical_tables(cur)


def init_lexical_tables(cursor) -> None:
    """Crea tablas de episodios e índice invertido. Idempotente."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lexical_learning_episode (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expression_norm TEXT NOT NULL,
            expression_surface TEXT NOT NULL,
            canonical_concept TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            context_hash TEXT,
            source TEXT NOT NULL,
            provenance TEXT,
            confidence REAL DEFAULT 0.5,
            confirmations INTEGER DEFAULT 1,
            state TEXT DEFAULT 'explicit',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_lle_norm ON lexical_learning_episode(expression_norm)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_lle_canon ON lexical_learning_episode(canonical_concept)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_lle_state ON lexical_learning_episode(state)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lexical_form_index (
            form_norm TEXT NOT NULL,
            canonical_concept TEXT NOT NULL,
            episode_id INTEGER NOT NULL,
            confidence REAL NOT NULL,
            state TEXT NOT NULL,
            PRIMARY KEY (form_norm, canonical_concept, episode_id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_lfi_form ON lexical_form_index(form_norm)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lexical_audit_event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            episode_id INTEGER,
            action TEXT NOT NULL,
            payload TEXT,
            created_at REAL NOT NULL
        )
        """
    )


def _upsert_index(cursor, episode_id: int, forms: Iterable[str], concept: str, conf: float, state: str) -> None:
    cursor.execute("DELETE FROM lexical_form_index WHERE episode_id = ?", (episode_id,))
    if state not in ESTADOS_RECUPERABLES:
        return
    for form in forms:
        if not form:
            continue
        cursor.execute(
            """
            INSERT OR REPLACE INTO lexical_form_index
                (form_norm, canonical_concept, episode_id, confidence, state)
            VALUES (?, ?, ?, ?, ?)
            """,
            (form, concept, episode_id, conf, state),
        )


def ensenar_expresion(
    cerebro,
    expression_surface: str,
    canonical_concept: str,
    *,
    relation_type: str = "paraphrase_aprendida",
    source: str = "explicit_user",
    provenance: str = "",
    context: str = "",
    confidence: float = 0.9,
    state: str = "explicit",
) -> dict:
    """Transacción única de enseñanza léxica.

    Pasos (auditoría Cap. «Cómo funcionaría el circuito»):
      1. normalizar A
      2. identificar nodo B (debe existir en largo_plazo)
      3. registrar episodio
      4. actualizar forma léxica (índice + columna sinonimos como ESPEJO, no fuente)
      5. sinapsis tipada bidireccional
      6. procedencia + confianza
      7. marcar SDM dirty / invalidar caches derivadas
      8. evento auditable (reversible)

    NO fusiona nodos (R7). Si B no existe, no inventa un nodo.
    """
    init_lexical_tables(cerebro.cursor)
    surface = (expression_surface or "").strip()
    concept = (canonical_concept or "").strip().lower()
    if not surface or not concept:
        return {"ok": False, "error": "expresion y concepto requeridos"}

    norm = normalizar_expresion(surface)
    if not norm:
        return {"ok": False, "error": "expresion vacia tras normalizar"}

    cerebro.cursor.execute(
        "SELECT concepto FROM largo_plazo WHERE concepto = ?", (concept,)
    )
    if not cerebro.cursor.fetchone():
        return {"ok": False, "error": f"concepto '{concept}' no existe en largo_plazo"}

    ch = context_hash(context)
    now_iso = time.strftime("%Y-%m-%d %H:%M:%S")

    cerebro.cursor.execute(
        """
        SELECT id, confirmations, confidence, state FROM lexical_learning_episode
        WHERE expression_norm = ? AND canonical_concept = ? AND relation_type = ?
        """,
        (norm, concept, relation_type),
    )
    row = cerebro.cursor.fetchone()
    if row:
        eid, confs, old_conf, old_state = row
        new_confs = int(confs or 1) + 1
        new_conf = min(1.0, max(float(old_conf or 0.5), float(confidence)))
        new_state = "consolidated" if new_confs >= 3 and old_state == "explicit" else (state or old_state)
        cerebro.cursor.execute(
            """
            UPDATE lexical_learning_episode
            SET confirmations = ?, confidence = ?, state = ?, updated_at = ?,
                provenance = COALESCE(?, provenance)
            WHERE id = ?
            """,
            (new_confs, new_conf, new_state, now_iso, provenance or None, eid),
        )
        episode_id = eid
        action = "confirm"
        conf_out = new_conf
        state_out = new_state
    else:
        cerebro.cursor.execute(
            """
            INSERT INTO lexical_learning_episode (
                expression_norm, expression_surface, canonical_concept,
                relation_type, context_hash, source, provenance,
                confidence, confirmations, state, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                norm, surface, concept, relation_type, ch, source,
                provenance, float(confidence), state, now_iso, now_iso,
            ),
        )
        episode_id = cerebro.cursor.lastrowid
        action = "teach"
        conf_out = float(confidence)
        state_out = state

    forms = variantes_morfologicas(norm)
    _upsert_index(cerebro.cursor, episode_id, forms, concept, conf_out, state_out)

    # Espejo en sinonimos (compatibilidad histórica). La fuente de verdad es el episodio.
    cerebro.cursor.execute(
        "SELECT sinonimos FROM largo_plazo WHERE concepto = ?", (concept,)
    )
    syn_row = cerebro.cursor.fetchone()
    syns = [s.strip() for s in (syn_row[0] or "").split(",") if s.strip()]
    if surface not in syns:
        syns.append(surface)
        cerebro.cursor.execute(
            "UPDATE largo_plazo SET sinonimos = ? WHERE concepto = ?",
            (",".join(syns), concept),
        )

    # Sinapsis bidireccional tipada. Destino = concepto canónico; origen usa
    # una clave de forma (no crea nodo nuevo). Guardamos arista concepto↔concepto
    # solo si la expresión coincide con OTRO nodo existente; si no, no inventamos
    # un nodo-alias (R7). La recuperación usa el índice, no un nodo fantasma.
    cerebro.cursor.execute(
        "SELECT concepto FROM largo_plazo WHERE concepto = ?",
        (norm.replace(" ", "_"),),
    )
    alias_nodo = cerebro.cursor.fetchone()
    if alias_nodo and alias_nodo[0] != concept:
        _upsert_sinapsis_lexica(cerebro, alias_nodo[0], concept, conf_out)

    cerebro.cursor.execute(
        "INSERT INTO lexical_audit_event (episode_id, action, payload, created_at) VALUES (?, ?, ?, ?)",
        (episode_id, action, f"{surface} -> {concept}", time.time()),
    )

    try:
        from core.sdm import marcar_sdm_dirty
        marcar_sdm_dirty(cerebro, {concept})
    except Exception:
        pass
    if hasattr(cerebro, "_ppmi_index"):
        cerebro._ppmi_index = cerebro._ppmi_index  # no rebuild; dirty flag conceptual

    cerebro.conn.commit()
    return {
        "ok": True,
        "episode_id": episode_id,
        "expression_norm": norm,
        "canonical_concept": concept,
        "state": state_out,
        "confidence": conf_out,
        "action": action,
    }


def _upsert_sinapsis_lexica(cerebro, a: str, b: str, peso: float) -> None:
    """Arista tipada bidireccional en `sinapsis` (fuente canónica del grafo)."""
    ahora = time.time()
    for origen, destino in ((a, b), (b, a)):
        cerebro.cursor.execute(
            """
            INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(origen, destino) DO UPDATE SET
                peso = MAX(sinapsis.peso, excluded.peso),
                tipo = CASE WHEN sinapsis.tipo IN ('manual', 'manual_v7', 'sinonimo_explicito', 'test')
                            THEN sinapsis.tipo ELSE excluded.tipo END,
                ultimo_uso = COALESCE(sinapsis.ultimo_uso, excluded.creado_en)
            """,
            (origen, destino, float(peso), TIPO_SINAPSIS_LEXICO, ahora),
        )


def resolver_formas_aprendidas(cerebro, query: str, conf_min: float = CONF_MIN_EXPANSION) -> list[dict]:
    """Índice invertido: formas de la query → conceptos canónicos de alta confianza.

    POR QUÉ: debe ocurrir ANTES del ranking para GENERAR candidatos, no solo
    reordenarlos. Solo estados explicit/consolidated.
    """
    init_lexical_tables(cerebro.cursor)
    qn = normalizar_expresion(query)
    if not qn:
        return []
    forms = set(variantes_morfologicas(qn))
    # También cada token largo y n-gramas de 2-4 palabras de la query.
    tokens = qn.split()
    forms.update(tokens)
    for n in (2, 3, 4):
        for i in range(0, max(0, len(tokens) - n + 1)):
            forms.add(" ".join(tokens[i : i + n]))

    hits: dict[str, dict] = {}
    for form in forms:
        if not form:
            continue
        cerebro.cursor.execute(
            """
            SELECT canonical_concept, MAX(confidence), state, episode_id
            FROM lexical_form_index
            WHERE form_norm = ? AND state IN ('explicit', 'consolidated') AND confidence >= ?
            GROUP BY canonical_concept
            """,
            (form, conf_min),
        )
        for concept, conf, state, eid in cerebro.cursor.fetchall():
            prev = hits.get(concept)
            if prev is None or float(conf) > prev["confidence"]:
                hits[concept] = {
                    "canonical_concept": concept,
                    "confidence": float(conf),
                    "state": state,
                    "episode_id": eid,
                    "matched_form": form,
                    "provenance": "lexical_learning_episode",
                }
    return list(hits.values())


def revertir_episodio(cerebro, episode_id: int) -> bool:
    """Reversa auditable: quita índice y marca quarantined. No borra historia."""
    init_lexical_tables(cerebro.cursor)
    cerebro.cursor.execute(
        "UPDATE lexical_learning_episode SET state = 'quarantined', updated_at = datetime('now') WHERE id = ?",
        (episode_id,),
    )
    cerebro.cursor.execute("DELETE FROM lexical_form_index WHERE episode_id = ?", (episode_id,))
    cerebro.cursor.execute(
        "INSERT INTO lexical_audit_event (episode_id, action, payload, created_at) VALUES (?, 'revert', '', ?)",
        (episode_id, time.time()),
    )
    cerebro.conn.commit()
    return cerebro.cursor.rowcount >= 0
