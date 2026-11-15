"""Copia portable de código, configuración y datos; sin entornos ni credenciales.

No restaura ni borra archivos. El ZIP incluye un manifiesto SHA-256 para verificar
la integridad. Copiar el ZIP fuera de este ordenador sigue siendo necesario.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

CARPETAS = ('src', 'config', 'datos', 'docs', 'tests')
EXTENSIONES = ('.py', '.json', '.md', '.txt', '.sh', '.command')


def crear_respaldo(base, destino):
    base, destino = Path(base).resolve(), Path(destino).resolve()
    archivos = [p for p in base.iterdir() if p.is_file() and p.suffix in EXTENSIONES]
    for carpeta in CARPETAS:
        archivos.extend(p for p in (base/carpeta).rglob('*') if p.is_file()
                        and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.tmp'))
    archivos.extend(p for p in (base / '.gitignore',) if p.is_file())
    archivos = sorted(set(p for p in archivos if not p.is_symlink() and p.resolve() != destino))
    destino.parent.mkdir(parents=True, exist_ok=True)
    hashes = {}
    # Modo x: nunca sobreescribir un respaldo anterior.
    with zipfile.ZipFile(destino, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as copia:
        for ruta in archivos:
            nombre = ruta.relative_to(base).as_posix()
            digest = hashlib.sha256()
            with ruta.open('rb') as entrada, copia.open(nombre, 'w', force_zip64=True) as salida:
                for bloque in iter(lambda: entrada.read(1024*1024), b''):
                    digest.update(bloque)
                    salida.write(bloque)
            hashes[nombre] = digest.hexdigest()
        copia.writestr('MANIFIESTO_SHA256.json', json.dumps(dict(version=1, creada=datetime.now(timezone.utc).isoformat(),
                                                              archivos=hashes), ensure_ascii=False, indent=2))
    verificar_respaldo(destino)
    return destino


def verificar_respaldo(ruta):
    with zipfile.ZipFile(ruta) as copia:
        manifiesto = json.loads(copia.read('MANIFIESTO_SHA256.json'))
        nombres = copia.namelist()
        if len(nombres) != len(set(nombres)) or manifiesto.get('version') != 1:
            raise ValueError('Manifiesto inválido o entradas duplicadas.')
        if set(nombres) != set(manifiesto['archivos']) | {'MANIFIESTO_SHA256.json'}:
            raise ValueError('El contenido no coincide con el manifiesto.')
        for nombre, esperado in manifiesto['archivos'].items():
            digest = hashlib.sha256()
            with copia.open(nombre) as archivo:
                for bloque in iter(lambda: archivo.read(1024*1024), b''):
                    digest.update(bloque)
            if digest.hexdigest() != esperado:
                raise ValueError(f'Contenido alterado: {nombre}')
    return len(manifiesto['archivos'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, help='ZIP nuevo; nunca reemplaza otro archivo.')
    parser.add_argument('--verificar', type=Path, help='Comprueba un ZIP sin extraerlo.')
    args = parser.parse_args()
    if args.verificar:
        if args.salida:
            parser.error('Usa --salida o --verificar, no ambos.')
        print(f'Respaldo íntegro: {verificar_respaldo(args.verificar)} archivos.')
    else:
        from herramientas.datos.configuracion import BASE
        base = BASE
        destino = args.salida or base/'respaldos'/f'reto007_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%f}.zip'
        print(f'Respaldo creado y verificado: {crear_respaldo(base, destino)}')
        print('Copia este ZIP a otro dispositivo. Contiene imágenes y anotaciones locales.')


if __name__ == '__main__':
    main()
