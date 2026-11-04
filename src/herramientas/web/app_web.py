"""Mesa local para calibrar, etiquetar y exportar fotografías con Streamlit."""

from io import BytesIO
from pathlib import Path
import importlib
import zipfile

import cv2
import numpy as np
import streamlit as st

from herramientas.web import actualizacion
# Hacerlo antes de importar funciones evita conservar el validador antiguo en
# una web ya abierta. Un clic en Guardar basta; no hay que reiniciar su sesión.
if getattr(actualizacion, "VERSION_ACTUALIZACION", None) != 4:
    importlib.reload(actualizacion)
actualizacion.actualizar_modulos_etiquetado()

from herramientas.datos.configuracion import BASE, LIMITES, cargar_configuracion, configuracion_para_imagen, validar_configuracion, guardar_configuracion
from herramientas.datos.etiquetado import (
    CLASES, cargar_etiquetas_existentes, exportar_sesion, firma_deteccion,
    huella_imagen,
)
from herramientas.datos.catalogo import agregar_clase, cargar_clases
from herramientas.vision.vision import dibujar_resultado, procesar_imagen
from herramientas.web.panel_analisis import mostrar_analisis
from herramientas.vision.geometria import VERSION_CARACTERISTICAS
from herramientas.web.panel_video import mostrar_video
from herramientas.web.panel_clasificacion import mostrar_reconocimiento
from herramientas.web.panel_entrega import mostrar_preparacion
from herramientas.web import biblioteca
if getattr(biblioteca, 'VERSION_BIBLIOTECA', None) != 2:
    importlib.reload(biblioteca)
from herramientas.web.biblioteca import seleccionar_foto, preparar_siguiente, mostrar_papelera
from herramientas.web.panel_directo import mostrar_directo, detener_directo


