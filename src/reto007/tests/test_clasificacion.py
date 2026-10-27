"""Pruebas del contrato, abstención e invariancia del clasificador manual."""

from copy import deepcopy
import json
import math
import unittest

import cv2
import numpy as np

from clasificacion import (
    CARACTERISTICAS, CLASES_SOPORTADAS, GRUPOS_DESARROLLO,
    VERSION_CLASIFICADOR, clasificar_objeto, clasificar_objetos, snapshot_reglas,
)
from geometria import caracteristicas_forma


# Casos explícitos de geometría, sin rutas, IDs, catálogo ni etiquetas de disco.
# Son ejemplos de desarrollo del código, no una evaluación independiente.
EJEMPLOS = {
    "Metro": (1.1, .97, .77, .87, .04, .95, .03, .98),
    "Cuter": (2.8, .92, .51, .78, .06, .95, .06, .95),
    "Nivel": (5.3, .96, .35, .94, .01, 1.0, .01, .93),
    "Desbarbador manual": (11.0, .82, .17, .72, .8, .8, .3, .9),
    "Destornillador": (7.3, .64, .13, .4, .85, .425, .55, .3),
    "Calibre": (3.2, .53, .17, .33, .65, .175, .23, .21),
    "Martillo": (3.2, .49, .17, .35, .45, .2, .145, .31),
    "Juego de llaves Allen": (3.2, .7, .145, .54, .4, .775, .18, .71),
    "Alicate": (2.9, .64, .16, .47, .66, .675, .415, .765),
}


def ejemplo(clase):
    return dict(zip(CARACTERISTICAS, EJEMPLOS[clase]))


def medidas(contorno):
    contorno = np.asarray(contorno, dtype=np.float32).reshape(-1, 1, 2)
    area = cv2.contourArea(contorno)
    perimetro = cv2.arcLength(contorno, True)
    lados = cv2.minAreaRect(contorno)[1]
    resultado = caracteristicas_forma(contorno)
    resultado.update(relacion_aspecto=max(lados) / min(lados),
                     solidez=area / cv2.contourArea(cv2.convexHull(contorno)),
                     circularidad=4 * math.pi * area / perimetro**2)
    return resultado


