"""Pruebas de la mesa web: no abren navegador, ventanas ni cámaras.

Las sesiones se guardan únicamente en una carpeta temporal. Ejecutar con el
Python de .venv-web para incluir las pruebas de interacción de Streamlit.
"""

import contextlib
import csv
from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

import configuracion
from vision import procesar_imagen
from geometria import METRICAS_GEOMETRICAS, VERSION_CARACTERISTICAS

try:
    from streamlit.testing.v1 import AppTest
    import app_web
    import panel_analisis
except ModuleNotFoundError as error:
    if error.name != "streamlit":
        raise
    AppTest = None


BASE_REAL = Path(__file__).resolve().parents[1]
FOTO_REAL = BASE_REAL / "capturas" / "escena_20261016_113231_782061.png"
NOMBRES = {
    "1": "Destornillador", "2": "Calibre", "3": "Desbarbador manual",
    "4": "Martillo", "5": "Juego de llaves Allen", "6": "Nivel",
}


@unittest.skipIf(AppTest is None, "Streamlit no está instalado: usa .venv-web/bin/python")
class MesaWeb(unittest.TestCase):
    def setUp(self):
        self.pila = contextlib.ExitStack()
        self.addCleanup(self.pila.close)
        self.base = Path(self.pila.enter_context(tempfile.TemporaryDirectory())).resolve()
        (self.base / "capturas").mkdir()
        (self.base / "etiquetas").mkdir()
        self.foto = self.base / "capturas" / "escena_z.png"
        shutil.copyfile(FOTO_REAL, self.foto)
        (self.base / "etiquetas" / "escena_z.json").write_text(
            json.dumps(NOMBRES, ensure_ascii=False), encoding="utf-8"
        )
        self.otra = self.base / "capturas" / "escena_a.png"
        sintetica = np.full((800, 800, 3), (100, 150, 0), np.uint8)
        cv2.rectangle(sintetica, (200, 150), (280, 350), (255, 255, 255), -1)
        self.assertTrue(cv2.imwrite(str(self.otra), sintetica))
        self.pila.enter_context(patch.object(configuracion, "BASE", self.base))
        self.pila.enter_context(patch.object(configuracion, "RUTA_CONFIGURACION", self.base / "configuracion.json"))
        self.pila.enter_context(patch.object(cv2, "VideoCapture", side_effect=AssertionError("La web abrió una cámara")))
        self.at = AppTest.from_file(str(BASE_REAL / "app_web.py"), default_timeout=60)

    def ejecutar(self):
        self.at.run()
        self.assertEqual(list(self.at.exception), [])
        return self.at

    def elemento(self, grupo, etiqueta):
        encontrados = [x for x in getattr(self.at, grupo) if x.label == etiqueta]
        self.assertEqual(len(encontrados), 1, etiqueta)
        return encontrados[0]

    def pulsar(self, etiqueta):
        self.elemento("button", etiqueta).click()
        return self.ejecutar()

    def sesion(self, foto=None):
        fuente = str(foto or self.foto)
        return next(s for token, s in self.at.session_state["sesiones_trabajo"].items() if token.endswith("_" + fuente))

    def test_propuestas_legacy_confirmacion_y_foto_aislada(self):
        self.ejecutar()
        self.assertEqual(self.elemento("metric", "Objetos detectados").value, "6")
        self.assertEqual(self.elemento("metric", "Etiquetas confirmadas").value, "0 / 6")
        self.assertEqual(self.sesion()["revisadas"], set())
        self.assertEqual(self.elemento("selectbox", "Herramienta real").value, "Destornillador")
        self.assertTrue(self.at.warning)

        self.pulsar("Confirmar y siguiente")
        self.assertEqual(self.sesion()["revisadas"], {1})
        self.assertEqual(self.elemento("selectbox", "Objeto para revisar").value, 2)
        self.assertEqual(self.elemento("selectbox", "Herramienta real").value, "Calibre")

        self.elemento("selectbox", "Foto guardada").set_value(self.otra)
        self.ejecutar()
        self.assertEqual(self.elemento("metric", "Objetos detectados").value, "1")
        self.assertEqual(self.elemento("selectbox", "Herramienta real").value, "Sin etiquetar")
        self.assertEqual(self.sesion(self.otra)["revisadas"], set())
        self.elemento("selectbox", "Herramienta real").set_value("Martillo")
        self.pulsar("Confirmar y siguiente")
        self.assertEqual(self.sesion(self.otra)["etiquetas"], {1: "Martillo"})

        self.elemento("selectbox", "Foto guardada").set_value(self.foto)
        self.ejecutar()
        self.assertEqual(self.sesion()["revisadas"], {1})
        self.assertEqual(self.sesion()["etiquetas"][1], "Destornillador")
        self.assertEqual(self.elemento("metric", "Etiquetas confirmadas").value, "1 / 6")

    def test_herramienta_nueva_se_conserva_en_catalogo_sesion_csv_y_analisis(self):
        from catalogo import cargar_clases
        self.ejecutar()
        self.pulsar("Confirmar y siguiente")
        self.elemento("text_input", "Nombre de la nueva herramienta").set_value("  Alicates   de corte  ")
        self.pulsar("Añadir y seleccionar")
        self.assertFalse(self.at.error)
        self.assertEqual(self.elemento("selectbox", "Objeto para revisar").value, 2)
        self.assertEqual(self.elemento("selectbox", "Herramienta real").value, "Alicates de corte")
        self.assertEqual(self.sesion()["etiquetas"][2], "Alicates de corte")
        self.assertEqual(self.sesion()["revisadas"], {1})
        self.assertIn("Alicates de corte", cargar_clases(self.base))
        self.pulsar("Confirmar y siguiente")
        self.assertEqual(self.sesion()["revisadas"], {1, 2})
        self.pulsar("Guardar sesión y CSV")
        self.assertFalse(self.at.error)
        destino = Path(self.sesion()["guardado"])
        with (destino / "caracteristicas.csv").open(encoding="utf-8-sig", newline="") as archivo:
            filas = list(csv.DictReader(archivo, delimiter=";"))
        self.assertEqual(filas[1]["nombre_real"], "Alicates de corte")

        self.at = AppTest.from_file(str(BASE_REAL / "app_web.py"), default_timeout=60)
        self.ejecutar()
        self.elemento("selectbox", "Foto guardada").set_value(self.otra)
        self.ejecutar()
        self.assertIn("Alicates de corte", self.elemento("selectbox", "Herramienta real").options)
        self.assertEqual(self.sesion(self.otra)["revisadas"], set())

        # Una sesión sigue siendo portable aunque no se traslade el catálogo.
        (self.base / "herramientas.json").unlink()
        self.elemento("radio", "Origen de la foto").set_value("Sesiones guardadas")
        self.ejecutar()
        self.elemento("selectbox", "Objeto para revisar").set_value(2)
        self.ejecutar()
        recuperada = self.sesion(destino / "imagen_origen.png")
        self.assertEqual(recuperada["revisadas"], {1, 2})
        self.assertEqual(self.elemento("selectbox", "Herramienta real").value, "Alicates de corte")
        self.at.session_state["pestana_principal"] = "Análisis"
        self.ejecutar()
        self.assertIn("Alicates de corte", self.elemento("multiselect", "Herramientas a comparar").options)
        self.assertEqual(self.elemento("metric", "Clases representadas").value, "2")
        self.assertEqual(len(self.at.get("vega_lite_chart")), 2)

    def test_nombre_vacio_o_reservado_no_cambia_etiqueta_y_duplicados_se_reutilizan(self):
        from catalogo import cargar_clases
        self.ejecutar()
        antes = self.sesion()["etiquetas"].copy()
        for nombre in ("   ", "Sin etiquetar"):
            self.elemento("text_input", "Nombre de la nueva herramienta").set_value(nombre)
            self.pulsar("Añadir y seleccionar")
            self.assertTrue(self.at.error)
            self.assertEqual(self.sesion()["etiquetas"], antes)
            self.assertFalse((self.base / "herramientas.json").exists())
        for nombre in ("Alicates", "  ALICATES  "):
            self.elemento("text_input", "Nombre de la nueva herramienta").set_value(nombre)
            self.pulsar("Añadir y seleccionar")
            self.assertFalse(self.at.error)
            self.assertEqual(self.elemento("selectbox", "Herramienta real").value, "Alicates")
        self.assertEqual(cargar_clases(self.base).count("Alicates"), 1)
        self.assertEqual(self.sesion()["revisadas"], set())
        self.elemento("selectbox", "Herramienta real").set_value(None)
        self.pulsar("Dejar pendiente")
        self.assertEqual(self.sesion()["etiquetas"][1], "")
        self.pulsar("Guardar sesión y CSV")
        self.assertFalse(self.at.error)

    def test_recarga_modulo_antiguo_guarda_nueva_clase_sin_perder_trabajo(self):
        import analisis
        import etiquetado

        self.ejecutar()
        self.pulsar("Confirmar y siguiente")
        self.elemento("text_input", "Nombre de la nueva herramienta").set_value("Metro")
        self.pulsar("Añadir y seleccionar")
        self.pulsar("Confirmar y siguiente")
        sesion = self.sesion()
        self.assertEqual(sesion["revisadas"], {1, 2})
        self.assertIsNone(sesion["guardado"])
        self.assertTrue(sesion["modificada"])
        antes = {
            "etiquetas": sesion["etiquetas"].copy(),
            "revisadas": sesion["revisadas"].copy(),
            "firma": sesion["firma"],
            "revision": sesion["revision"],
        }
        seleccionado = self.elemento("selectbox", "Objeto para revisar").value
        aplicacion = self.at
        llamadas_antiguas = []

        def nombres_antiguos(etiquetas, objetos):
            llamadas_antiguas.append(etiquetas)
            raise ValueError("Nombre no reconocido para el objeto 2: 'Metro'.")

        # reload modifica el diccionario del módulo, incluidos valores por
        # defecto tomados de configuracion.BASE. Restaurar los diccionarios
        # originales evita dejar rutas temporales o funciones viejas a otros tests.
        modulos = (etiquetado, analisis, panel_analisis)
        originales = [(modulo, modulo.__dict__.copy()) for modulo in modulos]
        try:
            etiquetado.VERSION_ETIQUETADO = 1
            etiquetado._nombres_validos = nombres_antiguos
            analisis._nombres_validos = nombres_antiguos
            self.pulsar("Guardar sesión y CSV")
            self.assertIs(self.at, aplicacion)
            self.assertIs(self.sesion(), sesion)
            self.assertFalse(self.at.error)
            self.assertEqual(llamadas_antiguas, [])
            self.assertEqual(etiquetado.VERSION_ETIQUETADO, 2)
            self.assertIs(analisis._nombres_validos, etiquetado._nombres_validos)
            self.assertIs(panel_analisis.reunir_datos, analisis.reunir_datos)
            for clave, valor in antes.items():
                self.assertEqual(sesion[clave], valor, clave)
            self.assertEqual(self.elemento("selectbox", "Objeto para revisar").value,
                             seleccionado)
            self.assertFalse(sesion["modificada"])
            destino = Path(sesion["guardado"])
            self.assertTrue(destino.is_relative_to(self.base / "resultados"))
            with (destino / "caracteristicas.csv").open(encoding="utf-8-sig", newline="") as archivo:
                filas = list(csv.DictReader(archivo, delimiter=";"))
            self.assertEqual([f["nombre_real"] for f in filas],
                             ["Destornillador", "Metro", "", "", "", ""])
            nombres = json.loads((destino / "etiquetas.json").read_text(encoding="utf-8"))
            self.assertEqual(nombres, {"1": "Destornillador", "2": "Metro",
                                      "3": "", "4": "", "5": "", "6": ""})
            anotaciones = json.loads((destino / "anotaciones.json").read_text(encoding="utf-8"))
            self.assertEqual(anotaciones["firma_deteccion"], antes["firma"])
            self.assertEqual({o["id"] for o in anotaciones["objetos"] if o["revisada"]},
                             antes["revisadas"])
            self.at.session_state["pestana_principal"] = "Análisis"
            self.ejecutar()
            self.assertIn("Metro", self.elemento("multiselect", "Herramientas a comparar").options)
        finally:
            for modulo, original in originales:
                modulo.__dict__.clear()
                modulo.__dict__.update(original)

    def test_ajustes_se_aplican_explicitamente_e_invalidan_con_mismo_recuento(self):
        self.ejecutar()
        self.pulsar("Confirmar y siguiente")
        anterior = self.sesion()["firma"]
        self.elemento("number_input", "Área mínima · px²").set_value(1010)
        # Un campo de formulario queda en el navegador hasta pulsar Aplicar.
        self.assertEqual(self.sesion()["valores"]["area_min"], 1000)
        self.assertEqual(self.sesion()["revisadas"], {1})
        self.pulsar("Aplicar ajustes")
        self.assertEqual(self.elemento("metric", "Objetos detectados").value, "6")
        self.assertEqual(self.sesion()["valores"]["area_min"], 1010)
        self.assertNotEqual(self.sesion()["firma"], anterior)
        self.assertEqual(self.sesion()["revisadas"], set())
        self.assertEqual(self.sesion()["etiquetas"][1], "Destornillador")
        self.assertTrue(self.at.warning)

        self.pulsar("Confirmar y siguiente")
        firma = self.sesion()["firma"]
        revisadas = self.sesion()["revisadas"].copy()
        self.elemento("number_input", "Tono · H mín.").set_value(110)
        self.pulsar("Aplicar ajustes")
        self.assertTrue(self.at.error)
        self.assertEqual(self.sesion()["valores"]["h_min"], 80)
        self.assertEqual(self.sesion()["firma"], firma)
        self.assertEqual(self.sesion()["revisadas"], revisadas)

    def test_guardar_borrador_y_reabrir_recupera_confirmadas_y_propuestas(self):
        self.ejecutar()
        self.pulsar("Confirmar y siguiente")
        self.pulsar("Guardar sesión y CSV")
        self.assertFalse(self.at.error)
        destino = Path(self.sesion()["guardado"])
        self.assertTrue(destino.is_relative_to(self.base / "resultados"))
        for nombre in ("imagen_origen.png", "objetos.png", "mascara.png", "configuracion.json", "etiquetas.json", "anotaciones.json", "caracteristicas.csv", "resumen.json", "perfiles.json"):
            self.assertTrue((destino / nombre).is_file(), nombre)
        with (destino / "caracteristicas.csv").open(encoding="utf-8-sig", newline="") as archivo:
            filas = list(csv.DictReader(archivo, delimiter=";"))
        self.assertEqual(len(filas), 6)
        self.assertEqual(filas[0]["nombre_real"], "Destornillador")
        self.assertTrue(all(f["nombre_real"] == "" for f in filas[1:]))
        resultado = procesar_imagen(cv2.imread(str(self.foto)), self.sesion()["valores"])
        for fila, objeto in zip(filas, resultado["objetos"]):
            for medida in METRICAS_GEOMETRICAS:
                self.assertAlmostEqual(float(fila[medida]), objeto[medida], places=6)
        perfiles = json.loads((destino / "perfiles.json").read_text())
        self.assertEqual(perfiles["version_caracteristicas"], VERSION_CARACTERISTICAS)
        self.assertEqual(len(perfiles["objetos"]), 6)
        for perfil, objeto in zip(perfiles["objetos"], resultado["objetos"]):
            self.assertEqual(perfil["id"], objeto["id"])
            self.assertEqual(len(perfil["posiciones"]), 40)
            np.testing.assert_allclose(perfil["posiciones"], objeto["perfil_posiciones"])
            np.testing.assert_allclose(perfil["anchuras"], objeto["perfil_ancho"])
            self.assertEqual(perfil["nombre_real"], "Destornillador" if objeto["id"] == 1 else "")

        # Un navegador nuevo debe recuperar lo persistido, no memoria residual.
        self.at = AppTest.from_file(str(BASE_REAL / "app_web.py"), default_timeout=60)
        self.ejecutar()
        self.elemento("radio", "Origen de la foto").set_value("Sesiones guardadas")
        self.ejecutar()
        recuperada = self.sesion(destino / "imagen_origen.png")
        self.assertEqual(recuperada["revisadas"], {1})
        self.assertEqual(recuperada["etiquetas"][2], "Calibre")
        self.assertEqual(self.elemento("metric", "Etiquetas confirmadas").value, "1 / 6")
        np.testing.assert_array_equal(cv2.imread(str(destino / "imagen_origen.png")), cv2.imread(str(self.foto)))
        self.at.session_state["pestana_principal"] = "Análisis"
        self.ejecutar()
        self.assertEqual(self.elemento("metric", "Objetos de referencia").value, "1")
        self.assertEqual(self.elemento("metric", "Fotos distintas").value, "1")
        self.assertEqual(len(self.at.get("vega_lite_chart")), 2)

    def test_analisis_vacio_incluye_confirmacion_actual_sin_guardar(self):
        self.ejecutar()
        self.at.session_state["pestana_principal"] = "Análisis"
        self.ejecutar()
        self.assertEqual(self.elemento("metric", "Objetos de referencia").value, "0")
        self.assertTrue(any("Todavía no hay etiquetas confirmadas" in x.value for x in self.at.info))
        self.assertEqual(len(self.at.get("vega_lite_chart")), 0)
        self.pulsar("Confirmar y siguiente")
        self.assertEqual(self.elemento("metric", "Objetos de referencia").value, "1")
        self.assertEqual(self.elemento("metric", "Clases representadas").value, "1")
        self.assertEqual(self.elemento("metric", "Capturas agrupadas").value, "1")
        individuales = next(x.value for x in self.at.dataframe if "nombre_real" in x.value.columns)
        self.assertEqual(individuales["nombre_real"].tolist(), ["Destornillador"])
        self.assertTrue(individuales["actual"].all())
        self.assertTrue(set(METRICAS_GEOMETRICAS) <= set(individuales.columns))
        self.assertEqual(len(self.at.get("vega_lite_chart")), 2)
        self.assertFalse((self.base / "resultados").exists())

        self.elemento("checkbox", "Incluir etiquetas confirmadas de la foto abierta").set_value(False)
        self.ejecutar()
        self.assertEqual(self.elemento("metric", "Objetos de referencia").value, "0")
        self.assertEqual(self.sesion()["revisadas"], {1})
        self.assertEqual(len(self.at.get("vega_lite_chart")), 0)

    def test_analisis_filtra_graficos_y_descarga_medidas_con_procedencia(self):
        self.ejecutar()
        for _ in range(6):
            self.pulsar("Confirmar y siguiente")
        self.at.session_state["pestana_principal"] = "Análisis"
        self.ejecutar()
        self.assertEqual(self.elemento("multiselect", "Herramientas a comparar").value,
                         ["Calibre", "Martillo"])
        graficos = self.at.get("vega_lite_chart")
        self.assertEqual(len(graficos), 2)
        dispersion = json.loads(graficos[0].proto.spec)
        self.assertEqual(dispersion["encoding"]["x"]["field"], "relacion_aspecto")
        self.assertEqual(dispersion["encoding"]["y"]["field"], "ancho_central")
        perfil = json.loads(graficos[1].proto.spec)
        self.assertEqual(perfil["encoding"]["detail"]["field"], "serie")
        self.assertEqual(perfil["encoding"]["y"]["scale"]["domain"], [0, 1])

        # AppTest no descarga archivos: capturamos los bytes reales enviados al
        # botón, sin sustituir el exportador ni cambiar el resultado del render.
        descargas = []
        exportar_csv = panel_analisis.csv_analisis

        def observar_descarga(filas):
            contenido = exportar_csv(filas)
            descargas.append(contenido)
            return contenido

        self.elemento("multiselect", "Herramientas a comparar").set_value(["Nivel"])
        self.elemento("selectbox", "Medida horizontal").set_value("extension")
        self.elemento("selectbox", "Medida vertical").set_value("contraste_extremos")
        with patch.object(panel_analisis, "csv_analisis", side_effect=observar_descarga):
            self.ejecutar()
        self.assertEqual(len(descargas), 1)
        self.assertTrue(descargas[0].startswith(b"\xef\xbb\xbf"))
        filas = list(csv.DictReader(StringIO(descargas[0].decode("utf-8-sig")), delimiter=";"))
        self.assertEqual([f["nombre_real"] for f in filas], ["Nivel"])
        fila = filas[0]
        self.assertEqual(fila["fuente"], str(self.foto))
        self.assertEqual(fila["sesion"], "Sesión actual")
        self.assertEqual(fila["version_caracteristicas"], VERSION_CARACTERISTICAS)
        self.assertEqual(fila["firma_deteccion"], self.sesion()["firma"])
        self.assertTrue(fila["captura"])
        resultado = procesar_imagen(cv2.imread(str(self.foto)), self.sesion()["valores"])
        objeto = resultado["objetos"][5]
        for medida in METRICAS_GEOMETRICAS:
            self.assertAlmostEqual(float(fila[medida]), objeto[medida], places=6)
        np.testing.assert_allclose(json.loads(fila["perfil_ancho"]), objeto["perfil_ancho"])
        np.testing.assert_allclose(json.loads(fila["perfil_posiciones"]), objeto["perfil_posiciones"])
        self.assertEqual(len(json.loads(fila["perfil_ancho"])), 40)
        self.assertTrue(any(x.proto.label == "Descargar comparación · CSV"
                            for x in self.at.get("download_button")))
        rangos = next(x.value for x in self.at.dataframe if "Herramienta" in x.value.columns)
        self.assertEqual(rangos["Herramienta"].tolist(), ["Nivel"])
        self.assertEqual(rangos["Capturas"].tolist(), [1])
        dispersion = json.loads(self.at.get("vega_lite_chart")[0].proto.spec)
        self.assertEqual(dispersion["encoding"]["x"]["field"], "extension")
        self.assertEqual(dispersion["encoding"]["y"]["field"], "contraste_extremos")

        self.elemento("selectbox", "Medida horizontal").set_value("area_px2")
        self.ejecutar()
        self.assertTrue(any("Estás comparando píxeles" in x.value for x in self.at.warning))
        self.elemento("multiselect", "Herramientas a comparar").set_value([])
        self.ejecutar()
        self.assertEqual(len(self.at.get("vega_lite_chart")), 0)
        self.assertTrue(any("Selecciona al menos una herramienta" in x.value for x in self.at.info))

    def test_resaltado_no_modifica_fuente_mascara_ni_contornos(self):
        imagen = cv2.imread(str(self.foto))
        resultado = procesar_imagen(imagen, configuracion.VALORES_PREDETERMINADOS)
        antes = {clave: resultado[clave].copy() for clave in ("imagen", "mascara")}
        contornos = [o["contorno"].copy() for o in resultado["objetos"]]
        base = app_web.vista_resaltada(resultado)
        primera = app_web.vista_resaltada(resultado, 1)
        segunda = app_web.vista_resaltada(resultado, 2)
        self.assertFalse(np.array_equal(base, primera))
        self.assertFalse(np.array_equal(primera, segunda))
        for clave, copia in antes.items():
            np.testing.assert_array_equal(resultado[clave], copia)
        for objeto, copia in zip(resultado["objetos"], contornos):
            np.testing.assert_array_equal(objeto["contorno"], copia)

    def test_sesion_abierta_anterior_al_tapete_se_migra_sin_pulsar_aplicar(self):
        # Simula la foto amplia que antes solo producía el contorno exterior.
        shutil.copyfile(BASE_REAL / "capturas" / "escena_20261016_113207_730520.png", self.otra)
        self.ejecutar()
        self.elemento("selectbox", "Foto guardada").set_value(self.otra)
        self.ejecutar()
        sesion = self.sesion(self.otra)
        sesion["valores"].pop("limitar_tapete", None)
        sesion["valores"].pop("margen_tapete", None)
        sesion["firma"] = "0" * 64  # Firma persistida por el procesamiento previo.
        sesion["etiquetas"] = {1: "Nivel"}
        sesion["revisadas"] = {1}
        revision = sesion["revision"]
        self.ejecutar()
        self.assertEqual(self.elemento("metric", "Objetos detectados").value, "6")
        self.assertEqual(self.elemento("metric", "Etiquetas confirmadas").value, "0 / 6")
        self.assertEqual(sesion["valores"]["limitar_tapete"], 1)
        self.assertEqual(sesion["valores"]["margen_tapete"], 2)
        self.assertEqual(sesion["revisadas"], set())
        self.assertEqual(sesion["etiquetas"][1], "Nivel")
        self.assertGreater(sesion["revision"], revision)
        self.assertTrue(self.at.warning)

    def test_sin_tapete_muestra_aviso_y_no_ofrece_objeto_exterior(self):
        imagen = np.full((600, 800, 3), (90, 90, 90), np.uint8)
        cv2.rectangle(imagen, (200, 100), (300, 400), (240, 240, 240), -1)
        self.assertTrue(cv2.imwrite(str(self.otra), imagen))
        self.ejecutar()
        self.elemento("selectbox", "Foto guardada").set_value(self.otra)
        self.ejecutar()
        self.assertEqual(self.elemento("metric", "Objetos detectados").value, "0")
        self.assertFalse([x for x in self.at.selectbox if x.label == "Objeto para revisar"])
        self.assertTrue(any("tapete" in aviso.value.lower() for aviso in self.at.warning))


if __name__ == "__main__":
    unittest.main()
