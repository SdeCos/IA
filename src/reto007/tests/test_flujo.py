"""Pruebas del flujo offline; no abren cámaras ni ventanas."""

import contextlib
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

import calibrador
from configuracion import (
    BASE, VALORES_PREDETERMINADOS, cargar_configuracion,
    configuracion_para_imagen, guardar_configuracion, validar_configuracion,
)
from controles import ControlesPrecisos
from detector import exportar_resultado
from vision import dibujar_resultado, procesar_imagen


class FlujoOffline(unittest.TestCase):
    def setUp(self):
        self.valores = VALORES_PREDETERMINADOS.copy()
        self.imagen = np.full((800, 800, 3), (100, 150, 0), np.uint8)
        cv2.rectangle(self.imagen, (200, 150), (280, 350), (255, 255, 255), -1)

    def test_rotacion_sin_cambiar_escala(self):
        original = procesar_imagen(self.imagen, self.valores)["objetos"]
        girada = procesar_imagen(cv2.rotate(self.imagen, cv2.ROTATE_90_CLOCKWISE), self.valores)["objetos"]
        self.assertEqual((len(original), len(girada)), (1, 1))
        for clave in ("area_px2", "perimetro_px", "solidez", "relacion_aspecto", "circularidad"):
            self.assertAlmostEqual(original[0][clave], girada[0][clave], places=5)
        self.assertAlmostEqual((girada[0]["orientacion_grados"] - original[0]["orientacion_grados"]) % 180, 90)

    def test_foto_conocida_seis_objetos_y_dibujo_no_modifica_datos(self):
        ruta = BASE / "capturas" / "escena_20261016_113231_782061.png"
        foto = cv2.imread(str(ruta))
        self.assertIsNotNone(foto)
        copia = foto.copy()
        resultado = procesar_imagen(foto, self.valores)
        limpia = resultado["imagen"].copy()
        self.assertEqual([o["id"] for o in resultado["objetos"]], list(range(1, 7)))
        dibujar_resultado(resultado)
        np.testing.assert_array_equal(foto, copia)
        np.testing.assert_array_equal(resultado["imagen"], limpia)

    def test_configuracion_invalida_y_zoom_escena(self):
        for cambios in ({"kernel": 4}, {"h_min": 110}, {"zoom": True}, {"errata": 1}):
            with self.assertRaises(ValueError):
                validar_configuracion(cambios)
        with tempfile.TemporaryDirectory() as carpeta:
            escena = Path(carpeta) / "escena_prueba.png"
            guardar_configuracion({**self.valores, "zoom": 200}, escena.with_suffix(".json"))
            self.assertEqual(configuracion_para_imagen(escena)["zoom"], 200)
            self.assertEqual(configuracion_para_imagen(escena, zoom=1)["zoom"], 100)

    def test_guardado_reproduce_zoom_y_pixeles_sin_anotaciones(self):
        valores = {**self.valores, "zoom": 168}
        antes = procesar_imagen(self.imagen, valores)
        with tempfile.TemporaryDirectory() as carpeta, patch.object(calibrador, "CARPETA_CAPTURAS", Path(carpeta)):
            with contextlib.redirect_stdout(io.StringIO()):
                escena, original = calibrador.guardar_captura(self.imagen, antes["encuadre"], valores)
            np.testing.assert_array_equal(cv2.imread(str(original)), self.imagen)
            for ruta, zoom in ((original, 168), (escena, 100)):
                ajustes = configuracion_para_imagen(ruta)
                self.assertEqual(ajustes["zoom"], zoom)
                despues = procesar_imagen(cv2.imread(str(ruta)), ajustes)
                np.testing.assert_array_equal(antes["mascara"], despues["mascara"])

    def test_p_guarda_los_ajustes_que_se_recuperan_con_la_foto(self):
        with tempfile.TemporaryDirectory() as carpeta:
            foto = Path(carpeta) / "escena_prueba.png"
            cv2.imwrite(str(foto), self.imagen)
            guardar_configuracion(self.valores, foto.with_suffix(".json"))
            panel = ControlesPrecisos(self.valores)
            teclas = iter((ord("p"), ord("q")))
            def esperar(_):
                panel.valores["s_min"] = 120
                return next(teclas)
            with contextlib.ExitStack() as pila:
                pila.enter_context(patch.object(calibrador, "ControlesPrecisos", return_value=panel))
                pila.enter_context(patch.object(panel, "mostrar", return_value=True))
                pila.enter_context(patch.object(panel, "cerrar"))
                pila.enter_context(patch.object(cv2, "imshow"))
                pila.enter_context(patch.object(cv2, "destroyAllWindows"))
                pila.enter_context(patch.object(cv2, "VideoCapture", side_effect=AssertionError("Se abrió una cámara")))
                pila.enter_context(patch.object(cv2, "waitKeyEx", side_effect=esperar))
                pila.enter_context(contextlib.redirect_stdout(io.StringIO()))
                self.assertEqual(calibrador.main(["--imagen", str(foto)]), 0)
            self.assertEqual(configuracion_para_imagen(foto)["s_min"], 120)

    def test_csv_es_reproducible_y_no_sobrescribe_etiquetas(self):
        resultado = procesar_imagen(self.imagen, self.valores)
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "resultado"
            foto = Path(carpeta) / "entrada.png"
            cv2.imwrite(str(foto), self.imagen)
            exportar_resultado(resultado, foto, self.valores, destino, {1: "Referencia manual"})
            csv_path = destino / "caracteristicas.csv"
            contenido = csv_path.read_bytes()
            with csv_path.open(encoding="utf-8-sig", newline="") as archivo:
                filas = list(csv.DictReader(archivo, delimiter=";"))
            self.assertEqual(filas[0]["nombre_real"], "Referencia manual")
            self.assertAlmostEqual(float(filas[0]["area_px2"]), resultado["objetos"][0]["area_px2"])
            reproducido = procesar_imagen(self.imagen, cargar_configuracion(destino / "configuracion.json"))
            np.testing.assert_array_equal(resultado["mascara"], reproducido["mascara"])
            with self.assertRaises(FileExistsError):
                exportar_resultado(resultado, foto, self.valores, destino)
            self.assertEqual(csv_path.read_bytes(), contenido)
            with self.assertRaises(ValueError):
                exportar_resultado(resultado, foto, self.valores, Path(carpeta) / "invalido", {99: "Inexistente"})
            self.assertFalse((Path(carpeta) / "invalido").exists())


if __name__ == "__main__":
    unittest.main()
