"""Mesa de vídeo local: reproducción analítica, ajustes y exportación."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
import tempfile
import time
import uuid
import unicodedata

import cv2
import streamlit as st

from configuracion import cargar_configuracion, guardar_configuracion, validar_configuracion
from clasificacion import VERSION_CLASIFICADOR, clasificar_objetos
from seguimiento import SeguidorObjetos
from video import (
    listar_videos, inspeccionar_video, leer_fotograma, configuracion_para_video,
    exportar_fotograma, exportar_video, conteo_fotograma, es_video_desarrollo,
)
from vision import dibujar_resultado, procesar_imagen


VERSION_PANEL_VIDEO = 4


@st.cache_data(show_spinner=False, max_entries=12)
def metadatos_video(ruta, tamano, modificado, cambiado, inode):
    """Invalida la huella también al reemplazar un archivo con la misma fecha."""
    return inspeccionar_video(ruta)


def importar_video(datos, nombre, base):
    """Valida una copia local antes de publicarla; nunca reemplaza otro vídeo."""
    extension = Path(nombre).suffix.lower()
    if extension not in (".avi", ".mp4", ".mov", ".mkv", ".m4v"):
        raise ValueError("Utiliza un vídeo AVI, MP4, MOV, MKV o M4V.")
    if not datos:
        raise ValueError("El archivo de vídeo está vacío.")
    huella = hashlib.sha256(datos).hexdigest()
    carpeta = Path(base) / "videos" / "importados"
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"video_{huella}{extension}"
    if destino.exists():
        if hashlib.sha256(destino.read_bytes()).hexdigest() != huella:
            raise ValueError("La copia importada ha cambiado. Usa otro archivo o revisa esa copia.")
        return destino
    with tempfile.TemporaryDirectory(prefix=".importando_", dir=carpeta) as temporal:
        preparado = Path(temporal) / ("video" + extension)
        preparado.write_bytes(datos)
        inspeccionar_video(preparado)
        # Un enlace exclusivo impide pisar una importación concurrente.
        import os
        try:
            os.link(preparado, destino)
        except FileExistsError:
            if hashlib.sha256(destino.read_bytes()).hexdigest() != huella:
                raise ValueError("Otra importación ocupa este destino con un contenido diferente.")
    return destino


def ruta_ajustes_video(base, huella):
    return Path(base) / "videos" / "ajustes" / f"{huella}.json"


def nueva_sesion_video(ruta, info, base):
    ajustes = ruta_ajustes_video(base, info["huella"])
    valores = cargar_configuracion(ajustes) if ajustes.exists() else configuracion_para_video(ruta)
    return {"valores": valores, "indice": 0, "reproduciendo": False,
            "seguidor": SeguidorObjetos(), "cache": None, "resultado": None,
            "objetos": [], "salto": False, "ultimo_avance": time.monotonic(),
            "foto_guardada": None, "exportacion": None, "aviso": "", "modificada": False,
            "version_panel_video": VERSION_PANEL_VIDEO, "version_clasificador": VERSION_CLASIFICADOR}


def migrar_sesion_video(sesion):
    """Actualiza el cálculo sin perder ajustes, exportaciones o fotos pendientes."""
    if (sesion.get("version_panel_video") != VERSION_PANEL_VIDEO
            or sesion.get("version_clasificador") != VERSION_CLASIFICADOR):
        sesion.update(cache=None, reproduciendo=False, version_panel_video=VERSION_PANEL_VIDEO,
                      version_clasificador=VERSION_CLASIFICADOR)
        sesion["seguidor"].reiniciar()


def procesar_posicion(sesion, ruta, info):
    migrar_sesion_video(sesion)
    contexto = info["huella"] + VERSION_CLASIFICADOR + json.dumps(sesion["valores"], sort_keys=True)
    clave = (contexto, sesion["indice"])
    if sesion["cache"] != clave:
        imagen, posicion = leer_fotograma(ruta, sesion["indice"])
        resultado = procesar_imagen(imagen, sesion["valores"])
        objetos = clasificar_objetos(sesion["seguidor"].actualizar(resultado["objetos"], sesion["indice"], contexto=contexto))
        sesion.update(cache=clave, resultado=resultado, objetos=objetos, posicion=posicion)
    return sesion["resultado"], sesion["objetos"]


def vista_video(resultado, objetos):
    # Solo la copia destinada a dibujar cambia su texto; los IDs locales se
    # conservan en el procesamiento, las tablas y los CSV.
    para_dibujar = []
    for objeto in objetos:
        texto = f"P{objeto['id_pista']} {objeto['clase_predicha']}"
        texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
        # OpenCV no dibuja acentos; las tablas conservan los nombres completos.
        # Recortar la leyenda evita salir de la imagen incluso con nombres largos.
        while cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, .65, 2)[0][0] > resultado["imagen"].shape[1] - 28:
            texto = texto[:-4] + "..." if texto.endswith("...") else texto[:-1] + "..."
        para_dibujar.append({**objeto, "id": texto})
    return dibujar_resultado({**resultado, "objetos": para_dibujar}, telemetria=False)


def elegir_video(base):
    st.sidebar.markdown("### Vídeo de prueba")
    fuente = st.sidebar.radio("Origen del vídeo", ["Vídeos guardados", "Otro vídeo"], key="origen_video")
    if fuente == "Otro vídeo":
        archivo = st.sidebar.file_uploader("Importar vídeo local", type=["avi", "mp4", "mov", "mkv", "m4v"],
                                           key="archivo_video")
        if archivo is not None:
            token = (archivo.name, archivo.size, getattr(archivo, "file_id", None))
            anterior = st.session_state.get("video_importado")
            if not anterior or anterior[0] != token:
                with st.spinner("Comprobando y copiando el vídeo…"):
                    ruta = importar_video(archivo.getvalue(), archivo.name, base)
                st.session_state["video_importado"] = (token, str(ruta))
            return Path(st.session_state["video_importado"][1])
        st.sidebar.caption("Para vídeos grandes también puedes escribir su ruta en este Mac.")
        with st.sidebar.form("ruta_video_local"):
            ruta = st.text_input("Ruta del vídeo", placeholder="/Users/…/prueba.mov")
            abrir = st.form_submit_button("Abrir vídeo")
        if abrir:
            candidata = Path(ruta).expanduser().resolve()
            if not ruta.strip() or not candidata.is_file():
                st.sidebar.error("Indica la ruta de un archivo de vídeo existente.")
            elif candidata.suffix.lower() not in (".avi", ".mp4", ".mov", ".mkv", ".m4v"):
                st.sidebar.error("Utiliza un archivo AVI, MP4, MOV, MKV o M4V.")
            else:
                st.session_state["video_ruta_local"] = str(candidata)
        elegida = st.session_state.get("video_ruta_local")
        return Path(elegida) if elegida else None
    opciones = listar_videos(base)
    if not opciones:
        return None
    return st.sidebar.selectbox("Vídeo guardado", opciones, key="video_elegido",
                                 format_func=lambda p: f"{p.parent.name} / {p.name}")


def mostrar_video(base, controles_ajustes):
    st.markdown("### Laboratorio de vídeo")
    st.write("Reconoce herramientas por sus formas, sigue su movimiento y revisa la regla aplicada a cada predicción.")
    try:
        ruta = elegir_video(base)
        if ruta is None:
            st.info("Graba un vídeo en casa con el calibrador y pulsa R para iniciar o detener la grabación. "
                    "Después aparecerá en «Vídeos guardados». También puedes abrir otro vídeo local.")
            st.code("python3 calibrador.py --camara 1", language="bash")
            st.write("Haz uno o dos clips de 30–60 segundos: mueve y gira las herramientas despacio, "
                     "deja pausas con las manos fuera y prueba a retirar alguna. Mantén la cámara fija.")
            return
        estado_archivo = ruta.stat()
        info = metadatos_video(str(ruta), estado_archivo.st_size, estado_archivo.st_mtime_ns,
                              estado_archivo.st_ctime_ns, estado_archivo.st_ino)
        token = "video_" + info["huella"]
        sesiones = st.session_state.setdefault("sesiones_video", {})
        if token not in sesiones:
            sesiones[token] = nueva_sesion_video(ruta, info, base)
        sesion = sesiones[token]
        migrar_sesion_video(sesion)
        for otro_token, otra in sesiones.items():
            if otro_token != token:
                otra["reproduciendo"] = False
        candidatos = controles_ajustes(sesion, token)
        if candidatos is not None:
            try:
                nuevos = validar_configuracion(candidatos)
                if nuevos != sesion["valores"]:
                    sesion.update(valores=nuevos, cache=None, reproduciendo=False, modificada=True)
                    sesion["seguidor"].reiniciar()
                    sesion["aviso"] = "Ajustes aplicados. El seguimiento empieza de nuevo en este fotograma."
            except ValueError as error:
                st.sidebar.error(f"No se han aplicado los ajustes: {error}")
        if st.sidebar.button("Guardar ajustes del vídeo", key="guardar_cfg_video"):
            guardar_configuracion(sesion["valores"], ruta_ajustes_video(base, info["huella"]))
            sesion["modificada"] = False
            st.sidebar.success("Ajustes guardados para este vídeo.")
        if sesion["modificada"]:
            st.sidebar.caption("Hay ajustes del vídeo sin guardar.")
        st.caption(f"{ruta.name} · {info['ancho']} × {info['alto']} px · {info['fps']:.2f} fps · "
                   f"{info['fotogramas']} fotogramas · {info['duracion_s']:.1f} s")
        for aviso in info.get("avisos", []):
            st.warning(aviso)
        st.caption("La reproducción analiza cada fotograma consecutivo, hasta 10 por segundo; puede ir más lenta "
                   "que el vídeo original. Los tiempos indicados pertenecen al archivo.")
        if es_video_desarrollo(info):
            st.warning("Este vídeo se ha usado para definir las reglas. Sus resultados son de desarrollo, "
                       "no una evaluación independiente.")
        else:
            st.info("Vídeo distinto de los usados para definir las reglas. Para evaluar aciertos, "
                    "etiqueta algunas escenas y compáralas con las predicciones.")
        _reproductor = st.fragment(run_every=.1 if sesion["reproduciendo"] else None)(_mostrar_reproductor)
        _reproductor(sesion, ruta, info, token, base)
    except (OSError, ValueError, RuntimeError, cv2.error) as error:
        st.error(f"No se puede abrir este vídeo: {error}")


def _mostrar_reproductor(sesion, ruta, info, token, base):
    ultimo = info["fotogramas"] - 1
    clave_numero, clave_barra = f"frame_{token}", f"barra_{token}"

    def saltar(clave):
        # Un mensaje atrasado del navegador puede contener el valor anterior
        # de un control ya retirado. Solo una búsqueda en pausa puede moverlo.
        if sesion["reproduciendo"]:
            return
        sesion.update(indice=int(st.session_state[clave]), reproduciendo=False, salto=True, aviso="")
        st.session_state[clave_numero] = sesion["indice"]
        st.session_state[clave_barra] = sesion["indice"]
        sesion["seguidor"].reiniciar()
        sesion["cache"] = None

    if sesion.pop("salto", False):
        st.rerun()  # Cambia también el intervalo del fragmento al dejarlo pausado.
    botones = st.columns([1.4, 1, 1, 1])
    reproduciendo = sesion["reproduciendo"]
    if botones[0].button("Pausar" if reproduciendo else "Reproducir análisis",
                          key="pause_video" if reproduciendo else "play_video", type="primary"):
        # Acciones con identidades distintas: repetir un evento antiguo de
        # Reproducir nunca equivale a pulsar Pausar sobre el siguiente render.
        sesion["reproduciendo"] = not reproduciendo
        if not reproduciendo and sesion["indice"] >= ultimo:
            sesion["indice"] = 0
            sesion["cache"] = None
            sesion["seguidor"].reiniciar()
        sesion["ultimo_avance"] = time.monotonic()
        sesion["aviso"] = ""
        st.rerun()
    for columna, nombre, destino in ((botones[1], "Anterior", max(0, sesion["indice"] - 1)),
                                      (botones[2], "Siguiente", min(ultimo, sesion["indice"] + 1)),
                                      (botones[3], "Volver al inicio", 0)):
        if columna.button(nombre, key=f"video_{nombre}"):
            sesion.update(indice=destino, reproduciendo=False, aviso="")
            if nombre != "Siguiente":
                sesion["seguidor"].reiniciar()
                sesion["cache"] = None
            st.session_state[clave_numero] = destino
            st.session_state[clave_barra] = destino
            st.rerun()
    # Atender los botones antes del reloj conserva el fotograma visible al
    # pausar y evita que Siguiente avance dos posiciones. Un rerun interrumpido
    # tampoco puede saltar otro índice hasta terminar el que quedó pendiente.
    fin_reproduccion = False
    procesado_actual = sesion.get("cache") is not None and sesion["cache"][1] == sesion["indice"]
    if (sesion["reproduciendo"] and procesado_actual
            and time.monotonic() - sesion["ultimo_avance"] >= .09):
        sesion["indice"] = min(ultimo, sesion["indice"] + 1)
        sesion["ultimo_avance"] = time.monotonic()
    if sesion["reproduciendo"] and sesion["indice"] == ultimo:
        fin_reproduccion = True
    if sesion["reproduciendo"]:
        # El avance automático es una salida, no un widget editable. Así un
        # eco atrasado de su valor no dispara on_change y no pausa ni retrocede.
        st.progress((sesion["indice"] + 1) / info["fotogramas"],
                    text=f"Fotograma {sesion['indice']} de {ultimo} · Pausa para elegir una posición.")
    else:
        st.session_state[clave_numero] = sesion["indice"]
        st.session_state[clave_barra] = sesion["indice"]
        st.number_input("Fotograma · empieza en 0", min_value=0, max_value=ultimo, step=1,
                        key=clave_numero, on_change=saltar, args=(clave_numero,))
        if ultimo > 0:
            st.slider("Línea de tiempo · fotograma", min_value=0, max_value=ultimo, step=1,
                      key=clave_barra, on_change=saltar, args=(clave_barra,))
    try:
        resultado, objetos = procesar_posicion(sesion, ruta, info)
    except (OSError, ValueError, RuntimeError, cv2.error) as error:
        if sesion["reproduciendo"]:
            sesion["reproduciendo"] = False
            sesion["aviso"] = f"Reproducción detenida: {error}"
            st.rerun()
        st.error(str(error))
        return
    if fin_reproduccion:
        # Publicar primero el cálculo del último fotograma; después retirar el
        # temporizador del fragmento mediante un rerun completo.
        sesion["reproduciendo"] = False
        sesion["aviso"] = "Fin del vídeo. Puedes volver al inicio o elegir otro fotograma."
        st.rerun()
    if sesion["aviso"]:
        st.info(sesion["aviso"])
    for aviso in resultado["avisos"]:
        st.warning(aviso)
    m = st.columns(3)
    m[0].metric("Tiempo del vídeo", f"{sesion['posicion']['tiempo_s']:.2f} s")
    m[1].metric("Objetos en el fotograma", len(objetos))
    m[2].metric("Estado", "Reproduciendo" if sesion["reproduciendo"] else "Pausado")
    imagen, mascara = st.columns(2)
    with imagen:
        st.markdown("#### Fotograma y reconocimiento")
        st.image(vista_video(resultado, objetos), channels="BGR", width="stretch")
    with mascara:
        st.markdown("#### Máscara del fotograma")
        st.image(resultado["mascara"], width="stretch")
    st.caption("Los nombres son predicciones provisionales obtenidas con reglas manuales sobre la forma. "
               "Desconocido significa que las reglas no permiten decidir. P1, P2… son pistas temporales; se mantienen por cercanía y tamaño "
               "en avances consecutivos. Saltar, retroceder o cambiar ajustes reinicia el seguimiento. "
               "Manos, cruces, objetos juntos y movimientos rápidos pueden alterar la detección, el nombre y la pista.")
    st.markdown("#### Herramientas en este fotograma")
    conteo = conteo_fotograma(objetos)
    if conteo:
        st.dataframe([{"Predicción": clase, "Cantidad ahora": cantidad} for clase, cantidad in conteo.items()],
                     hide_index=True, width="stretch")
        st.dataframe([{"Pista": f"P{o['id_pista']}", "Predicción": o["clase_predicha"],
                       "Clasificación": o["estado_clasificacion"], "Regla": o["regla"],
                       "Por qué": o["explicacion"], "Seguimiento": o["estado_pista"]} for o in objetos],
                     hide_index=True, width="stretch")
    else:
        st.info("No se detectan herramientas en este fotograma.")
    st.caption("El conteo incluye solo los objetos visibles ahora; no suma pistas de momentos anteriores. "
               "Guardar una foto no confirma automáticamente estos nombres.")
    with st.expander("Medidas del fotograma"):
        st.dataframe([{"Objeto": o["id"], "Pista": o["id_pista"], "Seguimiento": o["estado_pista"],
                       "Área · px²": round(o["area_px2"], 1), "Relación de aspecto": round(o["relacion_aspecto"], 3),
                       "Solidez": round(o["solidez"], 3), "Anchura central": round(o["ancho_central"], 3)}
                      for o in objetos], hide_index=True, width="stretch")
    # Las acciones que escriben se habilitan pausado, para que su fotograma
    # coincida con el que el usuario está inspeccionando.
    if st.button("Guardar fotograma como foto", disabled=sesion["reproduciendo"], key="extraer_frame"):
        try:
            foto = exportar_fotograma(ruta, sesion["indice"], sesion["valores"], base=Path(base) / "capturas")
            sesion["foto_guardada"] = str(foto)
        except (OSError, ValueError, cv2.error) as error:
            st.error(f"No se pudo guardar el fotograma: {error}")
    if sesion["foto_guardada"]:
        st.success(f"Foto guardada con ajustes y procedencia: {Path(sesion['foto_guardada']).name}")
        if st.button("Abrir foto guardada para etiquetar", key="abrir_frame_foto"):
            sesion["reproduciendo"] = False
            st.session_state["foto_desde_video"] = sesion["foto_guardada"]
            st.rerun()
    with st.expander("Exportar medidas de un intervalo"):
        st.caption("Se guarda un CSV de objetos y otro de fotogramas, incluidos los vacíos, con la configuración "
                   "y la procedencia del vídeo. Incluye las predicciones, sus reglas y explicaciones, el conteo "
                   "de cada fotograma y una copia de las reglas. Las predicciones no son etiquetas confirmadas.")
        with st.form(f"exportar_{token}"):
            cols = st.columns(3)
            inicio = cols[0].number_input("Desde fotograma", 0, ultimo, 0, step=1)
            fin = cols[1].number_input("Hasta fotograma · incluido", 0, ultimo, ultimo, step=1)
            paso = cols[2].number_input("Guardar una fila de fotograma cada…", 1, max(1, info["fotogramas"]), 1, step=1,
                                        help="El seguimiento recorre también los intermedios. El paso reduce las filas guardadas, no el trabajo de procesamiento.")
            exportar = st.form_submit_button("Exportar intervalo a CSV", disabled=sesion["reproduciendo"])
        if exportar:
            if fin < inicio:
                st.error("El fotograma final debe ser igual o posterior al inicial.")
            else:
                barra = st.progress(0.0, text="Procesando el intervalo…")
                try:
                    destino = Path(base) / "resultados" / "videos" / (
                        f"{ruta.stem[:48]}_{datetime.now():%Y%m%d_%H%M%S_%f}_{uuid.uuid4().hex[:8]}"
                    )
                    carpeta = exportar_video(ruta, sesion["valores"], salida=destino, inicio=inicio, fin=fin, paso=paso,
                                              progreso=lambda actual, total: barra.progress(actual / max(1, total)))
                    sesion["exportacion"] = str(carpeta)
                except (OSError, ValueError, RuntimeError, cv2.error) as error:
                    st.error(f"No se pudo exportar: {error}")
                finally:
                    barra.empty()
        if sesion["exportacion"]:
            st.success("Intervalo exportado. Los ajustes y las medidas están juntos en esta carpeta:")
            carpeta = Path(sesion["exportacion"])
            st.text(str(carpeta))
            from io import BytesIO
            import zipfile
            memoria = BytesIO()
            with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as paquete:
                for archivo in sorted(carpeta.iterdir()):
                    if archivo.is_file():
                        paquete.write(archivo, archivo.name)
            st.download_button("Descargar análisis del vídeo · ZIP", memoria.getvalue(),
                               file_name=carpeta.name + ".zip", mime="application/zip", key="zip_video")
