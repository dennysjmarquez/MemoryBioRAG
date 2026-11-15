#!/usr/bin/env python3
"""E3 fase A: QA multilingüe sobre una base NUEVA, temporal y aislada.

Uso (las dos variables deben fijarse ANTES de iniciar Python):
  PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/evaluar_qa_multilingue_e3a.py \
    --salida docs/e3a_multilingue_resultados_20261027.json

Cada consulta abre una copia diferente de la base creada por la API canónica.
No se abren la base real ni el snapshot; el directorio temporal se elimina.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GOLD = ROOT / "scripts" / "casos_qa_multilingue_e3a.jsonl"
IDIOMAS = ("zh", "ja", "ko", "ru", "en", "es")
# Misma fecha para todas las escrituras y búsquedas: evita que la recencia o la
# duración de la evaluación altere las posiciones. No se modifican pesos.
RELOJ_FIJO = 1_793_059_200.0  # 2026-10-27T00:00:00Z


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def cargar_gold(path: Path = GOLD) -> list[dict]:
    casos = []
    for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            caso = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON inválido en línea {num}: {exc}") from exc
        if set(caso) != {"id", "idioma", "tipo", "concepto", "contenido", "query"}:
            raise ValueError(f"Campos inválidos en línea {num}")
        if caso["idioma"] not in IDIOMAS or not caso["id"] or not caso["query"]:
            raise ValueError(f"Idioma, id o consulta inválidos en línea {num}")
        negativo = caso["tipo"] == "negativo"
        if negativo != (caso["concepto"] is None and caso["contenido"] is None):
            raise ValueError(f"Gold negativo/positivo incoherente en línea {num}")
        if not negativo:
            if not caso["concepto"] or not caso["contenido"]:
                raise ValueError(f"Recuerdo vacío en línea {num}")
            if caso["concepto"] != caso["concepto"].strip().lower():
                raise ValueError(f"Concepto no canónico en línea {num}")
        casos.append(caso)
    ids = [c["id"] for c in casos]
    conceptos = [c["concepto"] for c in casos if c["concepto"] is not None]
    consultas = [(c["idioma"], c["query"]) for c in casos]
    if len(ids) != len(set(ids)) or len(conceptos) != len(set(conceptos)):
        raise ValueError("Hay ids o conceptos repetidos")
    if len(consultas) != len(set(consultas)):
        raise ValueError("Hay consultas repetidas en el mismo idioma")
    return casos


def crear_base(path: Path, casos: list[dict]) -> dict:
    """Crea y valida desde cero una DB sin WAL pendiente, usando aprender()."""
    from core.memory_service import aprender
    from core.memory_store import SQLiteMemoryBioRAG

    if path.exists() or Path(str(path) + "-wal").exists():
        raise FileExistsError(f"La base temporal ya existe: {path}")
    cerebro = SQLiteMemoryBioRAG(str(path))
    positivos = [c for c in casos if c["concepto"] is not None]
    try:
        for caso in positivos:
            aprender(cerebro, caso["concepto"], caso["contenido"], consolidar=True)
        cerebro.conn.commit()
        filas = cerebro.conn.execute(
            "SELECT concepto, contenido, estado FROM largo_plazo"
        ).fetchall()
        real = {concepto: (contenido, estado) for concepto, contenido, estado in filas}
        esperado = {c["concepto"]: (c["contenido"], "activo") for c in positivos}
        if real != esperado:
            raise RuntimeError("La base creada no coincide exactamente con el gold activo")
        grupo = {r[0] for r in cerebro.conn.execute(
            "SELECT DISTINCT concepto FROM nodo_grupos_semanticos"
        )}
        links = list(cerebro.conn.execute("SELECT origen, destino FROM sinapsis"))
        por_idioma = {}
        for lang in IDIOMAS:
            nombres = {c["concepto"] for c in positivos if c["idioma"] == lang}
            por_idioma[lang] = {
                "recuerdos": len(nombres),
                "con_grupo_wordnet": len(nombres & grupo),
                "con_sinapsis": len(nombres & {n for a, b in links for n in (a, b)}),
            }
        integridad = cerebro.conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integridad != "ok":
            raise RuntimeError(f"Integridad SQLite: {integridad}")
        cerebro.conn.commit()
        # Consolidación explícita del WAL antes de cualquier copia byte a byte.
        estado_wal = cerebro.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if estado_wal[0] != 0:
            raise RuntimeError(f"WAL ocupado: {estado_wal}")
    finally:
        cerebro.cerrar_sistema()
    wal = Path(str(path) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise RuntimeError(f"WAL no vacío; no se puede copiar la base: {wal}")
    return {"integridad": integridad, "nodos": len(filas), "sinapsis": len(links),
            "por_idioma": por_idioma, "sha256_sqlite": sha256(path)}


def buscar_caso(origen: Path, caso: dict, directorio: Path) -> dict:
    """Una copia por caso aísla todos los cambios y cachés de la consulta anterior."""
    from core.memory_store import SQLiteMemoryBioRAG

    with tempfile.TemporaryDirectory(prefix="caso_", dir=directorio) as carpeta:
        copia = Path(carpeta) / "copia.db"
        shutil.copyfile(origen, copia)
        cerebro = SQLiteMemoryBioRAG(str(copia))
        try:
            resultados, total = cerebro.buscar_por_frase(
                caso["query"], profundidad="activos", limite=5,
                ignore_peso_sinaptico=True,
            )
            if len(resultados) > 5:
                raise RuntimeError(f"{caso['id']}: el motor devolvió más de 5")
            devueltos = [{"concepto": r[0], "score": float(r[4])} for r in resultados]
        finally:
            cerebro.cerrar_sistema()
    esperado = caso["concepto"]
    nombres = [r["concepto"] for r in devueltos]
    rango = nombres.index(esperado) + 1 if esperado in nombres else None
    return {
        "id": caso["id"], "idioma": caso["idioma"], "tipo": caso["tipo"],
        "query": caso["query"], "esperado": esperado, "rango": rango,
        "resultados": devueltos, "total_motor": total,
        "falso_positivo": bool(devueltos) if esperado is None else None,
    }


def resumen(casos: list[dict]) -> dict:
    """R@1, R@5, MRR@5 y FP; ningún caso positivo se descarta."""
    pos = [c for c in casos if c["esperado"] is not None]
    neg = [c for c in casos if c["esperado"] is None]
    n = len(pos)
    r1 = sum(c["rango"] == 1 for c in pos)
    r5 = sum(c["rango"] is not None for c in pos)
    return {
        "positivos": n, "aciertos_r1": r1, "aciertos_r5": r5,
        "r1_pct": round(100 * r1 / n, 2) if n else None,
        "r5_pct": round(100 * r5 / n, 2) if n else None,
        "mrr_at_5": round(sum(1 / c["rango"] for c in pos if c["rango"]) / n, 4) if n else None,
        "sin_resultados_positivos": sum(not c["resultados"] for c in pos),
        "negativos": len(neg), "falsos_positivos": sum(bool(c["falso_positivo"]) for c in neg),
    }


def metricas(casos: list[dict]) -> dict:
    return {
        "global": resumen(casos),
        "por_idioma": {idioma: resumen([c for c in casos if c["idioma"] == idioma])
                       for idioma in IDIOMAS},
        "por_tipo": {tipo: resumen([c for c in casos if c["tipo"] == tipo])
                     for tipo in sorted({c["tipo"] for c in casos})},
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gold", type=Path, default=GOLD)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--orden", choices=("original", "inverso"), default="original",
                   help="Solo cambia el orden de las consultas, no el de escritura")
    p.add_argument("--verificar-orden", action="store_true",
                   help="Repite todos los casos en orden contrario sobre la misma base")
    args = p.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("BIORAG_NEURONA") != "0":
        p.error("Inicia el proceso con PYTHONHASHSEED=0 BIORAG_NEURONA=0")
    casos = cargar_gold(args.gold)
    counts = Counter((c["idioma"], c["tipo"] == "negativo") for c in casos)
    if any(counts[(lang, False)] != 20 or counts[(lang, True)] != 2 for lang in IDIOMAS):
        p.error("El gold debe tener exactamente 20 positivos y 2 negativos por idioma")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = None
    import numpy
    import nltk

    inicio = time.perf_counter()
    print(f"Gold: {len(casos)} consultas, 120 recuerdos y 12 controles; orden={args.orden}", flush=True)
    with tempfile.TemporaryDirectory(prefix="biorag_e3a_") as tmp:
        carpeta = Path(tmp)
        origen = carpeta / "base_nueva.db"
        # Reloj fijo también en la búsqueda, no solo en la creación.
        with patch("time.time", return_value=RELOJ_FIJO):
            base = crear_base(origen, casos)
            print(f"Base creada: {base['nodos']} recuerdos, integridad {base['integridad']}, "
                  f"sha256 {base['sha256_sqlite']}", flush=True)
            recorrido = casos if args.orden == "original" else list(reversed(casos))
            resultados = []
            for i, caso in enumerate(recorrido, 1):
                try:
                    resultados.append(buscar_caso(origen, caso, carpeta))
                except Exception as exc:
                    raise RuntimeError(f"Error ejecutando el caso {caso['id']}") from exc
                if i % 10 == 0 or i == len(recorrido):
                    print(f"  {i}/{len(recorrido)} consultas", flush=True)
            verificacion_orden = None
            if args.verificar_orden:
                # Misma fuente byte a byte: comprueba cada lista y puntuación,
                # no solo los promedios. Cada búsqueda conserva su copia propia.
                primero = {r["id"]: r for r in resultados}
                diferentes = []
                for i, caso in enumerate(reversed(recorrido), 1):
                    repetido = buscar_caso(origen, caso, carpeta)
                    if repetido != primero[caso["id"]]:
                        diferentes.append(caso["id"])
                    if i % 20 == 0 or i == len(recorrido):
                        print(f"  repetición inversa {i}/{len(recorrido)} consultas", flush=True)
                verificacion_orden = {
                    "misma_base_sha256": base["sha256_sqlite"],
                    "casos_comparados": len(recorrido), "diferentes": diferentes,
                }
                print(f"Comparación sobre la misma base: {len(diferentes)} casos diferentes", flush=True)
        if sha256(origen) != base["sha256_sqlite"]:
            raise RuntimeError("La base original temporal cambió durante las búsquedas")
    resultados.sort(key=lambda r: r["id"])
    stats = metricas(resultados)
    salida = {
        "metadatos": {
            "gold": str(args.gold.relative_to(ROOT)) if args.gold.is_relative_to(ROOT) else str(args.gold),
            "gold_sha256": sha256(args.gold), "commit_motor": commit, "orden_consultas": args.orden,
            "python": sys.version, "sqlite": sqlite3.sqlite_version, "numpy": numpy.__version__,
            "nltk": nltk.__version__, "pythonhashseed": os.environ["PYTHONHASHSEED"],
            "biorag_neurona": os.environ["BIORAG_NEURONA"], "reloj_fijo_unix": RELOJ_FIJO,
            "profundidad": "activos", "limite": 5, "ignore_peso_sinaptico": True,
            "aislamiento": "base nueva, una copia limpia por consulta", "duracion_s": round(time.perf_counter() - inicio, 2),
        },
        "base": base, "verificacion_orden_misma_base": verificacion_orden,
        "metricas": stats, "casos": resultados,
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nIdioma | R@5 | R@1 | MRR@5 | FP", flush=True)
    for lang, s in stats["por_idioma"].items():
        print(f"{lang:6} | {s['aciertos_r5']:2}/{s['positivos']} ({s['r5_pct']:6.2f}%) | "
              f"{s['aciertos_r1']:2}/{s['positivos']} ({s['r1_pct']:6.2f}%) | "
              f"{s['mrr_at_5']:.4f} | {s['falsos_positivos']}/{s['negativos']}", flush=True)
    print(f"\nArchivo: {args.salida}", flush=True)
    return 1 if verificacion_orden and verificacion_orden["diferentes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
