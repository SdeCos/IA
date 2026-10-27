"""Interacciones Streamlit con vídeos sintéticos y todas las salidas temporales."""

import contextlib
import csv
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cv2
import numpy as np

import configuracion
from configuracion import VALORES_PREDETERMINADOS, cargar_configuracion, guardar_configuracion
import video

try:
    from streamlit.testing.v1 import AppTest
    import panel_video
except ModuleNotFoundError as error:
    if error.name != "streamlit":
        raise
    AppTest = None


BASE_REAL = Path(__file__).resolve().parents[1]


@unittest.skipIf(AppTest is None, "Streamlit no está instalado: usa .venv-web/bin/python")
class LaboratorioVideo(unittest.TestCase):
    def setUp(self):
        self.pila = contextlib.ExitStack()
        self.addCleanup(self.pila.close)
        self.base = Path(self.pila.enter_context(tempfile.TemporaryDirectory())).resolve()
        carpeta = self.base / "videos" / "grabacion_prueba"
        carpeta.mkdir(parents=True)
        self.ruta = carpeta / "original.avi"
        writer = cv2.VideoWriter(str(self.ruta), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (320, 240))
        self.assertTrue(writer.isOpened())
        try:
            for indice in range(8):
                frame = np.full((240, 320, 3), (100, 150, 0), np.uint8)
                cv2.rectangle(frame, (70 + indice * 2, 60), (100 + indice * 2, 175), (255, 255, 255), -1)
                writer.write(frame)
        finally:
            writer.release()
        guardar_configuracion(VALORES_PREDETERMINADOS, carpeta / "configuracion.json")
        self.huella = video.inspeccionar_video(self.ruta)["huella"]
        self.pila.enter_context(patch.object(configuracion, "BASE", self.base))
        self.pila.enter_context(patch.object(configuracion, "RUTA_CONFIGURACION", self.base / "configuracion.json"))
        # Segunda barrera: ningún cambio en los defaults de exportación puede
        # escribir resultados dentro del proyecto durante estas pruebas.
        self.pila.enter_context(patch.object(video, "BASE", self.base))
        captura_real = cv2.VideoCapture
        def solo_archivos(origen=None, *args, **kwargs):
            if not isinstance(origen, (str, Path)):
                raise AssertionError("La interfaz web intentó abrir una cámara.")
            return captura_real(str(origen), *args, **kwargs)
        self.pila.enter_context(patch.object(cv2, "VideoCapture", side_effect=solo_archivos))
        self.reloj = 100.0
        self.pila.enter_context(patch.object(panel_video, "time", SimpleNamespace(monotonic=lambda: self.reloj)))
        self.navegador_nuevo()

    def navegador_nuevo(self):
        self.at = AppTest.from_file(str(BASE_REAL / "app_web.py"), default_timeout=60)
        self.at.session_state["modo_trabajo"] = "Vídeos"

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

    def sesion(self):
        return self.at.session_state["sesiones_video"]["video_" + self.huella]

    def test_video_sin_fotos_navegacion_numerica_y_mascara(self):
        self.assertFalse((self.base / "capturas").exists())
        self.ejecutar()
        self.assertFalse(self.at.error)
        self.assertEqual(self.elemento("metric", "Objetos en el fotograma").value, "1")
        self.assertEqual(self.elemento("metric", "Tiempo del vídeo").value, "0.00 s")
        resultado = self.sesion()["resultado"]
        objeto = self.sesion()["objetos"][0]
        self.assertIn("clase_predicha", objeto)
        self.assertIn("explicacion", objeto)
        self.assertNotIn("nombre_real", objeto)
        self.assertTrue(any("reglas manuales" in c.value for c in self.at.caption))
        predicciones = [tabla.value for tabla in self.at.dataframe if "Por qué" in tabla.value.columns]
        self.assertEqual(len(predicciones), 1)
        self.assertEqual(predicciones[0].iloc[0]["Predicción"], objeto["clase_predicha"])
        self.assertEqual(set(np.unique(resultado["mascara"])), {0, 255})
        self.assertEqual(resultado["imagen"].shape[:2], resultado["mascara"].shape)
        self.pulsar("Siguiente")
        self.assertEqual(self.sesion()["indice"], 1)
        self.assertEqual(self.sesion()["objetos"][0]["estado_pista"], "continua")
        self.ejecutar()  # Un rerun del mismo fotograma no reinicia sus pistas.
        self.assertEqual(self.sesion()["objetos"][0]["estado_pista"], "continua")
        self.pulsar("Anterior")
        self.assertEqual(self.sesion()["indice"], 0)
        self.assertEqual(self.sesion()["objetos"][0]["estado_pista"], "nueva")
        self.elemento("number_input", "Fotograma · empieza en 0").set_value(5)
        self.ejecutar()
        self.assertEqual(self.sesion()["indice"], 5)
        self.assertEqual(self.elemento("metric", "Tiempo del vídeo").value, "0.50 s")
        self.assertEqual(self.sesion()["objetos"][0]["estado_pista"], "nueva")
        self.elemento("slider", "Línea de tiempo · fotograma").set_value(3)
        self.ejecutar()
        self.assertEqual(self.sesion()["indice"], 3)

    def test_ajustes_reinician_seguimiento_y_se_recuperan_por_huella(self):
        self.ejecutar()
        self.pulsar("Siguiente")
        self.assertEqual(self.sesion()["objetos"][0]["estado_pista"], "continua")
        self.elemento("number_input", "Área mínima · px²").set_value(1100)
        self.pulsar("Aplicar ajustes")
        self.assertEqual(self.sesion()["valores"]["area_min"], 1100)
        self.assertEqual(self.sesion()["objetos"][0]["estado_pista"], "nueva")
        self.assertFalse(self.sesion()["reproduciendo"])
        self.assertTrue(self.sesion()["modificada"])
        self.pulsar("Guardar ajustes del vídeo")
        destino = self.base / "videos" / "ajustes" / f"{self.huella}.json"
        self.assertEqual(cargar_configuracion(destino)["area_min"], 1100)
        self.assertFalse(self.sesion()["modificada"])
        self.navegador_nuevo()
        self.ejecutar()
        self.assertEqual(self.sesion()["valores"]["area_min"], 1100)
        self.elemento("number_input", "Tono · H mín.").set_value(110)
        self.pulsar("Aplicar ajustes")
        self.assertTrue(self.at.error)
        self.assertEqual(self.sesion()["valores"]["h_min"], 80)

    def test_extraer_fotograma_y_abrir_foto_no_inventa_etiquetas(self):
        self.ejecutar()
        self.elemento("number_input", "Fotograma · empieza en 0").set_value(2)
        self.ejecutar()
        self.pulsar("Guardar fotograma como foto")
        foto = Path(self.sesion()["foto_guardada"])
        self.assertTrue(foto.is_relative_to(self.base / "capturas"))
        self.assertEqual(cv2.imread(str(foto)).shape, (240, 320, 3))
        self.assertTrue(foto.with_suffix(".json").is_file())
        self.assertTrue(foto.with_suffix(".origen.json").is_file())
        self.pulsar("Abrir foto guardada para etiquetar")
        self.assertEqual(self.elemento("radio", "Modo de trabajo").value, "Fotografías")
        self.assertEqual(self.elemento("selectbox", "Foto guardada").value, foto)
        self.assertEqual(self.elemento("selectbox", "Herramienta real").value, "Sin etiquetar")
        sesion_foto = next(iter(self.at.session_state["sesiones_trabajo"].values()))
        self.assertEqual(sesion_foto["revisadas"], set())
        self.assertTrue(all(not etiqueta for etiqueta in sesion_foto["etiquetas"].values()))

    def test_exportar_intervalo_csv_y_rechazar_intervalo_invertido(self):
        self.ejecutar()
        self.elemento("number_input", "Desde fotograma").set_value(1)
        self.elemento("number_input", "Hasta fotograma · incluido").set_value(5)
        self.elemento("number_input", "Guardar una fila de fotograma cada…").set_value(2)
        self.pulsar("Exportar intervalo a CSV")
        self.assertFalse(self.at.error)
        carpeta = Path(self.sesion()["exportacion"])
        self.assertTrue(carpeta.is_relative_to(self.base / "resultados" / "videos"))
        with (carpeta / "fotogramas.csv").open(encoding="utf-8-sig", newline="") as archivo:
            filas = list(csv.DictReader(archivo, delimiter=";"))
        self.assertEqual([int(f["fotograma"]) for f in filas], [1, 3, 5])
        self.assertEqual([float(f["tiempo_s"]) for f in filas], [.1, .3, .5])
        with (carpeta / "caracteristicas.csv").open(encoding="utf-8-sig", newline="") as archivo:
            objetos = list(csv.DictReader(archivo, delimiter=";"))
        self.assertEqual(len(objetos), 3)
        self.assertEqual({f["id_pista"] for f in objetos}, {"1"})
        self.assertNotIn("nombre_real", objetos[0])
        resumen = json.loads((carpeta / "resumen.json").read_text())
        self.assertEqual(resumen["fotogramas_procesados"], 5)
        self.assertTrue(resumen["clasificacion"])
        self.assertFalse(resumen["etiquetas_confirmadas"])
        self.assertIn("version_clasificador", resumen)
        self.assertTrue(all(objeto["explicacion"] for objeto in objetos))
        self.assertTrue((carpeta / "configuracion.json").is_file())
        self.elemento("number_input", "Desde fotograma").set_value(6)
        self.elemento("number_input", "Hasta fotograma · incluido").set_value(2)
        self.pulsar("Exportar intervalo a CSV")
        self.assertTrue(self.at.error)
        self.assertEqual(self.sesion()["exportacion"], str(carpeta))

    def test_play_pausa_y_fin_sin_esperas_reales(self):
        self.ejecutar()
        self.pulsar("Reproducir análisis")
        self.assertTrue(self.sesion()["reproduciendo"])
        self.assertTrue(self.elemento("button", "Guardar fotograma como foto").disabled)
        self.reloj += .2
        self.ejecutar()
        self.assertEqual(self.sesion()["indice"], 1)
        self.pulsar("Pausar")
        self.assertFalse(self.sesion()["reproduciendo"])
        self.reloj += 1
        self.ejecutar()
        self.assertEqual(self.sesion()["indice"], 1)
        self.assertFalse(self.elemento("button", "Guardar fotograma como foto").disabled)
        self.elemento("number_input", "Fotograma · empieza en 0").set_value(6)
        self.ejecutar()
        self.pulsar("Reproducir análisis")
        self.reloj += .2
        self.ejecutar()
        self.assertEqual(self.sesion()["indice"], 7)
        self.assertFalse(self.sesion()["reproduciendo"])
        self.assertTrue(any("Fin del vídeo" in i.value for i in self.at.info))
        self.pulsar("Anterior")
        self.assertEqual(self.sesion()["indice"], 6)
        self.assertFalse(any("Fin del vídeo" in i.value for i in self.at.info))

    def test_pausar_y_avanzar_tienen_prioridad_sobre_el_reloj(self):
        self.ejecutar()
        self.pulsar("Siguiente")
        self.pulsar("Reproducir análisis")
        self.reloj += .2  # El temporizador ya podría avanzar al llegar el clic.
        self.pulsar("Pausar")
        self.assertEqual(self.sesion()["indice"], 1)
        self.assertEqual(self.sesion()["objetos"][0]["estado_pista"], "continua")
        self.pulsar("Reproducir análisis")
        self.reloj += .2
        self.pulsar("Siguiente")
        self.assertEqual(self.sesion()["indice"], 2)
        self.assertEqual(self.sesion()["objetos"][0]["estado_pista"], "continua")
        self.assertFalse(self.sesion()["reproduciendo"])

    def test_estado_atrasado_del_navegador_no_pausa_ni_retrocede(self):
        self.ejecutar()
        # Un temporizador puede reenviar el número y la barra que el cliente
        # todavía veía antes de recibir el último fotograma. AppTest.run()
        # normalmente siempre envía el estado más reciente y oculta esta carrera.
        estado_atrasado = self.at._tree.get_widget_states()
        self.pulsar("Reproducir análisis")
        self.reloj += .2
        self.ejecutar()
        self.assertEqual(self.sesion()["indice"], 1)
        self.assertTrue(self.sesion()["reproduciendo"])
        pista = self.sesion()["objetos"][0]["id_pista"]

        self.reloj += .2
        self.at._run(estado_atrasado)
        self.assertEqual(list(self.at.exception), [])
        self.assertTrue(self.sesion()["reproduciendo"])
        self.assertEqual(self.sesion()["indice"], 2)
        self.assertEqual(self.sesion()["objetos"][0]["id_pista"], pista)
        self.assertEqual(self.sesion()["objetos"][0]["estado_pista"], "continua")

        self.pulsar("Pausar")
        self.assertEqual(self.elemento("number_input", "Fotograma · empieza en 0").value, 2)
        self.assertEqual(self.elemento("slider", "Línea de tiempo · fotograma").value, 2)
        self.elemento("number_input", "Fotograma · empieza en 0").set_value(5)
        self.ejecutar()
        self.assertEqual(self.sesion()["indice"], 5)
        self.assertFalse(self.sesion()["reproduciendo"])

    def test_repetir_clic_atrasado_de_reproducir_no_se_convierte_en_pausa(self):
        self.ejecutar()
        self.elemento("button", "Reproducir análisis").click()
        clic_reproducir = self.at._tree.get_widget_states()
        self.at._run(clic_reproducir)
        self.assertEqual(list(self.at.exception), [])
        self.assertTrue(self.sesion()["reproduciendo"])

        # Reenviar el mismo clic conserva su intención de reproducir, aunque
        # en pantalla ya aparezca el botón de pausa. No equivale a pulsar pausa.
        for indice in (1, 2):
            self.reloj += .2
            self.at._run(clic_reproducir)
            self.assertEqual(list(self.at.exception), [])
            self.assertTrue(self.sesion()["reproduciendo"])
            self.assertEqual(self.sesion()["indice"], indice)
        self.pulsar("Pausar")
        self.assertFalse(self.sesion()["reproduciendo"])
        self.assertEqual(self.sesion()["indice"], 2)

    def test_rerun_interrumpido_termina_el_fotograma_sin_saltar_otro(self):
        self.ejecutar()
        self.pulsar("Siguiente")
        self.pulsar("Reproducir análisis")
        procesar = panel_video.procesar_posicion
        interrumpido = False
        procesados = []
        def procesar_con_interrupcion(sesion, ruta, info):
            nonlocal interrumpido
            if sesion["indice"] == 2 and not interrumpido:
                interrumpido = True
                self.reloj += .2
                panel_video.st.rerun()
            procesados.append(sesion["indice"])
            return procesar(sesion, ruta, info)
        self.reloj += .2
        with patch.object(panel_video, "procesar_posicion", side_effect=procesar_con_interrupcion):
            self.ejecutar()
        self.assertTrue(interrumpido)
        self.assertEqual(procesados, [2])
        self.assertEqual(self.sesion()["indice"], 2)
        self.assertEqual(self.sesion()["objetos"][0]["estado_pista"], "continua")

    def test_importacion_valida_se_deduplica_e_invalida_no_publica(self):
        datos = self.ruta.read_bytes()
        primera = panel_video.importar_video(datos, "clip.avi", self.base)
        segunda = panel_video.importar_video(datos, "otro_nombre.avi", self.base)
        self.assertEqual(primera, segunda)
        self.assertEqual(primera.read_bytes(), datos)
        with self.assertRaises(ValueError):
            panel_video.importar_video(b"no es un video", "roto.avi", self.base)
        with self.assertRaises(ValueError):
            panel_video.importar_video(b"", "vacio.mp4", self.base)
        with self.assertRaises(ValueError):
            panel_video.importar_video(datos, "erroneo.png", self.base)
        self.assertEqual(list((self.base / "videos" / "importados").iterdir()), [primera])

    def test_sesion_antigua_conserva_foto_exportacion_y_ajustes_al_clasificar(self):
        info = video.inspeccionar_video(self.ruta)
        sesion = panel_video.nueva_sesion_video(self.ruta, info, self.base)
        resultado, objetos = panel_video.procesar_posicion(sesion, self.ruta, info)
        sesion.update(foto_guardada="mi_foto.png", exportacion="mi_exportacion", reproduciendo=True)
        sesion.pop("version_panel_video")
        sesion.pop("version_clasificador")
        sesion["valores"]["area_min"] = 1200
        with patch.object(panel_video, "clasificar_objetos", wraps=panel_video.clasificar_objetos) as clasificar:
            panel_video.procesar_posicion(sesion, self.ruta, info)
            clasificar.assert_called_once()
            panel_video.procesar_posicion(sesion, self.ruta, info)
            clasificar.assert_called_once()  # Redibujar no pierde identidad ni repite el cálculo.
        self.assertEqual(sesion["foto_guardada"], "mi_foto.png")
        self.assertEqual(sesion["exportacion"], "mi_exportacion")
        self.assertEqual(sesion["valores"]["area_min"], 1200)
        self.assertFalse(sesion["reproduciendo"])
        self.assertEqual(sesion["version_panel_video"], 4)
        self.assertIn(panel_video.VERSION_CLASIFICADOR, sesion["cache"][0])

    def test_vista_anotada_no_modifica_foto_ni_nombres_y_limita_texto(self):
        info = video.inspeccionar_video(self.ruta)
        sesion = panel_video.nueva_sesion_video(self.ruta, info, self.base)
        resultado, objetos = panel_video.procesar_posicion(sesion, self.ruta, info)
        limpia = resultado["imagen"].copy()
        objetos[0]["clase_predicha"] = "Herramienta muy larga con acentos áéíóú " * 10
        identificador = objetos[0]["id"]
        vista = panel_video.vista_video(resultado, objetos)
        self.assertEqual(vista.shape, limpia.shape)
        np.testing.assert_array_equal(resultado["imagen"], limpia)
        self.assertEqual(objetos[0]["id"], identificador)
        self.assertTrue(objetos[0]["clase_predicha"].startswith("Herramienta"))


if __name__ == "__main__":
    unittest.main()
