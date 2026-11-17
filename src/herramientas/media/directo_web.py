"""Captura local independiente del navegador; ningún hilo llama a Streamlit.

El hilo conserva la cámara entre reejecuciones. Un latido de la vista renueva
su permiso de uso: si desaparece, cierra vídeo y cámara tras 15 segundos.
"""
from pathlib import Path
import atexit
import weakref
from threading import Event, Lock, RLock, Thread
import time

import cv2

from herramientas.cli.calibrador import abrir_camara
from herramientas.datos.configuracion import validar_configuracion
from herramientas.media.grabacion import Grabacion
from herramientas.media.reproduccion import ReproductorArchivo
from herramientas.vision.vision import procesar_imagen
from herramientas.vision.reconocimiento import ReconocedorDirecto

_CAMARA_OCUPADA = Lock()
_ACTIVOS = weakref.WeakSet()


def _cerrar_al_salir():
    for captura in list(_ACTIVOS):
        captura.detener()


atexit.register(_cerrar_al_salir)


class DirectoWeb:
    """Mantiene una fuente de vídeo abierta durante una sesión web activa."""

    def __init__(self, base, valores, esperadas=None, *, camara=1, video=None, caducidad=15):
        self.base = Path(base)
        self.valores = validar_configuracion(valores)
        self.motor = ReconocedorDirecto(esperadas)
        self.camara, self.video = camara, Path(video) if video else None
        self.caducidad = caducidad
        self._lock = RLock()
        self._salir = Event()
        self._hilo = None
        self._latido = time.monotonic()
        self._pausado = False
        self._reiniciar = False
        self._grabar = False
        self._grabando = False
        self._ultimo = None
        self._mensaje = 'Preparado'
        self._error = ''
        self._grabaciones = []

    @property
    def activo(self):
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(self):
        with self._lock:
            if self._hilo is not None:
                raise RuntimeError('Esta captura ya se inició; crea una nueva al volver a conectar.')
            self._latido = time.monotonic()
            self._mensaje = 'Abriendo vídeo…' if self.video else 'Conectando con la cámara…'
            self._hilo = Thread(target=self._ejecutar, name='herramientas-directo', daemon=True)
            _ACTIVOS.add(self)
            self._hilo.start()

    def latido(self):
        with self._lock:
            self._latido = time.monotonic()

    def detener(self):
        self._salir.set()
        if self._hilo:
            self._hilo.join(timeout=1)

    def ajustar(self, valores):
        with self._lock:
            self.valores = validar_configuracion(valores)

    def pausar(self, pausa=True):
        with self._lock:
            if self.video:
                self._pausado = pausa
                self._mensaje = 'Vídeo de prueba · pausado' if pausa else 'Vídeo de prueba'

    def reiniciar(self):
        with self._lock:
            if self.video:
                self._reiniciar = True
                self._pausado = False

    def grabar(self, activo=True):
        with self._lock:
            if self.video:
                raise ValueError('El vídeo de prueba ya está guardado.')
            self._grabar = activo

    def estado(self):
        """Entrega a la interfaz el último paquete publicado y los ajustes solicitados."""
        with self._lock:
            return dict(activo=self.activo, pausado=self._pausado, grabando=self._grabando,
                        grabar_solicitado=self._grabar, ultimo=self._ultimo, mensaje=self._mensaje,
                        error=self._error, grabaciones=list(self._grabaciones), valores=self.valores.copy())

    def _ejecutar(self):
        cap = reproductor = grabacion = None
        posee_camara = False
        fallo_desde = None
        previo = None
        revision = None
        try:
            if self.video:
                reproductor = ReproductorArchivo(self.video)
            else:
                posee_camara = _CAMARA_OCUPADA.acquire(blocking=False)
                if not posee_camara:
                    raise RuntimeError('La cámara está abierta en otra sesión de esta web. Detén esa sesión primero.')
                cap = abrir_camara(self.camara)
            while not self._salir.is_set():
                inicio = time.monotonic()
                with self._lock:
                    if inicio - self._latido > self.caducidad:
                        self._mensaje = 'Detenido por inactividad de la vista. Pulsa Iniciar para volver.'
                        break
                    valores = self.valores.copy()
                    pausa, reiniciar, grabar = self._pausado, self._reiniciar, self._grabar
                    self._reiniciar = False
                # La lectura y el procesamiento ocurren fuera del bloqueo.
                # El paquete se publica completo al terminar el fotograma.
                if reproductor:
                    if reiniciar:
                        reproductor.reiniciar()
                        self.motor.reiniciar()
                    # En pausa se vuelve a procesar el mismo fotograma cuando
                    # cambian los ajustes, por ejemplo al ajustar el zoom.
                    if pausa and revision == valores and self._ultimo is not None and not reiniciar:
                        self._salir.wait(.05)
                        continue
                    reproductor.pausado = pausa
                    original = reproductor.leer()
                    if original is None:
                        raise ValueError('El vídeo no contiene imágenes legibles.')
                    indice = reproductor.indice
                else:
                    ok, original = cap.read()
                    if not ok or original is None:
                        self.motor.reiniciar()
                        fallo_desde = fallo_desde or inicio
                        if grabacion:
                            grabacion.sin_imagen()
                        if inicio - fallo_desde >= 5:
                            raise RuntimeError('La cámara lleva cinco segundos sin imagen. Comprueba Continuidad y vuelve a iniciar.')
                        with self._lock:
                            self._mensaje = 'Esperando imagen de la cámara…'
                        self._salir.wait(.05)
                        continue
                    fallo_desde = None
                    indice = None
                    if grabar and grabacion is None:
                        grabacion = Grabacion(original, valores, carpeta=self.base/'datos/videos')
                    elif grabacion is not None:
                        if grabar:
                            grabacion.agregar(original)
                        else:
                            ruta = grabacion.cerrar(motivo='Detener grabación desde la web')
                            with self._lock:
                                self._grabaciones.append(str(ruta))
                            grabacion = None
                resultado = procesar_imagen(original, valores)
                tiempo_imagen = indice / reproductor.info['fps'] if reproductor else inicio
                objetos, inventario = self.motor.procesar(resultado, valores, tiempo=tiempo_imagen)
                ahora = time.monotonic()
                fps = 1 / max(.001, ahora - previo) if previo is not None else 0
                previo, revision = ahora, valores
                with self._lock:
                    self._ultimo = dict(original=original, resultado=resultado, objetos=objetos,
                                        inventario=inventario, valores=valores, indice=indice, fps=fps,
                                        oclusiones=self.motor.oclusiones)
                    self._grabando = grabacion is not None
                    if reproductor and (reproductor.fin or indice == reproductor.info['fotogramas'] - 1):
                        self._pausado = True
                        self._mensaje = 'Fin del vídeo. Puedes reiniciarlo o guardar este fotograma.'
                    else:
                        self._mensaje = 'Vídeo de prueba · pausado' if pausa else 'Vídeo de prueba' if self.video else 'Cámara en directo'
                espera = max(.001, 1 / reproductor.info['fps'] - (time.monotonic() - inicio)) if reproductor else .001
                self._salir.wait(espera)
        except Exception as error:
            with self._lock:
                self._error = str(error)
                self._mensaje = 'Captura detenida'
        finally:
            try:
                if grabacion is not None:
                    ruta = grabacion.cerrar(interrumpida=bool(self._error), motivo=self._error or 'Fin de la sesión web')
                    with self._lock:
                        self._grabaciones.append(str(ruta))
            except Exception as error:
                with self._lock:
                    self._error = (self._error + '\n' + f'No se pudo cerrar la grabación: {error}').strip()
            finally:
                try:
                    if cap is not None:
                        cap.release()
                    if reproductor is not None:
                        reproductor.cerrar()
                finally:
                    if posee_camara:
                        _CAMARA_OCUPADA.release()
                    with self._lock:
                        self._grabando = self._grabar = False
                        if self._salir.is_set():
                            self._mensaje = 'Detenido · cámara liberada'
