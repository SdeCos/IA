"""Pruebas de procedencia y exclusión de etiquetas en el análisis de escenas."""

import json
import csv
from io import StringIO
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from analisis import identificar_captura, reunir_datos
from configuracion import VALORES_PREDETERMINADOS
from etiquetado import exportar_sesion, firma_deteccion, huella_imagen
from vision import procesar_imagen


class AnalisisTest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.base = Path(self.temporal.name)
        self.imagen = np.full((500, 800, 3), (180, 180, 0), np.uint8)
        cv2.rectangle(self.imagen, (130, 100), (170, 390), (240, 240, 240), -1)
        cv2.rectangle(self.imagen, (480, 140), (580, 340), (30, 30, 30), -1)
        self.valores = VALORES_PREDETERMINADOS.copy()
        self.origen = self.base / "capturas" / "escena_20261016_120000_123456.png"
        self.nombres = {1: "Destornillador", 2: "Nivel"}
        self.resultado = procesar_imagen(self.imagen, self.valores)

    def guardar(self, revisadas=(1, 2), imagen=None, origen=None):
        imagen = self.imagen if imagen is None else imagen
        resultado = procesar_imagen(imagen, self.valores)
        return exportar_sesion(resultado, origen or self.origen, imagen, self.valores,
                               self.nombres, set(revisadas), self.base / "resultados")

    def cambiar_anotaciones(self, sesion, mutacion):
        ruta = sesion / "anotaciones.json"
        datos = json.loads(ruta.read_text())
        mutacion(datos)
        ruta.write_text(json.dumps(datos))

    def actual(self, revisadas=(1, 2)):
        return {
            "origen": self.origen, "imagen": self.imagen,
            "valores": self.valores, "etiquetas": self.nombres,
            "revisadas": set(revisadas),
            "firma": firma_deteccion(self.imagen, self.valores, self.resultado),
        }

    def test_solo_confirmadas_recalcula_medidas_sin_escribir(self):
        sesion = self.guardar((1,))
        # Un CSV anterior o editado no debe determinar las medidas del análisis.
        (sesion / "caracteristicas.csv").write_text("id;area_px2\n1;99999999\n")
        antes = {p.name: p.read_bytes() for p in sesion.iterdir()}
        datos = reunir_datos(self.base)
        self.assertEqual(len(datos["filas"]), 1)
        fila = datos["filas"][0]
        self.assertEqual(fila["nombre_real"], "Destornillador")
        self.assertEqual(fila["area_px2"], self.resultado["objetos"][0]["area_px2"])
        self.assertEqual(fila["captura"], "20261016_120000_123456")
        self.assertEqual(datos["resumen"]["objetos_pendientes"], 1)
        self.assertEqual(datos["resumen"]["imagenes_unicas"], 1)
        self.assertEqual(datos["resumen"]["capturas"], 1)
        self.assertEqual(antes, {p.name: p.read_bytes() for p in sesion.iterdir()})

    def test_ultima_revision_prevalece_aunque_este_pendiente(self):
        self.guardar((1, 2))
        ultima = self.guardar(())
        datos = reunir_datos(self.base)
        self.assertEqual(datos["filas"], [])
        self.assertEqual(datos["resumen"]["sesiones_duplicadas"], 1)
        self.assertEqual(datos["resumen"]["objetos_pendientes"], 2)
        self.assertTrue(any(e["sesion"] == str(ultima) and e["tipo"] == "sin_confirmaciones"
                            for e in datos["exclusiones"]))

    def test_sesion_actual_sustituye_guardado_y_requiere_firma(self):
        self.guardar()
        datos = reunir_datos(self.base, self.actual((2,)))
        self.assertEqual([f["id"] for f in datos["filas"]], [2])
        self.assertTrue(datos["filas"][0]["actual"])
        self.assertEqual(datos["resumen"]["sesiones_duplicadas"], 1)
        actual = self.actual()
        actual["firma"] = "0" * 64
        datos = reunir_datos(self.base, actual)
        self.assertEqual(datos["filas"], [])
        self.assertEqual(datos["resumen"]["sesiones_invalidas"], 1)
        self.assertEqual(datos["resumen"]["sesiones_duplicadas"], 1)

    def test_clase_nueva_confirmada_se_analiza_sin_catalogo_guardada_y_actual(self):
        from panel_analisis import csv_analisis

        self.nombres = {1: "Alicates de corte", 2: "Nivel"}
        self.guardar((1,))
        for actual in (None, self.actual((1,))):
            with self.subTest(actual=actual is not None):
                datos = reunir_datos(self.base, actual)
                self.assertEqual(datos["resumen"]["sesiones_invalidas"], 0)
                self.assertEqual([f["nombre_real"] for f in datos["filas"]], ["Alicates de corte"])
                self.assertEqual(datos["resumen"]["objetos_pendientes"], 1)
                exportadas = list(csv.DictReader(StringIO(csv_analisis(datos["filas"]).decode("utf-8-sig")),
                                                 delimiter=";"))
                self.assertEqual(exportadas[0]["nombre_real"], "Alicates de corte")
        # Crear una clase nunca convierte una propuesta en una confirmación.
        self.assertEqual(reunir_datos(self.base, self.actual(()))["filas"], [])

    def test_filtros_y_graficos_incluyen_clases_nuevas_con_colores(self):
        from etiquetado import CLASES
        from panel_analisis import COLORES, clases_presentes, grafico_dispersion, grafico_perfiles

        nuevas = ["Sierra", "Alicates", "Tenazas"]
        filas = [{"nombre_real": nombre, "id": i, "captura": "foto", "fuente": "foto.png",
                  "huella_imagen": "a" * 64, "relacion_aspecto": 2., "solidez": .8,
                  "perfil_posiciones": [0., 1.], "perfil_ancho": [.5, .8]}
                 for i, nombre in enumerate([*nuevas, *reversed(CLASES)], 1)]
        orden = [*CLASES, *sorted(nuevas)]
        self.assertEqual(clases_presentes(filas), orden)
        graficos = [grafico_dispersion(filas, "relacion_aspecto", "solidez"), grafico_perfiles(filas)]
        for grafico in graficos:
            color = grafico.to_dict()["encoding"]["color"]
            self.assertEqual(color["scale"]["domain"], orden)
            self.assertEqual(color["legend"]["values"], orden)
            self.assertEqual(color["scale"]["range"][:len(CLASES)], COLORES)
            self.assertEqual(len(set(color["scale"]["range"])), len(orden))

    def test_rechaza_cambios_en_fuente_configuracion_firma_e_ids(self):
        for caso in ("fuente", "configuracion", "firma", "ids", "nombre"):
            with self.subTest(caso=caso), tempfile.TemporaryDirectory() as temporal:
                base = Path(temporal)
                sesion = exportar_sesion(self.resultado, self.origen, self.imagen,
                    self.valores, self.nombres, {1, 2}, base / "resultados")
                if caso == "fuente":
                    modificada = self.imagen.copy()
                    modificada[0, 0] = (181, 180, 0)
                    cv2.imwrite(str(sesion / "imagen_origen.png"), modificada)
                elif caso == "configuracion":
                    ruta = sesion / "configuracion.json"
                    config = json.loads(ruta.read_text())
                    config["parametros"]["s_min"] += 1
                    ruta.write_text(json.dumps(config))
                elif caso == "firma":
                    self.cambiar_anotaciones(sesion, lambda d: d.update(firma_deteccion="0" * 64))
                elif caso == "ids":
                    # Firma auténtica, pero las anotaciones omiten un objeto.
                    self.cambiar_anotaciones(sesion, lambda d: d.update(objetos=d["objetos"][:1]))
                else:
                    self.cambiar_anotaciones(sesion, lambda d: d["objetos"][0].update(nombre="Nivel\0Oculto"))
                datos = reunir_datos(base)
                self.assertEqual(datos["filas"], [])
                self.assertEqual(len(datos["exclusiones"]), 1)

    def test_identicos_no_duplican_y_recortes_comparten_captura(self):
        self.guardar()
        self.guardar(origen=self.origen.with_name("copia_renombrada.png"))
        recorte = self.imagen[20:480, 20:780].copy()
        self.guardar(imagen=recorte,
                     origen=self.origen.with_name("original_20261016_120000_123456.png"))
        datos = reunir_datos(self.base)
        self.assertEqual(datos["resumen"]["imagenes_unicas"], 2)
        self.assertEqual(datos["resumen"]["sesiones_duplicadas"], 1)
        # La copia más reciente renombrada no permite inferir el parentesco.
        self.assertEqual(datos["resumen"]["capturas"], 2)
        # Cuando la procedencia conserva su nombre, ambas variantes se agrupan.
        self.guardar()
        datos = reunir_datos(self.base)
        self.assertEqual(datos["resumen"]["capturas"], 1)
        self.assertEqual(datos["resumen"]["objetos_confirmados"], 4)
        self.assertTrue(any("recortes" in aviso for aviso in datos["avisos"]))

    def test_sesion_reabierta_conserva_grupo_por_ruta_de_copia(self):
        primera = self.guardar()
        segunda = self.guardar(origen=primera / "imagen_origen.png")
        tercera = self.guardar(origen=segunda / "imagen_origen.png")
        self.guardar(origen=tercera / "imagen_origen.png")
        datos = reunir_datos(self.base)
        self.assertEqual({f["captura"] for f in datos["filas"]}, {"20261016_120000_123456"})

    def test_legacy_y_archivos_corruptos_se_excluyen_con_motivo(self):
        legacy = self.base / "resultados" / "medicion_antigua"
        legacy.mkdir(parents=True)
        (legacy / "resumen.json").write_text("{}")
        sesion = self.guardar()
        (sesion / "anotaciones.json").write_text("{fallo")
        datos = reunir_datos(self.base)
        self.assertEqual(datos["filas"], [])
        self.assertEqual(datos["resumen"]["sesiones_invalidas"], 2)
        self.assertTrue(all(e["motivo"] for e in datos["exclusiones"]))

    def fotograma(self, clip, indice, imagen=None, hash_en_nombre=True):
        imagen = self.imagen if imagen is None else imagen
        nombre = (f"fotograma_video_{clip}_{indice:06d}_20261019_120000_123456_1234abcd.png"
                  if hash_en_nombre else f"fotograma_original_{indice:06d}.png")
        ruta = self.base / "capturas" / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(ruta), imagen)
        datos = {"version": 1, "tipo": "fotograma_video", "video": "/clip/original.avi",
                 "indice": indice, "tiempo_s": indice / 15, "huella_video": clip,
                 "huella_imagen": huella_imagen(imagen)}
        ruta.with_suffix(".origen.json").write_text(json.dumps(datos))
        return ruta

    def test_fotogramas_del_mismo_clip_no_inflan_capturas_y_no_heredan_etiquetas(self):
        clip_a, clip_b = "a" * 64, "b" * 64
        for i, clip, revisadas in ((1, clip_a, (1, 2)), (2, clip_a, (1,)), (3, clip_b, (2,))):
            imagen = self.imagen.copy()
            imagen[0, i] = (170, 180, 0)
            origen = self.fotograma(clip, i, imagen)
            self.guardar(imagen=imagen, origen=origen, revisadas=revisadas)
        datos = reunir_datos(self.base)
        self.assertEqual(datos["resumen"]["capturas"], 2)
        self.assertEqual(datos["resumen"]["imagenes_unicas"], 3)
        self.assertEqual(datos["resumen"]["objetos_confirmados"], 4)
        self.assertEqual(datos["resumen"]["objetos_pendientes"], 2)
        self.assertEqual({f["captura"] for f in datos["filas"]}, {"video_" + clip_a, "video_" + clip_b})
        self.assertTrue(any("fotogramas" in aviso for aviso in datos["avisos"]))

    def test_grupo_video_sigue_sesiones_reabiertas_y_sobrevive_sin_png_original(self):
        clip = "c" * 64
        origen = self.fotograma(clip, 4)
        primera = self.guardar(origen=origen)
        segunda = self.guardar(origen=primera / "imagen_origen.png")
        self.guardar(origen=segunda / "imagen_origen.png")
        origen.unlink()
        origen.with_suffix(".origen.json").unlink()
        datos = reunir_datos(self.base)
        self.assertEqual({f["captura"] for f in datos["filas"]}, {"video_" + clip})

    def test_sidecar_video_antiguo_verifica_png_y_rechaza_identidad_incorrecta(self):
        clip = "d" * 64
        ruta = self.fotograma(clip, 5, hash_en_nombre=False)
        sidecar = ruta.with_suffix(".origen.json")
        datos = json.loads(sidecar.read_text())
        datos.pop("huella_imagen")
        sidecar.write_text(json.dumps(datos))
        huella = huella_imagen(self.imagen)
        self.assertEqual(identificar_captura(ruta, huella, self.base), "video_" + clip)
        cambiada = self.imagen.copy()
        cambiada[0, 0] = (1, 2, 3)
        cv2.imwrite(str(ruta), cambiada)
        self.assertEqual(identificar_captura(ruta, huella, self.base), "imagen_" + huella[:16])

    def test_sidecar_invalido_no_gana_grupo_por_nombre(self):
        clip = "e" * 64
        ruta = self.fotograma(clip, 8)
        sidecar = ruta.with_suffix(".origen.json")
        original = json.loads(sidecar.read_text())
        huella = huella_imagen(self.imagen)
        for cambio in ({"huella_imagen": "0" * 64}, {"huella_video": "f" * 64},
                       {"indice": -1}, {"indice": True}, {"indice": 9}, {"tiempo_s": float("nan")},
                       {"huella_video": "invalida"}, {"version": 2}, {"version": True}):
            sidecar.write_text(json.dumps({**original, **cambio}))
            self.assertEqual(identificar_captura(ruta, huella, self.base), "imagen_" + huella[:16])


if __name__ == "__main__":
    unittest.main()
