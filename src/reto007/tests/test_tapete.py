"""Regresiones de la región de análisis: sin cámaras, ventanas ni archivos del usuario."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

import calibrador
import etiquetado
import vision
from configuracion import (
    BASE, VALORES_PREDETERMINADOS, cargar_configuracion,
    guardar_configuracion, validar_configuracion,
)
from controles import ControlesPrecisos
from detector import METRICAS
from etiquetado import cargar_etiquetas_existentes, exportar_sesion, firma_deteccion


class RegionTapete(unittest.TestCase):
    def setUp(self):
        self.valores = {**VALORES_PREDETERMINADOS, "limitar_tapete": 1,
                        "margen_tapete": 2, "suavizado": 1, "cierre": 0}
        # Mesa gris, tapete turquesa (H90), herramienta blanca y objeto exterior.
        self.imagen = np.full((600, 800, 3), (80, 80, 80), np.uint8)
        cv2.rectangle(self.imagen, (160, 80), (700, 540), (180, 180, 0), -1)
        cv2.rectangle(self.imagen, (300, 170), (350, 390), (240, 240, 240), -1)
        cv2.rectangle(self.imagen, (20, 150), (100, 450), (240, 240, 240), -1)

    def test_exterior_se_ignora_y_hueco_interior_conserva_herramienta(self):
        antes = self.imagen.copy()
        resultado = vision.procesar_imagen(self.imagen, self.valores)
        self.assertTrue(resultado["tapete"]["activo"])
        self.assertTrue(resultado["tapete"]["detectado"])
        self.assertEqual(len(resultado["objetos"]), 1)
        self.assertEqual(resultado["objetos"][0]["area_px2"], 50 * 220)
        self.assertEqual(resultado["mascara_tapete"][250, 325], 255)
        self.assertEqual(resultado["mascara"][250, 325], 255)
        self.assertEqual(resultado["mascara"][250, 60], 0)
        self.assertEqual(resultado["mascara_tapete"][250, 60], 0)
        self.assertEqual(resultado["imagen"].shape, self.imagen.shape)
        np.testing.assert_array_equal(self.imagen, antes)

    def test_fotos_guardadas_recuperan_seis_sin_mesa_y_encuadre_conserva_medidas(self):
        fotos = [BASE / "capturas" / f"{tipo}_{fecha}.png"
                 for fecha in ("20261016_113207_730520", "20261016_113218_711279",
                               "20261016_113231_782061")
                 for tipo in ("escena", "original")]
        valores = {**VALORES_PREDETERMINADOS, "area_min": 1000,
                   "limitar_tapete": 1, "margen_tapete": 2}
        for ruta in fotos:
            with self.subTest(foto=ruta.name):
                resultado = vision.procesar_imagen(cv2.imread(str(ruta)), valores)
                self.assertEqual(len(resultado["objetos"]), 6)
                self.assertTrue(resultado["tapete"]["detectado"])
                self.assertFalse(np.any(resultado["mascara"][resultado["mascara_tapete"] == 0]))
        foto = cv2.imread(str(BASE / "capturas" / "escena_20261016_113231_782061.png"))
        limitada = vision.procesar_imagen(foto, valores)
        completa = vision.procesar_imagen(foto, {**valores, "limitar_tapete": 0})
        areas_conocidas = [8588.5, 16401.5, 4115.0, 20848.5, 28581.5, 28419.5]
        self.assertEqual([o["area_px2"] for o in completa["objetos"]], areas_conocidas)
        for actual, anterior in zip(limitada["objetos"], completa["objetos"]):
            np.testing.assert_array_equal(actual["contorno"], anterior["contorno"])
            for metrica in METRICAS:
                self.assertEqual(actual[metrica], anterior[metrica])

    def test_sin_tapete_o_parche_insuficiente_no_analiza_todo_el_fondo(self):
        escenas = [np.full((600, 800, 3), 80, np.uint8)]
        pequena = escenas[0].copy()
        cv2.rectangle(pequena, (300, 200), (350, 250), (180, 180, 0), -1)
        escenas.append(pequena)
        # Un marco verde grande no justifica rellenar toda una mesa no verde.
        escasa = escenas[0].copy()
        cv2.rectangle(escasa, (100, 80), (700, 520), (180, 180, 0), 3)
        escenas.append(escasa)
        for indice, imagen in enumerate(escenas):
            with self.subTest(escena=indice):
                resultado = vision.procesar_imagen(imagen, self.valores)
                self.assertFalse(resultado["tapete"]["detectado"])
                self.assertEqual(resultado["objetos"], [])
                self.assertFalse(resultado["mascara"].any())
                self.assertFalse(resultado["mascara_tapete"].any())
                self.assertTrue(resultado["avisos"])

    def test_contorno_parcial_en_limite_se_descarta_con_aviso(self):
        imagen = self.imagen.copy()
        # El margen de 2 px deja el borde interior en x=162. Esta pieza cruza
        # dicho borde, aunque todavía esté dentro del contorno verde original.
        cv2.rectangle(imagen, (161, 200), (230, 300), (240, 240, 240), -1)
        resultado = vision.procesar_imagen(imagen, self.valores)
        self.assertEqual(len(resultado["objetos"]), 1)
        self.assertGreaterEqual(resultado["descartados_borde"], 1)
        self.assertTrue(resultado["avisos"])
        self.assertEqual(resultado["objetos"][0]["centroide_x_px"], 325)

    def test_morfologia_no_reintroduce_exterior_ni_sobrescribe_mascara_roi(self):
        valores = {**self.valores, "cierre": 4, "kernel": 9}
        resultado = vision.procesar_imagen(self.imagen, valores)
        fuera = resultado["mascara_tapete"] == 0
        self.assertTrue(fuera.any())
        self.assertFalse(resultado["mascara_bruta"][fuera].any())
        self.assertFalse(resultado["mascara"][fuera].any())

    def test_desactivar_limitacion_recupera_contorno_exterior_original(self):
        resultado = vision.procesar_imagen(
            self.imagen, {**self.valores, "limitar_tapete": 0}
        )
        self.assertFalse(resultado["tapete"]["activo"])
        self.assertEqual(len(resultado["objetos"]), 1)
        self.assertEqual(resultado["objetos"][0]["area_px2"], 799 * 599)
        self.assertEqual(resultado["mascara"][0, 0], 255)
        self.assertEqual(resultado["mascara"][250, 325], 255)
        self.assertEqual(resultado["mascara"][100, 200], 0)

    def test_configuracion_exportada_reproduce_roi_y_firma_de_sesion(self):
        resultado = vision.procesar_imagen(self.imagen, self.valores)
        with tempfile.TemporaryDirectory() as carpeta:
            base = Path(carpeta)
            origen = base / "foto.png"
            cv2.imwrite(str(origen), self.imagen)
            destino = exportar_sesion(resultado, origen, self.imagen, self.valores,
                                      {1: "Nivel"}, {1}, base / "resultados")
            ajustes = cargar_configuracion(destino / "configuracion.json")
            self.assertEqual(ajustes["limitar_tapete"], 1)
            self.assertEqual(ajustes["margen_tapete"], 2)
            copia = cv2.imread(str(destino / "imagen_origen.png"))
            recuperado = vision.procesar_imagen(copia, ajustes)
            np.testing.assert_array_equal(resultado["mascara_tapete"], recuperado["mascara_tapete"])
            np.testing.assert_array_equal(cv2.imread(str(destino / "tapete.png"), cv2.IMREAD_GRAYSCALE),
                                          resultado["mascara_tapete"])
            self.assertEqual(firma_deteccion(self.imagen, self.valores, resultado),
                             firma_deteccion(copia, ajustes, recuperado))
            resumen = json.loads((destino / "resumen.json").read_text())
            self.assertIn("region_analisis", resumen)
            carga = cargar_etiquetas_existentes(destino / "imagen_origen.png", copia,
                                                ajustes, recuperado, base)
            self.assertEqual(carga["revisadas"], {1})
            otros = {**ajustes, "margen_tapete": 3}
            resultado_otro = vision.procesar_imagen(copia, otros)
            self.assertEqual(len(resultado_otro["objetos"]), 1)
            carga = cargar_etiquetas_existentes(destino / "imagen_origen.png", copia,
                                                otros, resultado_otro, base)
            self.assertEqual(carga["revisadas"], set())
            self.assertEqual(carga["etiquetas"], {1: "Nivel"})

    def test_firma_incluye_region_y_version_aunque_objetos_no_cambien(self):
        resultado = vision.procesar_imagen(self.imagen, self.valores)
        firma = firma_deteccion(self.imagen, self.valores, resultado)
        otra_roi = {**resultado, "mascara_tapete": resultado["mascara_tapete"].copy()}
        otra_roi["mascara_tapete"][100, 200] = 0
        self.assertNotEqual(firma, firma_deteccion(self.imagen, self.valores, otra_roi))
        with patch.object(etiquetado, "VERSION_PROCESADO", "tapete-version-posterior"):
            self.assertNotEqual(firma, firma_deteccion(self.imagen, self.valores, resultado))

    def test_campos_nuevos_se_validan_y_calibrador_conserva_camara_uno(self):
        self.assertEqual(validar_configuracion({})["limitar_tapete"], 1)
        for invalido in ({"limitar_tapete": 2}, {"limitar_tapete": True},
                         {"margen_tapete": -1}, {"margen_tapete": 31}):
            with self.subTest(valores=invalido), self.assertRaises(ValueError):
                validar_configuracion(invalido)
        controles = ControlesPrecisos(self.valores)
        self.assertEqual(controles.valores["limitar_tapete"], 1)
        self.assertEqual(controles.valores["margen_tapete"], 2)
        camara = Mock()
        camara.read.return_value = True, self.imagen
        with tempfile.TemporaryDirectory() as carpeta, contextlib.ExitStack() as pila:
            archivo = guardar_configuracion(self.valores, Path(carpeta) / "config.json")
            abrir = pila.enter_context(patch.object(calibrador, "abrir_camara", return_value=camara))
            pila.enter_context(patch.object(ControlesPrecisos, "mostrar", return_value=True))
            pila.enter_context(patch.object(ControlesPrecisos, "cerrar"))
            pila.enter_context(patch.object(cv2, "imshow"))
            pila.enter_context(patch.object(cv2, "waitKeyEx", return_value=ord("q")))
            pila.enter_context(patch.object(cv2, "destroyAllWindows"))
            pila.enter_context(contextlib.redirect_stdout(io.StringIO()))
            self.assertEqual(calibrador.main(["--config", str(archivo), "--camara", "1"]), 0)
            abrir.assert_called_once_with(1)
            camara.release.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
