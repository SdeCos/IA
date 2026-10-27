"""Persistencia de etiquetas manuales para la web, sin cámaras ni interfaz.

Un ID es una posición dentro de una detección. Solo una coincidencia exacta de
fuente, parámetros, máscara y contornos permite recuperar una revisión previa.
Las etiquetas antiguas sin esa evidencia se ofrecen siempre como propuestas.
"""

import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

import cv2
import numpy as np

from configuracion import BASE, cargar_configuracion, validar_configuracion
from catalogo import CLASES_PREDETERMINADAS, normalizar_nombre
from detector import exportar_resultado, leer_etiquetas, validar_etiquetas
from vision import ANCHO_PROCESADO, VERSION_PROCESADO, procesar_imagen


# Conserva la API anterior para programas que importan los seis nombres iniciales.
CLASES = CLASES_PREDETERMINADAS
VERSION_ETIQUETADO = 2  # Nombres personalizados válidos; sin lista cerrada.


def _actualizar_array(firma, array):
    firma.update(json.dumps([str(array.dtype), list(array.shape)]).encode("ascii"))
    firma.update(np.ascontiguousarray(array).tobytes())


def huella_imagen(imagen):
    """Identifica los píxeles BGR, independientemente del nombre o formato PNG/JPG."""
    if (not isinstance(imagen, np.ndarray) or imagen.dtype != np.uint8
            or imagen.ndim != 3 or imagen.shape[2] != 3 or not imagen.size):
        raise ValueError("La fuente debe ser una imagen BGR uint8 de tres canales.")
    firma = hashlib.sha256(b"reto007-fuente-v1\0")
    _actualizar_array(firma, imagen)
    return firma.hexdigest()


def _objetos_validos(resultado):
    if not isinstance(resultado, dict) or not isinstance(resultado.get("objetos"), list):
        raise ValueError("Falta la lista de objetos de la detección.")
    objetos = resultado["objetos"]
    ids = [o.get("id") for o in objetos]
    if any(type(i) is not int for i in ids) or ids != list(range(1, len(ids) + 1)):
        raise ValueError("Los IDs de la detección deben ser consecutivos y estar ordenados desde 1.")
    return objetos


def firma_deteccion(imagen, valores, resultado):
    """Huella estricta de una detección; cambiar un ajuste invalida la revisión."""
    parametros = validar_configuracion(valores)
    objetos = _objetos_validos(resultado)
    firma = hashlib.sha256(b"reto007-deteccion-v2\0")
    firma.update(VERSION_PROCESADO.encode("ascii"))
    firma.update(huella_imagen(imagen).encode("ascii"))
    firma.update(json.dumps(parametros, sort_keys=True, separators=(",", ":")).encode("ascii"))
    firma.update(str(ANCHO_PROCESADO).encode("ascii"))
    mascara = resultado.get("mascara")
    if not isinstance(mascara, np.ndarray) or mascara.ndim != 2 or mascara.dtype != np.uint8:
        raise ValueError("La detección debe incluir una máscara uint8 de un canal.")
    _actualizar_array(firma, mascara)
    _actualizar_array(firma, resultado["mascara_tapete"])
    alto, ancho = mascara.shape
    for objeto in objetos:
        contorno = objeto.get("contorno")
        if (not isinstance(contorno, np.ndarray) or contorno.ndim != 3
                or contorno.shape[1:] != (1, 2) or not contorno.size
                or not np.issubdtype(contorno.dtype, np.integer)):
            raise ValueError(f"Contorno no válido del objeto {objeto['id']}.")
        puntos = contorno.reshape(-1, 2)
        if (puntos < 0).any() or (puntos[:, 0] >= ancho).any() or (puntos[:, 1] >= alto).any():
            raise ValueError(f"El contorno {objeto['id']} sale de la imagen procesada.")
        firma.update(str(objeto["id"]).encode("ascii"))
        _actualizar_array(firma, contorno.astype("<i4"))
    return firma.hexdigest()


