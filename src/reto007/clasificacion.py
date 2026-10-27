"""Reglas geométricas escritas a mano; no entrena ni consulta etiquetas.

Estas reglas describen los ejemplares del proyecto, en las configuraciones
documentadas en docs/REGLAS.md. No son un reconocedor universal de herramientas.
La banda de abstención es una tolerancia geométrica, nunca una probabilidad.
"""

import math
from numbers import Real


VERSION_CLASIFICADOR = "reglas-manuales-v1"
VERSION_GEOMETRIA = "geometria-v1"
GRUPOS_DESARROLLO = (
    "20261016_113207_730520",
    "20261016_113218_711279",
    "20261016_113231_782061",
    "video_2eaa614e1f7fa5ba99870b79f3a729103af094aabe85cf620c98fa42b98aca91",
)
CARACTERISTICAS = (
    "relacion_aspecto", "solidez", "circularidad", "extension",
    "contraste_extremos", "fraccion_ancha", "asimetria_longitudinal",
    "ancho_central",
)
NOMBRES = {
    "relacion_aspecto": "AR",
    "solidez": "solidez",
    "circularidad": "circularidad",
    "extension": "extensión",
    "contraste_extremos": "contraste entre extremos",
    "fraccion_ancha": "fracción ancha",
    "asimetria_longitudinal": "asimetría longitudinal",
    "ancho_central": "ancho central",
}

# Cada intervalo lo ha establecido una persona/modelo como regla explícita,
# al inspeccionar la geometría y las medidas de desarrollo. No hay búsqueda
# de umbrales, ajuste de parámetros, árbol aprendido ni consulta a ejemplos.
# Orden: AR, solidez, circularidad, extensión, contraste, fracción ancha,
# asimetría, ancho central. La coincidencia exige TODAS las condiciones.
_REGLAS = (
    ("R1", "Metro", "cuerpo compacto casi cuadrado y convexo, con extremos similares", (
        (1.0, 1.6), (.90, 1.0), (.65, .90), (.75, 1.0),
        (0.0, .25), (.85, 1.0), (0.0, .20), (.80, 1.0))),
    ("R2", "Cuter", "cuerpo convexo de longitud moderada, ancho en el centro y casi simétrico", (
        (2.0, 3.8), (.85, 1.0), (.40, .65), (.65, .88),
        (0.0, .25), (.80, 1.0), (0.0, .20), (.80, 1.0))),
    ("R3", "Nivel", "cuerpo largo, casi rectangular y de anchura uniforme", (
        (4.0, 6.5), (.90, 1.0), (.25, .50), (.85, 1.0),
        (0.0, .15), (.90, 1.0), (0.0, .12), (.80, 1.0))),
    ("R4", "Desbarbador manual", "cuerpo muy alargado con mango ancho en casi toda su longitud y punta fina", (
        (8.5, 14.0), (.70, .95), (.10, .25), (.55, .85),
        (.55, .95), (.65, .90), (.15, .50), (.75, 1.0))),
    ("R5", "Destornillador", "mango ancho y vástago largo, fino y muy distinto del extremo opuesto", (
        (5.5, 9.0), (.50, .78), (.08, .20), (.25, .50),
        (.70, 1.0), (.30, .55), (.40, .75), (.12, .45))),
    ("R6", "Calibre", "cabeza ancha y cuerpo estrecho, con centro especialmente fino", (
        (2.5, 4.5), (.40, .65), (.10, .25), (.22, .43),
        (.55, .85), (.10, .30), (.12, .35), (.12, .25))),
    ("R7", "Martillo", "cabeza ancha y mango de anchura intermedia, con contraste moderado", (
        (2.5, 4.5), (.35, .65), (.10, .27), (.25, .48),
        (.25, .55), (.10, .32), (.06, .25), (.28, .45))),
    ("R8", "Juego de llaves Allen", "conjunto ancho y ramificado, con centro ancho y asimetría moderada", (
        (2.3, 4.3), (.60, .82), (.07, .22), (.40, .65),
        (.20, .55), (.65, .90), (.07, .28), (.55, .85))),
    ("R9", "Alicate", "cuerpo ramificado, ancho en el centro y claramente asimétrico entre mordaza y mangos", (
        (2.0, 4.0), (.50, .78), (.08, .25), (.30, .65),
        (.55, .85), (.50, .82), (.30, .60), (.60, .95))),
)
CLASES_SOPORTADAS = tuple(regla[1] for regla in _REGLAS)


def snapshot_reglas():
    """Especificación independiente, JSON-safe, para guardar con cada resultado."""
    return {
        "version_clasificador": VERSION_CLASIFICADOR,
        "version_caracteristicas": VERSION_GEOMETRIA,
        "metodo": "reglas geométricas conjuntas escritas a mano; sin entrenamiento",
        "grupos_desarrollo": list(GRUPOS_DESARROLLO),
        "clases_soportadas": list(CLASES_SOPORTADAS),
        "criterio": "Una única regla compatible, todas sus condiciones satisfechas y fuera de sus bandas de abstención.",
        "banda_abstencion": {"relacion_aspecto": .15, "otros_cocientes": .02,
                              "excepcion": "No se aplica banda en los límites físicos 0/1; AR mínimo físico 1."},
        "reglas": [
            {"regla": codigo, "clase": clase, "descripcion": descripcion,
             "condiciones": [
                 {"caracteristica": clave, "minimo": limites[0], "maximo": limites[1]}
                 for clave, limites in zip(CARACTERISTICAS, intervalos)
             ]}
            for codigo, clase, descripcion, intervalos in _REGLAS
        ],
        "limitacion": "Desarrollo con 3 capturas de la misma disposición y 1 vídeo; falta evaluación independiente. Objetos ajenos con geometría similar pueden cumplir las reglas.",
    }


