"""Evalúa reglas fijas sobre objetos ya detectados y etiquetas confirmadas.

Las etiquetas sirven exclusivamente de referencia, nunca entran al clasificador.
Las métricas no evalúan herramientas que la segmentación haya omitido. Los grupos
de adquisición separan el material usado para diseñar reglas del material nuevo;
varios fotogramas de un clip no equivalen a varias capturas independientes.
"""

from collections import Counter, defaultdict

import clasificacion
from geometria import METRICAS_GEOMETRICAS


_MEDIDAS = (
    "area_px2", "perimetro_px", "relacion_aspecto", "solidez", "circularidad",
    "centroide_x_px", "centroide_y_px", "largo_px", "corto_px",
    "orientacion_grados", *METRICAS_GEOMETRICAS,
    "perfil_ancho", "perfil_posiciones", "version_caracteristicas",
)
_PREDICCION = (
    "clase_predicha", "estado_clasificacion", "regla", "explicacion",
    "ruta_decision", "version_clasificador",
)


def _matriz(filas):
    conteo = Counter((fila["nombre_real"], fila["clase_predicha"]) for fila in filas)
    return [dict(nombre_real=real, clase_predicha=predicha, cantidad=cantidad)
            for (real, predicha), cantidad in sorted(conteo.items())]


def _resumen(filas):
    total = len(filas)
    aciertos = sum(fila["resultado"] == "acierto" for fila in filas)
    errores = sum(fila["resultado"] == "error" for fila in filas)
    rechazos = total - aciertos - errores
    identificados = aciertos + errores
    grupos = sorted({fila["grupo_evaluacion"] for fila in filas if fila.get("grupo_evaluacion")})
    imagenes = {fila["huella_imagen"] for fila in filas if fila.get("huella_imagen")}
    return {
        "total": total, "aciertos": aciertos, "errores": errores,
        "rechazos": rechazos, "identificados": identificados,
        "cobertura": identificados / total if total else None,
        "exactitud_total": aciertos / total if total else None,
        "exactitud_identificados": aciertos / identificados if identificados else None,
        "grupos": len(grupos), "ids_grupos": grupos, "imagenes": len(imagenes),
        "matriz": _matriz(filas),
    }


