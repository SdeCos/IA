"""Perfil de la demostración; nunca elimina clases ni referencias anteriores."""

import json
import os
from pathlib import Path
import tempfile

from herramientas.vision.clasificacion import CLASES_SOPORTADAS
from herramientas.datos.evaluacion import inventario_objetos


def escribir_json(ruta, datos):
    """Publica un JSON completo mediante reemplazo atómico en el mismo disco."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=ruta.parent,
                                         delete=False, suffix=".tmp") as archivo:
            temporal = archivo.name
            json.dump(datos, archivo, ensure_ascii=False, indent=2, allow_nan=False)
            archivo.write("\n")
        os.replace(temporal, ruta)
    finally:
        if temporal and os.path.exists(temporal):
            os.unlink(temporal)


def validar_perfil(datos):
    if not isinstance(datos, dict) or datos.get("version") != 1:
        raise ValueError("El perfil debe tener versión 1.")
    clases = datos.get("clases")
    if (not isinstance(clases, list) or any(not isinstance(c, str) for c in clases)
            or not 5 <= len(clases) <= 8 or len(set(clases)) != len(clases)
            or not set(clases) <= set(CLASES_SOPORTADAS)):
        raise ValueError("Selecciona entre 5 y 8 clases distintas con reglas disponibles.")
    esperadas = inventario_objetos([], datos.get("esperadas"))["esperadas"]
    if esperadas is None or set(esperadas) != set(clases):
        raise ValueError("Indica una cantidad (puede ser cero) para cada clase seleccionada.")
    return {"version": 1, "clases": clases.copy(), "esperadas": esperadas}


def cargar_perfil(base):
    ruta = Path(base) / "config" / "entrega.json"
    return validar_perfil(json.loads(ruta.read_text(encoding="utf-8"))) if ruta.exists() else None


def guardar_perfil(base, clases, esperadas):
    datos = validar_perfil({"version": 1, "clases": clases, "esperadas": esperadas})
    escribir_json(Path(base) / "config" / "entrega.json", datos)
    return datos
