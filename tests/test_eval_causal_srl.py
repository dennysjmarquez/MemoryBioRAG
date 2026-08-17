"""
Suite de Evaluación Empírica para Recuperación Causal SRL (v1.0)
================================================================
Verifica que las búsquedas abstractas basadas en patrones causales
(quién-hizo-qué-a-quién) recuperen recuerdos relevantes a través del
fallback de roles semánticos (SRL).
Nativo con unittest (sin dependencias externas).
"""

import unittest
import tempfile
import os
import shutil
from core.memory_store import SQLiteMemoryBioRAG
from core.srl_extractor import extraer_predicados_determinista


class TestEvalCausalSRL(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_file = os.path.join(self.temp_dir, "test_biorag_srl.db")
        self.ms = SQLiteMemoryBioRAG(db_path=self.db_file)

        # Insertar nodos de prueba con predicados
        self.ms.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, sinonimos) VALUES (?, ?, ?, ?, ?)",
            ("protocolo_autoinferencia_metacognitiva", "Dennys enseñó a Athena cómo realizar auto-inferencia metacognitiva.", 0.8, "activo", "metacognicion,inferencia")
        )
        self.ms.cursor.execute(
            "INSERT INTO predicados (concepto, sujeto, accion, objeto, contexto) VALUES (?, ?, ?, ?, ?)",
            ("protocolo_autoinferencia_metacognitiva", "dennys", "ensena", "metacognicion", "entrenamiento")
        )

        self.ms.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, sinonimos) VALUES (?, ?, ?, ?, ?)",
            ("principio_reflex_post_accion_emocional", "Mecanismo donde Dennys enseñó sobre el freno de inteligencia emocional.", 0.7, "activo", "emocion,freno")
        )
        self.ms.cursor.execute(
            "INSERT INTO predicados (concepto, sujeto, accion, objeto, contexto) VALUES (?, ?, ?, ?, ?)",
            ("principio_reflex_post_accion_emocional", "dennys", "ensena", "inteligencia_emocional", "reflexion")
        )

        self.ms.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, sinonimos) VALUES (?, ?, ?, ?, ?)",
            ("historia_tasajera_fumigador_rufino", "Un compañero echó Rufino al fumigador y mató las maticas bonitas.", 0.9, "activo", "tasajera,rufino")
        )
        self.ms.cursor.execute(
            "INSERT INTO predicados (concepto, sujeto, accion, objeto, contexto) VALUES (?, ?, ?, ?, ?)",
            ("historia_tasajera_fumigador_rufino", "companero", "mato", "maticas_bonitas", "tasajera")
        )

        self.ms.conn.commit()

    def tearDown(self):
        if hasattr(self.ms, 'conn') and self.ms.conn:
            try:
                self.ms.conn.close()
            except Exception:
                pass
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extractor_srl_determinista(self):
        texto = "Dennys enseñó un nuevo protocolo a Athena."
        predicados = extraer_predicados_determinista(texto)
        self.assertGreater(len(predicados), 0)
        self.assertEqual(predicados[0]["accion"], "ensena")

    def test_fallback_busqueda_predicados_directo(self):
        res = self.ms._fallback_busqueda_predicados("quién ensena protocolos", limite=10)
        self.assertGreaterEqual(len(res), 2)
        conceptos = [r[0] for r in res]
        self.assertIn("protocolo_autoinferencia_metacognitiva", conceptos)
        self.assertIn("principio_reflex_post_accion_emocional", conceptos)

    def test_buscar_por_frase_abstracta_con_fallback_srl(self):
        # Consulta abstracta sin coincidencia léxica exacta con "tasajera" o "rufino"
        # Desactivar umbral para probar solo el fallback SRL
        # (el cold start a 0.65 filtraría estos resultados de baja confianza)
        resultados, total = self.ms.buscar_por_frase(
            "quién mató la planta decorativa", limite=5, usar_umbral=False
        )
        self.assertGreater(total, 0)
        conceptos = [r[0] for r in resultados]
        self.assertIn("historia_tasajera_fumigador_rufino", conceptos)


if __name__ == "__main__":
    unittest.main()
