"""Grabación CFR y ciclo del calibrador sin abrir una cámara física."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

import calibrador
import grabacion
from configuracion import VALORES_PREDETERMINADOS, cargar_configuracion
from vision import procesar_imagen


class GrabacionLocal(unittest.TestCase):
    def setUp(self):
        self.imagen = np.full((48, 64, 3), (100, 150, 0), np.uint8)
        self.valores = {**VALORES_PREDETERMINADOS, "zoom": 200}

    def test_cfr_conserva_duracion_original_config_y_muestras(self):
        copia = self.imagen.copy()
        with tempfile.TemporaryDirectory() as carpeta:
            video = grabacion.Grabacion(self.imagen, self.valores, carpeta, ahora=10, fps=10)
            self.valores["zoom"] = 100
            siguiente = np.full_like(self.imagen, (0, 0, 255))
            video.agregar(siguiente, ahora=10.2)
            siguiente[:] = 0  # El recorder conserva su copia limpia.
            ruta = video.cerrar(ahora=10.4)
            self.assertEqual(ruta, video.cerrar())
            datos = json.loads(ruta.with_name("grabacion.json").read_text())
            self.assertEqual(datos["estado"], "completa")
            self.assertEqual(datos["fotogramas"], 4)
            self.assertAlmostEqual(datos["duracion_real_s"], 0.4)
            self.assertAlmostEqual(datos["duracion_video_s"], 0.4)
            self.assertEqual(datos["fotogramas_duplicados"], 2)
            self.assertEqual([f["muestra_camara"] for f in datos["muestras"]], [0, 0, 1, 1])
            self.assertEqual([f["tiempo_video_s"] for f in datos["muestras"]], [0, .1, .2, .3])
            self.assertEqual(cargar_configuracion(ruta.with_name("configuracion.json"))["zoom"], 200)
            lector = cv2.VideoCapture(str(ruta))
            try:
                fotogramas = []
                while True:
                    ok, frame = lector.read()
                    if not ok:
                        break
                    fotogramas.append(frame)
            finally:
                lector.release()
            self.assertEqual(len(fotogramas), 4)
            self.assertTrue(all(f.shape == copia.shape for f in fotogramas))
            np.testing.assert_allclose(fotogramas[0].mean(axis=(0, 1)), copia.mean(axis=(0, 1)), atol=3)
            np.testing.assert_allclose(fotogramas[-1].mean(axis=(0, 1)), [0, 0, 255], atol=3)
            np.testing.assert_array_equal(self.imagen, copia)
            self.assertFalse(video.temporal.exists())

    def test_fallo_camara_duplica_y_cierre_interrumpido(self):
        with tempfile.TemporaryDirectory() as carpeta:
            video = grabacion.Grabacion(self.imagen, self.valores, carpeta, ahora=0, fps=10)
            video.sin_imagen(ahora=.35)
            ruta = video.cerrar(ahora=.38, interrumpida=True, motivo="Sin cámara")
            datos = json.loads(ruta.with_name("grabacion.json").read_text())
            self.assertEqual(datos["estado"], "interrumpida")
            self.assertEqual(datos["fotogramas"], 4)
            self.assertEqual(datos["fotogramas_duplicados"], 3)
            self.assertLess(abs(datos["duracion_real_s"] - datos["duracion_video_s"]), 1 / datos["fps"])
            self.assertTrue(datos["avisos"])

    def test_error_no_publica_grabacion_aparentemente_completa(self):
        with tempfile.TemporaryDirectory() as carpeta:
            video = grabacion.Grabacion(self.imagen, self.valores, carpeta, ahora=0)
            with patch.object(video, "_verificar", side_effect=OSError("archivo truncado")):
                with self.assertRaises(OSError):
                    video.cerrar(ahora=.1)
            self.assertFalse(video.destino.exists())
            self.assertTrue(video.temporal.exists())
            self.assertEqual(json.loads((video.temporal / "grabacion.json").read_text())["estado"], "error")

    def test_error_codec_y_resolucion_no_abre_camara(self):
        with tempfile.TemporaryDirectory() as carpeta:
            escritor = MagicMock()
            escritor.isOpened.return_value = False
            with patch.object(cv2, "VideoWriter", return_value=escritor):
                with self.assertRaises(OSError):
                    grabacion.Grabacion(self.imagen, self.valores, carpeta)
            escritor.release.assert_called_once()
            self.assertTrue(all(p.name.startswith(".") for p in Path(carpeta).iterdir()))
            with self.assertRaises(ValueError):
                grabacion.Grabacion(self.imagen[:, :-1], self.valores, carpeta)

    def _calibrador_mock(self, pila, teclas):
        panel = MagicMock()
        panel.valores = self.valores.copy()
        panel.mostrar.return_value = True
        panel.manejar_tecla.return_value = False
        captura = MagicMock()
        captura.read.return_value = (True, self.imagen)
        abrir = pila.enter_context(patch.object(calibrador, "abrir_camara", return_value=captura))
        pila.enter_context(patch.object(calibrador, "ControlesPrecisos", return_value=panel))
        pila.enter_context(patch.object(cv2, "waitKeyEx", side_effect=teclas))
        pila.enter_context(patch.object(cv2, "imshow"))
        pila.enter_context(patch.object(cv2, "destroyAllWindows"))
        pila.enter_context(contextlib.redirect_stdout(io.StringIO()))
        pila.enter_context(contextlib.redirect_stderr(io.StringIO()))
        return captura, abrir

    def test_r_permite_dos_videos_y_q_finaliza_sin_segunda_camara(self):
        with tempfile.TemporaryDirectory() as carpeta, contextlib.ExitStack() as pila:
            pila.enter_context(patch.object(grabacion, "CARPETA_VIDEOS", Path(carpeta)))
            captura, abrir = self._calibrador_mock(pila, [ord("r"), ord("r"), ord("r"), ord("q")])
            self.assertEqual(calibrador.main(["--camara", "1"]), 0)
            abrir.assert_called_once_with(1)
            captura.release.assert_called_once()
            rutas = list(Path(carpeta).glob("grabacion_*/original.avi"))
            self.assertEqual(len(rutas), 2)
            for ruta in rutas:
                datos = json.loads(ruta.with_name("grabacion.json").read_text())
                self.assertEqual(datos["estado"], "completa")
                self.assertGreater(datos["fotogramas"], 0)

    def test_excepcion_del_procesado_cierra_video_y_libera_camara(self):
        resultado = procesar_imagen(self.imagen, self.valores)
        with tempfile.TemporaryDirectory() as carpeta, contextlib.ExitStack() as pila:
            pila.enter_context(patch.object(grabacion, "CARPETA_VIDEOS", Path(carpeta)))
            captura, _ = self._calibrador_mock(pila, [ord("r")])
            pila.enter_context(patch.object(calibrador, "procesar_imagen", side_effect=[resultado, RuntimeError("fallo")]))
            self.assertEqual(calibrador.main(["--camara", "1"]), 1)
            captura.release.assert_called_once()
            datos = json.loads(next(Path(carpeta).glob("grabacion_*/grabacion.json")).read_text())
            self.assertEqual(datos["estado"], "interrumpida")

    def test_r_en_foto_no_abre_camara_ni_grabacion(self):
        with tempfile.TemporaryDirectory() as carpeta, contextlib.ExitStack() as pila:
            ruta = Path(carpeta) / "foto.png"
            cv2.imwrite(str(ruta), self.imagen)
            _, abrir = self._calibrador_mock(pila, [ord("r"), ord("q")])
            iniciar = pila.enter_context(patch.object(calibrador, "Grabacion", side_effect=AssertionError("Grabación en modo foto")))
            self.assertEqual(calibrador.main(["--imagen", str(ruta)]), 0)
            abrir.assert_not_called()
            iniciar.assert_not_called()

    def test_ctrl_c_durante_cierre_libera_camara_y_ventanas(self):
        with tempfile.TemporaryDirectory() as carpeta, contextlib.ExitStack() as pila:
            pila.enter_context(patch.object(grabacion, "CARPETA_VIDEOS", Path(carpeta)))
            captura, _ = self._calibrador_mock(pila, [ord("r"), ord("q")])
            # Interrupción realista: el writer ya cerró, pero se interrumpe la
            # comprobación del archivo antes de publicar su carpeta definitiva.
            pila.enter_context(patch.object(grabacion.Grabacion, "_verificar", side_effect=KeyboardInterrupt))
            self.assertEqual(calibrador.main(["--camara", "1"]), 130)
            captura.release.assert_called_once()
            calibrador.ControlesPrecisos.return_value.cerrar.assert_called_once()
            cv2.destroyAllWindows.assert_called_once()
            self.assertFalse(list(Path(carpeta).glob("grabacion_*")))
            incompletas = list(Path(carpeta).glob(".grabacion_*.incompleta"))
            self.assertEqual(len(incompletas), 1)
            self.assertEqual(json.loads((incompletas[0] / "grabacion.json").read_text())["estado"], "error")


if __name__ == "__main__":
    unittest.main()
