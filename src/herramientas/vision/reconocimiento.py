"""Reconocimiento de una secuencia de cámara, sin depender de Streamlit."""

import csv
from collections import Counter
import json
from pathlib import Path
import unicodedata

import cv2
import numpy as np

from herramientas.vision.clasificacion import CLASES_SOPORTADAS, VERSION_CLASIFICADOR, clasificar_objetos, snapshot_reglas
from herramientas.datos.evaluacion import inventario_objetos
from herramientas.vision.seguimiento import SeguidorObjetos
from herramientas.vision.vision import dibujar_resultado
from herramientas.vision.arbol import diagrama_decision, diagrama_regla


def cargar_inventario(ruta):
    if ruta is None:
        return None
    datos = json.loads(Path(ruta).expanduser().read_text(encoding="utf-8"))
    inventario_objetos([], datos)  # Validar cantidades sin inferir las esperadas.
    desconocidas = set(datos) - set(CLASES_SOPORTADAS)
    if desconocidas:
        raise ValueError(f"No hay reglas para estas herramientas del inventario: {sorted(desconocidas)}")
    return datos


class ReconocedorDirecto:
    """Coordina el seguimiento, la clasificación y el inventario por fotograma."""

    OCLUSION_SEGUNDOS = 1.5

    def __init__(self, esperadas=None):
        self.esperadas = inventario_objetos([], esperadas)["esperadas"]
        self.seguidor = SeguidorObjetos()
        self.indice = 0
        self._contexto = None
        self._vistos = {}
        self.oclusiones = []

    def reiniciar(self):
        """Tras perder imagen no se atribuye continuidad a la reconexión."""
        self.seguidor.reiniciar()
        self._vistos.clear()
        self.oclusiones = []

    def procesar(self, resultado, valores, *, tiempo=None):
        """Devuelve los objetos etiquetados y el recuento de la imagen actual.

        Con una marca de tiempo, conserva también indicios breves de oclusión.
        Esos indicios se muestran aparte y dejan el inventario provisional.
        """
        # Cambiar el encuadre o la máscara invalida las posiciones anteriores.
        contexto = VERSION_CLASIFICADOR + json.dumps(valores, sort_keys=True)
        if contexto != self._contexto:
            self._vistos.clear()
            self._contexto = contexto
        objetos = clasificar_objetos(self.seguidor.actualizar(resultado["objetos"], self.indice, contexto))
        self.indice += 1
        inventario = inventario_objetos(objetos, self.esperadas)
        self.oclusiones = []
        if tiempo is not None:
            self.oclusiones = self._posibles_oclusiones(resultado, objetos, tiempo)
            if self.oclusiones:
                ocultables = Counter(o["clase_predicha"] for o in self.oclusiones)
                inventario.update(posiblemente_ocultas=dict(ocultables), provisional=True, completo=None)
        return objetos, inventario

    def _posibles_oclusiones(self, resultado, objetos, tiempo):
        tapete = resultado["tapete"]
        if tapete["activo"] and not tapete["detectado"]:
            self._vistos.clear()
            return []
        # La delimitación actual puede excluir la mano junto con la herramienta.
        # Se consulta el color sin recortar, únicamente dentro de la última silueta.
        mascara = resultado["mascara_no_verde"]
        identificados = {o["id_pista"]: o for o in objetos if o["estado_clasificacion"] == "identificada"}
        recientes = {}
        ocultables = []
        mascara_borde = None
        for pista, (anterior, ultima_vez, zona) in self._vistos.items():
            if pista in identificados or not 0 <= tiempo - ultima_vez < self.OCLUSION_SEGUNDOS:
                continue
            nombre = anterior["clase_predicha"]
            contorno = anterior["contorno"]
            # Una retirada que deja el tapete despejado se refleja de inmediato.
            x, y, ancho, alto = cv2.boundingRect(contorno)
            region = mascara[y:y+alto, x:x+ancho]
            if region.shape != zona.shape:
                continue
            minimo = .35 * np.count_nonzero(zona)
            if np.count_nonzero(region[zona]) < minimo:
                # Una salida por el borde puede desplazar la silueta unos
                # píxeles antes de que el detector la descarte.
                if not resultado["descartados_borde"]:
                    continue
                if mascara_borde is None:
                    mascara_borde = cv2.dilate(mascara, np.ones((11, 11), np.uint8))
                if np.count_nonzero(mascara_borde[y:y+alto, x:x+ancho][zona]) < minimo:
                    continue
            # Una detección que recuperó el nombre con otro ID puede ocupar la
            # misma posición después de una fusión o de caducar en el seguidor.
            if any(o["clase_predicha"] == nombre and SeguidorObjetos._contiene(
                    dict(contorno=contorno), (float(o["centroide_x_px"]), float(o["centroide_y_px"])))
                   for o in identificados.values()):
                continue
            recientes[pista] = (anterior, ultima_vez, zona)
            ocultables.append(anterior)
        for pista, objeto in identificados.items():
            contorno = objeto["contorno"]
            x, y, ancho, alto = cv2.boundingRect(contorno)
            zona = np.zeros((alto, ancho), dtype=np.uint8)
            cv2.drawContours(zona, [contorno], -1, 1, cv2.FILLED, offset=(-x, -y))
            recientes[pista] = (objeto, tiempo, zona.astype(bool))
        self._vistos = recientes
        return ocultables


