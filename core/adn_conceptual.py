"""ADN Conceptual v29: cromosomas emergentes e índice persistido de búsqueda por esencia.

El archivo no define categorías semánticas fijas ni usa reglas de palabras clave.  Los
cromosomas se descubren mediante clustering de la topología real de sinapsis y sus
centroides se calculan desde los vectores PPMI/SVD.  El trabajo costoso se realiza en
``reconstruir_indice_nocturno``; las consultas usan cachés persistidos y candidatos
acotados, sin recorrer todo el corpus.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from core.auto_clustering import detectar_comunidades
from core.ppmi_hybrid_search import IndicesBioRAG, _coseno, _tokenizar

VERSION_INDICE = "adn_conceptual_v29"
TOP_VECINOS = 24
TOP_CANDIDATOS_TOKEN = 32
TOP_CANDIDATOS_CROMOSOMA = 160


def _normalizar(vector: np.ndarray) -> np.ndarray:
    norma = float(np.linalg.norm(vector))
    return vector / norma if norma > 1e-12 else np.zeros_like(vector)


def _a_blob(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype="float32").tobytes()


def _desde_blob(blob: bytes, dimension: int) -> np.ndarray:
    vector = np.frombuffer(blob, dtype="float32").astype("float64")
    if dimension and vector.size != dimension:
        raise ValueError(f"Vector ADN corrupto: dimensión esperada {dimension}, obtenida {vector.size}.")
    return vector


class _CerebroSoloLectura:
    """Adaptador mínimo para reutilizar el clustering LPA existente."""

    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.cursor = self.conn.cursor()

    def close(self) -> None:
        self.conn.close()


class ADNConceptualEngine:
    """Consulta ADN contra un índice ya precalculado; no recalcula centroides en caliente."""

    def __init__(self, db_path: str, indices: Optional[IndicesBioRAG] = None):
        self.db_path = Path(db_path)
        self.indices = indices
        self.cromosoma_centroides: Dict[str, np.ndarray] = {}
        self.firmas: Dict[str, Dict[str, float]] = {}
        self.vecinos: Dict[str, List[Dict[str, Any]]] = {}
        self.membresias_por_cromosoma: Dict[str, List[tuple[str, float]]] = {}
        self.metadata: Dict[str, Any] = {}
        self._cargar_indice_persistido()

    @property
    def indice_listo(self) -> bool:
        return bool(self.cromosoma_centroides and self.firmas)

    @property
    def nombres_cromosomas(self) -> List[str]:
        return list(self.cromosoma_centroides.keys())

    def _conexion_lectura(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)

    @staticmethod
    def asegurar_esquema(conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS adn_meta_v29 (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS adn_cromosomas_v29 (
                nombre TEXT PRIMARY KEY,
                centroide BLOB NOT NULL,
                dimension INTEGER NOT NULL,
                miembros_json TEXT NOT NULL,
                confianza REAL NOT NULL,
                generado_en REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS adn_firmas_v29 (
                concepto TEXT PRIMARY KEY,
                firma BLOB NOT NULL,
                dimension INTEGER NOT NULL,
                actualizado_en REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS adn_membresias_v29 (
                concepto TEXT NOT NULL,
                cromosoma TEXT NOT NULL,
                valor REAL NOT NULL,
                PRIMARY KEY (concepto, cromosoma)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_adn_membresias_crom ON adn_membresias_v29(cromosoma, valor DESC)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS adn_vecinos_v29 (
                origen TEXT NOT NULL,
                destino TEXT NOT NULL,
                afinidad REAL NOT NULL,
                genes_json TEXT NOT NULL,
                PRIMARY KEY (origen, destino)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_adn_vecinos_origen ON adn_vecinos_v29(origen, afinidad DESC)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS neocortex_token_candidatos_v29 (
                token TEXT NOT NULL,
                concepto TEXT NOT NULL,
                similitud REAL NOT NULL,
                PRIMARY KEY (token, concepto)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_neocortex_token ON neocortex_token_candidatos_v29(token, similitud DESC)")

    def _cargar_indice_persistido(self) -> None:
        if not self.db_path.exists():
            return
        try:
            con = self._conexion_lectura()
            tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            requeridas = {"adn_cromosomas_v29", "adn_firmas_v29", "adn_vecinos_v29", "adn_membresias_v29"}
            if not requeridas.issubset(tablas):
                con.close()
                return

            for clave, valor in con.execute("SELECT clave, valor FROM adn_meta_v29"):
                self.metadata[clave] = valor
            for nombre, blob, dimension, miembros_json, confianza, generado_en in con.execute(
                "SELECT nombre, centroide, dimension, miembros_json, confianza, generado_en FROM adn_cromosomas_v29 ORDER BY nombre"
            ):
                self.cromosoma_centroides[nombre] = _desde_blob(blob, dimension)
            nombres = self.nombres_cromosomas
            for concepto, blob, dimension, _actualizado in con.execute(
                "SELECT concepto, firma, dimension, actualizado_en FROM adn_firmas_v29"
            ):
                firma_vector = _desde_blob(blob, dimension)
                if firma_vector.size == len(nombres):
                    self.firmas[concepto] = {nombre: float(firma_vector[i]) for i, nombre in enumerate(nombres)}
            for origen, destino, afinidad, genes_json in con.execute(
                "SELECT origen, destino, afinidad, genes_json FROM adn_vecinos_v29 ORDER BY origen, afinidad DESC"
            ):
                self.vecinos.setdefault(origen, []).append({
                    "concepto": destino,
                    "afinidad_genetica": float(afinidad),
                    "genes_compartidos": json.loads(genes_json),
                })
            for cromosoma, concepto, valor in con.execute(
                "SELECT cromosoma, concepto, valor FROM adn_membresias_v29 ORDER BY cromosoma, valor DESC"
            ):
                self.membresias_por_cromosoma.setdefault(cromosoma, []).append((concepto, float(valor)))
            con.close()
        except (sqlite3.Error, ValueError):
            self.cromosoma_centroides = {}
            self.firmas = {}
            self.vecinos = {}
            self.membresias_por_cromosoma = {}

    @classmethod
    def reconstruir_indice_nocturno(
        cls,
        db_path: str,
        top_vecinos: int = TOP_VECINOS,
        top_candidatos_token: int = TOP_CANDIDATOS_TOKEN,
    ) -> Dict[str, Any]:
        """Reconstruye y persiste todos los artefactos pesados durante el ciclo DMN.

        Esta es la única ruta que llama al clustering o compara todos los pares del
        corpus.  Si el grafo aún no tiene comunidades densas, devuelve un estado
        explícito ``sin_comunidades`` sin inventar ejes semánticos.
        """
        ruta = Path(db_path)
        if not ruta.exists():
            raise FileNotFoundError(f"No existe la base de datos: {ruta}")

        indices = IndicesBioRAG(ruta)
        if not indices.vecs:
            return {"estado": "sin_vectores", "nodos": 0, "cromosomas": 0}

        cerebro = _CerebroSoloLectura(ruta)
        try:
            comunidades = detectar_comunidades(cerebro, min_densidad=0.1, min_nodos=2)
        finally:
            cerebro.close()

        # Solo aceptar comunidades cuyos nodos poseen vector SVD vigente.
        comunidades = [
            c for c in comunidades
            if len([n for n in c["nodos"] if n in indices.vecs]) >= 2
        ]
        if not comunidades:
            return {"estado": "sin_comunidades", "nodos": len(indices.vecs), "cromosomas": 0}

        nombres = []
        centroides = []
        miembros_por_nombre: Dict[str, List[str]] = {}
        confianza_por_nombre: Dict[str, float] = {}
        nombres_usados = set()
        for pos, comunidad in enumerate(comunidades):
            base = comunidad["nombre"] or f"cluster_{pos}"
            nombre = base
            sufijo = 2
            while nombre in nombres_usados:
                nombre = f"{base}_{sufijo}"
                sufijo += 1
            nombres_usados.add(nombre)
            miembros = [n for n in comunidad["nodos"] if n in indices.vecs]
            centroide = _normalizar(np.mean([indices.vecs[n] for n in miembros], axis=0))
            if float(np.linalg.norm(centroide)) <= 1e-12:
                continue
            nombres.append(nombre)
            centroides.append(centroide)
            miembros_por_nombre[nombre] = miembros
            confianza_por_nombre[nombre] = float(comunidad.get("confianza", 0.0))

        if not centroides:
            return {"estado": "centroides_nulos", "nodos": len(indices.vecs), "cromosomas": 0}

        matriz_centroides = np.vstack(centroides)
        conceptos = sorted(indices.vecs.keys())
        matriz_nodos = np.vstack([_normalizar(indices.vecs[c]) for c in conceptos])
        firmas = np.maximum(0.0, matriz_nodos @ matriz_centroides.T)
        firmas_norm = np.vstack([_normalizar(f) for f in firmas])
        afinidades = firmas_norm @ firmas_norm.T

        ahora = time.time()
        con = sqlite3.connect(ruta)
        try:
            cls.asegurar_esquema(con)
            for tabla in (
                "adn_cromosomas_v29", "adn_firmas_v29", "adn_membresias_v29",
                "adn_vecinos_v29", "neocortex_token_candidatos_v29",
            ):
                con.execute(f"DELETE FROM {tabla}")
            con.execute("DELETE FROM adn_meta_v29")

            for nombre, centroide in zip(nombres, centroides):
                con.execute(
                    "INSERT INTO adn_cromosomas_v29 VALUES (?, ?, ?, ?, ?, ?)",
                    (nombre, _a_blob(centroide), centroide.size, json.dumps(miembros_por_nombre[nombre]),
                     confianza_por_nombre[nombre], ahora),
                )

            for i, concepto in enumerate(conceptos):
                con.execute(
                    "INSERT INTO adn_firmas_v29 VALUES (?, ?, ?, ?)",
                    (concepto, _a_blob(firmas[i]), len(nombres), ahora),
                )
                top_ejes = np.argsort(firmas[i])[::-1][: min(3, len(nombres))]
                for eje in top_ejes:
                    if firmas[i, eje] > 0.0:
                        con.execute(
                            "INSERT INTO adn_membresias_v29 VALUES (?, ?, ?)",
                            (concepto, nombres[int(eje)], float(firmas[i, eje])),
                        )

                orden = np.argsort(afinidades[i])[::-1]
                guardados = 0
                for j in orden:
                    if i == int(j):
                        continue
                    genes = [
                        nombres[k] for k in range(len(nombres))
                        if firmas[i, k] >= 0.35 and firmas[int(j), k] >= 0.35
                    ]
                    con.execute(
                        "INSERT INTO adn_vecinos_v29 VALUES (?, ?, ?, ?)",
                        (concepto, conceptos[int(j)], float(afinidades[i, int(j)]), json.dumps(genes)),
                    )
                    guardados += 1
                    if guardados >= top_vecinos:
                        break

            # Índice token→candidatos: la consulta posterior solo mira el top-k persistido.
            for token, vector_token in indices.token_vecs.items():
                v_token = _normalizar(vector_token)
                sims = matriz_nodos @ v_token
                for j in np.argsort(sims)[::-1][:top_candidatos_token]:
                    if sims[int(j)] > 0.0:
                        con.execute(
                            "INSERT INTO neocortex_token_candidatos_v29 VALUES (?, ?, ?)",
                            (token, conceptos[int(j)], float(sims[int(j)])),
                        )

            meta = {
                "version": VERSION_INDICE,
                "generado_en": str(ahora),
                "nodos": str(len(conceptos)),
                "cromosomas": str(len(nombres)),
                "top_vecinos": str(top_vecinos),
                "top_candidatos_token": str(top_candidatos_token),
            }
            con.executemany("INSERT INTO adn_meta_v29 VALUES (?, ?)", meta.items())
            con.commit()
        finally:
            con.close()

        return {
            "estado": "ok",
            "nodos": len(conceptos),
            "cromosomas": len(nombres),
            "cromosomas_nombres": nombres,
            "generado_en": ahora,
        }

    def extraer_firma_vectorial(self, vector_concepto: np.ndarray) -> Dict[str, float]:
        if not self.cromosoma_centroides:
            return {}
        v = _normalizar(vector_concepto)
        return {
            nombre: max(0.0, float(np.dot(v, centroide)))
            for nombre, centroide in self.cromosoma_centroides.items()
        }

    def inferir_firma_por_concepto(self, concepto: str) -> Dict[str, float]:
        clave = concepto.lower().strip()
        if clave in self.firmas:
            return dict(self.firmas[clave])
        if self.indices is None or not self.indice_listo:
            return {}
        vector = self.indices.vector_query(_tokenizar(concepto))
        return self.extraer_firma_vectorial(vector)

    def buscar_por_esencia(self, query_concepto: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Busca por índice persistido; no itera ``indices.vecs`` en la consulta."""
        clave = query_concepto.lower().strip()
        if not self.indice_listo:
            return []
        if clave in self.vecinos:
            return self.vecinos[clave][:top_k]

        firma_q = self.inferir_firma_por_concepto(query_concepto)
        if not firma_q:
            return []
        # Para una consulta nueva, examinar solo candidatos de sus dos cromosomas dominantes.
        ejes = sorted(firma_q, key=firma_q.get, reverse=True)[:2]
        candidatos: List[str] = []
        vistos = set()
        for eje in ejes:
            for concepto, _valor in self.membresias_por_cromosoma.get(eje, [])[:TOP_CANDIDATOS_CROMOSOMA]:
                if concepto not in vistos:
                    vistos.add(concepto)
                    candidatos.append(concepto)
        resultados = []
        v_q = np.array([firma_q[n] for n in self.nombres_cromosomas], dtype="float64")
        for concepto in candidatos:
            firma_c = self.firmas.get(concepto)
            if not firma_c:
                continue
            v_c = np.array([firma_c[n] for n in self.nombres_cromosomas], dtype="float64")
            genes = [n for n in self.nombres_cromosomas if firma_q[n] >= 0.35 and firma_c[n] >= 0.35]
            resultados.append({
                "concepto": concepto,
                "afinidad_genetica": round(_coseno(v_q, v_c), 4),
                "genes_compartidos": genes,
                "firma": firma_c,
            })
        resultados.sort(key=lambda r: r["afinidad_genetica"], reverse=True)
        return resultados[:top_k]

    # Compatibilidad: no se usa para inferir en caliente; la nueva firma se materializa en sueño.
    def registrar_concepto(self, concepto: str, firma: Dict[str, float]) -> None:
        if firma:
            self.firmas[concepto.lower().strip()] = dict(firma)

    def inferir_firma_por_texto(self, texto: str) -> Dict[str, float]:
        return self.inferir_firma_por_concepto(texto)


# Compatibilidad mínima con clientes previos; ya no existe un catálogo fijo de cromosomas.
def _vector_firma(firma: Dict[str, float]) -> np.ndarray:
    return np.asarray(list(firma.values()), dtype="float64")


CROMOSOMAS_CATALOGO: List[str] = []
