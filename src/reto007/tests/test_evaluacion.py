"""Métricas honestas, procedencia y recuento sin aprender de las etiquetas."""

from copy import deepcopy
import unittest
from unittest.mock import patch

import evaluacion


def predecir(medidas):
    # Oráculo de prueba deliberadamente sencillo e independiente del nombre real.
    valor = medidas.get("relacion_aspecto", 0)
    nombre, estado = (("Martillo", "identificada") if valor == 1 else
                      ("Nivel", "identificada") if valor == 2 else
                      ("Desconocido", "ambigua") if valor == 3 else
                      ("Desconocido", "desconocida"))
    return dict(clase_predicha=nombre, estado_clasificacion=estado,
                regla="regla-prueba", explicacion="Regla fija de prueba.",
                ruta_decision=["AR de prueba"], version_clasificador="test-v1")


def fila(identificador=1, nombre="Martillo", medida=1, captura="desarrollo",
         imagen="a", **otros):
    return dict(id=identificador, nombre_real=nombre, relacion_aspecto=medida,
                captura=captura, huella_imagen=imagen,
                firma_deteccion="firma-" + imagen, fuente="foto.png", sesion="sesion", **otros)


class EvaluacionTest(unittest.TestCase):
    def setUp(self):
        for nombre, valor in (("GRUPOS_DESARROLLO", ("desarrollo",)),
                              ("CLASES_SOPORTADAS", ("Martillo", "Nivel")),
                              ("VERSION_CLASIFICADOR", "test-v1")):
            parche = patch.object(evaluacion.clasificacion, nombre, valor)
            parche.start()
            self.addCleanup(parche.stop)
        parche = patch.object(evaluacion.clasificacion, "clasificar_objeto", side_effect=predecir)
        self.clasificar = parche.start()
        self.addCleanup(parche.stop)

    def test_aciertos_errores_y_rechazos_tienen_denominadores_distintos(self):
        datos = evaluacion.evaluar_filas([
            fila(1), fila(2, "Martillo", 2), fila(3, "Nivel", 0), fila(4, "Nivel", 3),
            fila(1, "Nivel", 2, "nuevo", "b"),
        ])
        desarrollo = datos["desarrollo"]
        self.assertEqual((desarrollo["total"], desarrollo["aciertos"], desarrollo["errores"],
                          desarrollo["rechazos"]), (4, 1, 1, 2))
        self.assertEqual(desarrollo["cobertura"], .5)
        self.assertEqual(desarrollo["exactitud_total"], .25)
        self.assertEqual(desarrollo["exactitud_identificados"], .5)
        self.assertEqual(datos["prueba"]["exactitud_total"], 1)
        self.assertEqual(datos["prueba"]["grupos"], 1)
        self.assertEqual(datos["filas"][1]["resultado"], "error")
        self.assertEqual(datos["filas"][3]["resultado"], "rechazo")
        self.assertIn(dict(nombre_real="Nivel", clase_predicha="Desconocido", cantidad=2),
                      datos["matriz"])
        self.assertIn("ya detectados", datos["alcance"])

    def test_cero_objetos_o_cero_identificados_no_producen_porcentajes_ficticios(self):
        vacio = evaluacion.evaluar_filas([])
        self.assertIsNone(vacio["total"]["exactitud_total"])
        self.assertIsNone(vacio["total"]["cobertura"])
        rechazo = evaluacion.evaluar_filas([fila(medida=0)])
        self.assertEqual(rechazo["total"]["exactitud_total"], 0)
        self.assertIsNone(rechazo["total"]["exactitud_identificados"])
        self.assertEqual(rechazo["prueba"]["total"], 0)
        self.assertTrue(any("No hay grupos nuevos" in aviso for aviso in rechazo["avisos"]))

    def test_no_filtra_etiquetas_rutas_ids_o_grupos_al_clasificador(self):
        original = fila(nombre="Nivel", perfil_ancho=[.1, .9], solidez=.8,
                        clase_predicha="Nivel", etiqueta="Nivel")
        antes = deepcopy(original)
        datos = evaluacion.evaluar_filas([original])
        argumentos = self.clasificar.call_args.args[0]
        self.assertEqual(set(argumentos), {"relacion_aspecto", "perfil_ancho", "solidez"})
        self.assertEqual(datos["filas"][0]["clase_predicha"], "Martillo")
        self.assertEqual(datos["filas"][0]["resultado"], "error")
        self.assertEqual(original, antes)
        original["nombre_real"] = "Martillo"
        otra = evaluacion.evaluar_filas([original])
        self.assertEqual(otra["filas"][0]["clase_predicha"], "Martillo")
        self.assertEqual(otra["filas"][0]["resultado"], "acierto")

    def test_fotogramas_y_recortes_no_se_reparten_ni_inflan_grupos(self):
        filas = [fila(imagen="original"), fila(imagen="recorte")]
        filas.extend(fila(imagen=f"frame-{i}", captura="video-nuevo") for i in range(25))
        datos = evaluacion.evaluar_filas(filas)
        self.assertEqual(datos["desarrollo"]["grupos"], 1)
        self.assertEqual(datos["desarrollo"]["imagenes"], 2)
        self.assertEqual(datos["prueba"]["grupos"], 1)
        self.assertEqual(datos["prueba"]["imagenes"], 25)
        self.assertEqual(datos["prueba"]["ids_grupos"], ["video-nuevo"])

    def test_duplicados_y_aliases_de_captura_no_contaminan_prueba(self):
        filas = [fila(), fila(captura="alias"), fila(imagen="otra", captura="alias"),
                 fila(imagen="otra", captura="alias-dos"),
                 fila(imagen="tercera", captura="alias-dos")]
        datos = evaluacion.evaluar_filas(filas)
        self.assertEqual(datos["duplicados_omitidos"], 2)
        self.assertEqual(datos["desarrollo"]["total"], 3)
        self.assertEqual(datos["desarrollo"]["grupos"], 1)
        self.assertEqual(datos["prueba"]["total"], 0)
        self.assertTrue(any("más de un grupo" in aviso for aviso in datos["avisos"]))

    def test_sin_procedencia_no_se_presenta_como_prueba_y_sin_etiqueta_se_excluye(self):
        datos = evaluacion.evaluar_filas([fila(captura=""), fila(2, nombre=" ")])
        self.assertEqual(datos["desarrollo"]["total"], 1)
        self.assertEqual(datos["desarrollo"]["grupos"], 0)
        self.assertEqual(datos["prueba"]["total"], 0)
        self.assertEqual(len(datos["exclusiones"]), 1)

    def test_nueva_etiqueta_no_amplia_reglas_y_figura_en_matriz(self):
        datos = evaluacion.evaluar_filas([fila(nombre="Sierra", medida=0)])
        self.assertEqual(datos["filas"][0]["resultado"], "rechazo")
        self.assertTrue(any("Sierra" in aviso and "no entrena" in aviso for aviso in datos["avisos"]))
        self.assertEqual(datos["matriz"], [dict(nombre_real="Sierra",
                                                clase_predicha="Desconocido", cantidad=1)])


