"""Flujo de reconocimiento en cámara simulada, sin ventanas ni datos nuevos de usuario."""

import contextlib
import csv
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

import calibrador
import directo
from configuracion import BASE, configuracion_para_imagen
from reconocimiento import ReconocedorDirecto, cargar_inventario, dibujar_directo
from vision import procesar_imagen


class DirectoTests(unittest.TestCase):
    def setUp(self):
        self.foto = BASE / "capturas" / "escena_20261016_113231_782061.png"
        self.imagen = cv2.imread(str(self.foto))
        self.valores = configuracion_para_imagen(self.foto)
        self.resultado = procesar_imagen(self.imagen, self.valores)
        self.pila = contextlib.ExitStack()
        self.addCleanup(self.pila.close)
        self.temporal = Path(self.pila.enter_context(tempfile.TemporaryDirectory()))

    def simular(self, teclas):
        panel = MagicMock()
        panel.valores = self.valores.copy()
        panel.mostrar.return_value = True
        panel.manejar_tecla.return_value = False
        cap = MagicMock()
        cap.read.side_effect = lambda: (True, self.imagen.copy())
        self.abrir = self.pila.enter_context(patch.object(calibrador, "abrir_camara", return_value=cap))
        self.pila.enter_context(patch.object(calibrador, "ControlesPrecisos", return_value=panel))
        self.pila.enter_context(patch.object(calibrador, "BASE", self.temporal))
        self.pila.enter_context(patch.object(calibrador, "CARPETA_CAPTURAS", self.temporal / "capturas"))
        self.pila.enter_context(patch.object(cv2, "waitKeyEx", side_effect=teclas))
        self.mostrar = self.pila.enter_context(patch.object(cv2, "imshow"))
        self.cerrar = self.pila.enter_context(patch.object(cv2, "destroyAllWindows"))
        self.pila.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.pila.enter_context(contextlib.redirect_stderr(io.StringIO()))
        return cap, panel

    def test_secuencia_predice_no_etiqueta_y_no_acumula_inventario(self):
        motor = ReconocedorDirecto({"Martillo": 1})
        objetos, inventario = motor.procesar(self.resultado, self.valores)
        self.assertEqual(inventario["presentes"]["Martillo"], 1)
        self.assertFalse(inventario["faltantes"])
        self.assertTrue(all("clase_predicha" not in o for o in self.resultado["objetos"]))
        self.assertTrue(all("nombre_real" not in o for o in objetos))
        segundo, _ = motor.procesar(self.resultado, self.valores)
        self.assertTrue(all(o["estado_pista"] == "continua" for o in segundo))
        motor.reiniciar()
        reconectados, _ = motor.procesar(self.resultado, self.valores)
        self.assertTrue(all(o["estado_pista"] == "nueva" for o in reconectados))
        _, vacio = motor.procesar({**self.resultado, "objetos": []}, self.valores)
        self.assertEqual(vacio["presentes"], {})
        self.assertEqual(vacio["faltantes"], {"Martillo": 1})

    def test_inventario_invalido_no_abre_camara(self):
        self.simular([ord("q")])
        for datos in ({"Martillo": -1}, {"Sin regla": 1}, [], {"Martillo": True}):
            ruta = self.temporal / "inventario.json"
            ruta.write_text(json.dumps(datos))
            self.assertEqual(directo.main(["--inventario", str(ruta)]), 1)
        self.abrir.assert_not_called()
        self.assertIsNone(cargar_inventario(None))

    def test_camara_exporta_predicciones_y_preserva_referencia_sin_confirmar(self):
        cap, panel = self.simular([ord("e"), ord("q")])
        self.assertEqual(directo.main(["--camara", "1"]), 0)
        self.abrir.assert_called_once_with(1)
        cap.release.assert_called_once()
        panel.cerrar.assert_called_once()
        self.cerrar.assert_called_once()
        self.assertIn("2. Reconocimiento en directo", [c.args[0] for c in self.mostrar.call_args_list])
        paquete = next((self.temporal / "resultados").iterdir())
        datos = json.loads((paquete / "predicciones.json").read_text())
        self.assertFalse(datos["etiquetas_confirmadas"])
        self.assertEqual(len(datos["objetos"]), 6)
        self.assertEqual(datos["inventario"]["total"], 6)
        self.assertEqual(datos["inventario"]["esperadas"], None)
        self.assertTrue(all(not n for n in json.loads((paquete / "etiquetas.json").read_text()).values()))
        with (paquete / "predicciones.csv").open(encoding="utf-8-sig") as archivo:
            filas = list(csv.DictReader(archivo, delimiter=";"))
        self.assertEqual(len(filas), 6)
        self.assertIn("Martillo", {f["clase_predicha"] for f in filas})
        self.assertTrue((paquete / "reconocimiento.png").is_file())

    def test_grabacion_recibe_imagen_limpia_y_q_cierra_camara(self):
        cap, _ = self.simular([ord("r"), ord("q")])
        grabar = self.pila.enter_context(patch.object(calibrador, "Grabacion"))
        grabar.return_value.inicio = 0.0
        grabar.return_value.cerrar.return_value = None
        self.assertEqual(directo.main(["--camara", "1"]), 0)
        np.testing.assert_array_equal(grabar.call_args.args[0], self.imagen)
        np.testing.assert_array_equal(grabar.return_value.agregar.call_args.args[0], self.imagen)
        grabar.return_value.cerrar.assert_called_once()
        cap.release.assert_called_once()

    def test_perdida_de_imagen_finaliza_con_error_y_libera_camara(self):
        cap, _ = self.simular([-1] * 20)
        cap.read.side_effect = lambda: (False, None)
        self.pila.enter_context(patch.object(calibrador.time, "monotonic", side_effect=itertools.count()))
        self.pila.enter_context(patch.object(calibrador.time, "sleep"))
        self.assertEqual(directo.main(["--camara", "1"]), 1)
        cap.release.assert_called_once()

    def test_ctrl_c_libera_camara_y_foto_no_abre_camara(self):
        cap, _ = self.simular([ord("q")])
        cap.read.side_effect = KeyboardInterrupt
        self.assertEqual(directo.main(["--camara", "1"]), 130)
        cap.release.assert_called_once()
        self.abrir.reset_mock()
        self.assertEqual(directo.main(["--imagen", str(self.foto)]), 0)
        self.abrir.assert_not_called()

    def test_render_no_modifica_imagen_y_contiene_panel_de_inventario(self):
        original = self.resultado["imagen"].copy()
        motor = ReconocedorDirecto(cargar_inventario(BASE / "ejemplos" / "inventario.json"))
        objetos, inventario = motor.procesar(self.resultado, self.valores)
        vista = dibujar_directo(self.resultado, objetos, inventario, en_vivo=False)
        np.testing.assert_array_equal(original, self.resultado["imagen"])
        self.assertGreater(vista.shape[0], original.shape[0])
        self.assertTrue(inventario["completo"])


if __name__ == "__main__":
    unittest.main()
