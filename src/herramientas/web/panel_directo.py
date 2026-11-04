"""Vista de demostración: cámara local o vídeo, sin entrenar ni confirmar etiquetas."""
from datetime import datetime
from pathlib import Path

import cv2
import streamlit as st

from herramientas.cli.calibrador import guardar_captura
from herramientas.cli.detector import exportar_resultado
from herramientas.datos.configuracion import cargar_configuracion, guardar_configuracion
from herramientas.datos.entrega import cargar_perfil
from herramientas.datos.nombres import guardar_nombre, validar_nombre
from herramientas.media.directo_web import DirectoWeb
from herramientas.media.video import listar_videos, configuracion_para_video, exportar_fotograma
from herramientas.web.panel_video import vista_video
from herramientas.vision.reconocimiento import exportar_predicciones
from herramientas.vision.clasificacion import VERSION_CLASIFICADOR


def detener_directo():
    controlador = st.session_state.get('directo_controlador')
    if controlador and controlador.activo:
        controlador.detener()


def guardar_instante(base, controlador, instante, nombre, medidas=False):
    """Guarda el paquete mostrado, no un fotograma posterior del hilo de captura."""
    base = Path(base)
    if controlador.video:
        escena = exportar_fotograma(controlador.video, instante['indice'], instante['valores'], base=base/'datos/capturas')
        origen = escena
        if nombre:
            guardar_nombre(escena, nombre)
    else:
        escena, origen = guardar_captura(instante['original'], instante['resultado']['encuadre'],
                                        instante['valores'], nombre=nombre, carpeta=base/'datos/capturas')
    destino = None
    if medidas:
        destino = base/'datos/resultados'/f'directo_{datetime.now():%Y%m%d_%H%M%S_%f}'
        exportar_resultado(instante['resultado'], origen, instante['valores'], destino)
        exportar_predicciones(destino, instante['objetos'], instante['inventario'],
                              vista_video(instante['resultado'], instante['objetos']))
    return escena, destino


def mostrar_directo(base, controles_ajustes):
    base = Path(base)
    controlador = st.session_state.get('directo_controlador')
    activo = bool(controlador and controlador.activo)
    st.subheader('En directo')
    st.caption(f'{VERSION_CLASIFICADOR} · la cámara se abre solo al pulsar Iniciar.')
    with st.sidebar.expander('Fuente y captura', expanded=not activo):
        fuente = st.radio('Fuente del directo', ['Cámara del Mac / iPhone', 'Vídeo de prueba'],
                          key='directo_fuente', disabled=activo)
        ruta = None
        camara = 1
        if fuente == 'Vídeo de prueba':
            videos = listar_videos(base)
            if videos:
                ruta = st.selectbox('Vídeo para simular directo', videos, format_func=lambda p: p.parent.name,
                                    key='directo_video', disabled=activo)
            else:
                st.info('Añade un vídeo desde Vídeos para probar sin cámara.')
        else:
            camara = st.number_input('Índice de cámara', min_value=0, max_value=20, value=1,
                                     step=1, disabled=activo)
            st.caption('En tu montaje: iPhone disponible en Photo Booth y cámara 1.')
        nombre = st.text_input('Nombre de las capturas', max_chars=80, key='directo_nombre',
                               placeholder='Alicate abierto')
        comparar = st.checkbox('Usar inventario de Entrega', value=True, disabled=activo)
    sesion = st.session_state.setdefault('directo_ajustes', {'valores': cargar_configuracion()})
    # Cada fuente recupera sus ajustes; no trasladar el zoom de una a otra.
    clave = str(ruta) if ruta else f'camara_{camara}'
    if not activo and st.session_state.get('directo_clave_ajustes') != clave:
        # No presentar una foto congelada de la fuente anterior como nueva.
        controlador = None
        st.session_state.pop('directo_controlador', None)
        st.session_state.pop('directo_visible', None)
        st.session_state.pop('directo_foto', None)
        st.session_state.pop('directo_exportado', None)
        perfil_video = None
        if ruta:
            from herramientas.media.video import inspeccionar_video
            perfil_video = base/'datos/videos/ajustes'/f"{inspeccionar_video(ruta)['huella']}.json"
        sesion['valores'] = (cargar_configuracion(perfil_video) if perfil_video and perfil_video.exists()
                            else configuracion_para_video(ruta) if ruta else cargar_configuracion())
        st.session_state['directo_clave_ajustes'] = clave
        st.session_state['directo_revision_ajustes'] = st.session_state.get('directo_revision_ajustes', 0) + 1
    nuevos = controles_ajustes(sesion, 'directo_' + str(st.session_state.get('directo_revision_ajustes', 0)))
    if nuevos is not None:
        from herramientas.datos.configuracion import validar_configuracion
        try:
            sesion['valores'] = validar_configuracion(nuevos)
            if activo:
                controlador.ajustar(nuevos)
        except ValueError as error:
            st.sidebar.error(str(error))
    if st.sidebar.button('Guardar ajustes del directo'):
        destino = base/'config/configuracion.json'
        if ruta:
            from herramientas.media.video import inspeccionar_video
            destino = base/'datos/videos/ajustes'/f"{inspeccionar_video(ruta)['huella']}.json"
        guardar_configuracion(sesion['valores'], destino)
        st.sidebar.success('Ajustes guardados.')
    if not activo:
        if st.button('Iniciar', type='primary', disabled=fuente == 'Vídeo de prueba' and ruta is None):
            try:
                validar_nombre(nombre)
                perfil = cargar_perfil(base) if comparar else None
                controlador = DirectoWeb(base, sesion['valores'], perfil['esperadas'] if perfil else None,
                                         camara=camara, video=ruta)
                st.session_state['directo_controlador'] = controlador
                st.session_state.pop('directo_visible', None)
                st.session_state.pop('directo_foto', None)
                st.session_state.pop('directo_exportado', None)
                controlador.iniciar()
                st.rerun()
            except (OSError, ValueError, RuntimeError, cv2.error) as error:
                st.error(str(error))
    mascara = st.toggle('Mostrar máscara', value=False, key='directo_mascara')
    if controlador is None:
        st.info('Elige cámara o un vídeo guardado y pulsa Iniciar. Aquí podrás guardar fotos y grabar nuevas pruebas.')
        return
    refresco = st.fragment(run_every=.2 if activo else None)(_mostrar_flujo)
    refresco(base, controlador, nombre, mascara, activo)


