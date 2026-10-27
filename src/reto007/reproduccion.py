"""Fuente de vídeo secuencial para sustituir la cámara durante las pruebas."""

import cv2

from video import inspeccionar_video


class ReproductorArchivo:
    def __init__(self, ruta):
        self.info = inspeccionar_video(ruta)
        self.cap = None
        self.reiniciar()

    def reiniciar(self):
        self.cerrar()
        self.cap = cv2.VideoCapture(self.info["ruta"])
        if not self.cap.isOpened():
            self.cerrar()
            raise ValueError("No se ha podido abrir el vídeo para reproducirlo.")
        self.indice = -1
        self.imagen = None
        self.pausado = False
        self.fin = False

    def leer(self):
        if self.pausado and self.imagen is not None:
            return self.imagen
        if self.indice + 1 >= self.info["fotogramas"]:
            self.fin = self.pausado = True
            return self.imagen
        ok, imagen = self.cap.read()
        if not ok or imagen is None:
            raise ValueError(f"El vídeo se interrumpe antes del fotograma {self.indice + 1}. No es un fin normal.")
        self.indice += 1
        self.imagen = imagen
        return imagen

    def alternar_pausa(self):
        if not self.fin:
            self.pausado = not self.pausado

    def espera_ms(self, tiempo_procesado):
        if self.pausado:
            return 30
        # No se saltan imágenes para alcanzar el reloj. Si procesar cuesta más
        # que el intervalo nominal, se reproduce más despacio.
        return max(1, round(1000 * (1 / self.info["fps"] - tiempo_procesado)))

    def cerrar(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
