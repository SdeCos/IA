"""Comprobación de la interfaz automática sin alterar capturas ni etiquetas reales."""

import contextlib
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import cv2

import configuracion
from clasificacion import clasificar_objetos
from configuracion import configuracion_para_imagen
from etiquetado import exportar_sesion
from evaluacion import inventario_objetos
from vision import procesar_imagen

try:
    from streamlit.testing.v1 import AppTest
    import panel_clasificacion
except ModuleNotFoundError as error:
    if error.name != "streamlit":
        raise
    AppTest = None

BASE_REAL = Path(__file__).resolve().parents[1]
FOTO_REAL = BASE_REAL / "capturas" / "escena_20261016_113231_782061.png"


@unittest.skipIf(AppTest is None, "Usa .venv-web/bin/python para probar Streamlit")
class ReconocimientoWeb(unittest.TestCase):
    def setUp(self):
        pila = contextlib.ExitStack()
        self.addCleanup(pila.close)
        self.base = Path(pila.enter_context(tempfile.TemporaryDirectory())).resolve()
        (self.base / "capturas").mkdir()
        self.foto = self.base / "capturas" / FOTO_REAL.name
        shutil.copyfile(FOTO_REAL, self.foto)
        self.imagen = cv2.imread(str(self.foto))
        self.valores = configuracion_para_imagen(FOTO_REAL)
        self.resultado = procesar_imagen(self.imagen, self.valores)
        exportar_sesion(self.resultado, self.foto, self.imagen, self.valores,
                        {1: "Destornillador"}, {1}, base_salida=self.base / "resultados")
        pila.enter_context(patch.object(configuracion, "BASE", self.base))
        pila.enter_context(patch.object(configuracion, "RUTA_CONFIGURACION", self.base / "configuracion.json"))
        pila.enter_context(patch.object(cv2, "VideoCapture", side_effect=AssertionError("No se debe abrir una cámara")))
        self.at = AppTest.from_file(str(BASE_REAL / "app_web.py"), default_timeout=60)

    def ejecutar(self):
        self.at.run()
        self.assertFalse(self.at.exception)

    def elemento(self, tipo, nombre):
        elementos = [elemento for elemento in getattr(self.at, tipo) if elemento.label == nombre]
        self.assertEqual(len(elementos), 1, nombre)
        return elementos[0]

    def test_reconocimiento_inventario_y_evaluacion_sin_alterar_referencia(self):
        self.ejecutar()
        sesion = next(iter(self.at.session_state["sesiones_trabajo"].values()))
        antes = deepcopy(sesion)
        archivos_antes = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        self.at.session_state["pestana_principal"] = "Reconocimiento automático"
        self.ejecutar()
        tablas = [d.value for d in self.at.dataframe if "Predicción" in d.value.columns]
        self.assertEqual(len(tablas), 1)
        self.assertEqual(len(tablas[0]), 6)
        self.assertIn("Martillo", tablas[0]["Predicción"].tolist())
        self.assertEqual(sesion, antes)
        self.elemento("checkbox", "Definir cantidades esperadas").check()
        self.ejecutar()
        self.elemento("multiselect", "Herramientas esperadas").set_value(["Martillo"])
        self.ejecutar()
        self.elemento("number_input", "Cantidad esperada · Martillo").set_value(2)
        self.ejecutar()
        inventario = next(d.value for d in self.at.dataframe if "Faltan" in d.value.columns)
        self.assertEqual(inventario.loc[inventario["Herramienta"] == "Martillo", "Faltan"].iloc[0], 1)
        self.elemento("button", "Evaluar sesiones guardadas").click()
        self.ejecutar()
        self.assertEqual(self.elemento("metric", "Objetos evaluados").value, "1")
        self.elemento("radio", "Muestras para comprobar").set_value("Grupos nuevos")
        self.ejecutar()
        self.assertEqual(self.elemento("metric", "Objetos evaluados").value, "0")
        self.assertEqual(self.elemento("metric", "Aciertos sobre el total").value, "Sin datos")
        self.assertTrue(any("prueba independiente" in x.value for x in self.at.info))
        self.assertEqual(sesion, antes)
        self.assertEqual(archivos_antes, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})

    def test_zip_no_contiene_etiquetas_confirmadas_y_conserva_imagen_original(self):
        objetos = clasificar_objetos(self.resultado["objetos"])
        sesion = {"valores": self.valores, "etiquetas": {1: "Otra etiqueta"}, "revisadas": {1}}
        antes = deepcopy(sesion)
        datos = panel_clasificacion.paquete_reconocimiento(self.resultado, objetos, sesion,
                                                           self.foto, self.imagen, inventario_objetos(objetos))
        with zipfile.ZipFile(BytesIO(datos)) as archivo:
            self.assertNotIn("etiquetas.json", archivo.namelist())
            self.assertIn("reglas.json", archivo.namelist())
            informe = json.loads(archivo.read("predicciones.json"))
            self.assertFalse(informe["etiquetas_confirmadas_por_esta_operacion"])
            self.assertTrue(all("nombre_real" not in p for p in informe["predicciones"]))
            self.assertEqual(len(informe["predicciones"]), 6)
            import numpy as np
            original = cv2.imdecode(np.frombuffer(archivo.read("imagen_origen.png"), np.uint8), cv2.IMREAD_COLOR)
            np.testing.assert_array_equal(self.imagen, original)
        self.assertEqual(sesion, antes)

    def test_servidor_con_modulos_video_antiguos_recarga_sin_perder_etiquetas(self):
        import actualizacion
        import panel_video
        import video
        self.ejecutar()
        sesion = next(iter(self.at.session_state["sesiones_trabajo"].values()))
        antes = deepcopy(sesion)
        modulos = [(m, m.__dict__.copy()) for m in (actualizacion, video, panel_video)]
        try:
            actualizacion.VERSION_ACTUALIZACION = 1
            video.VERSION_VIDEO = 1
            panel_video.VERSION_PANEL_VIDEO = 1
            self.ejecutar()
            self.assertEqual(actualizacion.VERSION_ACTUALIZACION, 4)
            self.assertEqual(video.VERSION_VIDEO, 2)
            self.assertEqual(panel_video.VERSION_PANEL_VIDEO, 4)
            self.assertIs(panel_video.exportar_video, video.exportar_video)
            self.assertEqual(sesion, antes)
        finally:
            for modulo, original in modulos:
                modulo.__dict__.clear()
                modulo.__dict__.update(original)


if __name__ == "__main__":
    unittest.main()
