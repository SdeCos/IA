"""Nombres no semánticos, estados verificables y filtros sin pérdida de trabajo."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from streamlit.testing.v1 import AppTest

from herramientas.cli import calibrador
from herramientas.datos import configuracion
from herramientas.datos.analisis import identificar_captura
from herramientas.datos.configuracion import VALORES_PREDETERMINADOS, guardar_configuracion
from herramientas.datos.etiquetado import exportar_sesion, firma_deteccion, huella_imagen
from herramientas.datos.nombres import guardar_nombre, leer_nombre, sufijo_nombre
from herramientas.datos.papelera import retirar_captura, restaurar_captura, pareja_captura
from herramientas.vision.clasificacion import clasificar_objetos
from herramientas.vision.vision import procesar_imagen
from herramientas.web.biblioteca import resumen_foto

RAIZ = Path(__file__).resolve().parents[1]


class BibliotecaTest(unittest.TestCase):
    def setUp(self):
        self.pila = contextlib.ExitStack()
        self.addCleanup(self.pila.close)
        self.base = Path(self.pila.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.capturas = self.base/'datos'/'capturas'
        self.capturas.mkdir(parents=True)
        self.foto = self.capturas/'escena_20261103_150000_000001.png'
        self.imagen = np.full((300, 400, 3), (130, 140, 20), np.uint8)
        cv2.rectangle(self.imagen, (100, 70), (130, 230), (230, 230, 230), -1)
        cv2.imwrite(str(self.foto), self.imagen)
        self.valores = VALORES_PREDETERMINADOS.copy()
        self.resultado = procesar_imagen(self.imagen, self.valores)
        self.pila.enter_context(patch.object(configuracion, 'BASE', self.base))
        self.pila.enter_context(patch.object(configuracion, 'RUTA_CONFIGURACION', self.base/'config'/'configuracion.json'))

    def guardar(self, revisadas):
        return exportar_sesion(self.resultado, self.foto, self.imagen, self.valores,
                              {1: 'Nivel'}, revisadas, self.base/'datos'/'resultados')

    def test_nombre_camara_conserva_zoom_grupo_y_no_etiqueta(self):
        with patch.object(calibrador, 'CARPETA_CAPTURAS', self.capturas), contextlib.redirect_stdout(io.StringIO()):
            escena, original = calibrador.guardar_captura(self.imagen, self.imagen, self.valores,
                                                         nombre='Alicate abierto 45°')
        self.assertTrue(escena.stem.endswith('_alicate-abierto-45'))
        self.assertEqual(leer_nombre(escena), 'Alicate abierto 45°')
        huella = huella_imagen(self.imagen)
        self.assertEqual(identificar_captura(escena, huella, self.base), identificar_captura(original, huella, self.base))
        self.assertFalse(resumen_foto(escena, self.base)['completa'])
        self.assertFalse((self.base/'datos'/'resultados').exists())
        self.assertEqual(sufijo_nombre('../../Llave Allen'), '_llave-allen')

    def test_nombre_no_modifica_firma_predicciones_ni_pixeles_y_viaja_con_sesion(self):
        antes = self.foto.read_bytes()
        firma = firma_deteccion(self.imagen, self.valores, self.resultado)
        prediccion = clasificar_objetos(self.resultado['objetos'])[0]['clase_predicha']
        guardar_nombre(self.foto, 'Martillo (nombre deliberadamente incorrecto)')
        self.assertEqual(self.foto.read_bytes(), antes)
        self.assertEqual(firma_deteccion(self.imagen, self.valores, self.resultado), firma)
        self.assertEqual(clasificar_objetos(procesar_imagen(cv2.imread(str(self.foto)), self.valores)['objetos'])[0]['clase_predicha'], prediccion)
        destino = self.guardar({1})
        self.assertEqual(leer_nombre(destino/'imagen_origen.png'), leer_nombre(self.foto))

    def test_solo_confirmacion_guardada_vigente_completa(self):
        self.assertFalse(resumen_foto(self.foto, self.base)['completa'])
        self.guardar(set())
        self.assertFalse(resumen_foto(self.foto, self.base)['completa'])
        self.guardar({1})
        self.assertTrue(resumen_foto(self.foto, self.base)['completa'])
        guardar_configuracion({**self.valores, 'cierre': 2}, self.foto.with_suffix('.json'))
        self.assertFalse(resumen_foto(self.foto, self.base)['completa'])

    def test_pixeles_modificados_y_escena_sin_objetos_no_se_ocultan(self):
        self.guardar({1})
        self.imagen[:] = (130, 140, 20)
        cv2.imwrite(str(self.foto), self.imagen)
        resumen = resumen_foto(self.foto, self.base)
        self.assertFalse(resumen['completa'])
        self.assertIn('Sin detecciones', resumen['estado'])

    def test_borrador_nuevo_prevalece_sobre_confirmacion_antigua(self):
        self.guardar({1})
        self.guardar(set())
        self.assertFalse(resumen_foto(self.foto, self.base)['completa'])

    def abrir_web(self):
        self.pila.enter_context(patch.object(cv2, 'VideoCapture', side_effect=AssertionError('Sin cámara')))
        self.at = AppTest.from_file(str(RAIZ/'src/herramientas/web/app_web.py'), default_timeout=30)
        self.ejecutar()

    def ejecutar(self):
        self.at.run()
        self.assertFalse(self.at.exception)

    def elemento(self, tipo, etiqueta):
        return next(e for e in getattr(self.at, tipo) if e.label == etiqueta)

    def test_web_nombre_busqueda_confirmacion_guardado_y_filtros(self):
        self.abrir_web()
        self.elemento('text_input', 'Nombre para organizar').set_value('Alicate abierto')
        self.elemento('button', 'Guardar nombre').click()
        self.ejecutar()
        self.assertIn('Alicate abierto', self.elemento('selectbox', 'Foto guardada').options[0])
        self.elemento('text_input', 'Buscar foto').set_value('ALICATE')
        self.ejecutar()
        self.assertEqual(self.elemento('selectbox', 'Foto guardada').value, self.foto)
        self.elemento('selectbox', 'Herramienta real').set_value('Nivel')
        self.elemento('button', 'Confirmar y siguiente').click()
        self.ejecutar()
        self.elemento('selectbox', 'Estado de las fotos').set_value('Pendientes')
        self.ejecutar()
        self.assertEqual(self.elemento('selectbox', 'Foto guardada').value, self.foto)
        self.elemento('button', 'Guardar sesión y CSV').click()
        self.ejecutar()
        self.ejecutar()  # La siguiente navegación actualiza el índice de guardados.
        self.assertTrue(any('No hay fotos con estos filtros' in e.value for e in self.at.info))
        self.elemento('selectbox', 'Estado de las fotos').set_value('Etiquetadas y guardadas')
        self.ejecutar()
        self.assertEqual(self.elemento('selectbox', 'Foto guardada').value, self.foto)
        self.assertEqual(leer_nombre(self.foto), 'Alicate abierto')
        # La caché debe invalidarse al cambiar el archivo de ajustes.
        guardar_configuracion({**self.valores, 'cierre': 2}, self.foto.with_suffix('.json'))
        self.ejecutar()
        self.assertTrue(any('No hay fotos con estos filtros' in e.value for e in self.at.info))

    def test_web_cambios_sin_guardar_no_se_ocultan(self):
        self.guardar({1})
        self.abrir_web()
        self.elemento('button', 'Dejar pendiente').click()
        self.ejecutar()
        self.elemento('selectbox', 'Estado de las fotos').set_value('Pendientes')
        self.ejecutar()
        opciones = self.elemento('selectbox', 'Foto guardada').options
        self.assertTrue(any('Cambios sin guardar' in opcion for opcion in opciones))
        self.assertTrue(self.foto.exists())

    def test_original_y_recorte_no_se_presentan_como_dos_tareas(self):
        original = pareja_captura(self.foto)
        otra_imagen = np.pad(self.imagen, ((10, 10), (10, 10), (0, 0)))
        cv2.imwrite(str(original), otra_imagen)
        self.guardar({1})
        self.abrir_web()
        self.assertEqual(len(self.elemento('selectbox', 'Foto guardada').options), 1)
        self.assertTrue(any('0 pendientes' in c.value for c in self.at.caption))
        self.elemento('checkbox', 'Mostrar también originales sin recortar').check()
        self.ejecutar()
        self.assertEqual(len(self.elemento('selectbox', 'Foto guardada').options), 2)
        self.assertFalse(resumen_foto(original, self.base)['completa'])

    def test_guardado_rapido_avanza_y_ajustes_persisten_al_reabrir(self):
        otra = self.capturas/'escena_20261103_140000_000001.png'
        imagen = self.imagen.copy()
        imagen[0, 0] = 0
        cv2.imwrite(str(otra), imagen)
        self.abrir_web()
        self.elemento('number_input', 'Área mínima · px²').set_value(1010)
        self.elemento('button', 'Aplicar ajustes').click()
        self.ejecutar()
        self.elemento('selectbox', 'Herramienta real').set_value('Nivel')
        self.elemento('button', 'Confirmar, guardar y siguiente foto').click()
        self.ejecutar()
        self.assertEqual(self.elemento('selectbox', 'Foto guardada').value, otra)
        self.assertTrue(resumen_foto(self.foto, self.base)['completa'])
        self.assertEqual(configuracion.cargar_configuracion(self.foto.with_suffix('.json'))['area_min'], 1010)
        self.assertEqual(len(list((self.base/'datos/resultados').glob('*/anotaciones.json'))), 1)
        self.at.session_state['sesiones_trabajo'] = {}
        self.elemento('selectbox', 'Foto guardada').set_value(self.foto)
        self.ejecutar()
        self.assertEqual(self.elemento('metric', 'Etiquetas confirmadas').value, '1 / 1')
        self.assertEqual(self.elemento('number_input', 'Área mínima · px²').value, 1010)

    def test_guardado_fallido_no_avanza_ni_pierde_etiqueta(self):
        self.abrir_web()
        self.elemento('selectbox', 'Herramienta real').set_value('Nivel')
        with patch('herramientas.datos.etiquetado.exportar_sesion', side_effect=OSError('Disco no disponible')):
            self.elemento('button', 'Confirmar, guardar y siguiente foto').click()
            self.ejecutar()
        self.assertTrue(self.at.error)
        self.assertEqual(self.elemento('selectbox', 'Foto guardada').value, self.foto)
        sesiones = self.at.session_state['sesiones_trabajo']
        self.assertTrue(next(iter(sesiones.values()))['modificada'])
        self.assertEqual(next(iter(sesiones.values()))['etiquetas'][1], 'Nivel')
        self.assertFalse(resumen_foto(self.foto, self.base)['completa'])

    def test_papelera_web_recupera_ultima_foto_y_sus_ajustes(self):
        original = pareja_captura(self.foto)
        cv2.imwrite(str(original), self.imagen)
        guardar_configuracion(self.valores, self.foto.with_suffix('.json'))
        self.abrir_web()
        self.elemento('button', 'Mover captura a la papelera').click()
        self.ejecutar()
        self.assertFalse(self.foto.exists())
        self.assertFalse(original.exists())
        self.elemento('button', 'Restaurar captura').click()
        self.ejecutar()
        self.assertTrue(self.foto.exists())
        self.assertTrue(original.exists())
        self.assertTrue(self.foto.with_suffix('.json').exists())

    def test_papelera_no_sobrescribe_ni_sale_de_capturas(self):
        destino = self.guardar({1})
        with self.assertRaises(ValueError):
            retirar_captura(destino/'imagen_origen.png', self.base)
        papelera = retirar_captura(self.foto, self.base)
        self.assertTrue((destino/'anotaciones.json').exists())
        self.foto.write_bytes(b'otra foto')
        with self.assertRaises(ValueError):
            restaurar_captura(papelera, self.base)
        self.assertEqual(self.foto.read_bytes(), b'otra foto')
        manifiesto = papelera/'papelera.json'
        manifiesto.write_text(json.dumps({'foto': '../escape.png', 'archivos': ['../escape.png']}))
        with self.assertRaises(ValueError):
            restaurar_captura(papelera, self.base)