def _nombres_validos(etiquetas, objetos):
    nombres = validar_etiquetas(etiquetas, objetos)
    # Valida el texto original: el strip de validar_etiquetas podría ocultar
    # controles en sus extremos. La ausencia de nombre sigue siendo válida.
    for clave, nombre in (etiquetas or {}).items():
        identificador = int(clave)
        if nombre.strip(" ") == "":
            nombres[identificador] = ""
            continue
        try:
            nombres[identificador] = normalizar_nombre(nombre)
        except ValueError as error:
            raise ValueError(f"Nombre no válido para el objeto {identificador}: {error}") from error
    return nombres


def _revisadas_validas(revisadas, nombres, ids):
    if not isinstance(revisadas, (set, frozenset, list, tuple)):
        raise ValueError("Las revisiones deben ser una colección de IDs.")
    if any(type(i) is not int for i in revisadas) or len(revisadas) != len(set(revisadas)):
        raise ValueError("Las revisiones deben contener IDs enteros no repetidos.")
    revisadas = set(revisadas)
    if not revisadas <= set(ids):
        raise ValueError("Hay revisiones de objetos que no existen en esta detección.")
    if any(not nombres.get(i) for i in revisadas):
        raise ValueError("Un objeto sin nombre no puede marcarse como revisado.")
    return revisadas


