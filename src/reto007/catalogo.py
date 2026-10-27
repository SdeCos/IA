"""Nombres de herramientas disponibles para el etiquetado manual local.

El catálogo facilita la selección, pero no determina si una anotación de una
sesión es válida: sus nombres viajan con ella y pueden abrirse en otro equipo.
"""

import json
from pathlib import Path
import tempfile
import unicodedata

from configuracion import BASE


CLASES_PREDETERMINADAS = (
    "Destornillador", "Calibre", "Desbarbador manual", "Martillo",
    "Juego de llaves Allen", "Nivel",
)


def normalizar_nombre(nombre):
    """Normaliza un nombre visible sin introducir categorías ni confirmaciones."""
    if not isinstance(nombre, str):
        raise ValueError("El nombre de la herramienta debe ser texto.")
    if any(unicodedata.category(caracter).startswith("C") for caracter in nombre):
        raise ValueError("El nombre de la herramienta contiene caracteres de control o invisibles.")
    nombre = " ".join(unicodedata.normalize("NFC", nombre).split())
    if not nombre:
        raise ValueError("Escribe el nombre de la herramienta.")
    if len(nombre) > 80:
        raise ValueError("El nombre de la herramienta no puede superar los 80 caracteres.")
    if nombre.casefold() == "sin etiquetar":
        raise ValueError("«Sin etiquetar» está reservado para los objetos sin nombre.")
    return nombre


def _sin_claves_repetidas(pares):
    resultado = {}
    for clave, valor in pares:
        if clave in resultado:
            raise ValueError(f"La clave {clave!r} está repetida en herramientas.json.")
        resultado[clave] = valor
    return resultado


def cargar_clases(base=BASE):
    """Devuelve los nombres de fábrica y los añadidos; leer no crea archivos."""
    ruta = Path(base).expanduser().resolve() / "herramientas.json"
    if not ruta.exists():
        return list(CLASES_PREDETERMINADAS)
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8-sig"),
                           object_pairs_hook=_sin_claves_repetidas)
        if (not isinstance(datos, dict) or type(datos.get("version")) is not int
                or datos["version"] != 1 or set(datos) != {"version", "herramientas"}
                or not isinstance(datos["herramientas"], list)):
            raise ValueError("Se espera versión 1 y una lista de herramientas.")
        nombres = list(CLASES_PREDETERMINADAS)
        conocidas = {nombre.casefold() for nombre in nombres}
        for nombre in datos["herramientas"]:
            normalizado = normalizar_nombre(nombre)
            if normalizado.casefold() not in conocidas:
                nombres.append(normalizado)
                conocidas.add(normalizado.casefold())
        return nombres
    except (ValueError, UnicodeError) as error:
        raise ValueError(f"El catálogo {ruta} no es válido: {error}") from error


def agregar_clase(nombre, base=BASE):
    """Guarda un nombre y devuelve su grafía canónica; nunca marca objetos."""
    nombre = normalizar_nombre(nombre)
    base = Path(base).expanduser().resolve()
    nombres = cargar_clases(base)
    for existente in nombres:
        if existente.casefold() == nombre.casefold():
            return existente
    nombres.append(nombre)
    base.mkdir(parents=True, exist_ok=True)
    ruta = base / "herramientas.json"
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=base,
                                         prefix=".herramientas_", suffix=".tmp",
                                         delete=False) as archivo:
            temporal = Path(archivo.name)
            json.dump({"version": 1, "herramientas": nombres}, archivo,
                      ensure_ascii=False, indent=2)
            archivo.write("\n")
        temporal.replace(ruta)
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)
    return nombre
