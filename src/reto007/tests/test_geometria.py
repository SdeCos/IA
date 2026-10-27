"""Comprobaciones de descriptores geométricos independientes de las clases."""

import unittest

import numpy as np

from geometria import METRICAS_GEOMETRICAS, MUESTRAS_PERFIL, caracteristicas_forma


def contorno(puntos):
    return np.asarray(puntos, dtype=np.float32).reshape(-1, 1, 2)


class GeometriaTests(unittest.TestCase):
    def setUp(self):
        # Cabeza de ancho 60 durante el 25 % del largo; mango de ancho 20.
        self.martillo = contorno([
            (0, 0), (50, 0), (50, 20), (200, 20),
            (200, 40), (50, 40), (50, 60), (0, 60),
        ])

    def test_rectangulo_y_martillo_tienen_medidas_interpretables(self):
        rectangulo = caracteristicas_forma(contorno([(0, 0), (100, 0), (100, 20), (0, 20)]))
        self.assertAlmostEqual(rectangulo["extension"], 1)
        self.assertAlmostEqual(rectangulo["contraste_extremos"], 0)
        self.assertAlmostEqual(rectangulo["asimetria_longitudinal"], 0)
        self.assertAlmostEqual(rectangulo["ancho_central"], 1)
        self.assertAlmostEqual(rectangulo["fraccion_ancha"], 1)
        np.testing.assert_allclose(rectangulo["perfil_ancho"], 1)

        forma = caracteristicas_forma(self.martillo)
        self.assertAlmostEqual(forma["extension"], .5)
        self.assertAlmostEqual(forma["contraste_extremos"], 2 / 3)
        self.assertAlmostEqual(forma["fraccion_ancha"], .25)
        self.assertAlmostEqual(forma["asimetria_longitudinal"], 1 / 3)
        self.assertAlmostEqual(forma["ancho_central"], 1 / 3)
        np.testing.assert_allclose(forma["perfil_ancho"][:10], 1)
        np.testing.assert_allclose(forma["perfil_ancho"][10:], 1 / 3)

    def test_rotacion_escala_traslacion_y_orden_no_cambian_los_rasgos(self):
        referencia = caracteristicas_forma(self.martillo)
        original = self.martillo.copy()
        for grados, escala in [(0, .25), (37, 3), (90, 1), (180, 2), (271, .8)]:
            rad = np.deg2rad(grados)
            rotacion = np.array([[np.cos(rad), -np.sin(rad)], [np.sin(rad), np.cos(rad)]])
            transformado = (self.martillo.reshape(-1, 2) @ rotacion.T) * escala + (172, 93)
            for orden in (transformado, transformado[::-1]):
                forma = caracteristicas_forma(contorno(orden))
                with self.subTest(grados=grados, escala=escala):
                    for metrica in METRICAS_GEOMETRICAS:
                        self.assertAlmostEqual(forma[metrica], referencia[metrica], places=5)
                    np.testing.assert_allclose(forma["perfil_ancho"], referencia["perfil_ancho"], atol=2e-6)
        np.testing.assert_array_equal(self.martillo, original)

    def test_empate_entre_extremos_resuelve_ambiguedad_180(self):
        # Los extremos tienen el mismo ancho, pero el saliente no está centrado.
        forma = contorno([(0, 10), (50, 10), (50, 0), (80, 0),
                          (80, 10), (200, 10), (200, 30), (0, 30)])
        directa = caracteristicas_forma(forma)
        invertida = caracteristicas_forma(-forma + 400)
        np.testing.assert_allclose(directa["perfil_ancho"], invertida["perfil_ancho"], atol=1e-6)
        self.assertAlmostEqual(directa["contraste_extremos"], 0)
        self.assertGreater(directa["asimetria_longitudinal"], 0)

    def test_perfil_mide_distancia_exterior_e_incluye_espacios_entre_ramas(self):
        horquilla = contorno([(0, 0), (100, 0), (100, 10), (50, 10),
                             (50, 40), (100, 40), (100, 50), (0, 50)])
        forma = caracteristicas_forma(horquilla)
        np.testing.assert_allclose(forma["perfil_ancho"], 1)
        self.assertAlmostEqual(forma["extension"], .7)

    def test_contornos_degenerados_devuelven_ceros_finitos(self):
        for puntos in [[], [(1, 1)], [(0, 0), (10, 10), (20, 20)]]:
            forma = caracteristicas_forma(contorno(puntos))
            self.assertEqual(len(forma["perfil_ancho"]), MUESTRAS_PERFIL)
            self.assertEqual(len(forma["perfil_posiciones"]), MUESTRAS_PERFIL)
            self.assertTrue(all(forma[nombre] == 0 for nombre in METRICAS_GEOMETRICAS))
            np.testing.assert_allclose(forma["perfil_ancho"], 0)
        with self.assertRaisesRegex(ValueError, "finitas"):
            caracteristicas_forma(contorno([(0, 0), (1, 1), (np.nan, 2)]))


if __name__ == "__main__":
    unittest.main()
