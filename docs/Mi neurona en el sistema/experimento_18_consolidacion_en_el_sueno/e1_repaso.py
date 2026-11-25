"""Experimento 18, E1 — repaso del sueño sobre una COPIA LIMPIA (PROTOCOLO_V3.md §1–§2).

Uso (lo llama e1_medir.py en un proceso aparte, con el entorno de la copia limpia ya puesto):
    python e1_repaso.py <base_original> <eventos.json> <salida.json>

- Copia la base con la API de backup de SQLite (la original solo se lee).
- En la copia vacía `sinapsis` y `sinapsis_latentes`.
- profundidad="profundo" por defecto (enmienda A1 del v3: el sueño repasa también las dormidas).
- Corre 3 sueños × (pista de contenido + pista de sustantivos clave) por recuerdo, con
  buscar_por_frase(..., usar_inferencia=False, context_window=0, ignore_peso_sinaptico=True).
- Escribe el top de cada pista. No toca el repo ni la base original.
"""
import contextlib
import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import unicodedata

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)

ENTORNO_LIMPIO = {"BIORAG_PPMI_WEIGHT": "0.0", "BIORAG_SDM_FALLBACK": "0", "BIORAG_DMN_SINTESIS_ACTIVA": "0",
                  "BIORAG_NO_LOG": "1", "BIORAG_MULTIHOP_EXPANSION": "0"}
SUENOS = (1, 2, 3)
VENTANA = 4

_SIN_ESPACIOS = ("CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH", "HIRAGANA", "KATAKANA", "HANGUL")


def _sin_espacios(ch):
    return unicodedata.name(ch, "").startswith(_SIN_ESPACIOS)


def unidades(texto):
    """Segmentación por fronteras Unicode: palabras entre espacios; bigramas en escritura sin espacios.
    Devuelve [(run_id, inicio, texto_unidad, es_cjk)] y la lista de corridas."""
    t = unicodedata.normalize("NFKC", texto).casefold()
    t = "".join(ch if unicodedata.category(ch)[0] in "LN" else " " for ch in t)
    corridas = []
    for trozo in t.split():
        actual, tipo = "", None
        for ch in trozo:
            k = _sin_espacios(ch)
            if tipo is None or k == tipo:
                actual += ch
            else:
                corridas.append((actual, tipo))
                actual = ch
            tipo = k
        if actual:
            corridas.append((actual, tipo))
    us = []
    for rid, (txt, cjk) in enumerate(corridas):
        if cjk and len(txt) >= 2:
            us += [(rid, i, txt[i:i + 2], True) for i in range(len(txt) - 1)]
        else:
            us.append((rid, 0, txt, bool(cjk)))
    return us, corridas


def pista_contenido(concepto, contenido, sueno):
    us, corridas = unidades(contenido)
    if not us:
        return ""
    n = max(1, len(us) - VENTANA + 1)
    ini = int(hashlib.sha256(("%s|%d" % (concepto, sueno)).encode()).hexdigest(), 16) % n
    ventana = us[ini:ini + VENTANA]
    partes, vistos = [], {}
    for rid, i, txt, cjk in ventana:
        if cjk and len(corridas[rid][0]) >= 2:
            a, b = vistos.get(rid, (i, i + 2))
            vistos[rid] = (min(a, i), max(b, i + 2))
            if rid not in [p[0] for p in partes]:
                partes.append((rid, None))
        else:
            partes.append((rid, txt))
    salida = [corridas[rid][0][vistos[rid][0]:vistos[rid][1]] if txt is None else txt for rid, txt in partes]
    return " ".join(salida)


def pistas(ev, sueno):
    out = [("c1", pista_contenido(ev["concepto"], ev["contenido"], sueno))]
    if ev["sk"]:
        out.append(("c2", " ".join(s.strip() for s in ev["sk"].split(",") if s.strip())))
    return [(k, p) for k, p in out if p]


def sha(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main(original, eventos_json, salida_json, profundidad="profundo"):
    for k, v in ENTORNO_LIMPIO.items():
        assert os.environ.get(k) == v, "falta el entorno limpio: %s" % k
    sha_antes = sha(original)
    d = tempfile.mkdtemp(prefix="exp18_vista_", dir="/tmp")
    vista = os.path.join(d, "vista.db")
    src = sqlite3.connect("file:%s?mode=ro" % original, uri=True)
    dst = sqlite3.connect(vista)
    src.backup(dst)
    src.close()
    dst.execute("DELETE FROM sinapsis")
    dst.execute("DELETE FROM sinapsis_latentes")
    dst.commit()
    dst.close()

    from core.memory_store import SQLiteMemoryBioRAG
    with contextlib.redirect_stdout(io.StringIO()):
        cerebro = SQLiteMemoryBioRAG(db_path=vista)
    n_ini = cerebro.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
    eventos = json.load(open(eventos_json))
    registros = []
    for s in SUENOS:
        for ev in eventos:
            x = ev["concepto"].lower().replace(" ", "_")
            for tipo, p in pistas(ev, s):
                with contextlib.redirect_stdout(io.StringIO()):
                    res, _ = cerebro.buscar_por_frase(p, limite=6, profundidad=profundidad, usar_inferencia=False,
                                                      context_window=0,
                                                      ignore_peso_sinaptico=True)
                registros.append({"x": x, "s": s, "tipo": tipo, "pista": p, "top": [r[0] for r in (res or [])][:6]})
    n_fin = cerebro.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
    with contextlib.redirect_stdout(io.StringIO()):
        cerebro.cerrar_sistema()
    json.dump({"registros": registros, "sinapsis_vista_inicio": n_ini, "sinapsis_vista_fin": n_fin,
               "sha_original_antes": sha_antes, "sha_original_despues": sha(original)},
              open(salida_json, "w"), ensure_ascii=False)


if __name__ == "__main__":
    main(*sys.argv[1:5])
