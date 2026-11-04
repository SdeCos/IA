"""Descriptores de la silueta exterior, normalizados respecto a su caja mínima.

El perfil toma 40 secciones perpendiculares al eje largo en posiciones
``(i + 0.5) / 40``. En cada sección mide la distancia entre las intersecciones
exteriores extremas, dividida por el lado corto de la caja. Por tanto incluye
el espacio entre ramas de una herramienta y no descuenta huecos interiores.
No se aplica PCA, aprendizaje ni ninguna regla que dependa de su clase.

Los cocientes son invariantes a escala y giro en geometría continua. La
segmentación, el muestreo en píxeles y la perspectiva pueden variar las medidas.
Una silueta cuadrada no tiene un eje largo único; conviene interpretar su perfil
con cautela. Estos descriptores no cambian las detecciones ni sus etiquetas.
"""

import math

import cv2
import numpy as np


VERSION_CARACTERISTICAS = "geometria-v1"
MUESTRAS_PERFIL = 40
METRICAS_GEOMETRICAS = (
    "extension", "contraste_extremos", "fraccion_ancha",
    "asimetria_longitudinal", "ancho_central",
)
POSICIONES_PERFIL = (np.arange(MUESTRAS_PERFIL, dtype=float) + .5) / MUESTRAS_PERFIL


def _orientar_perfil(perfil):
    """Sitúa primero el extremo más ancho sin asignarle un significado físico.

    Compara la media del primer y último 20 %. Un empate a seis decimales se
    resuelve comparando lexicográficamente ambos perfiles, también cuantizados.
    Así girar 180° no cambia el criterio ni depende del orden de los vértices.
    """
    n_extremo = MUESTRAS_PERFIL // 5
    directo = (round(float(perfil[:n_extremo].mean()), 6),
               *np.round(perfil, 6).tolist())
    inverso = (round(float(perfil[-n_extremo:].mean()), 6),
               *np.round(perfil[::-1], 6).tolist())
    return perfil[::-1].copy() if inverso > directo else perfil


def caracteristicas_forma(contorno, rect=None):
    """Devuelve cinco escalares y un perfil graficable como listas de números.

    ``extension`` = área del contorno / (largo × corto).
    ``contraste_extremos`` = |media inicial − media final| / mayor de ambas;
    cada extremo ocupa el 20 % de la longitud. Cero si ambos son nulos.
    ``fraccion_ancha`` = proporción de secciones con ancho ≥ 0.5 × corto.
    ``asimetria_longitudinal`` = media de |perfil − perfil invertido|.
    ``ancho_central`` = ancho normalizado medio entre el 40 y el 60 % del largo.

    Todos los escalares están en [0, 1]. Los contornos degenerados devuelven
    ceros. ``rect`` permite reutilizar la caja mínima calculada por el detector.
    La función no modifica el contorno ni usa posiciones absolutas como rasgos.
    """
    puntos = np.asarray(contorno, dtype=np.float64).reshape(-1, 2)
    if not np.isfinite(puntos).all():
        raise ValueError("El contorno debe tener coordenadas finitas.")
    vacio = dict.fromkeys(METRICAS_GEOMETRICAS, 0.0)
    vacio.update(perfil_ancho=[0.0] * MUESTRAS_PERFIL,
                 perfil_posiciones=POSICIONES_PERFIL.tolist())
    if len(puntos) < 3:
        return vacio
    contorno_cv = np.asarray(puntos, dtype=np.float32).reshape(-1, 1, 2)
    area = cv2.contourArea(contorno_cv)
    rect = cv2.minAreaRect(contorno_cv) if rect is None else rect
    centro, (ancho, alto), angulo = rect
    largo, corto = max(ancho, alto), min(ancho, alto)
    if area <= 0 or largo <= 0 or corto <= 0:
        return vacio

    angulo_largo = math.radians(angulo if ancho >= alto else angulo + 90.0)
    eje = np.array([math.cos(angulo_largo), math.sin(angulo_largo)])
    perpendicular = np.array([-eje[1], eje[0]])
    relativos = puntos - np.asarray(centro)
    u, v = relativos @ eje, relativos @ perpendicular
    longitud = float(np.ptp(u))
    if longitud <= 0:
        return vacio
    u = (u - u.min()) / longitud
    v = v / corto

    # Intersecciones de cada sección con todos los lados del polígono. La
    # convención de extremos semiabiertos evita contar dos veces un vértice.
    u0, u1 = u, np.roll(u, -1)
    v0, v1 = v, np.roll(v, -1)
    posiciones = POSICIONES_PERFIL[:, None]
    cruza = ((u0 <= posiciones) & (posiciones < u1)) | ((u1 <= posiciones) & (posiciones < u0))
    diferencia = u1 - u0
    fraccion = np.divide(posiciones - u0, diferencia,
                         out=np.zeros((MUESTRAS_PERFIL, len(u))),
                         where=np.abs(diferencia) > 1e-12)
    intersecciones = v0 + fraccion * (v1 - v0)
    minimo = np.min(np.where(cruza, intersecciones, np.inf), axis=1)
    maximo = np.max(np.where(cruza, intersecciones, -np.inf), axis=1)
    perfil = np.zeros(MUESTRAS_PERFIL)
    con_interseccion = cruza.any(axis=1)
    perfil[con_interseccion] = np.clip((maximo - minimo)[con_interseccion], 0.0, 1.0)
    perfil = _orientar_perfil(perfil)

    n_extremo = MUESTRAS_PERFIL // 5
    inicio = float(perfil[:n_extremo].mean())
    final = float(perfil[-n_extremo:].mean())
    mayor = max(inicio, final)
    return {
        "extension": float(np.clip(area / (largo * corto), 0.0, 1.0)),
        "contraste_extremos": abs(inicio - final) / mayor if mayor else 0.0,
        # La tolerancia absorbe únicamente redondeo de la caja de OpenCV.
        "fraccion_ancha": float(np.mean(perfil >= .5 - 1e-7)),
        "asimetria_longitudinal": float(np.mean(np.abs(perfil - perfil[::-1]))),
        "ancho_central": float(perfil[2 * n_extremo:3 * n_extremo].mean()),
        "perfil_ancho": perfil.tolist(),
        "perfil_posiciones": POSICIONES_PERFIL.tolist(),
    }
