"""Configuración reproducible compartida por el calibrador y el detector."""

import json
from numbers import Integral
from pathlib import Path
import tempfile

BASE = Path(__file__).resolve().parent
RUTA_CONFIGURACION = BASE / "configuracion.json"
VALORES_PREDETERMINADOS = {
    "h_min": 80, "h_max": 100,
    "s_min": 100, "s_max": 255,
    "v_min": 40, "v_max": 255,
    "apertura": 0, "cierre": 1, "kernel": 3, "suavizado": 3,
    "area_min": 1000, "zoom": 100,
    "limitar_tapete": 1, "margen_tapete": 2,
}
LIMITES = {
    "h_min": (0, 179), "h_max": (0, 179),
    "s_min": (0, 255), "s_max": (0, 255),
    "v_min": (0, 255), "v_max": (0, 255),
    "apertura": (0, 5), "cierre": (0, 10),
    "kernel": (1, 15), "suavizado": (1, 15),
    "area_min": (0, 100000), "zoom": (100, 300),
    "limitar_tapete": (0, 1), "margen_tapete": (0, 30),
}


def validar_configuracion(valores):
    """Completa valores omitidos y rechaza ajustes incompatibles con el panel."""
    if not isinstance(valores, dict):
        raise ValueError("Los parámetros deben ser un objeto JSON.")
    desconocidos = set(valores) - set(VALORES_PREDETERMINADOS)
    if desconocidos:
        raise ValueError(f"Parámetros desconocidos: {sorted(desconocidos)}")
    resultado = {**VALORES_PREDETERMINADOS, **valores}
    for clave, valor in resultado.items():
        minimo, maximo = LIMITES[clave]
        if isinstance(valor, bool) or not isinstance(valor, Integral):
            raise ValueError(f"{clave} debe ser un número entero.")
        if not minimo <= valor <= maximo:
            raise ValueError(f"{clave} debe estar entre {minimo} y {maximo}.")
        resultado[clave] = int(valor)
    for clave in ("kernel", "suavizado"):
        if resultado[clave] % 2 == 0:
            raise ValueError(f"{clave} debe ser impar.")
    for canal in ("h", "s", "v"):
        if resultado[f"{canal}_min"] > resultado[f"{canal}_max"]:
            raise ValueError(f"El mínimo de {canal.upper()} supera al máximo.")
    return resultado


def cargar_configuracion(ruta=None):
    destino = RUTA_CONFIGURACION if ruta is None else Path(ruta).expanduser()
    if ruta is None and not destino.exists():
        return VALORES_PREDETERMINADOS.copy()
    datos = json.loads(destino.read_text(encoding="utf-8"))
    if isinstance(datos, dict) and "parametros" in datos:
        if datos.get("version") != 1 or datos.get("ancho_procesado") != 800:
            raise ValueError("Configuración incompatible: se espera versión 1 y ancho 800.")
        datos = datos["parametros"]
    return validar_configuracion(datos)


def guardar_configuracion(valores, ruta=RUTA_CONFIGURACION):
    destino = Path(ruta).expanduser().resolve()
    parametros = validar_configuracion(valores)
    datos = {"version": 1, "ancho_procesado": 800, "parametros": parametros}
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destino.parent, suffix=".tmp", delete=False
        ) as archivo:
            temporal = Path(archivo.name)
            json.dump(datos, archivo, ensure_ascii=False, indent=2)
            archivo.write("\n")
        temporal.replace(destino)
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)
    return destino


def configuracion_para_imagen(ruta_imagen, ruta_config=None, zoom=None):
    """Una escena ya recortada se abre a 1x; un --config explícito tiene prioridad."""
    imagen = Path(ruta_imagen).expanduser()
    asociada = imagen.with_suffix(".json")
    if ruta_config is not None:
        valores = cargar_configuracion(ruta_config)
    elif asociada.exists():
        valores = cargar_configuracion(asociada)
    else:
        valores = cargar_configuracion()
        if imagen.name.startswith("escena_"):
            valores["zoom"] = 100
    if zoom is not None:
        if not 1 <= zoom <= 3:
            raise ValueError("El zoom debe estar entre 1 y 3.")
        valores["zoom"] = round(zoom * 100)
    return validar_configuracion(valores)
