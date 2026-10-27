"""Identidades temporales: continuidad, pérdidas y asociaciones ambiguas."""

import unittest

import numpy as np

from seguimiento import SeguidorObjetos


def objeto(x, y=100, identificador=1, area=1000, ancho=20):
    return {"id": identificador, "area_px2": area, "centroide_x_px": x, "centroide_y_px": y,
            "contorno": np.array([[[x - ancho / 2, y - 10]], [[x + ancho / 2, y - 10]],
                                   [[x + ancho / 2, y + 10]], [[x - ancho / 2, y + 10]]], dtype=np.float32)}


class SeguimientoTests(unittest.TestCase):
    def test_identidad_sigue_objeto_aunque_cambie_id_local(self):
        seguidor = SeguidorObjetos()
        primero = [objeto(100, identificador=1), objeto(400, identificador=2)]
        inicio = seguidor.actualizar(primero, 0)
        siguiente = seguidor.actualizar([objeto(405, identificador=1), objeto(105, identificador=2)], 1)
        self.assertEqual([o["id_pista"] for o in siguiente], [inicio[1]["id_pista"], inicio[0]["id_pista"]])
        self.assertEqual([o["id"] for o in siguiente], [1, 2])
        self.assertTrue(all(o["estado_pista"] == "continua" for o in siguiente))
        self.assertNotIn("id_pista", primero[0])

    def test_perdida_breve_y_caducidad(self):
        seguidor = SeguidorObjetos(tolerancia_perdidos=2)
        pista = seguidor.actualizar([objeto(100)], 0)[0]["id_pista"]
        seguidor.actualizar([], 1)
        seguidor.actualizar([], 2)
        recuperada = seguidor.actualizar([objeto(105)], 3)[0]
        self.assertEqual(recuperada["id_pista"], pista)
        self.assertEqual(recuperada["estado_pista"], "recuperada")
        for i in (4, 5, 6):
            seguidor.actualizar([], i)
        nueva = seguidor.actualizar([objeto(105)], 7)[0]
        self.assertNotEqual(nueva["id_pista"], pista)
        self.assertEqual(nueva["estado_pista"], "nueva")

    def test_saltos_y_contexto_reinician(self):
        seguidor = SeguidorObjetos()
        for indice, contexto in [(0, "video-A-ajustes-1"), (2, "video-A-ajustes-1"),
                                  (1, "video-A-ajustes-1"), (2, "video-A-ajustes-2"),
                                  (3, "video-B-ajustes-2"), (3, "video-B-ajustes-2")]:
            self.assertEqual(seguidor.actualizar([objeto(100)], indice, contexto)[0]["estado_pista"], "nueva")

    def test_union_y_separacion_no_heredan_identidad(self):
        seguidor = SeguidorObjetos()
        inicio = seguidor.actualizar([objeto(100), objeto(140, identificador=2)], 0)
        fusion = seguidor.actualizar([objeto(120, area=2000, ancho=70)], 1)[0]
        self.assertEqual(fusion["estado_pista"], "ambigua")
        self.assertNotIn(fusion["id_pista"], [o["id_pista"] for o in inicio])
        separados = seguidor.actualizar([objeto(100), objeto(140, identificador=2)], 2)
        self.assertTrue(all(o["estado_pista"] == "ambigua" for o in separados))
        self.assertTrue(all(o["id_pista"] != fusion["id_pista"] for o in separados))
        self.assertEqual(len({o["id_pista"] for o in separados}), 2)

    def test_cambio_de_area_o_salto_espacial_crea_pista(self):
        seguidor = SeguidorObjetos()
        inicio = seguidor.actualizar([objeto(100)], 0)[0]["id_pista"]
        nueva = seguidor.actualizar([objeto(100, area=4000)], 1)[0]
        self.assertNotEqual(nueva["id_pista"], inicio)
        salto = seguidor.actualizar([objeto(600, area=4000)], 2)[0]
        self.assertNotEqual(salto["id_pista"], nueva["id_pista"])

    def test_candidatos_equivalentes_se_marcan_ambiguos(self):
        seguidor = SeguidorObjetos()
        seguidor.actualizar([objeto(100), objeto(140)], 0)
        nuevo = seguidor.actualizar([objeto(120)], 1)[0]
        self.assertEqual(nuevo["estado_pista"], "ambigua")
        with self.assertRaises(ValueError):
            seguidor.actualizar([objeto(float("nan"))], 2)
        with self.assertRaises(ValueError):
            SeguidorObjetos(tolerancia_perdidos=-1)


if __name__ == "__main__":
    unittest.main()
