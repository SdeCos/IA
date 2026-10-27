"""Vídeos locales: lectura reproducible, fotogramas y exportación sin cámara.

El vídeo se conserva limpio. Cada fotograma reutiliza vision.procesar_imagen y
las pistas son asociaciones geométricas temporales, no clases de herramienta.
"""

import csv
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
from numbers import Integral
from pathlib import Path
import tempfile
import uuid

import cv2

from configuracion import BASE, cargar_configuracion, guardar_configuracion, validar_configuracion
from detector import METRICAS
from etiquetado import huella_imagen
from seguimiento import SeguidorObjetos
from vision import VERSION_PROCESADO, procesar_imagen
from geometria import VERSION_CARACTERISTICAS
from clasificacion import VERSION_CLASIFICADOR, GRUPOS_DESARROLLO, clasificar_objetos, snapshot_reglas


EXTENSIONES_VIDEO = {".avi", ".mp4", ".mov", ".mkv", ".m4v"}
VERSION_VIDEO = 2
COLUMNAS_CLASIFICACION = ("clase_predicha", "estado_clasificacion", "regla", "explicacion", "ruta_decision", "version_clasificador")


def es_video_desarrollo(info):
    return "video_" + info["huella"] in GRUPOS_DESARROLLO


def conteo_fotograma(objetos):
    """Cuenta únicamente detecciones presentes; no acumula pistas anteriores."""
    conteo = {}
    for objeto in objetos:
        clase = objeto["clase_predicha"] if objeto["estado_clasificacion"] == "identificada" else "Desconocido"
        conteo[clase] = conteo.get(clase, 0) + 1
    return dict(sorted(conteo.items()))


def listar_videos(base=BASE):
    carpeta = Path(base) / "videos"
    return sorted((p for p in carpeta.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONES_VIDEO
                   and not any(parte.startswith(".") for parte in p.relative_to(carpeta).parts)),
                  key=lambda p: (p.stat().st_mtime_ns, str(p)), reverse=True) if carpeta.exists() else []


def _ruta_video(ruta):
    if not isinstance(ruta, (str, Path)):
        raise ValueError("Se necesita la ruta de un vídeo local; no un índice de cámara.")
    origen = Path(ruta).expanduser().resolve()
    if not origen.is_file():
        raise ValueError(f"No existe el vídeo: {origen}")
    return origen


@lru_cache(maxsize=32)
def _huella(ruta, tamano, modificado_ns, cambio_ns, inode):
    digest = hashlib.sha256()
    with Path(ruta).open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def _abrir(ruta):
    captura = cv2.VideoCapture(str(ruta))
    if not captura.isOpened():
        captura.release()
        raise ValueError(f"No se puede abrir el vídeo: {ruta.name}. Prueba MP4/H.264 o AVI/MJPEG.")
    return captura


def inspeccionar_video(ruta):
    origen = _ruta_video(ruta)
    captura = _abrir(origen)
    try:
        fps, total = captura.get(cv2.CAP_PROP_FPS), captura.get(cv2.CAP_PROP_FRAME_COUNT)
        if not math.isfinite(fps) or fps <= 0 or not math.isfinite(total) or total < 1:
            raise ValueError("El vídeo no proporciona FPS y número de fotogramas válidos. Convierte a MP4 o AVI.")
        ok, imagen = captura.read()
        if not ok or imagen is None:
            raise ValueError("El vídeo se abre pero no se puede decodificar su primer fotograma.")
        alto, ancho = imagen.shape[:2]
    finally:
        captura.release()
    estado = origen.stat()
    return {"ruta": str(origen), "huella": _huella(str(origen), estado.st_size, estado.st_mtime_ns,
                                                 estado.st_ctime_ns, estado.st_ino),
            "fps": float(fps), "fotogramas": int(round(total)), "ancho": ancho, "alto": alto,
            "duracion_s": int(round(total)) / fps,
            "avisos": ["Tiempos nominales: índice / FPS. En vídeos externos de FPS variable pueden diferir del tiempo real."]}


def configuracion_para_video(ruta):
    origen = _ruta_video(ruta)
    propia = origen.with_suffix(".json")
    carpeta = origen.parent / "configuracion.json"
    return cargar_configuracion(propia if propia.is_file() else carpeta if carpeta.is_file() else None)


def _indice_valido(indice, total):
    if isinstance(indice, bool) or not isinstance(indice, Integral) or not 0 <= indice < total:
        raise ValueError(f"El fotograma debe ser un entero entre 0 y {total - 1}.")
    return int(indice)


