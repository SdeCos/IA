"""Panel numérico de OpenCV, sin dependencias de interfaces gráficas adicionales.

El bucle de la aplicación llama a ``mostrar()`` y entrega el resultado completo
de ``cv2.waitKeyEx`` a ``manejar_tecla()`` antes de procesar sus propios atajos.
La construcción y la validación de valores no abren ventanas.
"""

import cv2
import numpy as np


class ControlesPrecisos:
    VENTANA = "Controles HSV"
    # Clave, etiqueta, mínimo, máximo, incremento, valor inicial.
    CAMPOS = (
        ("h_min", "H minimo", 0, 179, 1, 35),
        ("h_max", "H maximo", 0, 179, 1, 100),
        ("s_min", "S minimo", 0, 255, 1, 40),
        ("s_max", "S maximo", 0, 255, 1, 255),
        ("v_min", "V minimo", 0, 255, 1, 40),
        ("v_max", "V maximo", 0, 255, 1, 255),
        ("apertura", "Apertura (iteraciones)", 0, 5, 1, 0),
        ("cierre", "Cierre (iteraciones)", 0, 10, 1, 1),
        ("kernel", "Kernel morfologico", 1, 15, 2, 3),
        ("suavizado", "Suavizado gaussiano", 1, 15, 2, 3),
        ("area_min", "Area minima (px2)", 0, 100000, 1, 1000),
        ("zoom", "Zoom % (200 = 2x)", 100, 300, 1, 100),
        ("limitar_tapete", "Solo tapete (0=no, 1=si)", 0, 1, 1, 1),
        ("margen_tapete", "Margen tapete (px)", 0, 30, 1, 2),
    )
    _ANCHO = 590
    _ALTO = 692
    _PRIMERA_FILA = 85
    _ALTO_FILA = 35
    _CAJA = (231, 315)
    _MENOS = (326, 362)
    _MAS = (372, 408)

    def __init__(self, valores_iniciales: dict):
        self.valores = {campo[0]: campo[5] for campo in self.CAMPOS}
        desconocidos = set(valores_iniciales) - set(self.valores)
        if desconocidos:
            raise ValueError(f"Ajustes desconocidos: {sorted(desconocidos)}")
        self.valores.update(valores_iniciales)
        for clave, valor in self.valores.items():
            if isinstance(valor, bool) or not isinstance(valor, (int, np.integer)):
                raise ValueError(f"{clave} debe ser un entero")
            error = self._validar(clave, valor)
            if error:
                raise ValueError(f"{clave}: {error}")
            self.valores[clave] = int(valor)
        self._abierta = False
        self._cerrada = False
        self._campo_edicion = None
        self._borrador = ""
        self._reemplazar = False
        self._mensaje = "Los cambios se aplican a la imagen al instante."
        self._error = False

    def _validar(self, clave, valor):
        campo = next(c for c in self.CAMPOS if c[0] == clave)
        minimo, maximo = campo[2:4]
        if not minimo <= valor <= maximo:
            return f"Escribe un entero entre {minimo} y {maximo}."
        if clave in ("kernel", "suavizado") and valor % 2 == 0:
            return "Usa un numero impar: 1, 3, 5, 7, 9, 11, 13 o 15."
        if clave in ("h_min", "s_min", "v_min"):
            if valor > self.valores[clave[:1] + "_max"]:
                return "El minimo no puede superar al maximo."
        if clave in ("h_max", "s_max", "v_max"):
            if valor < self.valores[clave[:1] + "_min"]:
                return "El maximo no puede ser menor que el minimo."
        return ""

    def _aplicar(self, clave, valor):
        error = self._validar(clave, valor)
        if error:
            self._mensaje = error
            self._error = True
            return False
        self.valores[clave] = valor
        etiqueta = next(c[1] for c in self.CAMPOS if c[0] == clave)
        self._mensaje = f"Aplicado: {etiqueta} = {valor}"
        self._error = False
        return True

    def _confirmar(self):
        if self._campo_edicion is None:
            return True
        if not self._borrador or not self._borrador.isdigit():
            self._mensaje = "Escribe un numero entero antes de confirmar."
            self._error = True
            return False
        if not self._aplicar(self._campo_edicion, int(self._borrador)):
            return False
        self._campo_edicion = None
        self._borrador = ""
        self._reemplazar = False
        return True

    def _editar(self, clave):
        self._campo_edicion = clave
        self._borrador = str(self.valores[clave])
        self._reemplazar = True
        self._error = False
        self._mensaje = "Escribe para sustituir el valor; Enter aplica el cambio."

    def _raton(self, evento, x, y, _flags, _param):
        if evento != cv2.EVENT_LBUTTONDOWN:
            return
        fila = (y - self._PRIMERA_FILA) // self._ALTO_FILA
        if not 0 <= fila < len(self.CAMPOS):
            return
        if y >= self._PRIMERA_FILA + fila * self._ALTO_FILA + 29:
            return
        clave, _, _, _, paso, _ = self.CAMPOS[fila]
        if not 15 <= x <= self._MAS[1]:
            return
        # Al cambiar de campo o pulsar un botón se confirma primero la edición.
        # Si es inválida, se conserva visible y no se ejecuta la otra acción.
        if self._campo_edicion is not None:
            if clave == self._campo_edicion and x <= self._CAJA[1]:
                return
            if not self._confirmar():
                return
        if x <= self._CAJA[1]:
            self._editar(clave)
        elif self._MENOS[0] <= x <= self._MENOS[1]:
            self._aplicar(clave, self.valores[clave] - paso)
        elif self._MAS[0] <= x <= self._MAS[1]:
            self._aplicar(clave, self.valores[clave] + paso)

    def manejar_tecla(self, tecla: int) -> bool:
        """Consume la entrada durante una edición para no activar atajos globales."""
        if tecla < 0 or self._campo_edicion is None:
            return False
        if tecla in (10, 13):
            self._confirmar()
        elif tecla == 27:
            self._campo_edicion = None
            self._borrador = ""
            self._reemplazar = False
            self._error = False
            self._mensaje = "Edicion cancelada. Se conserva el valor anterior."
        elif tecla in (8, 127):
            self._borrador = "" if self._reemplazar else self._borrador[:-1]
            self._reemplazar = False
            self._error = False
            self._mensaje = "Enter: aplicar | Esc: cancelar"
        elif ord("0") <= tecla <= ord("9"):
            if self._reemplazar:
                self._borrador = ""
                self._reemplazar = False
            if len(self._borrador) < 6:
                self._borrador += chr(tecla)
                self._error = False
                self._mensaje = "Enter: aplicar | Esc: cancelar"
            else:
                self._mensaje = "Maximo 6 digitos. Usa Retroceso para corregir."
                self._error = True
        elif tecla == 9:
            indice = next(i for i, c in enumerate(self.CAMPOS)
                          if c[0] == self._campo_edicion)
            if self._confirmar():
                self._editar(self.CAMPOS[(indice + 1) % len(self.CAMPOS)][0])
        else:
            self._mensaje = "Solo digitos. Enter aplica; Esc cancela la edicion."
            self._error = True
        return True

    @staticmethod
    def _texto(imagen, texto, posicion, escala=0.48, color=(225, 230, 235)):
        cv2.putText(imagen, texto, posicion, cv2.FONT_HERSHEY_SIMPLEX,
                    escala, color, 1, cv2.LINE_AA)

    def _dibujar(self):
        imagen = np.full((self._ALTO, self._ANCHO, 3), (29, 28, 26), np.uint8)
        self._texto(imagen, "Ajustes precisos", (18, 28), 0.72)
        self._texto(imagen, "Clic en un valor para escribir. Botones -/+ para afinar.",
                    (18, 52), 0.46, (165, 175, 185))
        self._texto(imagen, "AJUSTE", (18, 76), 0.39, (160, 170, 180))
        self._texto(imagen, "VALOR", (244, 76), 0.39, (160, 170, 180))
        self._texto(imagen, "RANGO", (425, 76), 0.39, (160, 170, 180))
        for i, (clave, etiqueta, minimo, maximo, paso, _) in enumerate(self.CAMPOS):
            y = self._PRIMERA_FILA + i * self._ALTO_FILA
            activo = clave == self._campo_edicion
            if i % 2 == 0:
                cv2.rectangle(imagen, (10, y - 1), (580, y + 31), (35, 34, 32), -1)
            self._texto(imagen, etiqueta, (18, y + 20), 0.46)
            color_caja = (80, 63, 33) if activo else (54, 52, 49)
            if activo and self._error:
                color_caja = (55, 49, 93)
            cv2.rectangle(imagen, (self._CAJA[0], y), (self._CAJA[1], y + 28),
                          color_caja, -1)
            if activo:
                cv2.rectangle(imagen, (self._CAJA[0], y), (self._CAJA[1], y + 28),
                              (120, 190, 250) if not self._error else (100, 120, 255), 1)
            texto = self._borrador if activo else str(self.valores[clave])
            if activo and not self._reemplazar:
                texto += "_"
            self._texto(imagen, texto, (self._CAJA[0] + 7, y + 20), 0.48)
            for intervalo, signo in ((self._MENOS, "-"), (self._MAS, "+")):
                cv2.rectangle(imagen, (intervalo[0], y), (intervalo[1], y + 28),
                              (62, 59, 55), -1)
                self._texto(imagen, signo, (intervalo[0] + 10, y + 21), 0.6)
            rango = f"{minimo}..{maximo}" + (" impares" if paso == 2 else "")
            self._texto(imagen, rango, (425, y + 20), 0.40, (160, 170, 180))
        pie = self._PRIMERA_FILA + len(self.CAMPOS) * self._ALTO_FILA + 9
        cv2.line(imagen, (18, pie), (571, pie), (70, 69, 66), 1)
        self._texto(imagen, "Enter: aplicar | Esc: cancelar | Tab: siguiente campo",
                    (18, pie + 21), 0.43, (165, 175, 185))
        color = (105, 135, 255) if self._error else (165, 215, 175)
        self._texto(imagen, self._mensaje, (18, pie + 44), 0.44, color)
        self._texto(imagen, "1 en kernel/suavizado: sin efecto. HSV: minimo <= maximo.",
                    (18, pie + 68), 0.40, (150, 160, 170))
        self._texto(imagen, "P: guardar ajustes | E: exportar CSV | G: foto | Q: salir",
                    (18, pie + 94), 0.43, (165, 175, 185))
        return imagen

    def mostrar(self) -> bool:
        """Pinta sin esperar teclas; False si el usuario ha cerrado este panel."""
        if self._cerrada:
            return False
        if not self._abierta:
            cv2.namedWindow(self.VENTANA, cv2.WINDOW_AUTOSIZE)
            cv2.setMouseCallback(self.VENTANA, self._raton)
            self._abierta = True
        else:
            try:
                visible = cv2.getWindowProperty(self.VENTANA, cv2.WND_PROP_VISIBLE)
            except cv2.error:
                visible = 0
            if visible < 1:
                self._cerrada = True
                return False
        cv2.imshow(self.VENTANA, self._dibujar())
        return True

    def cerrar(self):
        """Cierra únicamente este panel; admite llamadas repetidas."""
        if self._abierta and not self._cerrada:
            try:
                cv2.destroyWindow(self.VENTANA)
            except cv2.error:
                pass
        self._cerrada = True
