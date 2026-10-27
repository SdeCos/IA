"""Reconocimiento de una secuencia de cámara, sin depender de Streamlit."""

import csv
import json
from pathlib import Path
import unicodedata

import cv2
import numpy as np

from clasificacion import CLASES_SOPORTADAS, VERSION_CLASIFICADOR, clasificar_objetos, snapshot_reglas
from evaluacion import inventario_objetos
from seguimiento import SeguidorObjetos
from vision import dibujar_resultado


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
    def __init__(self, esperadas=None):
        self.esperadas = inventario_objetos([], esperadas)["esperadas"]
        self.seguidor = SeguidorObjetos()
        self.indice = 0

    def reiniciar(self):
        """Tras perder imagen no se atribuye continuidad a la reconexión."""
        self.seguidor.reiniciar()

    def procesar(self, resultado, valores):
        contexto = VERSION_CLASIFICADOR + json.dumps(valores, sort_keys=True)
        objetos = clasificar_objetos(self.seguidor.actualizar(resultado["objetos"], self.indice, contexto))
        self.indice += 1
        return objetos, inventario_objetos(objetos, self.esperadas)


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