def _leer_en(captura, indice):
    # OpenCV suele buscar desde un keyframe y decodificar hasta el índice pedido.
    # Si el backend no confirma la posición, leer desde el principio evita que
    # una captura de revisión quede asociada a otro número de fotograma.
    posicionada = captura.set(cv2.CAP_PROP_POS_FRAMES, indice)
    posicion = captura.get(cv2.CAP_PROP_POS_FRAMES)
    if not posicionada or not math.isfinite(posicion) or abs(posicion - indice) > .1:
        if not captura.set(cv2.CAP_PROP_POS_FRAMES, 0):
            raise ValueError("El formato no permite buscar fotogramas con posición comprobada.")
        for _ in range(indice):
            if not captura.grab():
                raise ValueError(f"No se puede alcanzar el fotograma {indice}; el vídeo está incompleto.")
    ok, imagen = captura.read()
    posicion = captura.get(cv2.CAP_PROP_POS_FRAMES)
    if not ok or imagen is None:
        raise ValueError(f"No se puede leer el fotograma {indice}; el vídeo puede estar incompleto.")
    if not math.isfinite(posicion) or abs(posicion - (indice + 1)) > .1:
        raise ValueError("El decodificador no confirma el índice del fotograma. Convierte el vídeo a AVI/MJPEG.")
    return imagen


def leer_fotograma(ruta, indice):
    info = inspeccionar_video(ruta)
    indice = _indice_valido(indice, info["fotogramas"])
    captura = _abrir(Path(info["ruta"]))
    try:
        imagen = _leer_en(captura, indice)
    finally:
        captura.release()
    return imagen, {"indice": indice, "tiempo_s": indice / info["fps"], "huella_video": info["huella"]}


def _json(ruta, datos):
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def exportar_fotograma(ruta, indice, valores, base=BASE / "capturas"):
    """Exporta PNG completo, ajustes (incluido zoom) y .origen.json de trazabilidad.

    El PNG no se recorta ni anota; al abrirlo se aplica el zoom exactamente una vez.
    No hereda etiquetas ni transforma una pista temporal en etiqueta confirmada.
    """
    valores = validar_configuracion(valores)
    imagen, posicion = leer_fotograma(ruta, indice)
    carpeta = Path(base).expanduser().resolve()
    carpeta.mkdir(parents=True, exist_ok=True)
    # Conservar el clip de procedencia incluso si luego se traslada la sesión
    # sin la captura/sidecar originales. Este grupo no confirma etiquetas.
    nombre = f"fotograma_video_{posicion['huella_video']}_{indice:06d}_{datetime.now():%Y%m%d_%H%M%S_%f}_{uuid.uuid4().hex[:8]}"
    destino = carpeta / f"{nombre}.png"
    with tempfile.TemporaryDirectory(prefix=".fotograma_", dir=carpeta) as temporal:
        preparacion = Path(temporal)
        if not cv2.imwrite(str(preparacion / destino.name), imagen):
            raise OSError("No se pudo guardar la imagen del fotograma.")
        guardar_configuracion(valores, preparacion / f"{nombre}.json")
        _json(preparacion / f"{nombre}.origen.json", {
            "version": 1, "tipo": "fotograma_video", "video": str(_ruta_video(ruta)),
            **posicion, "huella_imagen": huella_imagen(imagen), "imagen_limpia_completa": True,
        })
        publicados = []
        try:
            # El enlace exclusivo impide sobrescribir incluso ante una colisión.
            for archivo in preparacion.iterdir():
                final = carpeta / archivo.name
                final.hardlink_to(archivo)
                publicados.append(final)
        except OSError:
            for final in publicados:
                final.unlink(missing_ok=True)
            raise
    return destino