def _json(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _leer_anotaciones(ruta):
    datos = leer_etiquetas(ruta)
    if not isinstance(datos, dict) or datos.get("version") != 1:
        raise ValueError("Versión de anotaciones no compatible.")
    for clave in ("huella_imagen", "firma_deteccion"):
        if not isinstance(datos.get(clave), str) or not re.fullmatch(r"[0-9a-f]{64}", datos[clave]):
            raise ValueError(f"Falta una {clave} válida.")
    validar_configuracion(datos.get("parametros"))
    objetos = datos.get("objetos")
    if not isinstance(objetos, list):
        raise ValueError("Faltan los objetos anotados.")
    ids = [objeto.get("id") if isinstance(objeto, dict) else None for objeto in objetos]
    if any(type(i) is not int for i in ids) or ids != list(range(1, len(ids) + 1)):
        raise ValueError("Los IDs de anotaciones son inválidos o están repetidos.")
    nombres = _nombres_validos({o["id"]: o.get("nombre") for o in objetos}, objetos)
    if any(type(objeto.get("revisada")) is not bool for objeto in objetos):
        raise ValueError("Cada anotación debe declarar revisada como true o false.")
    revisadas = _revisadas_validas(
        [o["id"] for o in objetos if o["revisada"]], nombres, ids
    )
    return datos, nombres, revisadas


def _propuestas_actuales(nombres, objetos, avisos):
    ids = {o["id"] for o in objetos}
    descartadas = set(nombres) - ids
    if descartadas:
        avisos.append("Se descartan propuestas de IDs que ya no existen: "
                      + ", ".join(map(str, sorted(descartadas))) + ".")
    return {i: nombre for i, nombre in nombres.items() if i in ids}


def _misma_fuente_legacy(ruta_guardada, origen, huella):
    if not isinstance(ruta_guardada, str) or not ruta_guardada:
        return False
    guardada = Path(ruta_guardada).expanduser().resolve()
    if guardada == origen:
        return True
    if guardada.is_file():
        imagen = cv2.imread(str(guardada))
        return imagen is not None and huella_imagen(imagen) == huella
    return False


def cargar_etiquetas_existentes(origen: Path, imagen, valores, resultado, base=BASE):
    """Carga nombres y estado de revisión; jamás confirma por nombre de archivo.

    Si se abre una copia ``imagen_origen.png`` de una sesión, se prefiere esa
    versión. Para capturas se usa la sesión más reciente de los mismos píxeles.
    Las salidas anteriores al formato web solo aportan propuestas pendientes.
    """
    origen = Path(origen).expanduser().resolve()
    base = Path(base).expanduser().resolve()
    huella = huella_imagen(imagen)
    firma = firma_deteccion(imagen, valores, resultado)
    objetos = _objetos_validos(resultado)
    avisos = []
    vacio = {"etiquetas": {}, "revisadas": set(), "origen": None, "avisos": avisos}
    candidatos = sorted((base / "resultados").glob("*/anotaciones.json"),
                         key=lambda p: (p.stat().st_mtime_ns, str(p)), reverse=True)
    propia = origen.parent / "anotaciones.json"
    if origen.name == "imagen_origen.png" and propia.is_file():
        candidatos = [propia] + [p for p in candidatos if p != propia]
    for ruta in candidatos:
        try:
            datos, nombres, revisadas = _leer_anotaciones(ruta)
            if datos["huella_imagen"] != huella:
                if datos.get("imagen_original") == str(origen) or ruta == propia:
                    avisos.append(f"{ruta.parent.name}: los píxeles de la fuente han cambiado; no se cargan sus etiquetas.")
                continue
            exacta = datos["firma_deteccion"] == firma
            if exacta and set(nombres) != {o["id"] for o in objetos}:
                raise ValueError("La firma coincide pero los IDs anotados no corresponden a la detección.")
            if not exacta:
                avisos.append("Han cambiado los ajustes o la segmentación. Los nombres se conservan "
                              "solo como propuestas por número: los IDs pueden haberse reasignado. "
                              "Revisa todos los objetos antes de confirmarlos.")
                revisadas = set()
            nombres = _propuestas_actuales(nombres, objetos, avisos)
            return {"etiquetas": nombres, "revisadas": revisadas,
                    "origen": str(ruta), "avisos": avisos}
        except (OSError, ValueError, TypeError, KeyError) as error:
            avisos.append(f"No se pueden usar las anotaciones {ruta.parent.name}: {error}")

    # Los archivos anteriores no guardaban una huella verificable. Ninguno se
    # considera revisado, incluso si los valores y el número de objetos coinciden.
    resumenes = sorted((base / "resultados").glob("*/resumen.json"),
                        key=lambda p: (p.stat().st_mtime_ns, str(p)), reverse=True)
    for ruta in resumenes:
        if (ruta.parent / "anotaciones.json").is_file():
            continue
        try:
            resumen = leer_etiquetas(ruta)
            if not isinstance(resumen, dict) or not _misma_fuente_legacy(resumen.get("imagen_origen"), origen, huella):
                continue
            ruta_nombres = ruta.parent / "etiquetas.json"
            if ruta_nombres.is_file():
                nombres_crudos = leer_etiquetas(ruta_nombres)
            else:
                ruta_nombres = ruta.parent / "caracteristicas.csv"
                with ruta_nombres.open(encoding="utf-8-sig", newline="") as archivo:
                    filas = list(csv.DictReader(archivo, delimiter=";"))
                claves = [fila["id"] for fila in filas]
                if len(claves) != len(set(claves)):
                    raise ValueError("Hay IDs duplicados en el CSV.")
                nombres_crudos = {f["id"]: f["nombre_real"] for f in filas}
            numero = resumen.get("numero_objetos")
            if type(numero) is not int or numero < 0:
                raise ValueError("Falta un número de objetos válido en el resumen.")
            nombres = _nombres_validos(nombres_crudos, [{"id": i} for i in range(1, numero + 1)])
            if not any(nombres.values()):
                continue
            ruta_config = ruta.parent / "configuracion.json"
            if ruta_config.is_file() and cargar_configuracion(ruta_config) != validar_configuracion(valores):
                avisos.append("Las propuestas antiguas se guardaron con otros parámetros de segmentación.")
            avisos.append("Etiquetas antiguas sin firma verificable: se cargan como propuestas pendientes. "
                          "Comprueba cada nombre sobre la imagen; los números no garantizan la identidad.")
            return {"etiquetas": _propuestas_actuales(nombres, objetos, avisos), "revisadas": set(),
                    "origen": str(ruta_nombres), "avisos": avisos}
        except (OSError, ValueError, TypeError, KeyError) as error:
            avisos.append(f"No se pueden usar las etiquetas antiguas {ruta.parent.name}: {error}")

    # Una etiqueta por nombre solo es una asociación conocida dentro de capturas.
    # Un fichero subido con el mismo nombre nunca hereda etiquetas por casualidad.
    conocida = base / "capturas" / origen.name
    ruta = base / "etiquetas" / f"{origen.stem}.json"
    if origen == conocida and origen.is_file() and ruta.is_file():
        try:
            nombres = _nombres_validos(leer_etiquetas(ruta), objetos)
            avisos.append("Etiquetas por archivo sin firma de detección: revisa y confirma cada objeto.")
            return {"etiquetas": nombres, "revisadas": set(), "origen": str(ruta), "avisos": avisos}
        except (OSError, ValueError, TypeError, KeyError) as error:
            avisos.append(f"No se pueden usar las etiquetas {ruta.name}: {error}")
    return vacio


def exportar_sesion(resultado, origen, imagen, valores, etiquetas, revisadas,
                    base_salida=BASE / "resultados"):
    """Publica un paquete nuevo, reproducible y sin alterar fotos o ajustes previos.

    ``anotaciones.json`` conserva también propuestas pendientes; CSV y
    ``etiquetas.json`` contienen nombres únicamente donde la persona confirmó
    la etiqueta. La copia PNG completa permite reproducir exactamente el zoom.
    """
    parametros = validar_configuracion(valores)
    firma = firma_deteccion(imagen, parametros, resultado)
    # Evita empaquetar por accidente un resultado anterior con ajustes nuevos.
    comprobacion = procesar_imagen(imagen, parametros)
    if firma_deteccion(imagen, parametros, comprobacion) != firma:
        raise ValueError("La detección no corresponde a la imagen y los ajustes actuales; vuelve a procesarla.")
    objetos = _objetos_validos(resultado)
    nombres = _nombres_validos(etiquetas, objetos)
    ids = {o["id"] for o in objetos}
    revisadas = _revisadas_validas(revisadas, nombres, ids)
    confirmadas = {i: nombres[i] for i in sorted(revisadas)}
    pendientes = sorted(ids - revisadas)
    origen = Path(origen).expanduser().resolve()
    base_salida = Path(base_salida).expanduser().resolve()
    base_salida.mkdir(parents=True, exist_ok=True)
    nombre_fuente = re.sub(r"[^a-zA-Z0-9_-]", "_", origen.stem)[:48] or "imagen"
    nombre = f"sesion_{nombre_fuente}_{datetime.now():%Y%m%d_%H%M%S_%f}_{uuid.uuid4().hex}"
    destino = base_salida / nombre
    fuente_final = destino / "imagen_origen.png"
    with tempfile.TemporaryDirectory(prefix=".sesion_", dir=base_salida) as temporal:
        paquete = Path(temporal) / "paquete"
        datos_resultado = {**comprobacion, "dimensiones_origen": {
            "ancho_px": int(imagen.shape[1]), "alto_px": int(imagen.shape[0])},
            "configuracion_origen": "Parámetros confirmados en la interfaz web local"}
        exportar_resultado(datos_resultado, fuente_final, parametros, paquete, confirmadas)
        if not cv2.imwrite(str(paquete / "imagen_origen.png"), imagen):
            raise OSError("No se pudo guardar la imagen fuente de la sesión.")
        _json(paquete / "anotaciones.json", {
            "version": 1, "tipo": "etiquetado_manual", "creada_utc": datetime.now(timezone.utc).isoformat(),
            "imagen_original": str(origen), "imagen_copia": "imagen_origen.png",
            "huella_imagen": huella_imagen(imagen), "firma_deteccion": firma,
            "ancho_procesado": ANCHO_PROCESADO, "parametros": parametros,
            "version_procesado": VERSION_PROCESADO,
            "version_caracteristicas": comprobacion["version_caracteristicas"],
            "objetos": [{"id": o["id"], "nombre": nombres.get(o["id"], ""),
                         "revisada": o["id"] in revisadas} for o in objetos],
        })
        resumen = leer_etiquetas(paquete / "resumen.json")
        resumen.update({"imagen_original": str(origen), "imagen_copia": "imagen_origen.png",
                        "anotaciones": "anotaciones.json", "ids_pendientes_revision": pendientes,
                        "ids_revisados": sorted(revisadas), "firma_deteccion": firma})
        resumen["advertencias"].append(
            "El CSV solo incluye nombres confirmados. Las propuestas pendientes y su estado "
            "se conservan en anotaciones.json. Confirmar es una revisión manual, no una predicción."
        )
        if pendientes:
            resumen["advertencias"].append("Falta revisar los objetos: " + ", ".join(map(str, pendientes)) + ".")
        _json(paquete / "resumen.json", resumen)
        if destino.exists():
            raise FileExistsError(f"Ya existe la carpeta de sesión: {destino}")
        os.rename(paquete, destino)
    return destino
