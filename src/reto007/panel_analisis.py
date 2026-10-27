"""Comparación exploratoria de medidas confirmadas; no entrena clasificadores."""

import csv
import colorsys
from io import StringIO
import json
from pathlib import Path

import altair as alt
import cv2
import numpy as np
import pandas as pd
import streamlit as st

from analisis import reunir_datos
from configuracion import cargar_configuracion
from detector import METRICAS
from etiquetado import CLASES, firma_deteccion, huella_imagen
from geometria import VERSION_CARACTERISTICAS
from vision import procesar_imagen


NOMBRES_MEDIDAS = {
    "relacion_aspecto": "Relación de aspecto",
    "solidez": "Solidez",
    "circularidad": "Circularidad",
    "extension": "Ocupación de la caja",
    "contraste_extremos": "Contraste entre extremos",
    "fraccion_ancha": "Fracción ancha",
    "asimetria_longitudinal": "Asimetría longitudinal",
    "ancho_central": "Anchura central relativa",
    "area_px2": "Área · px²",
    "perimetro_px": "Perímetro · px",
    "largo_px": "Largo · px",
    "corto_px": "Ancho · px",
}
MEDIDAS_PIXELES = {"area_px2", "perimetro_px", "largo_px", "corto_px"}
COLORES = ["#54c9bf", "#f2b84b", "#b599f4", "#fa8279", "#74b8f5", "#b6d871"]


def csv_analisis(filas):
    """Exporta la selección y su procedencia, con el mismo formato del detector."""
    columnas = ["nombre_real", "id", "captura", "fuente", "sesion", "actual",
                "huella_imagen", "firma_deteccion", "zoom", "version_caracteristicas",
                *METRICAS, "perfil_posiciones", "perfil_ancho"]
    salida = StringIO(newline="")
    escritor = csv.DictWriter(salida, fieldnames=columnas, delimiter=";", extrasaction="ignore")
    escritor.writeheader()
    for fila in filas:
        copia = dict(fila)
        for clave in METRICAS:
            if clave in copia:
                copia[clave] = f"{float(copia[clave]):.6f}"
        for clave in ("perfil_posiciones", "perfil_ancho"):
            copia[clave] = json.dumps(copia.get(clave, []), separators=(",", ":"))
        escritor.writerow(copia)
    return salida.getvalue().encode("utf-8-sig")


def resumen_por_clase(filas, medida):
    """Rangos observados, sin confundir el número de filas con escenas nuevas."""
    tabla = pd.DataFrame(filas)
    return (tabla.groupby("nombre_real", sort=False).agg(
        Objetos=(medida, "size"),
        Fotos=("huella_imagen", "nunique"),
        Capturas=("captura", "nunique"),
        Mínimo=(medida, "min"),
        Mediana=(medida, "median"),
        Máximo=(medida, "max"),
    ).reset_index().rename(columns={"nombre_real": "Herramienta"}))


def clases_presentes(filas):
    """Incluye clases de sesiones portables, aunque no estén en el catálogo local."""
    nombres = {f["nombre_real"] for f in filas}
    return ([c for c in CLASES if c in nombres]
            + sorted(nombres - set(CLASES), key=lambda nombre: (nombre.casefold(), nombre)))


def _color(filas):
    presentes = clases_presentes(filas)
    extras = [c for c in presentes if c not in CLASES]
    colores_extra = []
    for indice in range(len(extras)):
        rgb = colorsys.hsv_to_rgb((.05 + indice * .61803398875) % 1, .48, .9)
        colores_extra.append("#" + "".join(f"{round(c * 255):02x}" for c in rgb))
    return alt.Color("nombre_real:N", title="Etiqueta manual",
                     scale=alt.Scale(domain=[*CLASES, *extras], range=COLORES + colores_extra),
                     legend=alt.Legend(values=presentes))