def evaluar_filas(filas):
    """Clasifica medidas y las compara con ``nombre_real`` confirmado.

    Consume las filas de ``analisis.reunir_datos``; no modifica filas ni reglas.
    Los cocientes están en [0, 1], o son None cuando no existe denominador.
    Las filas sin procedencia no entran en prueba. Una imagen atribuida a varios
    grupos propaga la pertenencia a desarrollo para evitar contaminar prueba.
    Los duplicados de una misma imagen y objeto se conservan solo una vez (la
    primera revisión, conforme al orden de prioridad de ``reunir_datos``).
    """
    entrada = list(filas)
    desarrollo = set(clasificacion.GRUPOS_DESARROLLO)
    grupos_por_imagen = defaultdict(set)
    avisos = [
        "Se evalúa la clasificación de objetos ya detectados y confirmados; "
        "estas cifras no miden la detección global ni las herramientas omitidas.",
        "Los originales, recortes y fotogramas del mismo vídeo comparten grupo. "
        "El número de objetos o fotogramas no equivale a observaciones independientes.",
    ]
    for fila in entrada:
        if fila.get("huella_imagen") and fila.get("captura"):
            grupos_por_imagen[str(fila["huella_imagen"])].add(str(fila["captura"]))
    # Canoniza los alias de un mismo grupo sin alterar la procedencia guardada.
    padres = {str(fila["captura"]): str(fila["captura"])
              for fila in entrada if fila.get("captura")}

    def raiz(grupo):
        while padres[grupo] != grupo:
            padres[grupo] = padres[padres[grupo]]
            grupo = padres[grupo]
        return grupo

    for grupos in grupos_por_imagen.values():
        ordenados = sorted(grupos)
        for grupo in ordenados[1:]:
            padres[raiz(grupo)] = raiz(ordenados[0])
    familias = defaultdict(set)
    for grupo in padres:
        familias[raiz(grupo)].add(grupo)
    canonicos = {}
    for familia in familias.values():
        representante = sorted(familia & desarrollo or familia)[0]
        canonicos.update(dict.fromkeys(familia, representante))
    # Cierre transitivo: un grupo enlazado a material de desarrollo permanece
    # en desarrollo incluso si una copia fue renombrada o perdió su procedencia.
    cambio = True
    while cambio:
        cambio = False
        for grupos in grupos_por_imagen.values():
            if grupos & desarrollo and not grupos <= desarrollo:
                desarrollo.update(grupos)
                cambio = True
    conflictos = sum(len(grupos) > 1 for grupos in grupos_por_imagen.values())
    if conflictos:
        avisos.append(f"{conflictos} imágenes aparecen vinculadas a más de un grupo; "
                      "ningún grupo enlazado a desarrollo se ha contado como prueba.")

    resultados, exclusiones, vistos = [], [], set()
    duplicados = 0
    sin_procedencia = 0
    for fila in entrada:
        nombre = fila.get("nombre_real")
        if not isinstance(nombre, str) or not nombre.strip():
            exclusiones.append({"id": fila.get("id"), "fuente": fila.get("fuente", ""),
                                "motivo": "Falta una etiqueta manual confirmada."})
            continue
        huella = fila.get("huella_imagen")
        identificador = fila.get("id")
        clave = (str(huella), identificador) if huella and identificador is not None else None
        if clave is not None and clave in vistos:
            duplicados += 1
            continue
        if clave is not None:
            vistos.add(clave)
        captura = str(fila.get("captura") or "")
        if not captura:
            sin_procedencia += 1
        particion = "desarrollo" if not captura or captura in desarrollo else "prueba"
        medidas = {clave: fila[clave] for clave in _MEDIDAS if clave in fila}
        prediccion = clasificacion.clasificar_objeto(medidas)
        identificada = (prediccion.get("estado_clasificacion") == "identificada"
                        and prediccion.get("clase_predicha") in clasificacion.CLASES_SOPORTADAS)
        salida = {**fila, **{clave: prediccion.get(clave) for clave in _PREDICCION}}
        if not identificada:
            salida["clase_predicha"] = "Desconocido"
        salida.update(
            captura=captura, grupo_evaluacion=canonicos.get(captura, captura), particion=particion,
            resultado=("acierto" if salida["clase_predicha"] == nombre else "error")
                      if identificada else "rechazo",
        )
        resultados.append(salida)
    if duplicados:
        avisos.append(f"Se han omitido {duplicados} filas duplicadas de la misma imagen y objeto.")
    if sin_procedencia:
        avisos.append(f"{sin_procedencia} objetos sin grupo de adquisición se mantienen en "
                      "desarrollo; no permiten una evaluación sobre grupos nuevos.")
    if exclusiones:
        avisos.append(f"Se han excluido {len(exclusiones)} filas sin etiqueta confirmada.")
    parte_desarrollo = [fila for fila in resultados if fila["particion"] == "desarrollo"]
    parte_prueba = [fila for fila in resultados if fila["particion"] == "prueba"]
    if not parte_prueba:
        avisos.append("No hay grupos nuevos reservados para prueba: los resultados de desarrollo "
                      "no demuestran generalización a escenas nuevas.")
    else:
        avisos.append("La partición de prueba contiene grupos ajenos al desarrollo registrado. "
                      "Si se usan para retocar reglas, deben pasar a desarrollo en la siguiente versión.")
    nuevas = sorted({fila["nombre_real"] for fila in resultados}
                    - set(clasificacion.CLASES_SOPORTADAS))
    if nuevas:
        avisos.append("Clases etiquetadas sin reglas propias: " + ", ".join(nuevas)
                      + ". Añadir etiquetas no entrena ni amplía el clasificador.")
    return {
        "version_clasificador": clasificacion.VERSION_CLASIFICADOR,
        "clases_soportadas": list(clasificacion.CLASES_SOPORTADAS),
        "grupos_desarrollo_registrados": sorted(clasificacion.GRUPOS_DESARROLLO),
        "alcance": "Clasificación de objetos ya detectados y etiquetados manualmente.",
        "desarrollo": _resumen(parte_desarrollo), "prueba": _resumen(parte_prueba),
        "total": _resumen(resultados), "filas": resultados, "matriz": _matriz(resultados),
        "avisos": avisos, "exclusiones": exclusiones, "duplicados_omitidos": duplicados,
    }


