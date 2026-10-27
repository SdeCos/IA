"""Asociación temporal conservadora, sin reconocer clases ni aprender modelos.

Las distancias se miden en la imagen procesada (800 px de ancho). Sólo se
mantienen identidades con proximidad y área compatibles; las fusiones y los
cruces dudosos reciben identidades nuevas. Un ID de pista no es una etiqueta.
"""

import math
from numbers import Integral

import cv2
import numpy as np


class SeguidorObjetos:
    def __init__(self, distancia_maxima=80.0, tolerancia_perdidos=5):
        if not math.isfinite(distancia_maxima) or distancia_maxima <= 0:
            raise ValueError("La distancia máxima debe ser positiva y finita.")
        if (isinstance(tolerancia_perdidos, bool)
                or not isinstance(tolerancia_perdidos, Integral) or tolerancia_perdidos < 0):
            raise ValueError("La tolerancia debe ser un entero no negativo.")
        self.distancia_maxima = float(distancia_maxima)
        self.tolerancia_perdidos = int(tolerancia_perdidos)
        self.reiniciar()

    def reiniciar(self):
        self._pistas = {}
        self._siguiente = 1
        self._indice = None
        self._contexto = None

    @staticmethod
    def _medidas(objeto):
        valores = tuple(float(objeto[k]) for k in ("centroide_x_px", "centroide_y_px", "area_px2"))
        if not all(math.isfinite(v) for v in valores) or valores[2] < 0:
            raise ValueError("Los centroides y áreas deben ser finitos y el área no negativa.")
        return valores

    @staticmethod
    def _contiene(objeto, punto):
        contorno = objeto.get("contorno")
        return (contorno is not None and len(contorno) >= 3
                and cv2.pointPolygonTest(np.asarray(contorno, dtype=np.float32), punto, False) >= 0)

    def actualizar(self, objetos, indice, contexto=None):
        """Devuelve copias con ``id_pista`` y ``estado_pista``; no cambia etiquetas.

        Procesar índices consecutivos, incluidos los fotogramas sin objetos.
        Un salto, retroceso, repetición o cambio de contexto reinicia las pistas.
        Una desaparición de hasta cinco fotogramas puede recuperarse si no hay
        ambigüedad. No se predicen posiciones ocultas ni se garantiza identidad
        tras oclusiones: cruces/fusiones detectados invalidan las pistas afectadas.
        """
        if isinstance(indice, bool) or not isinstance(indice, Integral) or indice < 0:
            raise ValueError("El índice debe ser un entero no negativo.")
        medidas = [self._medidas(o) for o in objetos]
        if self._indice is not None and (indice != self._indice + 1 or contexto != self._contexto):
            self.reiniciar()
        self._indice, self._contexto = int(indice), contexto
        pistas = {k: p for k, p in self._pistas.items()
                  if indice - p["indice"] <= self.tolerancia_perdidos + 1}
        costes = {}
        for j, (x, y, area) in enumerate(medidas):
            for k, pista in pistas.items():
                px, py, pa = pista["medidas"]
                distancia = math.hypot(x - px, y - py)
                cociente = (area + 1e-6) / (pa + 1e-6)
                if distancia <= self.distancia_maxima and .5 <= cociente <= 2:
                    costes[j, k] = distancia / self.distancia_maxima + .35 * abs(math.log(cociente))

        ambiguos, invalidas = set(), set()
        # Una mancha que contiene varios centroides previos puede ser una unión.
        for j, objeto in enumerate(objetos):
            dentro = [k for k, p in pistas.items() if self._contiene(objeto, p["medidas"][:2])]
            if len(dentro) > 1:
                ambiguos.add(j)
                invalidas.update(dentro)
        # Si una mancha previa se divide, no adjudicar su identidad a una mitad.
        for k, pista in pistas.items():
            dentro = [j for j, m in enumerate(medidas) if self._contiene(pista["objeto"], m[:2])]
            if len(dentro) > 1:
                invalidas.add(k)
                ambiguos.update(dentro)

        por_objeto, por_pista = {}, {}
        for (j, k), coste in costes.items():
            por_objeto.setdefault(j, []).append((coste, k))
            por_pista.setdefault(k, []).append((coste, j))
        for j, opciones in por_objeto.items():
            opciones.sort()
            if len(opciones) > 1 and opciones[1][0] - opciones[0][0] <= .20:
                ambiguos.add(j)
                invalidas.update(k for coste, k in opciones if coste - opciones[0][0] <= .20)
        for k, opciones in por_pista.items():
            opciones.sort()
            if len(opciones) > 1 and opciones[1][0] - opciones[0][0] <= .20:
                invalidas.add(k)
                ambiguos.update(j for coste, j in opciones if coste - opciones[0][0] <= .20)

        disponibles = {k: p for k, p in pistas.items() if k not in invalidas}
        usados, resultado = set(), []
        for j, objeto in enumerate(objetos):
            opciones = por_objeto.get(j, [])
            candidato = opciones[0][1] if opciones else None
            reciproco = (candidato is not None and por_pista[candidato][0][1] == j)
            if (j not in ambiguos and candidato in disponibles and candidato not in usados and reciproco):
                identificador = candidato
                estado = "continua" if indice - disponibles[candidato]["indice"] == 1 else "recuperada"
            else:
                identificador = self._siguiente
                self._siguiente += 1
                estado = "ambigua" if j in ambiguos or (opciones and candidato in invalidas) else "nueva"
            usados.add(identificador)
            copia = dict(objeto, id_pista=identificador, estado_pista=estado)
            disponibles[identificador] = {"indice": int(indice), "medidas": medidas[j], "objeto": objeto.copy()}
            resultado.append(copia)
        self._pistas = disponibles
        return resultado