def exportar_video(ruta, valores, salida=None, inicio=0, fin=None, paso=1, progreso=None):
    """Exporta un intervalo inclusivo con dos CSV y parámetros reproducibles.

    ``salida`` es una carpeta NUEVA; si se omite crea una bajo resultados/videos.
    ``progreso(actual,total)`` se invoca tras cada fotograma procesado. Aunque
    ``paso`` seleccione una muestra de cada N, se procesan los intermedios para
    mantener continuidad temporal. No escribe etiquetas ni calcula aciertos.
    """
    valores = validar_configuracion(valores)
    info = inspeccionar_video(ruta)
    inicio = _indice_valido(inicio, info["fotogramas"])
    fin = info["fotogramas"] - 1 if fin is None else _indice_valido(fin, info["fotogramas"])
    if fin < inicio:
        raise ValueError("El final del intervalo no puede ser anterior al inicio.")
    if isinstance(paso, bool) or not isinstance(paso, Integral) or paso < 1:
        raise ValueError("El paso debe ser un entero positivo.")
    destino = (Path(salida).expanduser().resolve() if salida is not None else
               BASE / "resultados" / "videos" / f"{Path(ruta).stem}_{datetime.now():%Y%m%d_%H%M%S_%f}_{uuid.uuid4().hex[:8]}")
    if destino.exists():
        raise ValueError(f"La carpeta de salida ya existe: {destino}. Elige una nueva.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    captura = _abrir(Path(info["ruta"]))
    try:
        with tempfile.TemporaryDirectory(prefix=".video_", dir=destino.parent) as temporal:
            preparacion = Path(temporal) / "resultado"
            preparacion.mkdir()
            guardar_configuracion(valores, preparacion / "configuracion.json")
            seguidor = SeguidorObjetos()
            muestras = filas = sin_tapete = ambiguas = 0
            with (preparacion / "caracteristicas.csv").open("w", newline="", encoding="utf-8-sig") as archivo, \
                    (preparacion / "fotogramas.csv").open("w", newline="", encoding="utf-8-sig") as escenas:
                csv_objetos = csv.DictWriter(archivo, fieldnames=("fotograma", "tiempo_s", "id", "id_pista", "estado_pista", *COLUMNAS_CLASIFICACION, *METRICAS), delimiter=";")
                csv_frames = csv.DictWriter(escenas, fieldnames=("fotograma", "tiempo_s", "objetos", "conteo_predicho_json", "tapete_detectado", "descartados_borde", "avisos"), delimiter=";")
                csv_objetos.writeheader()
                csv_frames.writeheader()
                imagen = _leer_en(captura, inicio)
                for indice in range(inicio, fin + 1):
                    if indice != inicio:
                        ok, imagen = captura.read()
                        if not ok or imagen is None:
                            raise ValueError(f"El vídeo termina antes del fotograma {indice}. No se publica una exportación incompleta.")
                    resultado = procesar_imagen(imagen, valores)
                    objetos = clasificar_objetos(seguidor.actualizar(resultado["objetos"], indice))
                    if (indice - inicio) % paso == 0:
                        muestras += 1
                        sin_tapete += int(resultado["tapete"]["activo"] and not resultado["tapete"]["detectado"])
                        tiempo = f"{indice / info['fps']:.6f}"
                        csv_frames.writerow({"fotograma": indice, "tiempo_s": tiempo, "objetos": len(objetos),
                                             "conteo_predicho_json": json.dumps(conteo_fotograma(objetos), ensure_ascii=False, sort_keys=True),
                                             "tapete_detectado": int(resultado["tapete"]["detectado"]),
                                             "descartados_borde": resultado["descartados_borde"],
                                             "avisos": " | ".join(resultado["avisos"])})
                        for objeto in objetos:
                            filas += 1
                            ambiguas += int(objeto["estado_pista"] == "ambigua")
                            csv_objetos.writerow({"fotograma": indice, "tiempo_s": tiempo,
                                                  "id": objeto["id"], "id_pista": objeto["id_pista"],
                                                  "estado_pista": objeto["estado_pista"],
                                                  **{k: objeto[k] for k in COLUMNAS_CLASIFICACION if k != "ruta_decision"},
                                                  "ruta_decision": json.dumps(objeto["ruta_decision"], ensure_ascii=False),
                                                  **{k: f"{objeto[k]:.6f}" for k in METRICAS}})
                    if progreso is not None:
                        progreso(indice - inicio + 1, fin - inicio + 1)
            _json(preparacion / "resumen.json", {
                "version": VERSION_VIDEO, "tipo": "deteccion_clasificacion_y_seguimiento_video", "creada_utc": datetime.now(timezone.utc).isoformat(),
                "video": info, "inicio": inicio, "fin": fin, "paso": int(paso),
                "fotogramas_procesados": fin - inicio + 1, "fotogramas_exportados": muestras,
                "filas_objetos": filas, "muestras_sin_tapete": sin_tapete, "asociaciones_ambiguas_exportadas": ambiguas,
                "version_procesado": VERSION_PROCESADO, "version_caracteristicas": VERSION_CARACTERISTICAS,
                "seguimiento": {"distancia_maxima_px": 80, "tolerancia_perdidos": 5,
                                "descripcion": "Centroides y área; sin identidad garantizada durante cruces u oclusiones."},
                "clasificacion": True, "etiquetas_confirmadas": False,
                "version_clasificador": VERSION_CLASIFICADOR, "reglas": snapshot_reglas(),
                "video_usado_para_desarrollo": es_video_desarrollo(info), "evaluacion_independiente": False,
                "nota": "Las clases son predicciones provisionales por reglas manuales, no etiquetas confirmadas. "
                        "Cada conteo corresponde solo a ese fotograma. Los ID locales pueden cambiar de orden; "
                        "id_pista es temporal. El vídeo original se identifica por SHA-256 y no se modifica.",
            })
            # Crear el destino de forma exclusiva antes de publicar los archivos.
            destino.mkdir(exist_ok=False)
            publicados = []
            try:
                for archivo in preparacion.iterdir():
                    final = destino / archivo.name
                    final.hardlink_to(archivo)
                    publicados.append(final)
            except OSError:
                for final in publicados:
                    final.unlink(missing_ok=True)
                destino.rmdir()
                raise
    finally:
        captura.release()
    return destino
