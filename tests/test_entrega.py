"""Métricas con omisiones reales, persistencia, perfil y respaldo recuperable."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import cv2
import numpy as np

from herramientas.vision.arbol import diagrama_decision, diagrama_regla, tabla_umbrales
from herramientas.vision.clasificacion import snapshot_reglas
from herramientas.datos.configuracion import VALORES_PREDETERMINADOS
from herramientas.datos.entrega import guardar_perfil, cargar_perfil
from herramientas.datos.evaluacion_escenas import (evaluar_escena, guardar_referencia, cargar_referencia,
                               evaluar_guardadas, resumen_escenas, csv_escenas)
from herramientas.datos.respaldo import crear_respaldo, verificar_respaldo
from herramientas.vision.vision import procesar_imagen


def objeto(i, nombre, estado='identificada'):
    return dict(id=i, clase_predicha=nombre, estado_clasificacion=estado)


class EvaluacionCompleta(unittest.TestCase):
    def test_omisiones_falsos_positivos_rechazos_y_matriz(self):
        objetos = [objeto(1,'Martillo'), objeto(2,'Nivel'), objeto(3,'Desconocido','ambigua')]
        resultado = evaluar_escena(objetos, ['Martillo','Calibre','Metro'], {1:1,2:0,3:2}, {'Martillo':1,'Metro':1})
        self.assertEqual((resultado['tp'],resultado['fp'],resultado['fn']), (2,1,1))
        self.assertEqual(resultado['identificacion_completa'], 1/3)
        self.assertEqual(resultado['clasificacion'], .5)
        self.assertFalse(resultado['inventario_exacto'])
        self.assertFalse(resultado['avisos_correctos'])
        self.assertEqual({f['resultado'] for f in resultado['filas']}, {'acierto','omision','rechazo','falso_positivo'})
        self.assertIn(dict(nombre_real='Metro', clase_predicha='No detectado', cantidad=1), resultado['matriz'])
        resumen = resumen_escenas([dict(resultado, grupo='clip')]*2)
        self.assertEqual((resumen['escenas'], resumen['grupos'], resumen['fn']), (2,1,2))

    def test_vacia_repetidas_y_validacion_correspondencias(self):
        vacia = evaluar_escena([], [], {}, {})
        self.assertIsNone(vacia['precision'])
        self.assertTrue(vacia['inventario_exacto'])
        self.assertTrue(vacia['avisos_correctos'])
        r = evaluar_escena([objeto(1,'Nivel'),objeto(2,'Nivel')], ['Nivel','Nivel'], {1:1,2:2}, {'Nivel':1})
        self.assertEqual(r['sobrantes_reales'], {'Nivel':1})
        self.assertTrue(r['avisos_correctos'])
        for mapa in ({1:1,2:1}, {1:1}, {1:3,2:0}, {1:None,2:0}, {1:True,2:0}):
            with self.assertRaises(ValueError):
                evaluar_escena([objeto(1,'Nivel'),objeto(2,'Nivel')], ['Nivel','Nivel'], mapa)
        omitida = evaluar_escena([], ['Otra herramienta'], {})
        self.assertEqual(omitida['fn'], 1)
        self.assertEqual(omitida['identificacion_completa'], 0)

    def test_persistencia_firma_cambios_y_reserva_por_grupo(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            imagen = np.full((300,400,3), (130,140,20), np.uint8)
            cv2.rectangle(imagen, (100,70), (130,230), (230,230,230), -1)
            valores = dict(VALORES_PREDETERMINADOS)
            resultado = procesar_imagen(imagen, valores)
            self.assertEqual(len(resultado['objetos']), 1)
            ruta = guardar_referencia(base, base/'foto.png', imagen, valores, resultado, ['Nivel'], {1:1}, {'Nivel':1}, True)
            datos, vigente = cargar_referencia(base, imagen, valores, resultado)
            self.assertTrue(vigente)
            self.assertTrue(datos['reservada'])
            informe = evaluar_guardadas(base)
            self.assertEqual(informe['prueba']['escenas'], 1)
            self.assertEqual(informe['prueba']['tp'], 1)
            self.assertIn(b'particion', csv_escenas(informe))
            otros = dict(valores, area_min=900)
            self.assertFalse(cargar_referencia(base, imagen, otros, procesar_imagen(imagen, otros))[1])
            # Una referencia alterada no se reutiliza silenciosamente.
            datos['firma'] = 'obsoleta'
            ruta.write_text(json.dumps(datos))
            self.assertEqual(len(evaluar_guardadas(base)['excluidas']), 1)
            guardar_referencia(base, base/'foto.png', imagen, valores, resultado, ['Nivel'], {1:1}, None, False)
            guardar_referencia(base, base/'foto.png', imagen, valores, resultado, ['Nivel'], {1:1}, None, True)
            self.assertEqual(evaluar_guardadas(base)['desarrollo']['escenas'], 1)
            with patch('herramientas.datos.evaluacion_escenas.identificar_captura', return_value='20261016_113207_730520'):
                with self.assertRaisesRegex(ValueError, 'desarrollo'):
                    guardar_referencia(base, base/'foto.png', imagen, valores, resultado, ['Nivel'], {1:1}, None, True)

    def test_grupo_compartido_no_mezcla_desarrollo_y_prueba(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch('herramientas.datos.evaluacion_escenas.identificar_captura', return_value='video_mismo'):
                for i, reserva in enumerate([True,False]):
                    imagen = np.full((200,300,3), (130+i,140,20), np.uint8)
                    r = procesar_imagen(imagen, VALORES_PREDETERMINADOS)
                    guardar_referencia(base, base/f'{i}.png', imagen, VALORES_PREDETERMINADOS, r, [], {}, {}, reserva)
            informe = evaluar_guardadas(base)
            self.assertEqual(informe['desarrollo']['escenas'], 2)
            self.assertEqual(informe['prueba']['escenas'], 0)
            # Invalidar la segmentación de la escena de desarrollo no convierte
            # el otro fotograma del mismo clip en una prueba independiente.
            for ruta in (base/"datos" / 'evaluaciones').glob('*/referencia.json'):
                datos = json.loads(ruta.read_text())
                if not datos['reservada']:
                    datos['firma'] = 'obsoleta'
                    ruta.write_text(json.dumps(datos))
            informe = evaluar_guardadas(base)
            self.assertEqual(informe['prueba']['escenas'], 0)
            self.assertEqual(informe['desarrollo']['escenas'], 1)
            self.assertEqual(len(informe['excluidas']), 1)


class PreparacionEntrega(unittest.TestCase):
    def test_perfil_5_a_8_y_datos_preservados(self):
        clases = snapshot_reglas()['clases_soportadas'][:5]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(cargar_perfil(tmp))
            perfil = guardar_perfil(tmp, clases, dict.fromkeys(clases, 1))
            self.assertEqual(cargar_perfil(tmp), perfil)
            for lista in (clases[:4], clases+clases, ['No existe']+clases[1:]):
                with self.assertRaises(ValueError):
                    guardar_perfil(tmp, lista, dict.fromkeys(lista,1))
            with self.assertRaises(ValueError):
                guardar_perfil(tmp, clases, dict.fromkeys(clases,True))
            self.assertEqual(cargar_perfil(tmp), perfil)

    def test_arbol_y_subarboles_derivan_de_reglas(self):
        self.assertEqual(len(tabla_umbrales()), 8 * len(snapshot_reglas()['reglas']))
        for regla in snapshot_reglas()['reglas']:
            self.assertIn(regla['regla'], diagrama_decision())
            self.assertIn('c7', diagrama_regla(regla['regla']))
        with self.assertRaises(ValueError):
            diagrama_regla('R99')
        # Cambiar una regla en la fuente de verdad modifica el diagrama.
        datos = snapshot_reglas()
        datos['reglas'][0]['condiciones'][0]['maximo'] = 1.9
        with patch('herramientas.vision.arbol.snapshot_reglas', return_value=datos):
            self.assertIn('2.05', diagrama_regla('R1'))
            self.assertIn('1.75', diagrama_regla('R1'))

    def test_respaldo_integridad_y_no_sobrescribir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base/"datos" / 'capturas').mkdir(parents=True)
            (base/"datos" / 'capturas'/'foto.png').write_bytes(b'datos de prueba')
            (base/'.venv-web').mkdir(parents=True)
            (base/'.venv-web'/'secreto.txt').write_text('no copiar')
            codigo = base/'src'/'herramientas'/'cli'/'directo.py'
            codigo.parent.mkdir(parents=True)
            codigo.write_text('# codigo')
            (base/'config').mkdir()
            (base/'config'/'herramientas.json').write_text('{}')
            (base/'ejecutar.sh').write_text('# lanzador')
            (base/'.gitignore').write_text('/datos/*')
            ruta = crear_respaldo(base, base/'respaldos'/'copia.zip')
            self.assertEqual(verificar_respaldo(ruta), 5)
            with zipfile.ZipFile(ruta) as copia:
                self.assertIn('src/herramientas/cli/directo.py', copia.namelist())
                self.assertIn('config/herramientas.json', copia.namelist())
                self.assertIn('datos/capturas/foto.png', copia.namelist())
                self.assertIn('.gitignore', copia.namelist())
                self.assertNotIn('.venv-web/secreto.txt', copia.namelist())
            with self.assertRaises(FileExistsError):
                crear_respaldo(base, ruta)
