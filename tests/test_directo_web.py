"""Captura de web: recursos exclusivos, vídeo real y flujos con cámara simulada."""
import contextlib
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from streamlit.testing.v1 import AppTest

from herramientas.datos import configuracion
from herramientas.datos.configuracion import VALORES_PREDETERMINADOS, guardar_configuracion
from herramientas.datos.nombres import leer_nombre
from herramientas.media import directo_web
from herramientas.media.directo_web import DirectoWeb
from herramientas.media.video import inspeccionar_video
from herramientas.web.panel_directo import guardar_instante

RAIZ = Path(__file__).resolve().parents[1]


def esperar(condicion, segundos=4):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return
        time.sleep(.01)
    raise AssertionError('No se alcanzó el estado esperado')


class CamaraFalsa:
    def __init__(self, imagen):
        self.imagen = imagen
        self.liberada = False

    def read(self):
        time.sleep(.02)
        return True, self.imagen.copy()

    def release(self):
        self.liberada = True


class DirectoWebTest(unittest.TestCase):
    def setUp(self):
        self.pila = contextlib.ExitStack()
        self.addCleanup(self.pila.close)
        self.base = Path(self.pila.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.valores = VALORES_PREDETERMINADOS.copy()
        self.imagen = np.full((240,320,3), (100,150,0), np.uint8)
        cv2.rectangle(self.imagen, (80,40), (110,210), (250,250,250), -1)
        self.video = self.base/'datos/videos/prueba/original.avi'
        self.video.parent.mkdir(parents=True)
        writer = cv2.VideoWriter(str(self.video), cv2.VideoWriter_fourcc(*'MJPG'), 15, (320,240))
        for _ in range(15):
            writer.write(self.imagen)
        writer.release()
        guardar_configuracion(self.valores, self.video.parent/'configuracion.json')

    def crear(self, **kwargs):
        c = DirectoWeb(self.base, self.valores, **kwargs)
        self.addCleanup(c.detener)
        c.iniciar()
        return c

    def test_video_pausa_ajustes_reinicio_fin_y_cierre(self):
        c = self.crear(video=self.video)
        esperar(lambda: c.estado()['ultimo'] is not None)
        c.pausar(True)
        time.sleep(.1)
        indice = c.estado()['ultimo']['indice']
        time.sleep(.1)
        self.assertEqual(c.estado()['ultimo']['indice'], indice)
        c.ajustar({**self.valores, 'cierre': 2})
        esperar(lambda: c.estado()['ultimo']['valores']['cierre'] == 2)
        self.assertEqual(c.estado()['ultimo']['indice'], indice)
        c.reiniciar()
        esperar(lambda: c.estado()['ultimo']['indice'] == 0)
        esperar(lambda: c.estado()['ultimo']['indice'] == 14)
        self.assertTrue(c.estado()['pausado'])
        c.detener()
        self.assertFalse(c.activo)
        self.assertFalse(c.estado()['error'])

    def test_inactividad_libera_camara_y_exclusion_entre_sesiones(self):
        falsa = CamaraFalsa(self.imagen)
        self.pila.enter_context(patch.object(directo_web, 'abrir_camara', return_value=falsa))
        c = self.crear(caducidad=.3)
        esperar(lambda: c.estado()['ultimo'] is not None)
        otra = self.crear()
        esperar(lambda: not otra.activo)
        self.assertIn('otra sesión', otra.estado()['error'])
        esperar(lambda: not c.activo)
        self.assertTrue(falsa.liberada)
        self.assertIn('inactividad', c.estado()['mensaje'])
        nueva = self.crear()
        esperar(lambda: nueva.estado()['ultimo'] is not None)
        nueva.detener()
        self.assertFalse(nueva.estado()['error'])

    def test_grabacion_cierra_al_detener_y_error_libera_recurso(self):
        falsa = CamaraFalsa(self.imagen)
        self.pila.enter_context(patch.object(directo_web, 'abrir_camara', return_value=falsa))
        c = self.crear()
        esperar(lambda: c.estado()['ultimo'] is not None)
        c.grabar(True)
        esperar(lambda: c.estado()['grabando'])
        c.detener()
        self.assertTrue(falsa.liberada)
        rutas = c.estado()['grabaciones']
        self.assertEqual(len(rutas),1)
        self.assertGreaterEqual(inspeccionar_video(Path(rutas[0]))['fotogramas'],1)
        with patch.object(directo_web, 'procesar_imagen', side_effect=ValueError('error simulado')):
            otra = self.crear()
            esperar(lambda: not otra.activo)
            self.assertIn('error simulado', otra.estado()['error'])
        ultima = self.crear()
        esperar(lambda: ultima.estado()['ultimo'] is not None)
        self.assertFalse(ultima.estado()['error'])

    def test_guardar_paquete_visible_no_el_ultimo_y_sin_confirmar_etiquetas(self):
        c = self.crear(video=self.video)
        esperar(lambda: c.estado()['ultimo'] is not None)
        visible = c.estado()['ultimo']
        esperar(lambda: c.estado()['ultimo']['indice'] > visible['indice'])
        foto, carpeta = guardar_instante(self.base, c, visible, 'Alicate prueba', True)
        import json
        origen = json.loads(foto.with_suffix('.origen.json').read_text())
        self.assertEqual(origen['indice'], visible['indice'])
        self.assertEqual(leer_nombre(foto), 'Alicate prueba')
        self.assertTrue((carpeta/'predicciones.csv').exists())
        self.assertFalse(json.loads((carpeta/'predicciones.json').read_text())['etiquetas_confirmadas'])

    def test_web_inicia_solo_boton_guarda_foto_y_cierra_al_cambiar_modo(self):
        self.pila.enter_context(patch.object(configuracion, 'BASE', self.base))
        self.pila.enter_context(patch.object(configuracion, 'RUTA_CONFIGURACION', self.base/'config/configuracion.json'))
        abrir = self.pila.enter_context(patch.object(directo_web, 'abrir_camara', side_effect=AssertionError('Sin cámara física')))
        at = AppTest.from_file(str(RAIZ/'src/herramientas/web/app_web.py'), default_timeout=30)
        def elemento(tipo, nombre):
            return next(e for e in getattr(at,tipo) if e.label == nombre)
        def ejecutar():
            at.run()
            self.assertFalse(at.exception)
        ejecutar()
        elemento('radio', 'Modo de trabajo').set_value('En directo')
        ejecutar()
        abrir.assert_not_called()
        elemento('radio', 'Fuente del directo').set_value('Vídeo de prueba')
        ejecutar()
        elemento('button', 'Iniciar').click()
        ejecutar()
        c = at.session_state['directo_controlador']
        self.addCleanup(c.detener)
        esperar(lambda: c.estado()['ultimo'] is not None)
        ejecutar()
        elemento('button','Pausar').click()
        ejecutar()
        esperar(lambda: c.estado()['pausado'])
        elemento('button','Guardar foto').click()
        ejecutar()
        self.assertTrue(Path(at.session_state['directo_foto']).exists())
        elemento('radio','Modo de trabajo').set_value('Entrega')
        ejecutar()
        self.assertFalse(c.activo)
        abrir.assert_not_called()
