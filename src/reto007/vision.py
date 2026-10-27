"""Segmentación y medidas compartidas por el calibrador y el detector.

Este módulo no abre cámaras, ventanas ni archivos. Las imágenes usan el orden
BGR de OpenCV. Todas las medidas corresponden a la imagen procesada de 800 px
de ancho y al contorno exterior: no se resta el área de los huecos interiores.
"""

import math
import unicodedata

import cv2
import numpy as np

from configuracion import validar_configuracion
from geometria import VERSION_CARACTERISTICAS, caracteristicas_forma


ANCHO_PROCESADO = 800
VERSION_PROCESADO = "tapete-v1"


def localizar_tapete(verde, margen=2, activo=True):
    """Delimita la mayor región verde; rellena sus huecos (las herramientas).

    Usa el contorno real, no un rectángulo ni una envolvente convexa que podrían
    incluir mesa. Los umbrales de plausibilidad (10 % del encuadre y 25 % verde
    dentro del contorno) son comprobaciones iniciales, no una garantía universal.
    La región se obtiene a la escala de procesamiento, sin recortar ni estirar.
    """
    total = verde.size
    info = {"activo": bool(activo), "detectado": False, "area_px2": 0,
            "proporcion": 0.0, "margen_px": int(margen), "motivo": ""}
    if not activo:
        info.update(area_px2=total, proporcion=1.0, motivo="Análisis de la imagen completa.")
        return np.full_like(verde, 255), info
    region = np.zeros_like(verde)
    contornos, _ = cv2.findContours(verde, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        info["motivo"] = "No se encuentra el tapete verde. Revisa los ajustes HSV o la fotografía."
        return region, info
    contorno = max(contornos, key=cv2.contourArea)
    cv2.drawContours(region, [contorno], -1, 255, cv2.FILLED)
    area = cv2.countNonZero(region)
    proporcion_verde = cv2.countNonZero(cv2.bitwise_and(verde, region)) / max(1, area)
    if area < .10 * total or proporcion_verde < .25:
        info["motivo"] = "No hay una región verde suficientemente grande para delimitar el tapete. Revisa HSV y encuadre."
        return np.zeros_like(verde), info
    if margen:
        region = cv2.erode(region, np.ones((3, 3), np.uint8), iterations=margen,
                           borderType=cv2.BORDER_CONSTANT, borderValue=0)
    area = cv2.countNonZero(region)
    if not area:
        info["motivo"] = "El margen deja el tapete sin zona útil. Reduce el margen interior."
        return region, info
    info.update(detectado=True, area_px2=area, proporcion=area / total,
                motivo="Mayor región verde rellena; exterior excluido del análisis.")
    return region, info


def _validar_imagen(frame):
    if (
        not isinstance(frame, np.ndarray)
        or frame.ndim != 3
        or frame.shape[2] != 3
        or frame.size == 0
        or frame.dtype != np.uint8
    ):
        raise ValueError("La imagen debe ser un array BGR uint8 no vacío, de tres canales.")


def recortar_zoom(frame, factor):
    """Devuelve una vista del recorte central, sin redimensionar ni anotar."""
    _validar_imagen(frame)
    if not isinstance(factor, (int, float, np.number)) or not math.isfinite(factor) or factor < 1:
        raise ValueError("El factor de zoom debe ser un número finito igual o mayor que 1.")
    alto, ancho = frame.shape[:2]
    ancho_recorte = max(1, round(ancho / factor))
    alto_recorte = max(1, round(alto / factor))
    x = (ancho - ancho_recorte) // 2
    y = (alto - alto_recorte) // 2
    return frame[y:y + alto_recorte, x:x + ancho_recorte]


def procesar_imagen(frame, valores):
    """Aplica el mismo pipeline del calibrador y devuelve imágenes y objetos.

    ``valores`` contiene h_min/h_max, s_min/s_max, v_min/v_max, suavizado,
    kernel, apertura, cierre, area_min y zoom (porcentaje, 100 equivale a 1x).
    No se modifican ni la imagen de entrada ni el diccionario de ajustes.

    Los IDs se asignan por centroide X creciente, con Y como desempate; son
    identificadores de esta escena, no identidades persistentes ni clases.
    El centroide se calcula por momentos del contorno exterior. Para contornos
    degenerados de área cero se usa el centro de su caja mínima. La orientación
    es la del eje largo de la caja mínima en [0, 180), medida en coordenadas de
    imagen (X hacia la derecha, Y hacia abajo); un cuadrado no tiene eje único.
    """
    _validar_imagen(frame)
    valores = validar_configuracion(valores)
    encuadre = recortar_zoom(frame, valores["zoom"] / 100.0)
    alto, ancho = encuadre.shape[:2]
    alto_procesado = max(1, int(alto * (ANCHO_PROCESADO / ancho)))
    imagen = cv2.resize(encuadre, (ANCHO_PROCESADO, alto_procesado))

    suavizado = valores["suavizado"]
    blurred = cv2.GaussianBlur(imagen, (suavizado, suavizado), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    verde_bajo = np.array([valores["h_min"], valores["s_min"], valores["v_min"]])
    verde_alto = np.array([valores["h_max"], valores["s_max"], valores["v_max"]])
    verde = cv2.inRange(hsv, verde_bajo, verde_alto)
    region, tapete = localizar_tapete(verde, valores["margen_tapete"], valores["limitar_tapete"])
    mascara_bruta = cv2.bitwise_and(cv2.bitwise_not(verde), region)
    avisos = []
    if tapete["activo"] and not tapete["detectado"]:
        avisos.append(tapete["motivo"] + " No se analizan objetos hasta localizarlo.")

    tam_kernel = valores["kernel"]
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (tam_kernel, tam_kernel))
    mascara = mascara_bruta.copy()
    if valores["apertura"] > 0:
        mascara = cv2.morphologyEx(
            mascara, cv2.MORPH_OPEN, kernel, iterations=valores["apertura"]
        )
    if valores["cierre"] > 0:
        mascara = cv2.morphologyEx(
            mascara, cv2.MORPH_CLOSE, kernel, iterations=valores["cierre"]
        )
    # La morfología puede extender píxeles hacia fuera: volver a limitar al final.
    mascara = cv2.bitwise_and(mascara, region)
    borde_region = cv2.subtract(region, cv2.erode(
        region, np.ones((3, 3), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0,
    )) if tapete["activo"] else np.zeros_like(region)

    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    objetos = []
    descartados_borde = 0
    for contorno in contornos:
        area = cv2.contourArea(contorno)
        puntos = contorno.reshape(-1, 2)
        if np.any(borde_region[puntos[:, 1], puntos[:, 0]]):
            cv2.drawContours(mascara, [contorno], -1, 0, cv2.FILLED)
            if area >= valores["area_min"]:
                descartados_borde += 1
            continue
        if area < valores["area_min"]:
            continue
        perimetro = cv2.arcLength(contorno, True)
        rect = cv2.minAreaRect(contorno)
        (cx_caja, cy_caja), (ancho_caja, alto_caja), angulo = rect
        largo, corto = max(ancho_caja, alto_caja), min(ancho_caja, alto_caja)
        hull = cv2.convexHull(contorno)
        area_hull = cv2.contourArea(hull)
        momentos = cv2.moments(contorno)
        cx = momentos["m10"] / momentos["m00"] if momentos["m00"] else cx_caja
        cy = momentos["m01"] / momentos["m00"] if momentos["m00"] else cy_caja
        orientacion = (angulo if ancho_caja >= alto_caja else angulo + 90.0) % 180.0
        objetos.append({
            "contorno": contorno,
            "hull": hull,
            "caja": np.int32(cv2.boxPoints(rect)),
            "area_px2": area,
            "perimetro_px": perimetro,
            "circularidad": 4 * np.pi * area / perimetro**2 if perimetro > 0 else 0.0,
            "relacion_aspecto": largo / corto if corto > 0 else 0.0,
            "solidez": area / area_hull if area_hull > 0 else 0.0,
            "centroide_x_px": cx,
            "centroide_y_px": cy,
            "largo_px": largo,
            "corto_px": corto,
            "orientacion_grados": orientacion,
            **caracteristicas_forma(contorno, rect),
        })

    objetos.sort(key=lambda objeto: (objeto["centroide_x_px"], objeto["centroide_y_px"]))
    for identificador, objeto in enumerate(objetos, start=1):
        objeto["id"] = identificador
    if descartados_borde:
        avisos.append(f"Se excluyen {descartados_borde} detecciones que llegan al límite de la zona útil: "
                      "pueden estar recortadas. Separa las herramientas del borde o reduce el margen.")
    return {
        "imagen": imagen,
        "encuadre": encuadre,
        "mascara_bruta": mascara_bruta,
        "mascara": mascara,
        "mascara_tapete": region,
        "tapete": tapete,
        "avisos": avisos,
        "descartados_borde": descartados_borde,
        "version_procesado": VERSION_PROCESADO,
        "version_caracteristicas": VERSION_CARACTERISTICAS,
        "objetos": objetos,
    }


def _ascii(texto):
    """La fuente integrada de OpenCV no dibuja Unicode correctamente."""
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "replace").decode("ascii").replace("?", "")


def _texto_ajustado(texto, ancho, escala=0.4):
    texto = _ascii(texto)
    if cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, 1)[0][0] <= ancho:
        return texto
    while texto and cv2.getTextSize(texto + "...", cv2.FONT_HERSHEY_SIMPLEX, escala, 1)[0][0] > ancho:
        texto = texto[:-1]
    return texto + "..."


