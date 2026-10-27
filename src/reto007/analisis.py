"""Reúne medidas reproducibles con etiquetas manuales confirmadas.

Solo lee las sesiones. Recalcula los descriptores desde sus píxeles y ajustes;
el CSV antiguo nunca se usa como fuente de medidas. Cada foto conserva su
revisión más reciente, incluso cuando esta necesita revisión. Los recortes y
originales de una captura se agrupan, sin tratarlos como escenas independientes.
"""

from collections import Counter
import json
import math
from pathlib import Path
import re

import cv2
import numpy as np

from configuracion import BASE, cargar_configuracion, validar_configuracion
from etiquetado import (
    _leer_anotaciones, _nombres_validos, firma_deteccion, huella_imagen,
)
from vision import procesar_imagen


_CAPTURA = re.compile(r"(?:escena|original)_(\d{8}_\d{6}_\d{6})(?=[_.]|$)")
_HASH = re.compile(r"[0-9a-f]{64}")
_FOTOGRAMA = re.compile(r"fotograma_video_([0-9a-f]{64})_(\d{6,})_\d{8}_\d{6}_\d{6}_[0-9a-f]{8}\.png")


def _captura_video(ruta, huella):
    """Agrupa por vídeo, validando procedencia sin trasladar etiquetas.

    Las primeras extracciones no incluían huella de imagen: se comprueban sus
    píxeles originales. Las nuevas también conservan el hash del clip en el
    nombre para poder agrupar sesiones aunque se borre el PNG original.
    Un sidecar presente pero inválido nunca se rescata a partir de su nombre.
    """
    sidecar = ruta.with_suffix(".origen.json")
    if not sidecar.is_file():
        nombre = _FOTOGRAMA.fullmatch(ruta.name)
        return "video_" + nombre.group(1) if nombre else None
    try:
        datos = json.loads(sidecar.read_text(encoding="utf-8"))
        if (not isinstance(datos, dict) or datos.get("tipo") != "fotograma_video"
                or type(datos.get("version")) is not int or datos.get("version") != 1):
            return None
        clip, indice, tiempo = datos.get("huella_video"), datos.get("indice"), datos.get("tiempo_s")
        if not isinstance(clip, str) or not _HASH.fullmatch(clip):
            return None
        if type(indice) is not int or indice < 0:
            return None
        if (type(tiempo) not in (int, float) or not math.isfinite(tiempo) or tiempo < 0
                or not isinstance(datos.get("video"), str) or not datos["video"].strip()):
            return None
        nombre = _FOTOGRAMA.fullmatch(ruta.name)
        if nombre and (nombre.group(1) != clip or int(nombre.group(2)) != indice):
            return None
        if "huella_imagen" in datos:
            if datos["huella_imagen"] != huella:
                return None
        else:
            original = cv2.imread(str(ruta)) if ruta.is_file() else None
            if original is None or huella_imagen(original) != huella:
                return None
        return "video_" + clip
    except (OSError, ValueError, TypeError, cv2.error):
        return None


def identificar_captura(origen, huella, base=BASE):
    """Agrupa originales/recortes y fotogramas del mismo vídeo.

    Una sesión reabierta y guardada otra vez puede apuntar a otra copia llamada
    ``imagen_origen.png``. Se sigue su procedencia, sin usar etiquetas anteriores
    ni confundir la fecha de guardado con la de adquisición.
    """
    visitados = set()
    raiz = (Path(base).expanduser().resolve() / "resultados").resolve()
    for _ in range(32):
        ruta = Path(origen).expanduser().resolve()
        video = _captura_video(ruta, huella)
        if video is not None:
            return video
        # Una extracción reconocible con procedencia rota no debe convertirse
        # en captura fotográfica por una fecha incidental del nombre del clip.
        if ruta.with_suffix(".origen.json").is_file() or _FOTOGRAMA.fullmatch(ruta.name):
            return "imagen_" + huella[:16]
        if ruta.name != "imagen_origen.png" or not ruta.is_relative_to(raiz):
            coincidencia = _CAPTURA.search(str(origen))
            if coincidencia:
                return coincidencia.group(1)
            break
        if ruta in visitados:
            break
        visitados.add(ruta)
        try:
            anteriores, _, _ = _leer_anotaciones(ruta.parent / "anotaciones.json")
            if anteriores["huella_imagen"] != huella or not anteriores.get("imagen_original"):
                break
            origen = anteriores["imagen_original"]
        except (OSError, ValueError, TypeError, KeyError):
            break
    return "imagen_" + huella[:16]


def _version_caracteristicas(resultado):
    # Los descriptores pueden evolucionar sin invalidar la identidad del contorno.
    if resultado.get("version_caracteristicas"):
        return str(resultado["version_caracteristicas"])
    try:
        from geometria import VERSION_CARACTERISTICAS
    except ImportError:
        return "medidas-basicas"
    return VERSION_CARACTERISTICAS


