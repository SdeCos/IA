"""Detecta y numera objetos de una fotografía; exporta medidas sin abrir la cámara.

El CSV usa UTF-8 con BOM, separador punto y coma y punto decimal. Las etiquetas
son nombres reales introducidos manualmente, no predicciones de un clasificador.
"""

import argparse
import csv
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import cv2

from configuracion import (
    BASE,
    RUTA_CONFIGURACION,
    configuracion_para_imagen,
    guardar_configuracion,
)
from vision import dibujar_resultado, procesar_imagen
from geometria import METRICAS_GEOMETRICAS, VERSION_CARACTERISTICAS


ARCHIVOS_RESULTADO = (
    "caracteristicas.csv", "objetos.png", "mascara.png", "configuracion.json",
    "etiquetas.json", "resumen.json",
    "tapete.png",
    "perfiles.json",
)
METRICAS = (
    "area_px2", "perimetro_px", "relacion_aspecto", "solidez", "circularidad",
    "centroide_x_px", "centroide_y_px", "largo_px", "corto_px",
    "orientacion_grados",
    *METRICAS_GEOMETRICAS,
)
COLUMNAS_CSV = ("id", "nombre_real", *METRICAS, "imagen_origen")


def validar_etiquetas(etiquetas, objetos):
    """Normaliza IDs de JSON y rechaza nombres o IDs que no corresponden a esta foto."""
    if etiquetas is None:
        return {}
    if not isinstance(etiquetas, dict):
        raise ValueError("Las etiquetas deben ser un objeto JSON: {\"1\": \"nombre real\"}.")
    ids_validos = {int(objeto["id"]) for objeto in objetos}
    normalizadas = {}
    for clave, nombre in etiquetas.items():
        if isinstance(clave, bool) or not isinstance(clave, (str, int)):
            raise ValueError(f"Identificador de etiqueta no válido: {clave!r}.")
        try:
            identificador = int(clave)
        except (TypeError, ValueError):
            raise ValueError(f"Identificador de etiqueta no válido: {clave!r}.") from None
        if identificador not in ids_validos:
            raise ValueError(f"La etiqueta {clave!r} no corresponde a ningún objeto de esta imagen.")
        if identificador in normalizadas:
            raise ValueError(f"El identificador {identificador} está repetido en las etiquetas.")
        if not isinstance(nombre, str):
            raise ValueError(f"El nombre real del objeto {identificador} debe ser texto.")
        normalizadas[identificador] = nombre.strip()
    return normalizadas


def leer_etiquetas(ruta):
    """No admite claves duplicadas, que json.load descartaría silenciosamente."""
    def sin_duplicados(pares):
        datos = {}
        for clave, valor in pares:
            if clave in datos:
                raise ValueError(f"La clave {clave!r} está repetida en {ruta}.")
            datos[clave] = valor
        return datos

    with Path(ruta).expanduser().open(encoding="utf-8-sig") as archivo:
        return json.load(archivo, object_pairs_hook=sin_duplicados)


