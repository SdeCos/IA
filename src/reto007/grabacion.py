"""Grabación local de la cámara: imagen limpia y reloj real a 15 fps constantes.

Se conserva la última imagen disponible hasta recibir la siguiente. Por eso una
cámara lenta produce fotogramas repetidos, nunca un vídeo acelerado. El sidecar
indica qué imagen de cámara originó cada fotograma y cuándo se recibió.
"""

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from configuracion import BASE, guardar_configuracion, validar_configuracion

CARPETA_VIDEOS = BASE / "videos"
FPS_GRABACION = 15.0


class Grabacion:
    """Escribe BGR sin redimensionar ni modificar los fotogramas recibidos."""

    def __init__(self, imagen, valores, carpeta=None, *, ahora=None, fps=FPS_GRABACION):
        self._validar_imagen(imagen)
        if not math.isfinite(fps) or not 1 <= fps <= 60:
            raise ValueError("Los fps de grabación deben estar entre 1 y 60.")
        valores = validar_configuracion(valores)
        self.fps = float(fps)
        self.alto, self.ancho = imagen.shape[:2]
        # MJPG puede recortar silenciosamente dimensiones impares.
        if self.alto % 2 or self.ancho % 2:
            raise ValueError("La grabación MJPG necesita una imagen de anchura y altura pares.")
        self.inicio = time.monotonic() if ahora is None else float(ahora)
        if not math.isfinite(self.inicio):
            raise ValueError("El instante de inicio no es válido.")
        self.inicio_utc = datetime.now(timezone.utc).isoformat()
        self._ultimo_tiempo = self.inicio
        self._imagen = imagen.copy()
        self._muestra = 0
        self._tiempo_muestra = 0.0
        self._ultima_muestra_emitida = None
        self.muestras = []
        self.avisos = []
        self.fotogramas_duplicados = 0
        self.cerrada = False
        self.ruta = None
        base = Path(carpeta) if carpeta is not None else CARPETA_VIDEOS
        base.mkdir(parents=True, exist_ok=True)
        nombre = f"grabacion_{datetime.now():%Y%m%d_%H%M%S_%f}_{uuid4().hex[:10]}"
        self.destino = base / nombre
        self.temporal = base / f".{nombre}.incompleta"
        self.temporal.mkdir()
        self._writer = None
        try:
            guardar_configuracion(valores, self.temporal / "configuracion.json")
            self._escribir_metadata("grabando", 0.0, "")
            self._writer = cv2.VideoWriter(
                str(self.temporal / "original.avi"),
                cv2.VideoWriter_fourcc(*"MJPG"), self.fps,
                (self.ancho, self.alto),
            )
            if not self._writer.isOpened():
                raise OSError("OpenCV no pudo iniciar la grabación MJPG.")
            self._escribir()
        except BaseException:
            self._registrar_error("No se pudo iniciar la grabación.")
            raise

    @staticmethod
    def _validar_imagen(imagen):
        if (not isinstance(imagen, np.ndarray) or imagen.dtype != np.uint8
                or imagen.ndim != 3 or imagen.shape[2] != 3 or imagen.size == 0):
            raise ValueError("La grabación necesita una imagen BGR de 8 bits.")

    @property
    def fotogramas(self):
        return len(self.muestras)

    def _tiempo(self, ahora):
        if self.cerrada:
            raise RuntimeError("La grabación ya está cerrada.")
        ahora = time.monotonic() if ahora is None else float(ahora)
        if not math.isfinite(ahora) or ahora < self._ultimo_tiempo:
            raise ValueError("El reloj de grabación no puede retroceder.")
        self._ultimo_tiempo = ahora
        return ahora - self.inicio

    def _escribir(self):
        repetido = self._ultima_muestra_emitida == self._muestra
        self._writer.write(self._imagen)
        self.muestras.append({
            "fotograma": self.fotogramas,
            "tiempo_video_s": round(self.fotogramas / self.fps, 6),
            "tiempo_real_s": round(self._tiempo_muestra, 6),
            "muestra_camara": self._muestra,
            "repetido": repetido,
        })
        if repetido:
            self.fotogramas_duplicados += 1
        self._ultima_muestra_emitida = self._muestra

    def _hasta(self, transcurrido):
        # Cada fotograma muestra la última muestra ya recibida en ese instante.
        limite = max(1, math.ceil(transcurrido * self.fps - 1e-8))
        while self.fotogramas < limite:
            self._escribir()

    def agregar(self, imagen, *, ahora=None):
        self._validar_imagen(imagen)
        if imagen.shape[:2] != (self.alto, self.ancho):
            raise ValueError("La cámara cambió de resolución durante la grabación.")
        transcurrido = self._tiempo(ahora)
        if transcurrido - self._tiempo_muestra > 2 / self.fps:
            mensaje = "La captura o el procesamiento fueron lentos: se repitieron imágenes para conservar la duración."
            if mensaje not in self.avisos:
                self.avisos.append(mensaje)
        self._hasta(transcurrido)
        self._imagen = imagen.copy()
        self._muestra += 1
        self._tiempo_muestra = transcurrido
        indice = round(transcurrido * self.fps)
        if abs(transcurrido * self.fps - indice) < 1e-8 and self.fotogramas == indice:
            self._escribir()

    def sin_imagen(self, *, ahora=None):
        transcurrido = self._tiempo(ahora)
        mensaje = "La cámara dejó de entregar imágenes; durante ese intervalo se conserva la última imagen."
        if mensaje not in self.avisos:
            self.avisos.append(mensaje)
        self._hasta(transcurrido)

    def _escribir_metadata(self, estado, duracion, motivo):
        metadata = {
            "version": 1,
            "estado": estado,
            "archivo": "original.avi",
            "configuracion": "configuracion.json",
            "inicio_utc": self.inicio_utc,
            "fin_utc": datetime.now(timezone.utc).isoformat() if estado != "grabando" else None,
            "codec": "MJPG", "audio": False,
            "fps": self.fps, "ancho": self.ancho, "alto": self.alto,
            "fotogramas": self.fotogramas,
            "duracion_video_s": self.fotogramas / self.fps,
            "duracion_real_s": duracion,
            "fotogramas_duplicados": self.fotogramas_duplicados,
            "motivo_fin": motivo,
            "avisos": self.avisos,
            "reloj": "CFR: fotograma n en n/fps segundos; se conserva la última muestra disponible.",
            "ajustes": "Configuración al iniciar. Cambiar los controles durante la grabación no modifica este vídeo original.",
            "muestras": self.muestras,
        }
        (self.temporal / "grabacion.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )

    def _registrar_error(self, motivo):
        if self._writer is not None:
            self._writer.release()
        self.cerrada = True
        try:
            self._escribir_metadata("error", self._ultimo_tiempo - self.inicio, motivo)
        except OSError:
            pass  # Se conserva la carpeta .incompleta para poder recuperarla.

    def _verificar(self):
        ruta = self.temporal / "original.avi"
        lector = cv2.VideoCapture(str(ruta))
        try:
            if not lector.isOpened():
                raise OSError("El vídeo grabado no se puede abrir.")
            ok, imagen = lector.read()
            cantidad = round(lector.get(cv2.CAP_PROP_FRAME_COUNT))
            if not ok or imagen.shape[:2] != (self.alto, self.ancho) or cantidad != self.fotogramas:
                raise OSError("El vídeo guardado no contiene los fotogramas esperados.")
            if self.fotogramas > 1:
                lector.set(cv2.CAP_PROP_POS_FRAMES, self.fotogramas - 1)
                ok, _ = lector.read()
                if not ok:
                    raise OSError("El último fotograma del vídeo no se puede leer.")
        finally:
            lector.release()

    def cerrar(self, *, ahora=None, interrumpida=False, motivo="Tecla R"):
        """Valida y publica; un error conserva únicamente la carpeta incompleta."""
        if self.cerrada:
            return self.ruta
        try:
            transcurrido = self._tiempo(ahora)
            self._hasta(transcurrido)
            self._writer.release()
            self._verificar()
            self._escribir_metadata("interrumpida" if interrumpida else "completa", transcurrido, motivo)
            self.temporal.rename(self.destino)
            self.ruta = self.destino / "original.avi"
            self.cerrada = True
            return self.ruta
        except BaseException as error:
            self._registrar_error(str(error))
            raise