def _mostrar_flujo(base, controlador, nombre, mascara, estaba_activo):
    controlador.latido()
    estado = controlador.estado()
    if estaba_activo and not estado['activo']:
        st.rerun()
    # Los botones operan sobre el último fotograma enviado al navegador.
    visible = st.session_state.get('directo_visible')
    acciones = st.columns(4)
    if acciones[0].button('Detener', disabled=not estado['activo'], key='directo_detener'):
        controlador.detener()
        st.rerun()
    if controlador.video:
        pausado = estado['pausado']
        if acciones[1].button('Continuar' if pausado else 'Pausar', disabled=not estado['activo'],
                              key='directo_continuar' if pausado else 'directo_pausar'):
            controlador.pausar(not pausado)
        if acciones[2].button('Reiniciar vídeo', disabled=not estado['activo']):
            controlador.reiniciar()
    else:
        grabando = estado['grabar_solicitado']
        if acciones[1].button('Finalizar grabación' if grabando else 'Grabar vídeo',
                              disabled=not estado['activo'] or visible is None,
                              key='directo_fin_grabar' if grabando else 'directo_grabar'):
            controlador.grabar(not grabando)
    foto = acciones[3].button('Guardar foto', disabled=visible is None, key='directo_guardar')
    with st.expander('Guardar medidas y revisar capturas'):
        medidas = st.button('Exportar foto y CSV', disabled=visible is None)
        if st.session_state.get('directo_foto'):
            st.caption(str(st.session_state['directo_foto']))
            if st.button('Abrir última foto para etiquetar'):
                controlador.detener()
                st.session_state['foto_desde_video'] = str(st.session_state['directo_foto'])
                st.rerun()
        if st.session_state.get('directo_exportado'):
            st.caption(str(st.session_state['directo_exportado']))
        for grabacion in estado['grabaciones']:
            st.caption('Vídeo guardado: ' + grabacion)
    if (foto or medidas) and visible is not None:
        try:
            ruta, carpeta = guardar_instante(base, controlador, visible, validar_nombre(nombre), medidas)
            st.session_state['directo_foto'] = ruta
            if carpeta:
                st.session_state['directo_exportado'] = carpeta
            st.toast('Foto y medidas guardadas' if medidas else 'Foto guardada')
        except (OSError, ValueError, cv2.error) as error:
            st.error(f'No se pudo guardar: {error}')
    if estado['error']:
        st.error(estado['error'])
    st.caption(estado['mensaje'] + (' · ● Grabando vídeo limpio' if estado['grabando'] else ''))
    paquete = estado['ultimo']
    if paquete is None:
        return
    st.session_state['directo_visible'] = paquete
    inventario = paquete['inventario']
    imagen, resumen = st.columns([3, 1])
    with imagen:
        st.image(vista_video(paquete['resultado'], paquete['objetos']), channels='BGR', width='stretch')
        if mascara:
            st.image(paquete['resultado']['mascara'], caption='Máscara de objetos', width='stretch')
    with resumen:
        st.metric('Objetos', inventario['total'])
        st.metric('Sin identificar', inventario['desconocidos'])
        st.caption(f"Procesamiento: {paquete['fps']:.1f} FPS" +
                   (f" · Fotograma {paquete['indice']}" if controlador.video else ''))
        st.dataframe([{'Herramienta': k, 'Cantidad': v} for k, v in inventario['presentes'].items()],
                     hide_index=True, width='stretch')
        if inventario['esperadas'] is not None:
            st.caption('Inventario provisional' if inventario['provisional'] else
                       'Inventario completo' if inventario['completo'] else 'Hay diferencias')
            if inventario['faltantes']:
                st.write('Faltan', inventario['faltantes'])
            if inventario['repetidos']:
                st.write('Sobran', inventario['repetidos'])
    for aviso in paquete['resultado']['avisos']:
        st.warning(aviso)
    with st.expander('Por qué se reconoce cada herramienta'):
        st.dataframe([{'Pista': o['id_pista'], 'Herramienta': o['clase_predicha'],
                       'Regla': o['regla'], 'Explicación': o['explicacion']} for o in paquete['objetos']],
                     hide_index=True, width='stretch')
        st.caption('Predicciones por reglas clásicas. Guardar fotos o vídeo no confirma etiquetas.')