def _escribir_json(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _dimension(imagen):
    alto, ancho = imagen.shape[:2]
    return {"ancho_px": int(ancho), "alto_px": int(alto)}


def _objetos_en_borde(resultado):
    alto, ancho = resultado["imagen"].shape[:2]
    ids = []
    for objeto in resultado["objetos"]:
        puntos = objeto["contorno"].reshape(-1, 2)
        if ((puntos[:, 0] <= 0).any() or (puntos[:, 0] >= ancho - 1).any()
                or (puntos[:, 1] <= 0).any() or (puntos[:, 1] >= alto - 1).any()):
            ids.append(int(objeto["id"]))
    return ids


def exportar_resultado(resultado, imagen_origen: Path, valores: dict,
                       salida: Path, etiquetas: dict | None = None) -> Path:
    """Exporta una detección completa sin sobrescribir resultados existentes.

    Cada ID pertenece a esta imagen y se asigna de izquierda a derecha. Si cambian
    la segmentación o la imagen, hay que revisar las etiquetas antes de reutilizarlas.
    """
    objetos = resultado["objetos"]
    nombres = validar_etiquetas(etiquetas, objetos)
    origen = Path(imagen_origen).expanduser().resolve()
    destino = Path(salida).expanduser().resolve()
    if destino.exists() and not destino.is_dir():
        raise ValueError(f"La salida debe ser una carpeta: {destino}")
    existentes = [nombre for nombre in ARCHIVOS_RESULTADO if (destino / nombre).exists()]
    if existentes:
        raise FileExistsError(
            f"Ya hay resultados en {destino}: {', '.join(existentes)}. "
            "Elige otra carpeta para conservarlos."
        )

    borde = _objetos_en_borde(resultado)
    advertencias = [
        "Detección sin clasificación: nombre_real es una etiqueta manual; "
        "no se ha calculado inventario ni porcentaje de aciertos.",
        "Los IDs se ordenan por centroide horizontal y solo identifican objetos "
        "en esta imagen. Revisa las etiquetas si cambias la imagen o la configuración.",
        "Las áreas y perímetros describen el contorno exterior; no descuentan "
        "los huecos interiores. Las medidas están en píxeles de la imagen procesada.",
    ]
    if borde:
        advertencias.append(
            f"Los objetos {', '.join(map(str, borde))} tocan el borde: "
            "pueden estar recortados o pertenecer al fondo."
        )
    if not objetos:
        advertencias.append("No se han encontrado objetos que superen el filtro de área.")
    advertencias.extend(resultado.get("avisos", []))
    resumen = {
        "imagen_origen": str(origen),
        "configuracion_origen": resultado.get("configuracion_origen", "Valores suministrados al exportador"),
        "configuracion_utilizada": "configuracion.json",
        "dimensiones_procesadas": _dimension(resultado["imagen"]),
        "dimensiones_encuadre": _dimension(resultado["encuadre"]),
        "numero_objetos": len(objetos),
        "orden_ids": "Centroide X ascendente; desempate por centroide Y",
        "ids_en_borde": borde,
        "ids_sin_etiquetar": [int(o["id"]) for o in objetos if not nombres.get(int(o["id"]), "")],
        "csv": {"archivo": "caracteristicas.csv", "codificacion": "utf-8-sig",
                "separador": ";", "decimal": "."},
        "advertencias": advertencias,
        "region_analisis": resultado.get("tapete"),
        "descartados_borde_tapete": resultado.get("descartados_borde", 0),
        "version_procesado": resultado.get("version_procesado"),
        "version_caracteristicas": VERSION_CARACTERISTICAS,
        "perfiles": "perfiles.json",
    }
    if "dimensiones_origen" in resultado:
        resumen["dimensiones_origen"] = resultado["dimensiones_origen"]

    # Preparar todo antes de publicar archivos evita resultados incompletos por
    # errores de procesamiento. Los enlaces exclusivos impiden sobrescrituras.
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".deteccion_", dir=destino.parent) as temporal:
        preparacion = Path(temporal)
        with (preparacion / "caracteristicas.csv").open("w", encoding="utf-8-sig", newline="") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS_CSV, delimiter=";")
            escritor.writeheader()
            for objeto in objetos:
                fila = {"id": int(objeto["id"]), "nombre_real": nombres.get(int(objeto["id"]), ""),
                        "imagen_origen": str(origen)}
                fila.update({clave: f"{float(objeto[clave]):.6f}" for clave in METRICAS})
                escritor.writerow(fila)
        imagen_anotada = dibujar_resultado(resultado, etiquetas=nombres, telemetria=True)
        for nombre, imagen in (("objetos.png", imagen_anotada), ("mascara.png", resultado["mascara"]),
                              ("tapete.png", resultado["mascara_tapete"])):
            if not cv2.imwrite(str(preparacion / nombre), imagen):
                raise OSError(f"No se pudo guardar {nombre}.")
        guardar_configuracion(valores, preparacion / "configuracion.json")
        _escribir_json(preparacion / "etiquetas.json",
                       {str(int(o["id"])): nombres.get(int(o["id"]), "") for o in objetos})
        _escribir_json(preparacion / "resumen.json", resumen)
        _escribir_json(preparacion / "perfiles.json", {
            "version_caracteristicas": VERSION_CARACTERISTICAS,
            "normalizacion": "Longitud / lado largo y anchura / lado corto de la caja mínima.",
            "sentido": "Extremo de mayor anchura media primero; empates resueltos por el perfil.",
            "objetos": [{"id": int(o["id"]),
                         "nombre_real": nombres.get(int(o["id"]), ""),
                         "posiciones": o["perfil_posiciones"],
                         "anchuras": o["perfil_ancho"]} for o in objetos],
        })
        creada = not destino.exists()
        destino.mkdir(parents=True, exist_ok=True)
        publicados = []
        try:
            for nombre in ARCHIVOS_RESULTADO:
                os.link(preparacion / nombre, destino / nombre)
                publicados.append(destino / nombre)
        except OSError:
            for ruta in publicados:
                ruta.unlink()
            if creada:
                try:
                    destino.rmdir()
                except OSError:
                    pass
            raise
    return destino