class ClasificacionTests(unittest.TestCase):
    def test_nueve_formas_tienen_regla_y_traza_explicita(self):
        self.assertEqual(set(EJEMPLOS), set(CLASES_SOPORTADAS))
        for nombre in EJEMPLOS:
            with self.subTest(nombre=nombre):
                salida = clasificar_objeto(ejemplo(nombre))
                self.assertEqual(salida["clase_predicha"], nombre)
                self.assertEqual(salida["estado_clasificacion"], "identificada")
                self.assertEqual(salida["version_clasificador"], VERSION_CLASIFICADOR)
                decision = next(paso for paso in salida["ruta_decision"]
                                if paso["nodo"] == salida["regla"])
                self.assertEqual(len(decision["detalle"]), 8)
                self.assertTrue(all(paso["interior"] for paso in decision["detalle"]))
                json.dumps(salida, allow_nan=False)

    def test_etiquetas_ids_coordenadas_escala_y_procedencia_no_intervienen(self):
        original = ejemplo("Martillo")
        esperado = clasificar_objeto(original)
        for falso_nombre in CLASES_SOPORTADAS + ("No etiquetado",):
            manipulado = dict(original, nombre_real=falso_nombre, etiqueta=falso_nombre,
                              id=1000, id_pista=53, captura="evaluacion",
                              fuente="otra.png", centroide_x_px=-900, centroide_y_px=13000,
                              orientacion_grados=179, area_px2=1e20, largo_px=10000,
                              corto_px=.02, perfil_ancho=[0] * 40)
            self.assertEqual(clasificar_objeto(manipulado), esperado)

    def test_copias_no_sobrescriben_la_referencia_ni_la_entrada(self):
        entradas = [dict(ejemplo("Nivel"), nombre_real="Metro", id=7)]
        antes = deepcopy(entradas)
        salida = clasificar_objetos(entradas)
        self.assertEqual(entradas, antes)
        self.assertIsNot(salida[0], entradas[0])
        self.assertEqual(salida[0]["nombre_real"], "Metro")
        self.assertEqual(salida[0]["clase_predicha"], "Nivel")
        self.assertEqual(salida[0]["id"], 7)
        self.assertEqual(clasificar_objetos([]), [])

    def test_sin_datos_no_se_inventa_una_clase(self):
        for dato in (None, [], {}, "Nivel"):
            salida = clasificar_objeto(dato)
            self.assertEqual(salida["clase_predicha"], "Desconocido")
            self.assertEqual(salida["estado_clasificacion"], "desconocida")
        for clave in CARACTERISTICAS:
            for valor in (None, math.nan, math.inf, -math.inf, True, "0.5", -1):
                with self.subTest(clave=clave, valor=valor):
                    dato = ejemplo("Nivel")
                    dato[clave] = valor
                    self.assertEqual(clasificar_objeto(dato)["regla"], "DATOS_INVALIDOS")
            dato = ejemplo("Nivel")
            del dato[clave]
            self.assertEqual(clasificar_objeto(dato)["regla"], "DATOS_INVALIDOS")

    def test_version_y_geometria_incoherente_se_rechazan(self):
        dato = dict(ejemplo("Nivel"), version_caracteristicas="otra-v9")
        self.assertEqual(clasificar_objeto(dato)["regla"], "VERSION_INCOMPATIBLE")
        dato = dict(ejemplo("Nivel"), extension=.95, solidez=.5)
        self.assertEqual(clasificar_objeto(dato)["regla"], "GEOMETRIA_INCONSISTENTE")

    def test_banda_de_abstencion_a_ambos_lados_del_umbral(self):
        for ar in (6.36, 6.5, 6.64):
            with self.subTest(ar=ar):
                salida = clasificar_objeto(dict(ejemplo("Nivel"), relacion_aspecto=ar))
                self.assertEqual(salida["clase_predicha"], "Desconocido")
                self.assertEqual(salida["estado_clasificacion"], "ambigua")
        for ar in (6.2, 6.8):
            salida = clasificar_objeto(dict(ejemplo("Nivel"), relacion_aspecto=ar))
            self.assertEqual(salida["estado_clasificacion"],
                             "identificada" if ar == 6.2 else "desconocida")

    def test_martillo_y_calibre_necesitan_mas_que_aspecto_y_solidez(self):
        martillo = ejemplo("Martillo")
        calibre = ejemplo("Calibre")
        for dato in (martillo, calibre):
            dato.update(relacion_aspecto=3.3, solidez=.52, circularidad=.17)
        self.assertEqual(clasificar_objeto(martillo)["clase_predicha"], "Martillo")
        self.assertEqual(clasificar_objeto(calibre)["clase_predicha"], "Calibre")
        # Una combinación intermedia no debe heredar la etiqueta del vecino.
        intermedio = dict(martillo, ancho_central=.26, contraste_extremos=.55)
        self.assertEqual(clasificar_objeto(intermedio)["clase_predicha"], "Desconocido")

    def test_nivel_sintetico_conserva_clase_en_giros_escalas_y_reflejos(self):
        base = np.array([(0, 0), (150, 0), (150, 30), (0, 30)], dtype=float)
        for angulo, escala in ((0, .5), (37, 3.0), (90, 1), (180, .75), (271, 2.2)):
            rad = math.radians(angulo)
            rotacion = np.array([[math.cos(rad), -math.sin(rad)],
                                 [math.sin(rad), math.cos(rad)]])
            for reflejo in (1, -1):
                contorno = base * [reflejo, 1] @ rotacion.T * escala + (213, 517)
                with self.subTest(angulo=angulo, escala=escala, reflejo=reflejo):
                    salida = clasificar_objeto(medidas(contorno))
                    self.assertEqual(salida["clase_predicha"], "Nivel")

    def test_circulo_y_fragmento_de_vastago_son_desconocidos(self):
        angulos = np.linspace(0, 2 * math.pi, 100, endpoint=False)
        circulo = np.column_stack((np.cos(angulos), np.sin(angulos))) * 50
        fragmento = [(0, 0), (150, 0), (150, 4), (0, 4)]
        for contorno in (circulo, fragmento):
            self.assertEqual(clasificar_objeto(medidas(contorno))["clase_predicha"], "Desconocido")

    def test_snapshot_no_comparte_estado_y_declara_desarrollo(self):
        snapshot = snapshot_reglas()
        json.dumps(snapshot, allow_nan=False)
        self.assertEqual(tuple(snapshot["grupos_desarrollo"]), GRUPOS_DESARROLLO)
        self.assertEqual(len(snapshot["reglas"]), 9)
        snapshot["reglas"][0]["condiciones"][0]["minimo"] = -100
        self.assertEqual(snapshot_reglas()["reglas"][0]["condiciones"][0]["minimo"], 1)


if __name__ == "__main__":
    unittest.main()