def _resultado(clase, estado, regla, explicacion, ruta):
    return {"clase_predicha": clase, "estado_clasificacion": estado,
            "regla": regla, "explicacion": explicacion, "ruta_decision": ruta,
            "version_clasificador": VERSION_CLASIFICADOR}


def _comprobar_intervalo(clave, valor, minimo, maximo):
    margen = .15 if clave == "relacion_aspecto" else .02
    limite_fisico_inferior = 1.0 if clave == "relacion_aspecto" else 0.0
    margen_inferior = 0.0 if minimo == limite_fisico_inferior else margen
    margen_superior = 0.0 if maximo == 1.0 and clave != "relacion_aspecto" else margen
    # Compatible incluye la banda a ambos lados del umbral. Identificada
    # exige además quedar dentro del intervalo y alejada de sus fronteras.
    compatible = minimo - margen_inferior <= valor <= maximo + margen_superior
    interior = (minimo <= valor <= maximo
                and (margen_inferior == 0 or valor > minimo + margen_inferior)
                and (margen_superior == 0 or valor < maximo - margen_superior))
    return {"caracteristica": clave, "valor": valor, "minimo": minimo,
            "maximo": maximo, "compatible": compatible, "interior": interior,
            "condicion": f"{minimo:g} ≤ {NOMBRES[clave]} ≤ {maximo:g}",
            "resultado": "cumple" if interior else ("frontera" if compatible else "no cumple")}


def clasificar_objeto(objeto):
    """Devuelve una predicción explicable a partir de ocho cocientes de forma.

    Ignora por completo nombre_real, identificación de pista, posición,
    orientación absoluta, procedencia, área y dimensiones en píxeles.
    No modifica objeto. Los datos ausentes o inválidos producen abstención.
    """
    ruta = []
    if not hasattr(objeto, "get"):
        return _resultado("Desconocido", "desconocida", "DATOS_INVALIDOS",
                          "No se han recibido características de una silueta.", ruta)
    version = objeto.get("version_caracteristicas", VERSION_GEOMETRIA)
    if version != VERSION_GEOMETRIA:
        return _resultado("Desconocido", "desconocida", "VERSION_INCOMPATIBLE",
                          f"Recalcula las características con {VERSION_GEOMETRIA}.", ruta)
    valores = {}
    invalidas = []
    for clave in CARACTERISTICAS:
        valor = objeto.get(clave)
        if isinstance(valor, bool) or not isinstance(valor, Real) or not math.isfinite(valor):
            invalidas.append(clave)
            continue
        valor = float(valor)
        if (clave == "relacion_aspecto" and valor < 1) or (clave != "relacion_aspecto" and not 0 <= valor <= 1):
            invalidas.append(clave)
            continue
        valores[clave] = valor
    if invalidas:
        return _resultado("Desconocido", "desconocida", "DATOS_INVALIDOS",
                          "Faltan medidas válidas: " + ", ".join(invalidas) + ".", ruta)
    if valores["extension"] > valores["solidez"] + .02:
        return _resultado("Desconocido", "desconocida", "GEOMETRIA_INCONSISTENTE",
                          "La extensión supera la solidez; revisa el cálculo de la silueta.", ruta)
    ruta.append({"nodo": "ENTRADA", "condicion": "Ocho cocientes geométricos finitos y coherentes", "resultado": "cumple"})

    compatibles = []
    interiores = []
    for codigo, clase, descripcion, intervalos in _REGLAS:
        detalle = [_comprobar_intervalo(clave, valores[clave], *limites)
                   for clave, limites in zip(CARACTERISTICAS, intervalos)]
        compatible = all(item["compatible"] for item in detalle)
        interior = all(item["interior"] for item in detalle)
        ruta.append({"nodo": codigo, "clase": clase, "condicion": descripcion,
                     "resultado": "cumple" if interior else ("frontera" if compatible else "no cumple"),
                     "detalle": detalle})
        if compatible:
            compatibles.append((codigo, clase, descripcion))
        if interior:
            interiores.append((codigo, clase, descripcion))

    if len(interiores) == 1 and len(compatibles) == 1:
        codigo, clase, descripcion = interiores[0]
        explicacion = (f"{codigo}: {descripcion}. AR={valores['relacion_aspecto']:.2f}; "
                       f"solidez={valores['solidez']:.2f}; ancho central={valores['ancho_central']:.2f}; "
                       f"contraste={valores['contraste_extremos']:.2f}. "
                       "Cumple todas las condiciones de esta regla.")
        return _resultado(clase, "identificada", codigo, explicacion, ruta)
    if compatibles:
        nombres = ", ".join(regla[1] for regla in compatibles)
        return _resultado("Desconocido", "ambigua", "FRONTERA_O_SOLAPAMIENTO",
                          f"La silueta está cerca de un límite o cumple reglas solapadas ({nombres}). Revisa la máscara; no se asigna un nombre.", ruta)
    return _resultado("Desconocido", "desconocida", "SIN_COINCIDENCIA",
                      "La silueta no cumple ninguna regla completa. Puede ser otra herramienta, otra configuración o una segmentación incompleta.", ruta)


def clasificar_objetos(objetos):
    """Enriquece copias sin sobrescribir las etiquetas manuales de referencia."""
    return [dict(objeto, **clasificar_objeto(objeto)) for objeto in objetos]
