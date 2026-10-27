"""Reconocimiento explicable y comprobación con referencias manuales guardadas."""

import csv
from io import BytesIO, StringIO
import json
from pathlib import Path
import unicodedata
import zipfile

import cv2
import pandas as pd
import streamlit as st

from analisis import reunir_datos
from clasificacion import CLASES_SOPORTADAS, VERSION_CLASIFICADOR, clasificar_objetos, snapshot_reglas
from etiquetado import firma_deteccion, huella_imagen
from evaluacion import evaluar_filas, inventario_objetos
from vision import dibujar_resultado


def vista_reconocimiento(resultado, objetos):
    dibujables = []
    for objeto in objetos:
        texto = f"{objeto['id']} {objeto['clase_predicha']}"
        texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
        dibujables.append({**objeto, "id": texto})
    return dibujar_resultado({**resultado, "objetos": dibujables}, telemetria=False)


def csv_predicciones(filas):
    campos = ["fuente", "captura", "id", "nombre_real", "clase_predicha", "estado_clasificacion",
              "particion", "resultado", "regla", "explicacion", "version_clasificador"]
    salida = StringIO(newline="")
    escritor = csv.DictWriter(salida, fieldnames=campos, delimiter=";", extrasaction="ignore")
    escritor.writeheader()
    escritor.writerows(filas)
    return salida.getvalue().encode("utf-8-sig")


def paquete_reconocimiento(resultado, objetos, sesion, origen, imagen, inventario):
    """Descarga reproducible; no escribe ni confirma etiquetas en el proyecto."""
    filas = [{clave: valor for clave, valor in objeto.items()
              if clave in ("id", "clase_predicha", "estado_clasificacion", "regla",
                           "explicacion", "ruta_decision", "version_clasificador")}
             for objeto in objetos]
    informe = {"fuente": str(origen), "huella_imagen": huella_imagen(imagen),
               "firma_deteccion": firma_deteccion(imagen, sesion["valores"], resultado),
               "etiquetas_confirmadas_por_esta_operacion": False,
               "predicciones": filas, "inventario": inventario}
    memoria = BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as archivo:
        for nombre, datos in (("predicciones.json", informe), ("reglas.json", snapshot_reglas()),
                              ("configuracion.json", sesion["valores"])):
            archivo.writestr(nombre, json.dumps(datos, ensure_ascii=False, indent=2))
        archivo.writestr("predicciones.csv", csv_predicciones([{**f, "fuente": str(origen)} for f in filas]))
        for nombre, datos in (("imagen_origen.png", imagen), ("mascara.png", resultado["mascara"]),
                              ("reconocimiento.png", vista_reconocimiento(resultado, objetos))):
            correcto, codificada = cv2.imencode(".png", datos)
            if not correcto:
                raise ValueError(f"No se ha podido codificar {nombre}.")
            archivo.writestr(nombre, codificada.tobytes())
    return memoria.getvalue()


def mostrar_inventario(objetos, token):
    st.markdown("#### Inventario de esta imagen")
    esperadas = None
    with st.expander("Comparar con un inventario esperado"):
        comparar = st.checkbox("Definir cantidades esperadas", key=f"comparar_{token}")
        st.caption("Indica todas las herramientas que deberían estar. Las no incluidas se consideran sobrantes.")
        if comparar:
            clases = st.multiselect("Herramientas esperadas", list(CLASES_SOPORTADAS),
                                    key=f"esperadas_{token}")
            esperadas = {nombre: st.number_input(f"Cantidad esperada · {nombre}", 1, 100, 1,
                                                 key=f"cantidad_{token}_{nombre}") for nombre in clases}
            if not clases:
                st.caption("Has indicado un inventario vacío: cualquier herramienta reconocida contará como sobrante.")
    inventario = inventario_objetos(objetos, esperadas)
    clases = sorted(set(inventario["presentes"]) | set(esperadas or {}))
    if clases:
        tabla = [{"Herramienta": nombre, "Reconocidas": inventario["presentes"].get(nombre, 0)} for nombre in clases]
        if esperadas is not None:
            for fila in tabla:
                nombre = fila["Herramienta"]
                fila.update(Esperadas=esperadas.get(nombre, 0),
                            Faltan=inventario["faltantes"].get(nombre, 0),
                            Sobran=inventario["repetidos"].get(nombre, 0))
        st.dataframe(tabla, hide_index=True, width="stretch")
    else:
        st.info("No hay herramientas reconocidas en esta imagen.")
    if inventario["desconocidos"]:
        st.warning(f"Hay {inventario['desconocidos']} objetos sin identificar; la comparación de inventario es provisional.")
    elif inventario["completo"] is True:
        st.success("Las cantidades reconocidas coinciden con el inventario esperado.")
    st.caption("El recuento depende de que todas las herramientas estén visibles y separadas. Una omisión de detección también puede aparecer como faltante.")
    return inventario


def _porcentaje(valor):
    return "Sin datos" if valor is None else f"{valor:.1%}"


