#!/usr/bin/env python3
"""E3A: trazas reproducibles de 14 aciertos zh/ja y dos negativos ingleses.

Solo abre bases temporales. Una copia por llamada; nunca altera el motor. Las
sondas WordNet apagado son ablaciones aisladas, NO son una propuesta de cambio.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluar_qa_multilingue_e3a import RELOJ_FIJO, cargar_gold, crear_base, sha256


def expansion_wordnet_como_motor(query: str) -> list[dict]:
    """Replica la expansión documentada en core/memory/search.py:228-268.

    Sirve para enumerar palabras FTS; se verifica también cada hit real en FTS.
    El experimento WordNet apagado usa el motor real sobre otra copia limpia.
    """
    from nltk.corpus import wordnet as wn
    from core.stopwords import STOPWORDS_ES
    agregados = []
    filas = []
    for token in query.split()[:6]:
        if len(token) < 3 or token.lower() in STOPWORDS_ES:
            continue
        try:
            if wn.synsets(token.lower(), lang="spa"):
                continue
        except Exception:
            pass
        if not token.isascii() or not token.isalpha():
            continue
        synsets = wn.synsets(token)
        nuevos = []
        for synset in synsets[:2]:
            for lema in synset.lemmas():
                nombre = lema.name().replace("_", " ")
                if nombre.lower() != token.lower() and nombre not in agregados:
                    agregados.append(nombre)
                    nuevos.append(nombre)
                    if len(agregados) >= 8:
                        break
            if len(agregados) >= 8:
                break
        filas.append({"token": token, "synsets": [s.name() for s in synsets[:2]],
                      "agregados": nuevos})
    return filas


def trazar(origen: Path, caso: dict, carpeta: Path, wordnet: str = "1") -> dict:
    from core.memory_store import SQLiteMemoryBioRAG
    from core.fallback_simbolico import _tokenizar_normalizado
    from core.stopwords import _STOPWORDS_QUERY
    from core.stemmer_es import stem
    import re

    with tempfile.TemporaryDirectory(prefix="sonda_", dir=carpeta) as tmp:
        copia = Path(tmp) / "copia.db"
        shutil.copyfile(origen, copia)
        with patch.dict(os.environ, {"BIORAG_WORDNET_ENABLED": wordnet}):
            cerebro = SQLiteMemoryBioRAG(str(copia))
            try:
                resultados, total = cerebro.buscar_por_frase(
                    caso["query"], profundidad="activos", limite=5, ignore_peso_sinaptico=True)
                query_filtrada = cerebro.last_query
                pool = [{"concepto": row[1], "origen": cerebro.last_origen_scores.get(row[1])}
                        for row in cerebro.last_todos]
                tokens = sorted(_tokenizar_normalizado(caso["query"]))
                extraidas = [t for t in re.findall(r'\w+', caso["query"].lower())
                             if t in _STOPWORDS_QUERY]
                expansiones = expansion_wordnet_como_motor(query_filtrada) if wordnet == "1" else []
                terminos = query_filtrada.split() + [word for row in expansiones
                                                     for expresion in row["agregados"]
                                                     for word in expresion.split()]
                hallazgos = []
                if caso["id"] in ("en-n01", "en-n02"):
                    for term in dict.fromkeys(terminos):
                        try:
                            rows = cerebro.conn.execute(
                                'SELECT highlight(largo_plazo_fts, 1, "[", "]") '
                                'FROM largo_plazo_fts JOIN largo_plazo l ON l.rowid = largo_plazo_fts.rowid '
                                'WHERE largo_plazo_fts MATCH ? AND l.concepto = ?',
                                ('"' + term.replace('"', '""') + '"', "model airplane")).fetchall()
                        except Exception:
                            rows = []
                        if rows:
                            hallazgos.append({"termino_fts": term, "contenido_resaltado": rows[0][0]})
                devueltos = [{"concepto": r[0], "score": float(r[4])} for r in resultados]
            finally:
                cerebro.cerrar_sistema()
    return {"id": caso["id"], "query": caso["query"], "query_filtrada": query_filtrada,
            "stopwords_retiradas": extraidas, "tokens_fallback": tokens,
            "stems": {t: stem(t) for t in tokens}, "wordnet": wordnet,
            "expansiones_wordnet": expansiones, "hits_fts_model_airplane": hallazgos,
            "resultados": devueltos, "pool": pool, "total_motor": total}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("BIORAG_NEURONA") != "0":
        parser.error("Inicia con PYTHONHASHSEED=0 BIORAG_NEURONA=0")
    gold = cargar_gold()
    ref_path = ROOT / "docs" / "e3a_multilingue_resultados_20261027.json"
    ref = {x["id"]: x for x in json.loads(ref_path.read_text(encoding="utf-8"))["casos"]}
    hits = [c for c in gold if c["idioma"] in ("zh", "ja") and ref[c["id"]]["rango"] is not None]
    negativas = [c for c in gold if c["id"] in ("en-n01", "en-n02")]
    if len(hits) != 14 or len(negativas) != 2:
        raise RuntimeError("La referencia no tiene los 14 aciertos y dos controles esperados")
    with tempfile.TemporaryDirectory(prefix="biorag_e3a_auditoria_") as tmp, \
         patch("time.time", return_value=RELOJ_FIJO):
        carpeta = Path(tmp)
        db = carpeta / "base.db"
        base = crear_base(db, gold)
        aciertos = [trazar(db, c, carpeta) for c in hits]
        controles = [trazar(db, c, carpeta) for c in negativas]
        ablations = [trazar(db, c, carpeta, wordnet="0") for c in negativas]
        for c, row in zip(hits + negativas, aciertos + controles):
            if row["resultados"] != ref[c["id"]]["resultados"]:
                raise RuntimeError(f"{c['id']}: la sonda no reproduce resultados y scores de la referencia")
        if sha256(db) != base["sha256_sqlite"]:
            raise RuntimeError("La base fuente fue modificada")
    salida = {"base": base, "coincidencia_con_referencia": "16/16 rankings y scores idénticos",
              "aciertos_zh_ja": aciertos, "negativos_ingleses": controles,
              "wordnet_apagado_solo_como_sonda": ablations}
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in aciertos:
        print(row['id'], 'query=', repr(row['query']), 'resultado=', row['resultados'], 'pool=', row['pool'])
    for row in controles + ablations:
        print(row['id'], 'wordnet=', row['wordnet'], 'query_filtrada=', row['query_filtrada'],
              'resultados=', row['resultados'], 'hits_fts=', row['hits_fts_model_airplane'])
    print('Referencia reproducida: 16/16 rankings y scores idénticos')
    print('Archivo:', args.salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