def grafico_dispersion(filas, eje_x, eje_y):
    columnas = ["nombre_real", "id", "captura", "fuente", eje_x, eje_y]
    tabla = pd.DataFrame(filas)[list(dict.fromkeys(columnas))].copy()
    tabla["foto"] = tabla["fuente"].map(lambda p: Path(p).name)
    return alt.Chart(tabla).mark_circle(size=120, opacity=.8, strokeWidth=1).encode(
        x=alt.X(f"{eje_x}:Q", title=NOMBRES_MEDIDAS[eje_x], scale=alt.Scale(zero=False)),
        y=alt.Y(f"{eje_y}:Q", title=NOMBRES_MEDIDAS[eje_y], scale=alt.Scale(zero=False)),
        color=_color(filas),
        tooltip=[alt.Tooltip("nombre_real:N", title="Herramienta"),
                 alt.Tooltip("foto:N", title="Foto"), alt.Tooltip("id:O", title="Objeto"),
                 alt.Tooltip(f"{eje_x}:Q", title=NOMBRES_MEDIDAS[eje_x], format=".4f"),
                 alt.Tooltip(f"{eje_y}:Q", title=NOMBRES_MEDIDAS[eje_y], format=".4f")],
    ).properties(height=320).interactive()


def grafico_perfiles(filas):
    puntos = []
    for fila in filas:
        for posicion, ancho in zip(fila.get("perfil_posiciones", []), fila.get("perfil_ancho", [])):
            puntos.append({"nombre_real": fila["nombre_real"], "posicion": posicion,
                           "ancho": ancho, "foto": Path(fila["fuente"]).name,
                           "id": fila["id"], "serie": f"{fila['huella_imagen']}_{fila['id']}"})
    return alt.Chart(alt.Data(values=puntos)).mark_line(opacity=.65, strokeWidth=2).encode(
        x=alt.X("posicion:Q", title="Posición a lo largo de la herramienta", axis=alt.Axis(format="%"),
                scale=alt.Scale(domain=[0, 1])),
        y=alt.Y("ancho:Q", title="Anchura / lado corto de la caja", scale=alt.Scale(domain=[0, 1])),
        color=_color(filas), detail="serie:N", order="posicion:Q",
        tooltip=[alt.Tooltip("nombre_real:N", title="Herramienta"),
                 alt.Tooltip("foto:N", title="Foto"), alt.Tooltip("id:O", title="Objeto"),
                 alt.Tooltip("posicion:Q", title="Posición", format=".0%"),
                 alt.Tooltip("ancho:Q", title="Anchura relativa", format=".3f")],
    ).properties(height=320)


def miniaturas_etiquetas(filas, actual):
    """Obtiene recortes de una sola foto, comprobando de nuevo su procedencia."""
    primera = filas[0]
    if primera["actual"]:
        imagen, valores = actual["imagen"], actual["valores"]
    else:
        carpeta = Path(primera["sesion"])
        imagen = cv2.imread(str(carpeta / "imagen_origen.png"))
        valores = cargar_configuracion(carpeta / "configuracion.json")
    if imagen is None or huella_imagen(imagen) != primera["huella_imagen"]:
        raise ValueError("La fotografía ha cambiado. Actualiza el análisis antes de revisar las etiquetas.")
    resultado = procesar_imagen(imagen, valores)
    if firma_deteccion(imagen, valores, resultado) != primera["firma_deteccion"]:
        raise ValueError("La detección ha cambiado. Actualiza el análisis.")
    miniaturas = []
    for fila in filas:
        objeto = next(o for o in resultado["objetos"] if o["id"] == fila["id"])
        x, y, ancho, alto = cv2.boundingRect(objeto["contorno"])
        recorte = resultado["imagen"][y:y + alto, x:x + ancho].copy()
        mascara = np.zeros((alto, ancho), np.uint8)
        contorno = objeto["contorno"] - np.array([x, y])
        cv2.drawContours(mascara, [contorno.astype(np.int32)], -1, 255, cv2.FILLED)
        recorte[mascara == 0] = (25, 28, 33)
        factor = min(180 / ancho, 190 / alto)
        nuevo_ancho, nuevo_alto = max(1, round(ancho * factor)), max(1, round(alto * factor))
        lienzo = np.full((210, 200, 3), (25, 28, 33), np.uint8)
        x0, y0 = (200 - nuevo_ancho) // 2, (210 - nuevo_alto) // 2
        lienzo[y0:y0 + nuevo_alto, x0:x0 + nuevo_ancho] = cv2.resize(recorte, (nuevo_ancho, nuevo_alto))
        miniaturas.append((fila, lienzo))
    return miniaturas