def _filas(resultado, nombres, revisadas, origen, sesion, imagen, valores, firma,
           huella, actual=False, base=BASE):
    filas = []
    captura = identificar_captura(origen, huella, base)
    for objeto in resultado["objetos"]:
        if objeto["id"] not in revisadas:
            continue
        fila = {
            "id": objeto["id"], "nombre_real": nombres[objeto["id"]],
            "fuente": str(origen), "sesion": str(sesion),
            "captura": captura,
            "huella_imagen": huella, "firma_deteccion": firma,
            "actual": bool(actual), "zoom": valores["zoom"],
            "ancho_origen_px": int(imagen.shape[1]),
            "alto_origen_px": int(imagen.shape[0]),
            "version_caracteristicas": _version_caracteristicas(resultado),
        }
        for clave, valor in objeto.items():
            if clave == "id" or isinstance(valor, (bool, np.bool_)):
                continue
            if isinstance(valor, (int, float, np.integer, np.floating)):
                if not math.isfinite(float(valor)):
                    raise ValueError(f"La medida {clave} del objeto {objeto['id']} no es finita.")
                fila[clave] = float(valor)
            elif clave in ("perfil_ancho", "perfil_posiciones"):
                perfil = np.asarray(valor, dtype=float)
                if perfil.ndim != 1 or not np.isfinite(perfil).all():
                    raise ValueError(f"El {clave} del objeto {objeto['id']} no es válido.")
                fila[clave] = perfil.tolist()
        filas.append(fila)
    return filas


def _validar_actual(actual):
    imagen = actual["imagen"]
    huella = huella_imagen(imagen)
    valores = validar_configuracion(actual["valores"])
    resultado = procesar_imagen(imagen, valores)
    firma = firma_deteccion(imagen, valores, resultado)
    if actual.get("firma") != firma:
        raise ValueError("La detección actual ha cambiado; vuelve a confirmar sus etiquetas.")
    nombres = _nombres_validos(actual["etiquetas"], resultado["objetos"])
    revisadas_crudas = actual["revisadas"]
    if not isinstance(revisadas_crudas, (set, frozenset, list, tuple)):
        raise ValueError("Las revisiones actuales deben ser una colección de IDs.")
    if (any(type(i) is not int for i in revisadas_crudas)
            or len(revisadas_crudas) != len(set(revisadas_crudas))):
        raise ValueError("Las revisiones actuales contienen IDs inválidos o repetidos.")
    revisadas = set(revisadas_crudas)
    if not revisadas <= set(nombres) or any(not nombres[i] for i in revisadas):
        raise ValueError("Hay una revisión actual sin objeto o sin etiqueta.")
    return imagen, huella, valores, resultado, firma, nombres, revisadas