class InventarioTest(unittest.TestCase):
    def setUp(self):
        parche = patch.object(evaluacion.clasificacion, "CLASES_SOPORTADAS", ("Martillo", "Nivel"))
        parche.start()
        self.addCleanup(parche.stop)

    def test_cuenta_solo_predicciones_y_no_supone_inventario_esperado(self):
        objetos = [dict(predecir({"relacion_aspecto": 1}), nombre_real="Nivel", id_pista=1),
                   dict(predecir({"relacion_aspecto": 1}), id_pista=2),
                   dict(predecir({"relacion_aspecto": 0}), nombre_real="Nivel", id_pista=3)]
        datos = evaluacion.inventario_objetos(objetos)
        self.assertEqual(datos["presentes"], {"Martillo": 2})
        self.assertEqual(datos["desconocidos"], 1)
        self.assertIsNone(datos["faltantes"])
        self.assertIsNone(datos["repetidos"])
        self.assertIsNone(datos["completo"])
        self.assertTrue(datos["provisional"])
        # Otro fotograma no acumula la cantidad anterior aunque repita la pista.
        self.assertEqual(evaluacion.inventario_objetos(objetos[:1])["presentes"], {"Martillo": 1})

    def test_cantidades_faltantes_y_excesos_y_ambiguedad(self):
        objetos = [predecir({"relacion_aspecto": 1}) for _ in range(3)]
        objetos += [predecir({"relacion_aspecto": 3})]
        datos = evaluacion.inventario_objetos(objetos, {"Martillo": 2, "Nivel": 1})
        self.assertEqual(datos["faltantes"], {"Nivel": 1})
        self.assertEqual(datos["repetidos"], {"Martillo": 1})
        self.assertEqual(datos["ambiguos"], 1)
        self.assertEqual(datos["desconocidos"], 1)
        self.assertIsNone(datos["completo"])
        self.assertEqual(evaluacion.inventario_objetos(objetos[:2], {"Martillo": 2})["completo"], True)
        self.assertEqual(evaluacion.inventario_objetos(objetos[:2], {"Martillo": 1})["completo"], False)

    def test_inventario_vacio_explicito_y_clases_sin_regla(self):
        datos = evaluacion.inventario_objetos([predecir({"relacion_aspecto": 1})], {})
        self.assertEqual(datos["repetidos"], {"Martillo": 1})
        nuevo = evaluacion.inventario_objetos([], {"Sierra": 1})
        self.assertEqual(nuevo["faltantes"], {"Sierra": 1})
        self.assertEqual(nuevo["completo"], False)

    def test_rechaza_cantidades_y_nombres_invalidos(self):
        for inventario in ([], {"Nivel": -1}, {"Nivel": True}, {"Nivel": 1.5},
                           {" ": 1}, {"Nivel": 1, " Nivel ": 2}):
            with self.subTest(inventario=inventario), self.assertRaises(ValueError):
                evaluacion.inventario_objetos([], inventario)


if __name__ == "__main__":
    unittest.main()