def mostrar_analisis(base, actual):
    st.markdown("### Comparar herramientas")
    st.write("Explora las medidas de tus etiquetas confirmadas para elegir las reglas del árbol de decisión.")
    incluir = st.checkbox("Incluir etiquetas confirmadas de la foto abierta", value=True,
                          key="analisis_incluir_actual",
                          help="Sustituye cualquier versión guardada de los mismos píxeles, incluso si hay cambios sin guardar.")
    datos = reunir_datos(base=base, actual=actual if incluir else None)
    filas, resumen = datos["filas"], datos["resumen"]
    for col, titulo, valor in zip(st.columns(4),
                                 ("Objetos de referencia", "Clases representadas", "Fotos distintas", "Capturas agrupadas"),
                                 (resumen["objetos_confirmados"], resumen["clases"], resumen["imagenes_unicas"], resumen["capturas"])):
        col.metric(titulo, valor)
    st.caption("Cada original y su recorte comparten captura. Volver a guardar una foto no añade otra muestra. "
               "Estos recuentos no representan escenas independientes de evaluación.")
    st.info("Las fotos de una misma disposición sirven para explorar medidas. Reserva escenas nuevas, "
            "con otras posiciones y orientaciones, para comprobar las reglas y medir aciertos.")
    with st.expander("Qué datos se han incluido"):
        st.write("Se recalculan las medidas con los ajustes de cada sesión y se comprueban los píxeles, "
                 "la detección y sus etiquetas. Solo se usa la última versión de cada foto; "
                 "las propuestas pendientes quedan fuera.")
        for aviso in datos["avisos"]:
            st.write(aviso)
        if datos["exclusiones"]:
            st.dataframe(datos["exclusiones"], hide_index=True, width="stretch")
        st.caption(f"Descriptores: {VERSION_CARACTERISTICAS}. Las sesiones antiguas se leen sin sobrescribir sus archivos.")
    if not filas:
        st.info("Todavía no hay etiquetas confirmadas vigentes para comparar. "
                "Revisa los objetos en «Calibración y etiquetas» y guarda una sesión.")
        return

    with st.expander("Revisar visualmente las etiquetas usadas"):
        st.write("Una confirmación guardada no garantiza que el nombre sea correcto. Comprueba estos recortes "
                 "antes de interpretar los gráficos; al girar la foto también puede cambiar el orden de los IDs.")
        fuentes = {f["huella_imagen"]: f for f in filas}
        elegida = st.selectbox("Foto para comprobar etiquetas", list(fuentes),
                               format_func=lambda h: Path(fuentes[h]["fuente"]).name + (" · abierta" if fuentes[h]["actual"] else ""),
                               key="analisis_auditoria")
        revision = [f for f in filas if f["huella_imagen"] == elegida]
        try:
            miniaturas = miniaturas_etiquetas(revision, actual)
            for inicio in range(0, len(miniaturas), 3):
                for col, (fila, miniatura) in zip(st.columns(3), miniaturas[inicio:inicio + 3]):
                    col.image(miniatura, channels="BGR", width="stretch")
                    col.caption(f"Objeto {fila['id']} · {fila['nombre_real']}")
        except (OSError, ValueError, cv2.error) as error:
            st.warning(str(error))
        st.caption("Para corregir: abre esta foto desde «Sesiones guardadas», cambia sus etiquetas en "
                   "«Calibración y etiquetas» y guarda una nueva sesión.")

    clases = clases_presentes(filas)
    iniciales = [c for c in ("Calibre", "Martillo") if c in clases]
    controles = st.columns([2, 1])
    elegidas = controles[0].multiselect("Herramientas a comparar", clases,
                                       default=iniciales if len(iniciales) == 2 else clases,
                                       key="analisis_clases")
    capturas = sorted({f["captura"] for f in filas})
    captura = controles[1].selectbox("Captura de referencia", ["Todas", *capturas], key="analisis_captura")
    seleccion = [f for f in filas if f["nombre_real"] in elegidas and (captura == "Todas" or f["captura"] == captura)]
    if not seleccion:
        st.info("Selecciona al menos una herramienta presente en la captura elegida.")
        return

    st.caption("Los cocientes reducen el efecto del tamaño, pero siguen cambiando con la segmentación, "
               "la resolución y la perspectiva. Área y longitudes en píxeles requieren la misma escala física.")
    izquierda, derecha = st.columns(2)
    claves = list(NOMBRES_MEDIDAS)
    eje_x = izquierda.selectbox("Medida horizontal", claves, format_func=NOMBRES_MEDIDAS.get,
                                index=claves.index("relacion_aspecto"), key="analisis_x")
    eje_y = derecha.selectbox("Medida vertical", claves, format_func=NOMBRES_MEDIDAS.get,
                              index=claves.index("ancho_central"), key="analisis_y")
    if eje_x in MEDIDAS_PIXELES or eje_y in MEDIDAS_PIXELES:
        st.warning("Estás comparando píxeles. Un original y su recorte tienen distinta escala aunque pertenezcan "
                   "a la misma captura. No fijes un umbral de tamaño mezclándolos.")
    st.altair_chart(grafico_dispersion(seleccion, eje_x, eje_y), width="stretch")
    st.caption("Cada punto es un objeto etiquetado. Pasa el cursor para ver su foto y sus valores; "
               "puedes ampliar el gráfico. Los puntos coincidentes pueden superponerse.")

    st.markdown("#### Cómo cambia la anchura")
    st.altair_chart(grafico_perfiles(seleccion), width="stretch")
    st.caption("Cada línea corresponde a un objeto. Se alinea con su eje largo y se coloca primero el extremo "
               "más ancho en promedio. El perfil mide 40 secciones del contorno exterior; incluye el espacio "
               "entre ramas y no descuenta huecos interiores. No identifica automáticamente la cabeza ni el mango.")

    st.markdown("#### Rangos observados")
    medida = st.selectbox("Medida para la tabla", claves, format_func=NOMBRES_MEDIDAS.get,
                          index=claves.index("ancho_central"), key="analisis_rango")
    if medida in MEDIDAS_PIXELES and eje_x not in MEDIDAS_PIXELES and eje_y not in MEDIDAS_PIXELES:
        st.warning("Esta tabla mide píxeles: controla la escala física antes de comparar sus rangos.")
    tabla = resumen_por_clase(seleccion, medida)
    st.dataframe(tabla, hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="%.4f") for c in ("Mínimo", "Mediana", "Máximo")})
    st.caption("Mínimo y máximo describen estas fotos, no el rango garantizado de una clase. "
               "Con una sola observación no se puede estimar su variabilidad.")

    with st.expander("Qué significa cada medida"):
        st.markdown(
            "- **Ocupación de la caja:** área del contorno / área de su rectángulo mínimo.\n"
            "- **Contraste entre extremos:** diferencia absoluta entre las anchuras medias del primer y último 20 %, "
            "dividida por la mayor.\n"
            "- **Fracción ancha:** proporción de las 40 secciones que alcanzan la mitad del lado corto de la caja.\n"
            "- **Asimetría longitudinal:** diferencia media absoluta entre el perfil normalizado y su inverso.\n"
            "- **Anchura central relativa:** media del perfil entre el 40 % y el 60 % del largo.\n\n"
            "Las cinco medidas están entre 0 y 1. Se calculan por geometría; no se ha entrenado un modelo ni definido aún un árbol."
        )
    with st.expander("Mediciones individuales y procedencia"):
        columnas = ["nombre_real", "id", "captura", *NOMBRES_MEDIDAS, "actual", "fuente", "sesion"]
        st.dataframe(pd.DataFrame(seleccion)[columnas], hide_index=True, width="stretch")
    st.download_button("Descargar comparación · CSV", csv_analisis(seleccion),
                       file_name="comparacion_herramientas.csv", mime="text/csv", key="descargar_analisis")
    st.caption("Descarga las filas de la selección con medidas, perfiles y procedencia. "
               "Las nuevas sesiones guardan además los perfiles en perfiles.json.")