def reunir_datos(base=BASE, actual=None):
    """Devuelve filas, avisos, exclusiones y resumen sin escribir archivos.

    ``actual`` es opcional: {origen, imagen, valores, etiquetas, revisadas, firma}.
    Sus confirmaciones sustituyen a cualquier sesión guardada con los mismos
    píxeles, también cuando se han dejado todas pendientes. La firma debe
    corresponder a la detección recalculada con el procesamiento vigente.

    ``imagenes_unicas`` y ``capturas`` cuentan solo fuentes con alguna etiqueta
    confirmada. ``capturas`` agrupa variantes por nombre de adquisición, pero
    no representa un número de escenas ni de observaciones independientes.
    """
    base = Path(base).expanduser().resolve()
    filas, avisos, exclusiones = [], [], []
    vistos = set()
    resumen = {
        "sesiones_examinadas": 0, "sesiones_utilizadas": 0,
        "sesiones_duplicadas": 0, "sesiones_invalidas": 0,
        "sesiones_desactualizadas": 0, "sesiones_sin_confirmaciones": 0,
        "objetos_pendientes": 0, "objetos_confirmados": 0,
        "imagenes_unicas": 0, "capturas": 0, "clases": 0,
    }

    def excluir(sesion, motivo, tipo):
        exclusiones.append({"sesion": str(sesion), "tipo": tipo, "motivo": motivo})
        resumen["sesiones_" + tipo] += 1

    def incluir(resultado, nombres, revisadas, origen, sesion, imagen, valores,
                firma, huella, es_actual=False):
        nuevas = _filas(resultado, nombres, revisadas, origen, sesion, imagen,
                        valores, firma, huella, es_actual, base)
        resumen["objetos_pendientes"] += len(resultado["objetos"]) - len(revisadas)
        if nuevas:
            filas.extend(nuevas)
            resumen["sesiones_utilizadas"] += 1
        else:
            excluir(sesion, "No contiene etiquetas manuales confirmadas.", "sin_confirmaciones")

    if actual is not None:
        resumen["sesiones_examinadas"] += 1
        try:
            # La revisión visible prevalece incluso si está desactualizada.
            vistos.add(huella_imagen(actual["imagen"]))
            imagen, huella, valores, resultado, firma, nombres, revisadas = _validar_actual(actual)
            incluir(resultado, nombres, revisadas, actual["origen"], "Sesión actual",
                    imagen, valores, firma, huella, True)
        except (OSError, ValueError, TypeError, KeyError, cv2.error) as error:
            excluir("Sesión actual", str(error), "invalidas")

    candidatos = []
    for ruta in (base / "resultados").glob("sesion_*/anotaciones.json"):
        try:
            candidatos.append((ruta.stat().st_mtime_ns, str(ruta), ruta))
        except OSError as error:
            resumen["sesiones_examinadas"] += 1
            excluir(ruta.parent, str(error), "invalidas")
    for _, _, ruta in sorted(candidatos, reverse=True):
        sesion = ruta.parent
        resumen["sesiones_examinadas"] += 1
        try:
            imagen = cv2.imread(str(sesion / "imagen_origen.png"))
            if imagen is None:
                raise ValueError("Falta la copia PNG de la fuente o no se puede abrir.")
            huella = huella_imagen(imagen)
            if huella in vistos:
                excluir(sesion, "Otra revisión más reciente usa los mismos píxeles.", "duplicadas")
                continue
            vistos.add(huella)
            datos, nombres, revisadas = _leer_anotaciones(ruta)
            if datos["huella_imagen"] != huella:
                excluir(sesion, "Los píxeles de la fuente han cambiado desde la revisión.", "desactualizadas")
                continue
            valores = cargar_configuracion(sesion / "configuracion.json")
            if valores != validar_configuracion(datos["parametros"]):
                excluir(sesion, "La configuración guardada no coincide con la revisión.", "desactualizadas")
                continue
            resultado = procesar_imagen(imagen, valores)
            firma = firma_deteccion(imagen, valores, resultado)
            if firma != datos["firma_deteccion"]:
                excluir(sesion, "La segmentación o los ajustes han cambiado; confirma de nuevo las etiquetas.",
                        "desactualizadas")
                continue
            if set(nombres) != {o["id"] for o in resultado["objetos"]}:
                raise ValueError("Los IDs anotados no coinciden con la detección reproducida.")
            origen = datos.get("imagen_original") or str(sesion / "imagen_origen.png")
            incluir(resultado, nombres, revisadas, origen, sesion, imagen, valores, firma, huella)
        except (OSError, ValueError, TypeError, KeyError, cv2.error) as error:
            excluir(sesion, str(error), "invalidas")

    # Los paquetes antiguos no prueban que sus etiquetas hayan sido revisadas.
    for ruta in sorted((base / "resultados").glob("*/resumen.json")):
        if not (ruta.parent / "anotaciones.json").exists():
            resumen["sesiones_examinadas"] += 1
            excluir(ruta.parent, "Formato antiguo sin firma verificable ni confirmaciones manuales.", "invalidas")

    resumen.update(
        objetos_confirmados=len(filas),
        imagenes_unicas=len({f["huella_imagen"] for f in filas}),
        capturas=len({f["captura"] for f in filas}),
        clases=len({f["nombre_real"] for f in filas}),
    )
    imagenes_por_captura = {}
    for fila in filas:
        imagenes_por_captura.setdefault(fila["captura"], set()).add(fila["huella_imagen"])
    if any(len(huellas) > 1 for captura, huellas in imagenes_por_captura.items()
           if not captura.startswith("video_")):
        avisos.append("Hay originales y recortes de la misma captura: conservan sus medidas, "
                      "pero no cuentan como observaciones independientes.")
    if any(captura.startswith("video_") for captura in imagenes_por_captura):
        avisos.append("Los fotogramas del mismo vídeo se agrupan como una captura. "
                      "Sus medidas siguen disponibles, pero no son observaciones independientes "
                      "ni deben repartirse entre ajuste de reglas y evaluación.")
    if filas:
        avisos.append("Las capturas pueden compartir la misma colocación de herramientas. "
                      "Estos datos sirven para explorar reglas; no son una evaluación con escenas nuevas.")
        avisos.append("El área y las longitudes en píxeles cambian con el zoom y el encuadre. "
                      "Para comparar fotos utiliza primero proporciones y perfiles normalizados.")
    if resumen["objetos_pendientes"]:
        avisos.append(f"Se excluyen {resumen['objetos_pendientes']} objetos pendientes de confirmar.")
    for tipo, cantidad in Counter(e["tipo"] for e in exclusiones).items():
        if tipo in ("invalidas", "desactualizadas"):
            avisos.append(f"Se excluyen {cantidad} sesiones {tipo.replace('invalidas', 'no válidas')}; "
                          "consulta los motivos antes de incorporarlas al análisis.")
    return {"filas": filas, "avisos": avisos, "exclusiones": exclusiones, "resumen": resumen}
