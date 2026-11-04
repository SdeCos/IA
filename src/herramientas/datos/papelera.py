"""Retirada reversible de capturas y sus ajustes; no borra sesiones de evaluación."""
from datetime import datetime
import json
from pathlib import Path
import uuid


def pareja_captura(ruta):
    ruta = Path(ruta)
    for prefijo, otro in (("escena_", "original_"), ("original_", "escena_")):
        if ruta.name.startswith(prefijo):
            return ruta.with_name(otro + ruta.name[len(prefijo):])
    return None


def retirar_captura(ruta, base):
    base = Path(base).resolve()
    ruta = Path(ruta).absolute()
    capturas = base / 'datos/capturas'
    if (ruta.parent != capturas or ruta.is_symlink() or not ruta.is_file()
            or ruta.suffix.lower() not in ('.png', '.jpg', '.jpeg')):
        raise ValueError('Solo se pueden retirar fotografías de datos/capturas.')
    fotos = [ruta]
    pareja = pareja_captura(ruta)
    if pareja and pareja.exists():
        fotos.append(pareja)
    archivos = []
    for foto in fotos:
        for p in (foto, *(foto.with_suffix(s) for s in ('.json', '.nombre.json', '.origen.json'))):
            if p.is_symlink():
                raise ValueError('No se pueden trasladar enlaces simbólicos.')
            if p.is_file():
                archivos.append(p)
    destino = base / 'datos/papelera' / (datetime.now().strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex)
    destino.mkdir(parents=True)
    manifiesto = {'foto': ruta.name, 'archivos': [p.name for p in archivos]}
    movidos = []
    try:
        (destino/'papelera.json').write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2))
        for p in archivos:
            p.rename(destino/p.name)
            movidos.append(p)
    except OSError:
        for p in reversed(movidos):
            (destino/p.name).rename(p)
        raise
    return destino


def restaurar_captura(carpeta, base):
    base = Path(base).resolve()
    carpeta = Path(carpeta).absolute()
    if carpeta.parent != base/'datos/papelera' or carpeta.is_symlink():
        raise ValueError('Papelera no válida.')
    datos = json.loads((carpeta/'papelera.json').read_text())
    nombres = datos['archivos']
    if (not isinstance(nombres, list) or not nombres or len(set(nombres)) != len(nombres)
            or any(not isinstance(n, str) or Path(n).name != n or n in ('.', '..', 'papelera.json') for n in nombres)
            or datos.get('foto') not in nombres):
        raise ValueError('Manifiesto de papelera no válido.')
    destino = base/'datos/capturas'
    for n in nombres:
        if (carpeta/n).is_symlink() or not (carpeta/n).is_file():
            raise ValueError('Faltan archivos de la captura.')
        if (destino/n).exists() or (destino/n).is_symlink():
            raise ValueError(f'Ya existe {n}; no se sobrescribirá.')
    destino.mkdir(parents=True, exist_ok=True)
    movidos = []
    try:
        for n in nombres:
            (carpeta/n).rename(destino/n)
            movidos.append(n)
    except OSError:
        for n in reversed(movidos):
            (destino/n).rename(carpeta/n)
        raise
    (carpeta/'papelera.json').unlink()
    carpeta.rmdir()
    return destino/datos['foto']