def _ascii(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def dibujar_directo(resultado, objetos, inventario, fps=0, en_vivo=True, estado_video=None):
    dibujables = []
    for objeto in objetos:
        texto = _ascii(f"P{objeto['id_pista']} {objeto['clase_predicha']}")
        while cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, .65, 2)[0][0] > resultado["imagen"].shape[1] - 28:
            texto = texto[:-1]
        dibujables.append({**objeto, "id": texto})
    vista = dibujar_resultado({**resultado, "objetos": dibujables}, telemetria=False)
    estado = estado_video or (f"DIRECTO | {fps:.1f} FPS" if en_vivo else "FOTO | Prueba sin camara")
    lineas = [f"{estado} | {inventario['total']} objetos | {inventario['desconocidos']} sin identificar",
              "Predicciones por reglas. Pistas temporales; manos y objetos juntos pueden alterar el resultado."]
    nombres = sorted(set(inventario["presentes"]) | set(inventario["esperadas"] or {}))
    for nombre in nombres:
        texto = f"{nombre}: {inventario['presentes'].get(nombre, 0)}"
        if inventario["esperadas"] is not None:
            texto += (f" / esperadas {inventario['esperadas'].get(nombre, 0)}"
                      f" | faltan {inventario['faltantes'].get(nombre, 0)}"
                      f" | sobran {inventario['repetidos'].get(nombre, 0)}")
        lineas.append(texto)
    if inventario["esperadas"] is None:
        lineas.append("Sin inventario esperado: se muestra solo el recuento actual.")
    elif inventario["provisional"]:
        lineas.append("Inventario provisional: quedan objetos sin identificar.")
    elif inventario["completo"]:
        lineas.append("Inventario coincide con el esperado (segun las detecciones).")
    else:
        lineas.append("Hay diferencias con el inventario esperado. Revisa la imagen y la mascara.")
    lineas.append("Espacio pausa/continua | R reinicio | G foto | E resultados | P ajustes | Q salir" if estado_video else
                  "G foto | R grabar/parar video | E guardar resultados | P ajustes | Q salir")
    panel = np.full((30 * len(lineas) + 16, vista.shape[1], 3), (30, 33, 36), np.uint8)
    for i, texto in enumerate(lineas):
        texto = _ascii(texto)
        escala = .48
        ancho = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, 1)[0][0]
        escala = min(escala, escala * (panel.shape[1] - 24) / max(ancho, 1))
        cv2.putText(panel, texto, (12, 24 + 30 * i), cv2.FONT_HERSHEY_SIMPLEX,
                    escala, (235, 235, 235), 1, cv2.LINE_AA)
    return np.vstack((vista, panel))


def exportar_predicciones(carpeta, objetos, inventario, vista):
    """Añade predicciones al paquete nuevo de medidas; nunca crea etiquetas reales."""
    carpeta = Path(carpeta)
    (carpeta / 'arbol.dot').write_text(diagrama_decision(), encoding='utf-8')
    for regla in snapshot_reglas()['reglas']:
        (carpeta / f"arbol_{regla['regla']}.dot").write_text(diagrama_regla(regla['regla']), encoding='utf-8')
    campos = ("id", "id_pista", "estado_pista", "clase_predicha", "estado_clasificacion",
              "regla", "explicacion", "version_clasificador")
    filas = [{k: objeto[k] for k in campos} for objeto in objetos]
    with (carpeta / "predicciones.csv").open("x", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos, delimiter=";")
        escritor.writeheader()
        escritor.writerows(filas)
    informe = {"etiquetas_confirmadas": False, "inventario": inventario, "reglas": snapshot_reglas(),
               "objetos": [{**fila, "ruta_decision": objeto["ruta_decision"]}
                           for fila, objeto in zip(filas, objetos)]}
    with (carpeta / "predicciones.json").open("x", encoding="utf-8") as archivo:
        json.dump(informe, archivo, ensure_ascii=False, indent=2, allow_nan=False)
    if not cv2.imwrite(str(carpeta / "reconocimiento.png"), vista):
        raise OSError("No se pudo guardar la imagen del reconocimiento.")