def listar_fotos(base=BASE):
    carpeta = Path(base) / "datos" / 'capturas'
    fotos = [p for p in carpeta.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg")]
    return sorted(fotos, key=lambda p: (p.name.startswith("escena_"), p.name), reverse=True)


def listar_sesiones(base=BASE):
    fotos = (Path(base) / "datos" / 'resultados').glob("*/imagen_origen.png")
    return sorted(
        (p for p in fotos if (p.parent / "anotaciones.json").is_file()),
        key=lambda p: (p.stat().st_mtime_ns, p.parent.name), reverse=True,
    )

def decodificar(datos):
    imagen = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
    if imagen is None:
        raise ValueError("No se ha podido leer la imagen. Utiliza una foto PNG o JPG válida.")
    return imagen


def nueva_sesion(origen, imagen, valores, base=BASE):
    resultado = procesar_imagen(imagen, valores)
    carga = cargar_etiquetas_existentes(origen, imagen, valores, resultado, base=base)
    return {
        "valores": valores.copy(), "etiquetas": carga["etiquetas"],
        "revisadas": set(carga["revisadas"]), "avisos": carga["avisos"],
        "origen_etiquetas": carga["origen"],
        "firma": firma_deteccion(imagen, valores, resultado),
        "revision": 0, "modificada": False, "guardado": None,
    }


def aplicar_ajustes(sesion, imagen, valores):
    """Un ID conservado no demuestra que siga siendo el mismo objeto."""
    valores = validar_configuracion(valores)
    resultado = procesar_imagen(imagen, valores)
    firma = firma_deteccion(imagen, valores, resultado)
    if firma != sesion["firma"]:
        ids = {o["id"] for o in resultado["objetos"]}
        anteriores = sesion["etiquetas"]
        sesion["etiquetas"] = {i: anteriores.get(i, "") for i in ids}
        sesion["revisadas"] = set()
        sesion["revision"] += 1
        sesion["modificada"] = True
        sesion["avisos"] = [
            "Han cambiado los ajustes o la zona de análisis. Revisa cada objeto: los números pueden "
            "corresponder a herramientas diferentes aunque el recuento sea el mismo. "
            "Los nombres anteriores se conservan solo como propuestas."
        ]
    sesion["valores"] = valores
    sesion["firma"] = firma
    return resultado


def vista_resaltada(resultado, seleccionado=None):
    vista = dibujar_resultado(resultado, telemetria=False)
    if seleccionado is not None:
        objeto = next((o for o in resultado["objetos"] if o["id"] == seleccionado), None)
        if objeto:
            relleno = vista.copy()
            cv2.drawContours(relleno, [objeto["contorno"]], -1, (0, 190, 255), cv2.FILLED)
            vista = cv2.addWeighted(vista, .78, relleno, .22, 0)
            cv2.drawContours(vista, [objeto["contorno"]], -1, (0, 190, 255), 3)
    return vista


def empaquetar_zip(carpeta):
    memoria = BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as archivo:
        for ruta in sorted(Path(carpeta).iterdir()):
            if ruta.is_file():
                archivo.write(ruta, ruta.name)
    return memoria.getvalue()


def elegir_fuente():
    st.sidebar.markdown("### Fotografía")
    mensaje = st.session_state.pop('biblioteca_mensaje', None)
    if mensaje:
        st.success(mensaje)
    mostrar_papelera(BASE)
    modo = st.sidebar.radio(
        "Origen de la foto", ["Capturas guardadas", "Sesiones guardadas", "Otra foto"],
        key="fuente_modo", label_visibility="collapsed",
    )
    if modo == "Otra foto":
        archivo = st.sidebar.file_uploader("Abrir PNG o JPG", type=["png", "jpg", "jpeg"])
        if archivo is None:
            st.info("Elige una fotografía en el panel lateral para empezar.")
            st.stop()
        origen = BASE / "datos" / 'importadas' / Path(archivo.name).name
        return origen, decodificar(archivo.getvalue()), None
    sesiones = modo == "Sesiones guardadas"
    opciones = listar_sesiones(BASE) if sesiones else listar_fotos(BASE)
    if not opciones:
        st.info("Todavía no hay sesiones guardadas." if sesiones else "No hay capturas. Puedes abrir otra foto desde el panel lateral.")
        st.stop()
    origen = seleccionar_foto(opciones, BASE, sesiones)
    configuracion = origen.parent / "configuracion.json" if sesiones else None
    return origen, decodificar(origen.read_bytes()), configuracion


def ajustes(sesion, token):
    with st.sidebar.expander("Ajustes de imagen", expanded=False):
        return _campos_ajustes(sesion, token)


def _campos_ajustes(sesion, token):
    st.markdown("### Ajustes de imagen")
    st.caption("Escribe un valor o usa −/+. Aplica los cambios para actualizar la vista.")
    with st.form(f"ajustes_{token}"):
        valores = {}
        valores["limitar_tapete"] = int(st.checkbox(
            "Limitar al tapete", value=bool(sesion["valores"]["limitar_tapete"]),
            key=f"cfg_{token}_limitar_tapete",
            help="Localiza la mayor región verde y excluye la mesa y el resto del exterior.",
        ))
        valores["margen_tapete"] = st.number_input(
            "Margen interior del tapete · px", *LIMITES["margen_tapete"],
            value=sesion["valores"]["margen_tapete"], step=1,
            key=f"cfg_{token}_margen_tapete",
            help="Pequeña separación del borde, medida en la imagen procesada. Empieza con 2 px.",
        )
        for nombre, canal in (("Tono · H", "h"), ("Saturación · S", "s"), ("Brillo · V", "v")):
            izquierda, derecha = st.columns(2)
            for columna, extremo, texto in ((izquierda, "min", "mín."), (derecha, "max", "máx.")):
                clave = f"{canal}_{extremo}"
                valores[clave] = columna.number_input(
                    f"{nombre} {texto}", *LIMITES[clave], value=sesion["valores"][clave],
                    step=1, key=f"cfg_{token}_{clave}",
                )
        campos = [
            ("apertura", "Apertura", 1), ("cierre", "Cierre", 1),
            ("kernel", "Kernel (impar)", 2), ("suavizado", "Suavizado (impar)", 2),
            ("area_min", "Área mínima · px²", 10), ("zoom", "Zoom · %", 1),
        ]
        for inicio in range(0, len(campos), 2):
            for columna, (clave, titulo, paso) in zip(st.columns(2), campos[inicio:inicio + 2]):
                valores[clave] = columna.number_input(
                    titulo, *LIMITES[clave], value=sesion["valores"][clave], step=paso,
                    key=f"cfg_{token}_{clave}",
                )
        aplicar = st.form_submit_button("Aplicar ajustes", width="stretch", type="primary")
    st.caption("100 % = 1× · 200 % = 2×. El kernel y el suavizado deben ser impares.")
    return valores if aplicar else None


def guardar_trabajo(sesion, resultado, origen, imagen, avanzar=False):
    destino = exportar_sesion(
        resultado, origen, imagen, sesion['valores'], sesion['etiquetas'],
        sesion['revisadas'], base_salida=BASE/'datos/resultados')
    # Al reabrir la captura y al calcular su estado se deben usar los mismos
    # ajustes guardados, no los que tenía cuando se tomó la fotografía.
    if Path(origen).parent == BASE/'datos/capturas' and Path(origen).is_file():
        guardar_configuracion(sesion['valores'], Path(origen).with_suffix('.json'))
    sesion['guardado'] = str(destino)
    sesion['modificada'] = False
    ids = {o['id'] for o in resultado['objetos']}
    completa = bool(ids) and all(i in sesion['revisadas'] and sesion['etiquetas'].get(i) for i in ids)
    st.session_state['biblioteca_mensaje'] = (
        f'Guardada: {Path(origen).name}. ' + ('Etiquetas completas y CSV guardados.' if completa
        else 'Borrador guardado: aún quedan etiquetas sin confirmar.'))
    if avanzar and completa:
        preparar_siguiente(origen)


def panel_etiqueta(sesion, seleccionado, token, ids, resultado, origen, imagen):
    nombre = sesion["etiquetas"].get(seleccionado, "")
    confirmado = seleccionado in sesion["revisadas"] and bool(nombre)
    clave_nombre = f"nombre_{token}_{sesion['revision']}_{seleccionado}"
    nueva = sesion.pop("herramienta_anadida", None)
    if nueva and nueva[0] == seleccionado:
        # El formulario anterior ya terminó. Seleccionar antes de crear el
        # widget evita modificar su estado después de haberlo mostrado.
        st.session_state[clave_nombre] = nueva[1]
    with st.container(border=True):
        st.markdown(f"#### Objeto {seleccionado}")
        st.caption("Etiqueta confirmada" if confirmado else "Pendiente de revisión")
        try:
            clases = cargar_clases(BASE)
        except (OSError, ValueError) as error:
            clases = list(CLASES)
            st.warning(f"No se pudo cargar la lista de herramientas: {error}")
        # Las sesiones trasladadas conservan sus nombres aunque en este Mac
        # todavía no exista el catálogo donde se crearon.
        opciones = ["Sin etiquetar", *dict.fromkeys([
            *clases, *(n for n in sesion["etiquetas"].values() if n),
        ])]
        with st.form(f"etiqueta_{token}_{sesion['revision']}_{seleccionado}"):
            elegido = st.selectbox(
                "Herramienta real", opciones,
                index=None if clave_nombre in st.session_state else opciones.index(nombre) if nombre in opciones else 0,
                key=clave_nombre,
            )
            ultima = all(i == seleccionado or (i in sesion['revisadas'] and sesion['etiquetas'].get(i)) for i in ids)
            rapido = st.form_submit_button('Confirmar, guardar y siguiente foto', type='primary', width='stretch') if ultima else False
            confirmar = st.form_submit_button("Confirmar y siguiente", type="secondary" if ultima else "primary", width="stretch")
            pendiente = st.form_submit_button("Dejar pendiente", width="stretch")
        if confirmar or pendiente or rapido:
            etiqueta = "" if elegido in (None, "Sin etiquetar") else elegido
            if (confirmar or rapido) and not etiqueta:
                st.error("Elige el nombre de la herramienta antes de confirmar.")
            else:
                sesion["etiquetas"][seleccionado] = etiqueta
                sesion["revisadas"].discard(seleccionado)
                if confirmar or rapido:
                    sesion["revisadas"].add(seleccionado)
                    pendientes = [i for i in ids if i not in sesion["revisadas"]]
                    if pendientes:
                        sesion["siguiente_id"] = pendientes[0]
                sesion["modificada"] = True
                if rapido:
                    try:
                        guardar_trabajo(sesion, resultado, origen, imagen, avanzar=True)
                    except (OSError, ValueError, cv2.error) as error:
                        st.error(f'No se pudo completar el guardado: {error}. Tus etiquetas siguen en esta sesión; vuelve a intentarlo.')
                        return
                st.rerun()
        if nueva and nueva[0] == seleccionado:
            st.success(f"«{nueva[1]}» está disponible. Confirma la etiqueta cuando hayas revisado el objeto.")
        with st.expander("Añadir herramienta"):
            st.caption("El nombre quedará disponible en tus próximas fotos.")
            with st.form(f"nueva_herramienta_{token}_{sesion['revision']}_{seleccionado}",
                         clear_on_submit=True, border=False):
                nuevo_nombre = st.text_input("Nombre de la nueva herramienta", max_chars=80,
                                            placeholder="Por ejemplo: Alicates")
                anadir = st.form_submit_button("Añadir y seleccionar", width="stretch")
            if anadir:
                try:
                    canonico = agregar_clase(nuevo_nombre, base=BASE)
                except (OSError, ValueError) as error:
                    st.error(f"No se pudo añadir la herramienta: {error}")
                else:
                    if sesion["etiquetas"].get(seleccionado, "") != canonico:
                        sesion["etiquetas"][seleccionado] = canonico
                        sesion["revisadas"].discard(seleccionado)
                        sesion["modificada"] = True
                    sesion["herramienta_anadida"] = (seleccionado, canonico)
                    st.rerun()
        st.caption("La etiqueta describe lo que ves. Es la referencia manual para evaluar las predicciones automáticas.")


def tabla_medidas(resultado, sesion):
    filas = []
    for o in resultado["objetos"]:
        i = o["id"]
        nombre = sesion["etiquetas"].get(i, "")
        filas.append({
            "ID": i, "Etiqueta manual": nombre or "Sin etiquetar",
            "Estado": "Confirmada" if i in sesion["revisadas"] and nombre else "Pendiente",
            "Área · px²": round(o["area_px2"], 1),
            "Perímetro · px": round(o["perimetro_px"], 1),
            "Relación de aspecto": round(o["relacion_aspecto"], 3),
            "Solidez": round(o["solidez"], 3),
            "Circularidad": round(o["circularidad"], 3),
            "Orientación · °": round(o["orientacion_grados"], 1),
        })
    st.dataframe(filas, hide_index=True, width="stretch")


def mostrar_calibracion(resultado, sesion, origen, imagen, token):
    ids = [o["id"] for o in resultado["objetos"]]
    revisadas = {i for i in ids if i in sesion["revisadas"] and sesion["etiquetas"].get(i)}
    columnas = st.columns(3)
    columnas[0].metric("Objetos detectados", len(ids))
    columnas[1].metric("Etiquetas confirmadas", f"{len(revisadas)} / {len(ids)}")
    columnas[2].metric("Zoom aplicado", f"{sesion['valores']['zoom'] / 100:.2f}×")
    for aviso in resultado["avisos"]:
        st.warning(aviso)

    if sesion["avisos"] and len(revisadas) < len(ids):
        st.warning(sesion["avisos"][-1])
    if sesion["origen_etiquetas"]:
        with st.expander("Procedencia de las etiquetas"):
            st.text(sesion["origen_etiquetas"])
            for aviso in sesion["avisos"]:
                st.write(aviso)
    seleccionado = None
    if ids:
        clave = f"objeto_{token}_{sesion['revision']}"
        siguiente = sesion.pop("siguiente_id", None)
        if siguiente in ids:
            st.session_state[clave] = siguiente
        seleccionado = st.selectbox("Objeto para revisar", ids, format_func=lambda i: f"Objeto {i}", key=clave)
    else:
        st.info("No se han detectado objetos. Ajusta el rango del fondo o el área mínima en el panel lateral.")

    foto, mascara = st.columns(2)
    with foto:
        st.markdown("#### Foto y detecciones")
        st.image(vista_resaltada(resultado, seleccionado), channels="BGR", width="stretch")
        st.caption("Amarillo: objeto seleccionado. Azul: límite del tapete; el exterior se oscurece y se ignora.")
    with mascara:
        st.markdown("#### Máscara de objetos")
        st.image(resultado["mascara"], width="stretch")
        st.caption("Blanco: objetos · Negro: fondo. Comprueba que cada herramienta forma un objeto separado.")
    with st.expander("Zona de análisis del tapete"):
        st.write(resultado["tapete"]["motivo"])
        st.image(resultado["mascara_tapete"], width="stretch")
        st.caption("Blanco: zona admitida. Las herramientas deben quedar dentro y separadas del borde. "
                   "El margen no corrige la perspectiva ni cambia la escala de las medidas.")
    detalle, medidas = st.columns([1, 2.2])
    with detalle:
        if seleccionado is not None:
            panel_etiqueta(sesion, seleccionado, token, ids, resultado, origen, imagen)
    with medidas, st.expander("Medidas de la escena", expanded=False):
        if ids:
            tabla_medidas(resultado, sesion)
        st.caption("Medidas del contorno exterior, a 800 px de ancho. Aquí confirmas las etiquetas reales; las predicciones están en Reconocimiento automático.")

    with st.container(border=True):
        st.markdown("#### Guardar el trabajo")
        pendientes = len(ids) - len(revisadas)
        if pendientes:
            st.write(f"Quedan {pendientes} objetos por revisar. Puedes guardar un borrador: sus propuestas se conservarán y sus nombres quedarán vacíos en el CSV.")
        elif ids:
            st.write("Las etiquetas están revisadas. Guarda una versión con la foto, los ajustes y las medidas.")
        else:
            st.write('No hay detecciones. Guardar conserva los ajustes, pero esta foto seguirá pendiente de revisión.')
        avanzar = st.button('Guardar y siguiente foto', disabled=bool(pendientes) or not ids)
        if st.button("Guardar sesión y CSV", key="guardar_sesion") or avanzar:
            try:
                guardar_trabajo(sesion, resultado, origen, imagen, avanzar=avanzar)
            except (OSError, ValueError, cv2.error) as error:
                st.error(f"No se pudo guardar la sesión: {error}")
            else:
                st.rerun()
        if sesion["guardado"]:
            destino = Path(sesion["guardado"])
            st.success("Sesión guardada. Hay cambios posteriores sin guardar." if sesion["modificada"] else "Sesión guardada con su foto, etiquetas, configuración y CSV.")
            st.text(str(destino))
            st.download_button(
                "Descargar última versión guardada · ZIP", empaquetar_zip(destino),
                file_name=f"{destino.name}.zip", mime="application/zip", key=f"zip_{token}",
            )
        elif sesion["modificada"]:
            st.caption("Hay cambios sin guardar. Cambiar de foto conserva el trabajo durante esta sesión del navegador.")
    with st.expander("Cómo trabajar"):
        st.markdown("1. Filtra por **Pendientes** y abre una foto.\n2. Elige la herramienta real de cada objeto y confirma.\n3. En el último objeto, usa **Confirmar, guardar y siguiente foto**: guarda el CSV y abre la siguiente pendiente del filtro actual.\n\nSi ya confirmaste todo, usa **Guardar y siguiente foto**. **Guardar sesión y CSV** también permite conservar borradores, pero no confirma los nombres del formulario. Una foto sin detecciones sigue pendiente.\n\nEtiquetar crea referencias para evaluar las reglas, no las entrena ni modifica. Si cambias los ajustes, revisa los nombres de nuevo. Guarda antes de cerrar el navegador.")


def main():
    st.set_page_config(page_title="Mesa de herramientas · Reto 07", page_icon="🔧", layout="wide")
    st.markdown("""<style>
      .block-container {padding-top:3.5rem; padding-bottom:2rem; max-width:1600px;}
      h1 {letter-spacing:-.035em; font-size:2rem;}
      [data-testid="stMetric"] {border:1px solid #52666e30; border-radius:12px; padding:12px 18px;}
      [data-testid="stMetricValue"] {font-size:1.8rem;}
      @media (min-width:900px) { [data-testid="stSidebar"] {min-width:325px;} }
    </style>""", unsafe_allow_html=True)
    st.caption("RETO 07  /  VISIÓN ARTIFICIAL CLÁSICA")
    st.title("Mesa de herramientas")
    foto_extraida = st.session_state.pop("foto_desde_video", None)
    if foto_extraida:
        st.session_state["modo_trabajo"] = "Fotografías"
        st.session_state["fuente_modo"] = "Capturas guardadas"
        st.session_state["foto_elegida"] = Path(foto_extraida)
        st.session_state["filtro_estado_fotos"] = "Todas"
        st.session_state["buscar_foto"] = ""
        st.session_state["pestana_principal"] = "Calibración y etiquetas"
    modo = st.sidebar.radio("Modo de trabajo", ["Fotografías", "En directo", "Vídeos", "Entrega"], key="modo_trabajo")
    if modo != "En directo":
        detener_directo()
    if modo == "En directo":
        for sesion_video in st.session_state.get("sesiones_video", {}).values():
            sesion_video["reproduciendo"] = False
        try:
            mostrar_directo(BASE, ajustes)
        except (OSError, ValueError, RuntimeError, cv2.error) as error:
            detener_directo()
            st.error(f"No se puede iniciar el directo: {error}")
        return
    if modo == "Vídeos":
        mostrar_video(BASE, ajustes)
        return
    for sesion_video in st.session_state.get("sesiones_video", {}).values():
        sesion_video["reproduciendo"] = False
    if modo == "Entrega":
        mostrar_preparacion(BASE)
        return
    try:
        origen, imagen, ruta_config = elegir_fuente()
        token = huella_imagen(imagen)[:16] + "_" + str(origen)
        sesiones = st.session_state.setdefault("sesiones_trabajo", {})
        if token not in sesiones:
            valores = cargar_configuracion(ruta_config) if ruta_config else configuracion_para_imagen(origen)
            sesiones[token] = nueva_sesion(origen, imagen, valores, base=BASE)
        sesion = sesiones[token]
        # También al actualizar el código con la web abierta: normalizar nuevos
        # campos y revisar identidades antes de pintar o permitir exportaciones.
        resultado = aplicar_ajustes(sesion, imagen, validar_configuracion(sesion["valores"]))
        candidatos = ajustes(sesion, token)
        if candidatos is not None:
            try:
                resultado = aplicar_ajustes(sesion, imagen, candidatos)
            except (ValueError, cv2.error) as error:
                st.sidebar.error(f"No se han aplicado los ajustes: {error}")
        calibracion, analisis, reconocimiento = st.tabs(["Calibración y etiquetas", "Análisis", "Reconocimiento automático"],
                                        key="pestana_principal", on_change="rerun")
        if calibracion.open:
            with calibracion:
                mostrar_calibracion(resultado, sesion, origen, imagen, token)
        if analisis.open:
            with analisis:
                if resultado.get("version_caracteristicas") != VERSION_CARACTERISTICAS:
                    st.info("Para cargar el nuevo análisis, guarda primero tus etiquetas en la otra pestaña. "
                            "Después detén la web con Ctrl+C en su terminal y vuelve a abrir iniciar_web.command. "
                            "El servidor que estaba abierto conserva el procesamiento anterior.")
                else:
                    mostrar_analisis(BASE, {
                        "origen": origen, "imagen": imagen, "valores": sesion["valores"],
                        "etiquetas": sesion["etiquetas"], "revisadas": sesion["revisadas"],
                        "firma": sesion["firma"], "resultado": resultado,
                    })
        if reconocimiento.open:
            with reconocimiento:
                mostrar_reconocimiento(BASE, resultado, sesion, origen, imagen, token)
    except (OSError, ValueError, cv2.error) as error:
        st.error(f"No se puede abrir esta fotografía: {error}")


if __name__ == "__main__":
    main()
