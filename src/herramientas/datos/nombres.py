"""Títulos humanos para organizar fotos; nunca son etiquetas del clasificador."""
import json
import re
import unicodedata
from pathlib import Path

from herramientas.datos.entrega import escribir_json


def validar_nombre(nombre):
    if not isinstance(nombre, str) or any(unicodedata.category(c).startswith('C') for c in nombre):
        raise ValueError('El nombre debe ser texto sin caracteres de control.')
    nombre = ' '.join(unicodedata.normalize('NFC', nombre).split())
    if len(nombre) > 80:
        raise ValueError('El nombre puede tener como máximo 80 caracteres.')
    return nombre


def sufijo_nombre(nombre):
    nombre = validar_nombre(nombre)
    ascii_nombre = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode()
    limpio = re.sub(r'[^a-zA-Z0-9]+', '-', ascii_nombre).strip('-').lower()[:60]
    return '_' + limpio if limpio else ''


def leer_nombre(ruta):
    try:
        datos = json.loads(Path(ruta).with_suffix('.nombre.json').read_text(encoding='utf-8'))
        return validar_nombre(datos['nombre']) if datos.get('version') == 1 else ''
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return ''


def guardar_nombre(ruta, nombre):
    nombre = validar_nombre(nombre)
    escribir_json(Path(ruta).with_suffix('.nombre.json'), {'version': 1, 'nombre': nombre})
    return nombre
