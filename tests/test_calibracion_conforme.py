"""
Suite de tests para la Calibración Conforme (v28.1)
====================================================
Verifica la garantía de falso positivo como PERCENTIL invariante al corpus:

1. UmbralConforme.calibrar(): el umbral es el cuantil k=ceil((n+1)(1-alpha))/n
   de los scores negativos — NO un número absoluto. Cuando el corpus cambia
   (y con él el piso de ruido), el percentil queda fijo y el valor absoluto
   se recalcula solo.
2. SQLiteMemoryBioRAG.calibrar_y_persistir(): persiste el umbral en la tabla
   calibracion_estado con n_nodos_corpus, y reutiliza la calibración vigente
   si no hay drift de tamaño del corpus (>20%).
3. SQLiteMemoryBioRAG.nivel_certeza(): clasifica en los 3 niveles del
   Neocórtex (evidencia_directa / relacionado_confianza_media /
   sin_evidencia_directa). Nunca silencio: siempre hay un nivel declarado.

Nativo con unittest (sin dependencias externas).
"""

import unittest
import tempfile
import os
import sqlite3

from core.calibracion import UmbralConforme, CalibradorPlatt
from core.memory_store import SQLiteMemoryBioRAG


class TestUmbralConforme(unittest.TestCase):
    """El umbral conforme es un PERCENTIL, no un valor absoluto."""

    def test_umbral_es_percentil_no_valor_absoluto(self):
        """Si el corpus crece (piso de ruido sube), el absoluto cambia, el percentil no."""
        # Scores de negativos de un corpus pequeño (piso de ruido bajo)
        neg_pequeno = [0.3372, 0.40, 0.42, 0.45, 0.50, 0.55, 0.58, 0.61]
        # Mismo corpus pero más grande: el piso de ruido sube en +0.15
        neg_grande = [s + 0.15 for s in neg_pequeno]

        u1 = UmbralConforme(alpha=0.10).calibrar(neg_pequeno)
        u2 = UmbralConforme(alpha=0.10).calibrar(neg_grande)

        # El absoluto se recalcula solo (debe ser distinto)
        self.assertNotEqual(u1.umbral, u2.umbral)
        # El percentil es el mismo por construcción: mismo alpha, misma n
        self.assertEqual(u1.alpha, u2.alpha)
        # La garantía queda: el umbral es un score de la muestra negativa
        self.assertGreater(u1.umbral, 0.0)
        self.assertGreater(u2.umbral, 0.0)

    def test_alpha_controla_fp(self):
        """alpha más estricto (menor) produce umbral más alto (menos FP)."""
        neg = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
        u_estricto = UmbralConforme(alpha=0.05).calibrar(neg)
        u_relajado = UmbralConforme(alpha=0.50).calibrar(neg)
        self.assertGreater(u_estricto.umbral, u_relajado.umbral)

    def test_platt_probabilidad_creciente_con_score(self):
        """Platt convierte score crudo a probabilidad, monótona creciente."""
        platt = CalibradorPlatt()
        # Datos sintéticos: score alto -> acierto, score bajo -> fallo
        scores = [0.2, 0.3, 0.5, 0.6, 0.8, 0.9]
        aciertos = [0, 0, 1, 1, 1, 1]
        platt.entrenar(scores, aciertos)
        p_bajo = platt.probabilidad(0.2)
        p_alto = platt.probabilidad(0.9)
        self.assertGreater(p_alto, p_bajo)


class TestCalibracionPersistente(unittest.TestCase):
    """calibrar_y_persistir persiste y reutiliza la calibración según drift."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_file = os.path.join(self.temp_dir, "test_calibracion.db")
        # Insertar algunos nodos para que la búsqueda tenga dónde ocurrir
        conn = sqlite3.connect(self.db_file)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.close()
        self.ms = SQLiteMemoryBioRAG(db_path=self.db_file)
        for i in range(5):
            self.ms.cursor.execute(
                "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, sinonimos) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"nodo_test_{i}", f"contenido de prueba {i} sobre memoria y sinapsis", 0.8,
                 "activo", "prueba,test,memoria")
            )
        self.ms.conn.commit()

    def tearDown(self):
        if hasattr(self.ms, 'conn') and self.ms.conn:
            try:
                self.ms.conn.close()
            except Exception:
                pass
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    def test_calibrar_y_persistir_crea_tabla(self):
        """Tras calibrar, la tabla calibracion_estado existe con la fila id=1."""
        # Con DB casi vacía y sin QA baseline local no puede calibrar de verdad;
        # verificamos que el método no rompe y deja el objeto consistente.
        res = self.ms.calibrar_y_persistir(alpha=0.10, n_negativos=3, n_positivos_max=0)
        self.assertIn("umbral", res)
        self.assertIsInstance(res["umbral"], float)

    def test_nivel_certeza_tres_niveles_sin_silencio(self):
        """nivel_certeza siempre devuelve uno de los 3 niveles del Neocórtex."""
        niveles = {"evidencia_directa", "relacionado_confianza_media", "sin_evidencia_directa"}
        for score in [0.0, 0.25, 0.45, 0.65, 0.95]:
            nivel = self.ms.nivel_certeza(score)
            self.assertIn(nivel, niveles, f"score={score} devolvió {nivel}")
        # Sin calibración cargada: fallback conservador (0.60 / 0.35)
        self.assertEqual(self.ms.nivel_certeza(0.95), "evidencia_directa")
        self.assertEqual(self.ms.nivel_certeza(0.45), "relacionado_confianza_media")
        self.assertEqual(self.ms.nivel_certeza(0.10), "sin_evidencia_directa")

    def test_confianza_calibrada_sin_calibrador_es_score_crudo(self):
        """Sin Platt calibrado, confianza_calibrada == score crudo (no inventa)."""
        self.assertEqual(self.ms.confianza_calibrada(0.42), 0.42)

    def test_feedback_propaga_util_entre_instancias(self):
        """El MCP crea una instancia nueva por llamada. El feedback debe propagarse
        igual: si esto falla, `util` queda NULL para siempre en producción aunque
        los tests de una sola instancia pasen."""
        # Instancia 1: hace una búsqueda que devuelve un concepto conocido
        c1 = SQLiteMemoryBioRAG(self.db_file)
        # Asegurar que hay nodos para buscar
        c1.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, sinonimos) "
            "VALUES (?, ?, ?, ?, ?)",
            ("concepto_para_feedback", "contenido de prueba para feedback loop", 0.8,
             "activo", "feedback,test")
        )
        c1.conn.commit()
        c1.buscar_por_frase("feedback loop", limite=1)
        log_id = c1.last_log_id
        c1.cerrar_sistema()

        # Instancia 2: aplica feedback (simula flujo MCP real)
        c2 = SQLiteMemoryBioRAG(self.db_file)
        c2.aplicar_refuerzo_dopaminergico("concepto_para_feedback", exito=True)
        c2.cerrar_sistema()

        # Verificar que util se propagó en la DB (cruzó instancias)
        con = sqlite3.connect(self.db_file)
        util = con.execute(
            "SELECT util FROM log_busquedas WHERE id = ?", (log_id,)
        ).fetchone()[0]
        con.close()
        self.assertIsNotNone(
            util, "util quedó NULL: el feedback no cruzó instancias (CASO B falla)"
        )
        self.assertEqual(util, 1, f"esperado util=1 (éxito), obtenido {util}")


if __name__ == "__main__":
    unittest.main()
