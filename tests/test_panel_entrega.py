"""Recorrido de usuario: perfil, referencia completa, recuperación y evaluación."""
import contextlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from streamlit.testing.v1 import AppTest
from herramientas.datos import configuracion
from herramientas.datos.entrega import cargar_perfil

BASE = Path(__file__).resolve().parents[1]


class PanelEntrega(unittest.TestCase):
    def setUp(self):
        self.pila = contextlib.ExitStack()
        self.addCleanup(self.pila.close)
        self.base = Path(self.pila.enter_context(tempfile.TemporaryDirectory()))
        (self.base/"datos" / 'capturas').mkdir(parents=True)
        imagen = np.full((300,400,3), (130,140,20), np.uint8)
        cv2.rectangle(imagen,(100,70),(130,230),(230,230,230),-1)
        cv2.imwrite(str(self.base/"datos" / 'capturas'/'escena_prueba.png'), imagen)
        self.pila.enter_context(patch.object(configuracion,'BASE',self.base))
        self.pila.enter_context(patch.object(configuracion,'RUTA_CONFIGURACION', self.base/'configuracion.json'))
        self.pila.enter_context(patch.object(cv2,'VideoCapture',side_effect=AssertionError('Sin cámara')))
        self.at = AppTest.from_file(str(BASE/ "src" / "herramientas" / "web" / "app_web.py"), default_timeout=30)

    def ejecutar(self):
        self.at.run()
        self.assertFalse(self.at.exception)

    def elemento(self, tipo, etiqueta):
        return next(e for e in getattr(self.at,tipo) if e.label == etiqueta)

    def test_perfil_referencia_evaluacion_y_recarga(self):
        self.ejecutar()
        self.at.session_state['modo_trabajo'] = 'Entrega'
        self.ejecutar()
        clases = ['Martillo','Nivel','Calibre','Metro','Destornillador']
        self.elemento('multiselect','Clases de la entrega (5–8)').set_value(clases)
        self.elemento('button','Guardar perfil de entrega').click()
        self.ejecutar()
        self.assertEqual(cargar_perfil(self.base)['clases'], clases)
        self.assertFalse(self.at.error)
        self.at.session_state['modo_trabajo'] = 'Fotografías'
        self.at.session_state['pestana_principal'] = 'Reconocimiento automático'
        self.ejecutar()
        self.assertTrue(self.elemento('checkbox','Definir cantidades esperadas').value)
        self.elemento('text_area','Objetos reales (uno por línea)').set_value('Nivel\nMartillo')
        self.ejecutar()
        self.elemento('selectbox','Detección 1 corresponde a').set_value(1)
        self.ejecutar()
        self.elemento('checkbox','He revisado todos los objetos reales y todas las correspondencias').check()
        self.ejecutar()
        self.elemento('button','Guardar referencia completa de la escena').click()
        self.ejecutar()
        rutas = list((self.base/"datos" / 'evaluaciones').glob('*/referencia.json'))
        self.assertEqual(len(rutas),1)
        datos = json.loads(rutas[0].read_text())
        self.assertEqual(datos['resultado_al_guardar']['fn'],1)
        self.elemento('button','Evaluar escenas completas').click()
        self.ejecutar()
        self.assertEqual(self.at.session_state['informe_escenas_completas'][1]['desarrollo']['fn'],1)
        # Una nueva sesión de navegador recupera las referencias de disco.
        self.at = AppTest.from_file(str(BASE/ "src" / "herramientas" / "web" / "app_web.py"), default_timeout=30)
        self.ejecutar()
        self.at.session_state['pestana_principal'] = 'Reconocimiento automático'
        self.ejecutar()
        self.assertEqual(self.elemento('text_area','Objetos reales (uno por línea)').value, 'Nivel\nMartillo')
        self.assertEqual(self.elemento('selectbox','Detección 1 corresponde a').value,1)
        self.assertFalse(self.elemento('checkbox','He revisado todos los objetos reales y todas las correspondencias').value)

    def test_entrega_disponible_sin_fotos(self):
        (self.base/"datos" / 'capturas'/'escena_prueba.png').unlink()
        self.ejecutar()
        self.at.session_state['modo_trabajo'] = 'Entrega'
        self.ejecutar()
        self.assertTrue(any(h.value=='Preparar la entrega' for h in self.at.header))
