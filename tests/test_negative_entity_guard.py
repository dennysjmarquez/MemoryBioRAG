"""Pruebas del Negative Entity Guard (NEG).

NEG solo degrada la etiqueta epistémica; no toca el ranking ni el pool de
buscar_por_frase. Una mención contextual de una entidad no se considera una
etiqueta canónica recuperable.
"""

import unittest

from core.memory_store import SQLiteMemoryBioRAG


class TestNegativeEntityGuard(unittest.TestCase):
    def setUp(self):
        self.db = SQLiteMemoryBioRAG(":memory:")
        self.db.cursor.executemany(
            "INSERT INTO largo_plazo "
            "(concepto, contenido, peso_sinaptico, estado, sinonimos) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (
                    "integracion_biorag",
                    "La integración local conserva la memoria del sistema.",
                    0.8,
                    "activo",
                    "integración, memoria",
                ),
                (
                    "telemetria_causal_retrieval_spec_v1",
                    "Especificación técnica de telemetry y retrieval.",
                    0.8,
                    "activo",
                    "telemetria, retrieval",
                ),
                (
                    "nota_arquitectura_vectorial",
                    "Una comparación menciona Pinecone como producto externo.",
                    0.8,
                    "activo",
                    "vectorial",
                ),
            ],
        )
        self.db.conn.commit()

    def tearDown(self):
        self.db.cerrar_sistema()

    def test_mencion_contextual_no_certifica_entidad_externa(self):
        query = "como funciona la integracion con Pinecone en BioRAG"

        self.assertFalse(self.db._entidad_existe_en_corpus(query))
        self.assertEqual(
            self.db.nivel_certeza(0.95, query=query),
            "sin_evidencia_directa",
        )

    def test_entidad_en_etiqueta_canonica_si_certifica(self):
        self.db.cursor.execute(
            "INSERT INTO largo_plazo "
            "(concepto, contenido, peso_sinaptico, estado, sinonimos) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "pinecone_integracion",
                "Integración explícita con el servicio Pinecone.",
                0.8,
                "activo",
                "pinecone",
            ),
        )
        self.db.conn.commit()

        query = "como funciona la integracion con Pinecone en BioRAG"
        self.assertTrue(self.db._entidad_existe_en_corpus(query))
        self.assertEqual(
            self.db.nivel_certeza(0.95, query=query),
            "evidencia_directa",
        )

    def test_consulta_tecnica_sin_marca_usa_vocabulario_del_corpus(self):
        query = "telemetry causal retrieval specification"
        self.assertTrue(self.db._entidad_existe_en_corpus(query))
        self.assertEqual(
            self.db.nivel_certeza(0.95, query=query),
            "evidencia_directa",
        )

    def test_api_anterior_sin_query_se_mantiene_compatible(self):
        self.assertEqual(
            self.db.nivel_certeza(0.95),
            "evidencia_directa",
        )
        self.assertEqual(
            self.db.nivel_certeza(0.10),
            "sin_evidencia_directa",
        )


if __name__ == "__main__":
    unittest.main()
