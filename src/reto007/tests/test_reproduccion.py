"""Archivo como fuente del modo directo: nunca usa una cámara ni ventanas reales."""

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
import directo
from configuracion import VALORES_PREDETERMINADOS, guardar_configuracion, cargar_configuracion
from reconocimiento import ReconocedorDirecto
from reproduccion import ReproductorArchivo


class VideoComoCamaraTests(unittest.TestCase):
    def setUp(self):
        self.pila = contextlib.ExitStack()
        self.addCleanup(self.pila.close)
        self.base = Path(self.pila.enter_context(tempfile.TemporaryDirectory())).resolve()
        carpeta = self.base / "videos" / "prueba"
        carpeta.mkdir(parents=True)
        self.ruta = carpeta / "original.avi"
        escritor = cv2.VideoWriter(str(self.ruta), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 240))
        self.assertTrue(escritor.isOpened())
        for i in range(4):
            imagen = np.full((240, 320, 3), (100, 150, 0), np.uint8)
            cv2.rectangle(imagen, (70 + i * 4, 60), (100 + i * 4, 175), (255, 255, 255), -1)
            escritor.write(imagen)
        escritor.release()
        self.original = self.ruta.read_bytes()
        guardar_configuracion(VALORES_PREDETERMINADOS, carpeta / "configuracion.json")
        captura = cv2.VideoCapture
        def solo_archivos(origen, *args, **kwargs):
            if not isinstance(origen, str):
                raise AssertionError("No se permite abrir una cámara")
            return captura(origen, *args, **kwargs)
        self.pila.enter_context(patch.object(cv2, "VideoCapture", side_effect=solo_archivos))
        self.pila.enter_context(patch.object(calibrador, "abrir_camara", side_effect=AssertionError("Abrió cámara")))
        self.pila.enter_context(patch.object(calibrador, "BASE", self.base))
        self.pila.enter_context(patch.object(calibrador, "CARPETA_CAPTURAS", self.base / "capturas"))
        self.pila.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.pila.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def interfaz(self, teclas):
        panel = MagicMock()
        panel.mostrar.return_value = True
        panel.manejar_tecla.return_value = False
        def crear(valores):
            panel.valores = valores.copy()
            return panel
        self.pila.enter_context(patch.object(calibrador, "ControlesPrecisos", side_effect=crear))
        self.pila.enter_context(patch.object(cv2, "waitKeyEx", side_effect=teclas))
        self.pila.enter_context(patch.object(cv2, "imshow"))
        self.pila.enter_context(patch.object(cv2, "destroyAllWindows"))
        return panel

    def test_fuente_secuencial_pausa_fin_reinicio_y_tiempos(self):
        r = ReproductorArchivo(self.ruta)
        self.addCleanup(r.cerrar)
        primero = r.leer().copy()
        r.alternar_pausa()
        np.testing.assert_array_equal(r.leer(), primero)
        self.assertEqual(r.indice, 0)
        self.assertEqual(r.espera_ms(0), 30)
        r.alternar_pausa()
        self.assertEqual(r.espera_ms(.04), 60)
        self.assertEqual(r.espera_ms(.2), 1)
        for i in range(1, 4):
            r.leer()
            self.assertEqual(r.indice, i)
        ultimo = r.imagen.copy()
        np.testing.assert_array_equal(r.leer(), ultimo)
        self.assertTrue(r.fin and r.pausado)
        r.reiniciar()
        np.testing.assert_array_equal(r.leer(), primero)
        self.assertFalse(r.fin)
        r.cerrar()
        self.assertIsNone(r.cap)
        self.assertEqual(self.ruta.read_bytes(), self.original)

    def test_fin_pausa_sin_falsa_perdida_camara_y_reinicio_no_graba(self):
        self.interfaz([-1, -1, -1, -1, ord("r"), ord("q")])
        leidos = []
        procesar = ReconocedorDirecto.procesar
        def registrar(motor, resultado, valores):
            objetos, inventario = procesar(motor, resultado, valores)
            leidos.append(objetos[0]["estado_pista"])
            return objetos, inventario
        with patch.object(ReconocedorDirecto, "procesar", registrar), \
             patch.object(calibrador, "Grabacion", side_effect=AssertionError("R no debe grabar otro vídeo")):
            self.assertEqual(directo.main(["--ultimo-video"]), 0)
        # El último fotograma repetido por fin no vuelve a procesar las pistas.
        self.assertEqual(leidos, ["nueva", "continua", "continua", "continua", "nueva"])
        self.assertEqual(self.ruta.read_bytes(), self.original)

    def test_pausa_conserva_pistas_y_g_e_guardan_procedencia(self):
        self.interfaz([ord(" "), ord("g"), ord("e"), ord(" "), ord("q")])
        leidos = []
        procesar = ReconocedorDirecto.procesar
        def registrar(motor, resultado, valores):
            leidos.append(motor.indice)
            return procesar(motor, resultado, valores)
        with patch.object(ReconocedorDirecto, "procesar", registrar):
            self.assertEqual(directo.main(["--video", str(self.ruta)]), 0)
        self.assertEqual(leidos, [0, 1])
        procedencias = list((self.base / "capturas").glob("*.origen.json"))
        self.assertEqual(len(procedencias), 2)
        datos = [json.loads(p.read_text()) for p in procedencias]
        self.assertEqual(datos[0], datos[1])
        self.assertIn("video", datos[0])
        paquete = next((self.base / "resultados").iterdir())
        self.assertFalse(json.loads((paquete / "predicciones.json").read_text())["etiquetas_confirmadas"])

    def test_ajustes_video_guardados_y_override_explicito(self):
        r = ReproductorArchivo(self.ruta)
        perfil = self.base / "videos" / "ajustes" / f"{r.info['huella']}.json"
        r.cerrar()
        valores = {**VALORES_PREDETERMINADOS, "area_min": 1234}
        guardar_configuracion(valores, perfil)
        panel = self.interfaz([ord("p"), ord("q")])
        self.assertEqual(directo.main(["--video", str(self.ruta)]), 0)
        self.assertEqual(panel.valores["area_min"], 1234)
        self.assertEqual(cargar_configuracion(perfil)["area_min"], 1234)
        self.assertEqual(cargar_configuracion(self.ruta.parent / "configuracion.json")["area_min"], 1000)
        explicita = self.base / "explicita.json"
        guardar_configuracion({**valores, "area_min": 500}, explicita)
        with patch.object(cv2, "waitKeyEx", return_value=ord("q")):
            self.assertEqual(directo.main(["--video", str(self.ruta), "--config", str(explicita), "--zoom", "1.5"]), 0)
        self.assertEqual(panel.valores["area_min"], 500)
        self.assertEqual(panel.valores["zoom"], 150)

    def test_archivo_invalido_no_cae_a_camara_y_fuentes_excluyentes(self):
        self.assertEqual(directo.main(["--video", str(self.base / "no_existe.avi")]), 1)
        with self.assertRaises(SystemExit) as error:
            directo.main(["--video", str(self.ruta), "--ultima"])
        self.assertEqual(error.exception.code, 2)

    def test_lectura_truncada_es_error_y_cierra_la_fuente(self):
        self.interfaz([-1] * 4)
        real = ReproductorArchivo.leer
        fuentes = []
        def truncado(r):
            fuentes.append(r)
            if r.indice == 0:
                raise ValueError("vídeo incompleto")
            return real(r)
        with patch.object(ReproductorArchivo, "leer", truncado):
            self.assertEqual(directo.main(["--video", str(self.ruta)]), 1)
        self.assertIsNone(fuentes[-1].cap)


if __name__ == "__main__":
    unittest.main()
