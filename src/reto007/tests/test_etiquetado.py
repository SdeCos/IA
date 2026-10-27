"""Pruebas de identidad, revisión manual y reproducción de las sesiones web."""

import csv
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import cv2
import numpy as np

from configuracion import VALORES_PREDETERMINADOS, cargar_configuracion
from catalogo import agregar_clase
from detector import exportar_resultado
from etiquetado import (
    cargar_etiquetas_existentes, exportar_sesion, firma_deteccion, huella_imagen,
)
from vision import procesar_imagen


class SesionesEtiquetadoTest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.base = Path(self.temporal.name).resolve()
        (self.base / "capturas").mkdir()
        # Fondo turquesa H90 y dos herramientas sintéticas muy separadas.
        self.imagen = np.full((500, 800, 3), (180, 180, 0), np.uint8)
        cv2.rectangle(self.imagen, (130, 100), (170, 390), (240, 240, 240), -1)
        cv2.rectangle(self.imagen, (480, 140), (580, 340), (30, 30, 30), -1)
        self.origen = self.base / "capturas" / "escena_prueba.png"
        cv2.imwrite(str(self.origen), self.imagen)
        self.valores = VALORES_PREDETERMINADOS.copy()
        self.resultado = procesar_imagen(self.imagen, self.valores)
        self.assertEqual(len(self.resultado["objetos"]), 2)
        self.nombres = {1: "Destornillador", 2: "Nivel"}

    def exportar(self, revisadas=(1,), valores=None, resultado=None):
        return exportar_sesion(
            resultado or self.resultado, self.origen, self.imagen,
            valores or self.valores, self.nombres, set(revisadas), self.base / "resultados",
        )

    def cargar(self, origen=None, imagen=None, valores=None, resultado=None):
        return cargar_etiquetas_existentes(
            origen or self.origen, self.imagen if imagen is None else imagen,
            valores or self.valores, resultado or self.resultado, self.base,
        )

    def test_paquete_reproduce_pixeles_medidas_y_estados_sin_sobrescribir(self):
        origen_antes = self.origen.read_bytes()
        sesion = self.exportar()
        copia = cv2.imread(str(sesion / "imagen_origen.png"))
        np.testing.assert_array_equal(copia, self.imagen)
        parametros = cargar_configuracion(sesion / "configuracion.json")
        resultado = procesar_imagen(copia, parametros)
        self.assertEqual(firma_deteccion(copia, parametros, resultado),
                         firma_deteccion(self.imagen, self.valores, self.resultado))
        carga = self.cargar()
        self.assertEqual(carga["etiquetas"], self.nombres)
        self.assertEqual(carga["revisadas"], {1})
        self.assertFalse(carga["avisos"])
        copia_cargada = self.cargar(sesion / "imagen_origen.png", copia, parametros, resultado)
        self.assertEqual(copia_cargada["revisadas"], {1})
        with (sesion / "caracteristicas.csv").open(encoding="utf-8-sig", newline="") as archivo:
            filas = list(csv.DictReader(archivo, delimiter=";"))
        self.assertEqual([f["nombre_real"] for f in filas], ["Destornillador", ""])
        self.assertEqual(filas[0]["imagen_origen"], str(sesion / "imagen_origen.png"))
        self.assertAlmostEqual(float(filas[0]["area_px2"]), resultado["objetos"][0]["area_px2"], places=6)
        resumen = json.loads((sesion / "resumen.json").read_text())
        self.assertEqual(resumen["ids_pendientes_revision"], [2])
        self.assertEqual(resumen["imagen_original"], str(self.origen))
        self.assertEqual(self.origen.read_bytes(), origen_antes)
        segunda = self.exportar((1, 2))
        self.assertNotEqual(sesion, segunda)
        self.assertEqual(self.cargar()["revisadas"], {1, 2})
        self.assertEqual(self.cargar(sesion / "imagen_origen.png")["revisadas"], {1})

    def test_otro_parametro_mismo_numero_invalida_todas_las_revisiones(self):
        self.exportar((1, 2))
        valores = {**self.valores, "s_min": self.valores["s_min"] + 1}
        resultado = procesar_imagen(self.imagen, valores)
        self.assertEqual(len(resultado["objetos"]), 2)
        np.testing.assert_array_equal(resultado["mascara"], self.resultado["mascara"])
        carga = self.cargar(valores=valores, resultado=resultado)
        self.assertEqual(carga["etiquetas"], self.nombres)
        self.assertEqual(carga["revisadas"], set())
        self.assertTrue(any("reasignado" in aviso for aviso in carga["avisos"]))

    def test_fuente_distinta_mismo_nombre_no_hereda_nombres(self):
        self.exportar((1, 2))
        distinta = self.imagen.copy()
        distinta[0, 0] = (181, 180, 0)
        self.assertNotEqual(huella_imagen(distinta), huella_imagen(self.imagen))
        resultado = procesar_imagen(distinta, self.valores)
        carga = self.cargar(imagen=distinta, resultado=resultado)
        self.assertEqual(carga["etiquetas"], {})
        self.assertEqual(carga["revisadas"], set())
        self.assertTrue(any("píxeles" in aviso for aviso in carga["avisos"]))
        (self.base / "etiquetas").mkdir()
        (self.base / "etiquetas" / f"{self.origen.stem}.json").write_text(json.dumps(self.nombres))
        subida = self.base / "importadas" / self.origen.name
        carga = self.cargar(subida, distinta, resultado=resultado)
        self.assertEqual(carga["etiquetas"], {})

    def test_legacy_vacio_no_oculta_etiquetas_anteriores_y_no_autoconfirma(self):
        exportar_resultado(self.resultado, self.origen, self.valores,
                           self.base / "resultados" / "primera", self.nombres)
        exportar_resultado(self.resultado, self.origen, self.valores,
                           self.base / "resultados" / "posterior", {})
        carga = self.cargar()
        self.assertEqual(carga["etiquetas"], self.nombres)
        self.assertEqual(carga["revisadas"], set())
        self.assertTrue(any("sin firma" in aviso for aviso in carga["avisos"]))
        # La carga también admite el CSV antiguo si no queda el JSON de nombres.
        (self.base / "resultados" / "primera" / "etiquetas.json").unlink()
        self.assertEqual(self.cargar()["etiquetas"], self.nombres)

    def test_errores_no_publican_paquete_y_etiquetas_corruptas_avisan(self):
        invalidas = ({3: "Nivel"}, {1: "Sin etiquetar"}, {1: "\nNivel"}, {1: 123})
        for nombres in invalidas:
            with self.subTest(nombres=nombres), self.assertRaises(ValueError):
                exportar_sesion(self.resultado, self.origen, self.imagen, self.valores,
                                nombres, set(), self.base / "resultados")
        with self.assertRaises(ValueError):
            exportar_sesion(self.resultado, self.origen, self.imagen, self.valores,
                            {1: ""}, {1}, self.base / "resultados")
        valores = {**self.valores, "zoom": 200}
        with self.assertRaisesRegex(ValueError, "no corresponde"):
            self.exportar(valores=valores)
        self.assertFalse((self.base / "resultados").exists())
        sesion = self.exportar()
        anotaciones = json.loads((sesion / "anotaciones.json").read_text())
        anotaciones["objetos"][0]["nombre"] = "Nivel\x00"
        (sesion / "anotaciones.json").write_text(json.dumps(anotaciones))
        carga = self.cargar()
        self.assertEqual(carga["etiquetas"], {})
        self.assertTrue(any("Nombre no válido" in a for a in carga["avisos"]))

    def test_clases_personalizadas_viajan_con_sesion_sin_catalogo_global(self):
        self.nombres = {1: "  Llave   inglesa  ", 2: "Alicate de presio\u0301n"}
        esperadas = {1: "Llave inglesa", 2: "Alicate de presión"}
        sesion = self.exportar((1,))
        carga = self.cargar()
        self.assertEqual(carga["etiquetas"], esperadas)
        self.assertEqual(carga["revisadas"], {1})
        with (sesion / "caracteristicas.csv").open(encoding="utf-8-sig", newline="") as archivo:
            self.assertEqual([f["nombre_real"] for f in csv.DictReader(archivo, delimiter=";")],
                             ["Llave inglesa", ""])
        otro_equipo = self.base / "otro_equipo"
        copia = otro_equipo / "sesion_copiada"
        shutil.copytree(sesion, copia)
        carga = cargar_etiquetas_existentes(copia / "imagen_origen.png", self.imagen,
                                            self.valores, self.resultado, otro_equipo)
        self.assertEqual(carga["etiquetas"], esperadas)
        self.assertEqual(carga["revisadas"], {1})
        self.assertFalse((otro_equipo / "herramientas.json").exists())
        self.assertFalse(carga["avisos"])

    def test_agregar_clase_no_confirma_propuesta_y_cambio_invalida_revision(self):
        self.nombres = {1: "Llave inglesa", 2: "Alicate"}
        self.exportar((1,))
        agregar_clase("Alicate", self.base)
        self.assertEqual(self.cargar()["revisadas"], {1})
        valores = {**self.valores, "s_min": self.valores["s_min"] + 1}
        resultado = procesar_imagen(self.imagen, valores)
        carga = self.cargar(valores=valores, resultado=resultado)
        self.assertEqual(carga["etiquetas"], self.nombres)
        self.assertEqual(carga["revisadas"], set())
        self.assertTrue(any("reasignado" in a for a in carga["avisos"]))

    def test_ids_desaparecidos_se_descartan_con_aviso_y_sin_revision(self):
        self.exportar((1, 2))
        # El umbral elimina únicamente el rectángulo estrecho.
        valores = {**self.valores, "area_min": 15000}
        resultado = procesar_imagen(self.imagen, valores)
        self.assertEqual(len(resultado["objetos"]), 1)
        carga = self.cargar(valores=valores, resultado=resultado)
        self.assertEqual(carga["etiquetas"], {1: "Destornillador"})
        self.assertEqual(carga["revisadas"], set())
        self.assertTrue(any("ya no existen: 2" in a for a in carga["avisos"]))
        self.assertTrue(any("reasignado" in a for a in carga["avisos"]))


if __name__ == "__main__":
    unittest.main()
