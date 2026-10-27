"""Reproducción y exportación reales de AVI cortos, sin conectar ninguna cámara."""

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from configuracion import VALORES_PREDETERMINADOS, guardar_configuracion, configuracion_para_imagen
from video import (listar_videos, inspeccionar_video, leer_fotograma, configuracion_para_video,
                   exportar_fotograma, exportar_video, conteo_fotograma, COLUMNAS_CLASIFICACION)
from clasificacion import VERSION_CLASIFICADOR
from vision import procesar_imagen


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.base = Path(self.temporal.name)
        self.carpeta = self.base / "videos" / "prueba"
        self.carpeta.mkdir(parents=True)
        self.ruta = self.carpeta / "original.avi"
        self.valores = {**VALORES_PREDETERMINADOS, "area_min": 100, "suavizado": 1, "cierre": 0}
        writer = cv2.VideoWriter(str(self.ruta), cv2.VideoWriter_fourcc(*"MJPG"), 15, (640, 360))
        self.assertTrue(writer.isOpened())
        try:
            for i in range(8):
                imagen = np.full((360, 640, 3), (150, 150, 0), np.uint8)
                if i != 3:
                    cv2.rectangle(imagen, (180 + i * 4, 100), (210 + i * 4, 250), (255, 255, 255), -1)
                writer.write(imagen)
        finally:
            writer.release()
        guardar_configuracion(self.valores, self.carpeta / "configuracion.json")

    def test_inspeccion_lectura_busqueda_y_liberacion(self):
        incompleta = self.base / "videos" / ".incompleta_prueba"
        incompleta.mkdir()
        (incompleta / "original.avi").write_bytes(self.ruta.read_bytes())
        self.assertEqual(listar_videos(self.base), [self.ruta])
        info = inspeccionar_video(self.ruta)
        self.assertEqual(info["fotogramas"], 8)
        self.assertEqual(info["fps"], 15)
        self.assertEqual((info["ancho"], info["alto"]), (640, 360))
        self.assertEqual(len(info["huella"]), 64)
        # Buscar hacia atrás y delante debe devolver el fotograma solicitado.
        for indice in (7, 0, 3, 6):
            imagen, posicion = leer_fotograma(self.ruta, indice)
            self.assertEqual(posicion["indice"], indice)
            self.assertAlmostEqual(posicion["tiempo_s"], indice / 15)
            deteccion = procesar_imagen(imagen, self.valores)
            self.assertEqual(len(deteccion["objetos"]), 0 if indice == 3 else 1)
            if indice != 3:
                self.assertAlmostEqual(deteccion["objetos"][0]["centroide_x_px"], (195 + indice * 4) * 1.25, delta=2)
        self.assertEqual(configuracion_para_video(self.ruta), self.valores)

    def test_indices_errores_no_abren_webcam(self):
        for indice in (-1, 8, .5, True):
            with self.assertRaises(ValueError):
                leer_fotograma(self.ruta, indice)
        with patch("video.cv2.VideoCapture") as abrir:
            with self.assertRaises(ValueError):
                inspeccionar_video(1)
            abrir.assert_not_called()
        corrupto = self.carpeta / "corrupto.avi"
        corrupto.write_text("no es un vídeo")
        with self.assertRaises(ValueError):
            inspeccionar_video(corrupto)

    def test_fotograma_limpio_trazable_zoom_aplicado_una_vez(self):
        valores = {**self.valores, "zoom": 150}
        foto = exportar_fotograma(self.ruta, 4, valores, base=self.base / "capturas")
        original, _ = leer_fotograma(self.ruta, 4)
        imagen = cv2.imread(str(foto))
        np.testing.assert_array_equal(imagen, original)
        self.assertEqual(configuracion_para_imagen(foto), valores)
        trazabilidad = json.loads(foto.with_suffix(".origen.json").read_text())
        self.assertEqual(trazabilidad["indice"], 4)
        self.assertEqual(trazabilidad["huella_video"], inspeccionar_video(self.ruta)["huella"])
        self.assertTrue(foto.name.startswith("fotograma_video_" + trazabilidad["huella_video"]))
        self.assertEqual(len(trazabilidad["huella_imagen"]), 64)
        repetida = exportar_fotograma(self.ruta, 4, valores, base=self.base / "capturas")
        self.assertNotEqual(foto, repetida)

    def test_exportacion_csv_muestra_vacios_y_pistas_recuperadas(self):
        avances = []
        destino = exportar_video(self.ruta, self.valores, salida=self.base / "resultado",
                                  progreso=lambda actual, total: avances.append((actual, total)))
        with (destino / "fotogramas.csv").open(encoding="utf-8-sig") as archivo:
            escenas = list(csv.DictReader(archivo, delimiter=";"))
        with (destino / "caracteristicas.csv").open(encoding="utf-8-sig") as archivo:
            objetos = list(csv.DictReader(archivo, delimiter=";"))
        self.assertEqual(len(escenas), 8)
        self.assertEqual(escenas[3]["objetos"], "0")
        self.assertEqual(len(objetos), 7)
        self.assertEqual(len({o["id_pista"] for o in objetos}), 1)
        self.assertEqual(objetos[3]["estado_pista"], "recuperada")
        self.assertEqual(avances[-1], (8, 8))
        resumen = json.loads((destino / "resumen.json").read_text())
        self.assertTrue(resumen["clasificacion"])
        self.assertFalse(resumen["etiquetas_confirmadas"])
        self.assertFalse(resumen["evaluacion_independiente"])
        self.assertEqual(resumen["version_clasificador"], VERSION_CLASIFICADOR)
        self.assertTrue(resumen["reglas"])
        for objeto in objetos:
            self.assertTrue(set(COLUMNAS_CLASIFICACION).issubset(objeto))
            self.assertEqual(objeto["version_clasificador"], VERSION_CLASIFICADOR)
            self.assertTrue(objeto["clase_predicha"])
            self.assertTrue(objeto["explicacion"])
            self.assertIsInstance(json.loads(objeto["ruta_decision"]), list)
            self.assertNotIn("nombre_real", objeto)
        self.assertEqual(json.loads(escenas[3]["conteo_predicho_json"]), {})
        for escena in escenas:
            self.assertEqual(sum(json.loads(escena["conteo_predicho_json"]).values()), int(escena["objetos"]))
        self.assertEqual(resumen["video"]["huella"], inspeccionar_video(self.ruta)["huella"])
        with self.assertRaisesRegex(ValueError, "ya existe"):
            exportar_video(self.ruta, self.valores, salida=destino)

    def test_intervalo_y_paso_preservan_pistas(self):
        destino = exportar_video(self.ruta, self.valores, salida=self.base / "muestreo", inicio=1, fin=7, paso=3)
        with (destino / "caracteristicas.csv").open(encoding="utf-8-sig") as archivo:
            objetos = list(csv.DictReader(archivo, delimiter=";"))
        self.assertEqual([o["fotograma"] for o in objetos], ["1", "4", "7"])
        self.assertEqual(len({o["id_pista"] for o in objetos}), 1)
        for kwargs in ({"inicio": 4, "fin": 1}, {"paso": 0}, {"fin": 8}):
            with self.assertRaises(ValueError):
                exportar_video(self.ruta, self.valores, salida=self.base / "invalido", **kwargs)
        self.assertFalse((self.base / "invalido").exists())

    def test_error_durante_proceso_no_publica_resultados_incompletos(self):
        destino = self.base / "fallido"
        with patch("video.procesar_imagen", side_effect=ValueError("error intencional")):
            with self.assertRaisesRegex(ValueError, "intencional"):
                exportar_video(self.ruta, self.valores, salida=destino)
        self.assertFalse(destino.exists())
        self.assertFalse(list(self.base.glob(".video_*")))

    def test_conteo_es_del_fotograma_sin_acumular_pistas_y_separa_dudas(self):
        objetos = [{"clase_predicha": "Martillo", "estado_clasificacion": "identificada", "id_pista": 1},
                   {"clase_predicha": "Martillo", "estado_clasificacion": "identificada", "id_pista": 8},
                   {"clase_predicha": "Desconocido", "estado_clasificacion": "ambigua", "id_pista": 9}]
        self.assertEqual(conteo_fotograma(objetos), {"Desconocido": 1, "Martillo": 2})
        self.assertEqual(conteo_fotograma(objetos[1:2]), {"Martillo": 1})
        self.assertEqual(conteo_fotograma([]), {})


if __name__ == "__main__":
    unittest.main()