def inventario_objetos(objetos, esperadas=None):
    """Cuenta predicciones del fotograma, sin deducir un inventario del catálogo.

    ``esperadas`` es opcional: {nombre: cantidad entera >= 0}. Si está presente
    describe el inventario completo; las clases no incluidas tienen esperado 0.
    Faltantes y repetidos son diferencias de cantidades, no identificadores.
    Las detecciones desconocidas/ambiguas hacen provisional la comparación.
    No conserva recuentos de pistas de fotogramas anteriores.
    """
    previstas = None
    if esperadas is not None:
        if not isinstance(esperadas, dict):
            raise ValueError("El inventario esperado debe ser un diccionario de cantidades.")
        previstas = {}
        for nombre, cantidad in esperadas.items():
            if not isinstance(nombre, str) or not nombre.strip():
                raise ValueError("Cada herramienta esperada debe tener un nombre.")
            nombre = " ".join(nombre.split())
            if nombre in previstas:
                raise ValueError(f"La herramienta esperada {nombre!r} está repetida.")
            if type(cantidad) is not int or cantidad < 0:
                raise ValueError("Las cantidades esperadas deben ser enteros no negativos.")
            previstas[nombre] = cantidad
    presentes = Counter()
    desconocidos = ambiguos = total = 0
    for objeto in objetos:
        total += 1
        nombre = objeto.get("clase_predicha")
        if (objeto.get("estado_clasificacion") == "identificada"
                and nombre in clasificacion.CLASES_SOPORTADAS):
            presentes[nombre] += 1
        else:
            desconocidos += 1
            ambiguos += objeto.get("estado_clasificacion") == "ambigua"
    faltantes = repetidos = None
    if previstas is not None:
        faltantes = {nombre: cantidad - presentes[nombre]
                     for nombre, cantidad in sorted(previstas.items()) if cantidad > presentes[nombre]}
        repetidos = {nombre: cantidad - previstas.get(nombre, 0)
                     for nombre, cantidad in sorted(presentes.items())
                     if cantidad > previstas.get(nombre, 0)}
    avisos = ["Recuento del fotograma actual; no cuenta de nuevo las pistas de fotogramas anteriores."]
    if desconocidos:
        avisos.append("Inventario provisional: quedan objetos desconocidos o ambiguos; "
                      "los faltantes podrían estar entre ellos.")
    if previstas is None:
        avisos.append("No se ha definido un inventario esperado; no se deducen faltantes ni repetidos.")
    else:
        avisos.append("La comparación solo usa objetos detectados. Una omisión o un objeto fuera "
                      "del tapete también puede aparecer como faltante.")
    return {
        "presentes": dict(sorted(presentes.items())), "total": total,
        "reconocidos": sum(presentes.values()), "desconocidos": desconocidos,
        "ambiguos": ambiguos, "esperadas": previstas,
        "faltantes": faltantes, "repetidos": repetidos, "provisional": bool(desconocidos),
        "completo": None if previstas is None or desconocidos else not faltantes and not repetidos,
        "avisos": avisos,
    }
