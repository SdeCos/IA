"""Persistencia y validación del catálogo de nombres introducidos a mano."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from catalogo import (
    CLASES_PREDETERMINADAS, agregar_clase, cargar_clases, normalizar_nombre,
)


class CatalogoTest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.base = Path(self.temporal.name) / "proyecto"

    def test_leer_predeterminadas_no_crea_archivos(self):
        self.assertEqual(cargar_clases(self.base), list(CLASES_PREDETERMINADAS))
        self.assertFalse(self.base.exists())
        self.assertEqual(agregar_clase("  MARTILLO  ", self.base), "Martillo")
        self.assertFalse(self.base.exists())

    def test_persistencia_orden_normalizacion_y_duplicados(self):
        self.assertEqual(agregar_clase("  Alicate\u00a0 de  presio\u0301n ", self.base),
                         "Alicate de presión")
        ruta = self.base / "herramientas.json"
        antes = ruta.read_bytes()
        self.assertEqual(agregar_clase("alicate de PRESIÓN", self.base), "Alicate de presión")
        self.assertEqual(ruta.read_bytes(), antes)
        agregar_clase("Llave inglesa", self.base)
        self.assertEqual(cargar_clases(self.base),
                         [*CLASES_PREDETERMINADAS, "Alicate de presión", "Llave inglesa"])
        self.assertEqual(list(self.base.glob("*.tmp")), [])

    def test_rechaza_nombres_invalidos_sin_escribir(self):
        for nombre in (None, 7, "", "  ", "\u00a0", "x" * 81, "Sin etiquetar",
                       "  sIN   ETIQUETAR  ", "Martillo\n", "\tNivel", "Taladro\x00",
                       "Llave\u200b", "Alicate\u202e"):
            with self.subTest(nombre=repr(nombre)), self.assertRaises(ValueError):
                agregar_clase(nombre, self.base)
        self.assertFalse(self.base.exists())
        self.assertEqual(normalizar_nombre("Á" * 80), "Á" * 80)

    def test_catalogo_corrupto_nunca_se_sobrescribe(self):
        self.base.mkdir()
        ruta = self.base / "herramientas.json"
        corruptos = ["{", "[]", '{"version":true,"herramientas":[]}',
                     '{"version":1,"version":1,"herramientas":[]}',
                     json.dumps({"version": 1, "herramientas": ["Sin etiquetar"]}),
                     json.dumps({"version": 1, "herramientas": [123]})]
        for texto in corruptos:
            with self.subTest(texto=texto):
                ruta.write_text(texto)
                with self.assertRaises(ValueError):
                    cargar_clases(self.base)
                with self.assertRaises(ValueError):
                    agregar_clase("Alicate", self.base)
                self.assertEqual(ruta.read_text(), texto)

    def test_fallo_al_publicar_conserva_catalogo_y_limpia_temporal(self):
        agregar_clase("Alicate", self.base)
        ruta = self.base / "herramientas.json"
        antes = ruta.read_bytes()
        with patch("catalogo.Path.replace", side_effect=OSError("Sin espacio")):
            with self.assertRaises(OSError):
                agregar_clase("Taladro", self.base)
        self.assertEqual(ruta.read_bytes(), antes)
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), ["herramientas.json"])


if __name__ == "__main__":
    unittest.main()