def _posicion_id(cx, cy, ancho, alto, ocupados, ancho_imagen, alto_imagen):
    """Busca una posición próxima al centroide sin solapar otros identificadores."""
    candidatos = [(cx - ancho // 2, cy - alto // 2)]
    for distancia in range(1, 9):
        dx, dy = distancia * (ancho + 6), distancia * (alto + 6)
        candidatos.extend([
            (cx - ancho // 2, cy - alto // 2 - dy),
            (cx - ancho // 2, cy - alto // 2 + dy),
            (cx - ancho // 2 - dx, cy - alto // 2),
            (cx - ancho // 2 + dx, cy - alto // 2),
        ])
    # Respaldo para escenas densas: buscar una celda libre en toda la imagen.
    candidatos.extend(
        (x, y)
        for y in range(2, max(3, alto_imagen - alto), alto + 6)
        for x in range(2, max(3, ancho_imagen - ancho), ancho + 6)
    )
    for x, y in candidatos:
        x = max(0, min(int(x), ancho_imagen - ancho))
        y = max(0, min(int(y), alto_imagen - alto))
        caja = (x, y, x + ancho, y + alto)
        if all(caja[2] + 3 < a or caja[0] - 3 > c or caja[3] + 3 < b or caja[1] - 3 > d for a, b, c, d in ocupados):
            ocupados.append(caja)
            return caja
    # Solo es alcanzable si no queda espacio físico para todos los IDs.
    raise ValueError("No hay espacio en la imagen para dibujar todos los IDs sin solaparlos.")


def dibujar_resultado(resultado, etiquetas=None, telemetria=True):
    """Devuelve una imagen BGR anotada nueva; no modifica el resultado original.

    Las etiquetas son un mapping opcional ``id -> nombre`` introducido por una
    persona; se indican como manuales, nunca como predicciones. La telemetría se
    coloca en una tabla inferior, sin textos sobre las herramientas. Si se
    desactiva pero hay etiquetas, se mantiene una leyenda inferior de nombres.
    """
    imagen = resultado["imagen"].copy()
    _validar_imagen(imagen)
    objetos = resultado["objetos"]
    etiquetas = etiquetas or {}
    fuente = cv2.FONT_HERSHEY_SIMPLEX
    ocupados = []
    if resultado.get("tapete", {}).get("activo") and resultado["tapete"]["detectado"]:
        region = resultado["mascara_tapete"]
        imagen[region == 0] = (imagen[region == 0] * .35).astype(np.uint8)
        bordes, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(imagen, bordes, -1, (255, 220, 0), 1)
    for objeto in objetos:
        cv2.drawContours(imagen, [objeto["contorno"]], -1, (0, 255, 0), 2)
        cv2.drawContours(imagen, [objeto["hull"]], -1, (255, 150, 0), 1)
        cv2.drawContours(imagen, [objeto["caja"]], 0, (0, 0, 255), 2)

    for objeto in objetos:
        texto = str(objeto["id"])
        (ancho_texto, alto_texto), base = cv2.getTextSize(texto, fuente, 0.65, 2)
        ancho, alto = ancho_texto + 14, alto_texto + base + 12
        cx, cy = round(objeto["centroide_x_px"]), round(objeto["centroide_y_px"])
        x1, y1, x2, y2 = _posicion_id(cx, cy, ancho, alto, ocupados, imagen.shape[1], imagen.shape[0])
        cv2.line(imagen, (cx, cy), ((x1 + x2) // 2, (y1 + y2) // 2), (255, 255, 255), 1, cv2.LINE_AA)
        cv2.rectangle(imagen, (x1, y1), (x2, y2), (22, 22, 22), cv2.FILLED)
        cv2.rectangle(imagen, (x1, y1), (x2, y2), (255, 255, 255), 1)
        cv2.putText(imagen, texto, (x1 + 7, y1 + alto_texto + 5), fuente, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

    if not telemetria and not etiquetas:
        return imagen

    fila_alto = 27
    panel = np.full((88 + fila_alto * len(objetos), imagen.shape[1], 3), (30, 33, 36), dtype=np.uint8)
    cv2.putText(panel, f"{len(objetos)} objetos | IDs por posicion en esta imagen", (14, 23), fuente, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(panel, "Etiquetas manuales, sin clasificacion automatica. Medidas del contorno exterior.", (14, 44), fuente, 0.4, (190, 195, 200), 1, cv2.LINE_AA)
    columnas = [(14, 36), (60, 215), (285, 85), (380, 82), (472, 65), (547, 65), (622, 65), (697, 90)]
    cabeceras = ["ID", "Etiqueta manual", "Area px2", "Perim. px", "AR", "Sol.", "Circ.", "Ang. grados"]
    if not telemetria:
        columnas = [(14, 36), (60, imagen.shape[1] - 74)]
        cabeceras = cabeceras[:2]
    for (x, _), titulo in zip(columnas, cabeceras):
        cv2.putText(panel, titulo, (x, 69), fuente, 0.4, (100, 220, 240), 1, cv2.LINE_AA)
    for indice, objeto in enumerate(objetos):
        y = 93 + indice * fila_alto
        celdas = [
            str(objeto["id"]), etiquetas.get(objeto["id"], "Sin etiquetar"),
            f'{objeto["area_px2"]:.1f}', f'{objeto["perimetro_px"]:.1f}',
            f'{objeto["relacion_aspecto"]:.2f}', f'{objeto["solidez"]:.3f}',
            f'{objeto["circularidad"]:.3f}', f'{objeto["orientacion_grados"]:.1f}',
        ]
        cv2.line(panel, (14, y + 8), (imagen.shape[1] - 14, y + 8), (55, 59, 63), 1)
        for (x, ancho), valor in zip(columnas, celdas):
            cv2.putText(panel, _texto_ajustado(valor, ancho), (x, y), fuente, 0.4, (235, 235, 235), 1, cv2.LINE_AA)
    return np.vstack((imagen, panel))