def mostrar_evaluacion(base):
    st.markdown("#### Comprobar las predicciones con tus etiquetas")
    st.write("La comparación usa únicamente sesiones guardadas y etiquetas confirmadas. No utiliza las predicciones como respuestas correctas.")
    if st.button("Evaluar sesiones guardadas", key="evaluar_reglas"):
        with st.spinner("Comparando predicciones y referencias manuales…"):
            datos = reunir_datos(base)
            st.session_state["evaluacion_reglas"] = {
                "base": str(base), "version": VERSION_CLASIFICADOR,
                "informe": evaluar_filas(datos["filas"]), "resumen": datos["resumen"],
                "avisos_datos": datos["avisos"],
            }
    guardada = st.session_state.get("evaluacion_reglas")
    if not guardada or guardada["base"] != str(base) or guardada["version"] != VERSION_CLASIFICADOR:
        st.caption("Pulsa Evaluar después de guardar o modificar tus referencias.")
        return
    informe = guardada["informe"]
    st.caption("Resultado de la última pulsación de Evaluar; vuelve a pulsar tras guardar nuevas etiquetas.")
    parte = st.radio("Muestras para comprobar", ["Desarrollo", "Grupos nuevos"], horizontal=True,
                     key="particion_evaluacion")
    clave = "desarrollo" if parte == "Desarrollo" else "prueba"
    medidas = informe[clave]
    if clave == "desarrollo":
        st.info("Estas muestras sirvieron para definir las reglas. Sus aciertos describen el ajuste al desarrollo, no la precisión en escenas nuevas.")
    elif medidas["total"] == 0:
        st.info("Todavía no hay una prueba independiente: graba otro clip o una nueva disposición, etiqueta algunas escenas y guárdalas.")
    else:
        st.info("Estos grupos no figuran en el desarrollo registrado. Si los usas para cambiar reglas, deberán pasar a desarrollo en la próxima versión.")
    columnas = st.columns(4)
    columnas[0].metric("Objetos evaluados", medidas["total"])
    columnas[1].metric("Aciertos sobre el total", _porcentaje(medidas["exactitud_total"]))
    columnas[2].metric("Errores de nombre", medidas["errores"])
    columnas[3].metric("Sin identificar", medidas["rechazos"])
    st.caption(f"{medidas['imagenes']} imágenes · {medidas['grupos']} grupos de adquisición. "
               "Los fotogramas de un mismo clip permanecen juntos. Estas cifras solo evalúan objetos detectados y etiquetados; no miden omisiones de detección.")
    filas = [f for f in informe["filas"] if f["particion"] == clave]
    if medidas["matriz"]:
        matriz = pd.DataFrame(medidas["matriz"]).pivot(index="nombre_real", columns="clase_predicha", values="cantidad").fillna(0).astype(int)
        st.caption("Filas: etiqueta real · Columnas: predicción automática.")
        st.dataframe(matriz, width="stretch")
    with st.expander("Ver errores, rechazos y procedencia"):
        problemas = [f for f in filas if f["resultado"] != "acierto"]
        if problemas:
            st.dataframe([{k: f.get(k) for k in ("fuente", "id", "nombre_real", "clase_predicha", "resultado", "explicacion")}
                          for f in problemas], hide_index=True, width="stretch")
        else:
            st.write("Sin discrepancias en esta selección." if filas else "Sin muestras en esta selección.")
        for aviso in [*informe["avisos"], *guardada["avisos_datos"]]:
            st.caption(aviso)
    informe_exportado = {**informe, "reglas": snapshot_reglas(), "resumen_datos": guardada["resumen"]}
    st.download_button("Descargar evaluación · JSON", json.dumps(informe_exportado, ensure_ascii=False, indent=2),
                       "evaluacion_reglas.json", "application/json", key="json_evaluacion")
    st.download_button("Descargar comparación · CSV", csv_predicciones(informe["filas"]),
                       "evaluacion_reglas.csv", "text/csv", key="csv_evaluacion")


def mostrar_reconocimiento(base, resultado, sesion, origen, imagen, token):
    st.markdown("### Reconocimiento automático")
    st.write("Las reglas asignan un nombre a partir de la forma. Si la silueta no encaja claramente, aparece como Desconocido.")
    objetos = clasificar_objetos(resultado["objetos"])
    for aviso in resultado["avisos"]:
        st.warning(aviso)
    izquierda, derecha = st.columns(2)
    with izquierda:
        st.image(vista_reconocimiento(resultado, objetos), channels="BGR", width="stretch")
        st.caption("Predicciones automáticas. Los números corresponden a esta detección.")
    with derecha:
        st.image(resultado["mascara"], width="stretch")
        st.caption("Comprueba que cada silueta corresponda a una sola herramienta completa.")
    st.dataframe([{"Objeto": o["id"], "Predicción": o["clase_predicha"],
                   "Estado": o["estado_clasificacion"], "Regla": o["regla"], "Por qué": o["explicacion"]}
                  for o in objetos], hide_index=True, width="stretch")
    st.caption("Las predicciones no modifican tus etiquetas manuales. Añadir una herramienta al catálogo permite etiquetarla, pero su reconocimiento necesita una regla propia.")
    inventario = mostrar_inventario(objetos, token)
    st.download_button("Descargar reconocimiento · ZIP", paquete_reconocimiento(resultado, objetos, sesion, origen, imagen, inventario),
                       f"reconocimiento_{Path(origen).stem}.zip", "application/zip", key=f"reconocimiento_zip_{token}")
    with st.expander("Por qué se ha elegido cada nombre"):
        if objetos:
            elegido = st.selectbox("Decisión del objeto", [o["id"] for o in objetos], key=f"decision_{token}")
            objeto = next(o for o in objetos if o["id"] == elegido)
            st.write(objeto["explicacion"])
            st.json(objeto["ruta_decision"], expanded=False)
        st.caption(f"{VERSION_CLASIFICADOR} · Reglas manuales con ocho medidas geométricas. Sin entrenamiento ni redes neuronales.")
        st.download_button("Descargar reglas y umbrales · JSON", json.dumps(snapshot_reglas(), ensure_ascii=False, indent=2),
                           "reglas_herramientas.json", "application/json", key="descargar_reglas")
    st.divider()
    mostrar_evaluacion(base)