def crear_parser():
    parser = argparse.ArgumentParser(
        description="Detecta, numera y exporta características de una foto, sin cámara.",
        epilog="CSV: UTF-8 con BOM, separador ; y punto decimal. Sin opciones se procesa la última escena.",
    )
    fuente = parser.add_mutually_exclusive_group()
    fuente.add_argument("--imagen", type=Path, metavar="RUTA", help="Fotografía para procesar.")
    fuente.add_argument("--ultima", action="store_true", help="Usa la última escena de capturas (predeterminado).")
    parser.add_argument("--config", type=Path, metavar="RUTA", help="Configuración JSON; prevalece sobre la asociada a la foto.")
    parser.add_argument("--zoom", type=float, metavar="FACTOR", help="Sobrescribe el zoom (de 1 a 3).")
    parser.add_argument("--salida", type=Path, metavar="CARPETA", help="Carpeta de exportación; nunca sobrescribe resultados.")
    parser.add_argument("--etiquetas", type=Path, metavar="JSON", help="Nombres reales manuales: {\"1\": \"destornillador\"}.")
    parser.add_argument("--mostrar", action="store_true", help="Abre las imágenes al terminar; Q o Esc para cerrar.")
    return parser


def main(argv=None):
    parser = crear_parser()
    args = parser.parse_args(argv)
    try:
        if args.imagen is None:
            escenas = sorted((BASE / "capturas").glob("escena_*.png"))
            if not escenas:
                raise ValueError("No hay escenas guardadas. Indica --imagen RUTA o guarda una foto con G en el calibrador.")
            origen = escenas[-1].resolve()
        else:
            origen = args.imagen.expanduser().resolve()
        if not origen.is_file():
            raise ValueError(f"No existe la imagen: {origen}")
        etiquetas = leer_etiquetas(args.etiquetas) if args.etiquetas else None
        valores = configuracion_para_imagen(origen, args.config, args.zoom)
        imagen = cv2.imread(str(origen))
        if imagen is None:
            raise ValueError(f"No se pudo leer la imagen: {origen}")
        resultado = procesar_imagen(imagen, valores)
        resultado["dimensiones_origen"] = _dimension(imagen)
        sidecar = origen.with_suffix(".json")
        ruta_config = args.config.expanduser().resolve() if args.config else (
            sidecar if sidecar.is_file() else RUTA_CONFIGURACION
        )
        resultado["configuracion_origen"] = str(ruta_config) if ruta_config.is_file() else "Valores predeterminados"
        if args.zoom is not None:
            resultado["configuracion_origen"] += f"; zoom sobrescrito a {args.zoom:g}x"
        salida = args.salida or BASE / "resultados" / f"{origen.stem}_{datetime.now():%Y%m%d_%H%M%S_%f}"
        destino = exportar_resultado(resultado, origen, valores, salida, etiquetas)
    except json.JSONDecodeError as error:
        parser.exit(
            1,
            f"Error: JSON no válido en un archivo de configuración o etiquetas "
            f"(línea {error.lineno}, columna {error.colno}). "
            "Revisa las comas, llaves y comillas dobles.\n",
        )
    except FileNotFoundError as error:
        parser.exit(1, f"Error: No existe el archivo o directorio: {error.filename}\n")
    except (OSError, ValueError, cv2.error) as error:
        parser.exit(1, f"Error: {error}\n")

    print(f"Imagen: {origen}")
    print(f"Objetos detectados: {len(resultado['objetos'])}")
    for aviso in resultado.get("avisos", []):
        print(f"Aviso: {aviso}")
    print(f"Resultados guardados: {destino}")
    print("CSV: caracteristicas.csv (separador ; y punto decimal).")
    print("Los nombres reales se rellenan manualmente en etiquetas.json; todavía no hay clasificación.")
    if args.mostrar:
        try:
            cv2.imshow("Objetos numerados (Q o Esc para salir)", cv2.imread(str(destino / "objetos.png")))
            cv2.imshow("Mascara", resultado["mascara"])
            while True:
                if cv2.waitKeyEx(50) in (ord("q"), ord("Q"), 27):
                    break
                if cv2.getWindowProperty("Objetos numerados (Q o Esc para salir)", cv2.WND_PROP_VISIBLE) < 1:
                    break
        except cv2.error as error:
            print(f"No se pudieron mostrar las ventanas; los archivos ya están guardados. {error}", file=sys.stderr)
        finally:
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
