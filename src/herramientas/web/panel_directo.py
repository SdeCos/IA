"""Vista de demostración: cámara local o vídeo, sin entrenar ni confirmar etiquetas."""
from datetime import datetime
import json
from pathlib import Path

import cv2
import streamlit as st

from herramientas.cli.calibrador import guardar_captura
from herramientas.cli.detector import exportar_resultado
from herramientas.datos.configuracion import cargar_configuracion, guardar_configuracion
from herramientas.datos.entrega import cargar_perfil, escribir_json
from herramientas.datos.nombres import guardar_nombre, validar_nombre
from herramientas.media.directo_web import DirectoWeb
from herramientas.media.video import listar_videos, configuracion_para_video, exportar_fotograma, inspeccionar_video
from herramientas.web.panel_video import vista_video
from herramientas.vision.reconocimiento import exportar_predicciones
from herramientas.vision.clasificacion import VERSION_CLASIFICADOR

CAMARA_USB = 'iPhone por USB'
AYUDA_USB = 'Conecta el iPhone con un cable de datos y acepta «Confiar» si aparece. El transporte lo gestiona Cámara de Continuidad de macOS.'


def detener_directo():
    controlador = st.session_state.get('directo_controlador')
    if controlador and controlador.activo:
        controlador.detener()


def ajustes_de_fuente(base, ruta):
    if ruta is None:
        return cargar_configuracion()
    ajustes = base/'datos/videos/ajustes'/f"{inspeccionar_video(ruta)['huella']}.json"
    return cargar_configuracion(ajustes) if ajustes.is_file() else configuracion_para_video(ruta)


def indice_de_camara(base):
    if 'indice_camara_directo' not in st.session_state:
        ruta = base/'config/camara.json'
        indice = json.loads(ruta.read_text(encoding='utf-8')) if ruta.is_file() else 1
        if type(indice) is not int or not 0 <= indice <= 20:
            raise ValueError('El índice guardado en config/camara.json debe estar entre 0 y 20.')
        st.session_state['indice_camara_directo'] = indice
    return st.session_state['indice_camara_directo']


def iniciar_flujo(base, valores, esperadas, *, camara=1, video=None):
    controlador = DirectoWeb(base, valores, esperadas, camara=camara, video=video)
    st.session_state['directo_controlador'] = controlador
    for clave in ('directo_visible', 'directo_foto', 'directo_exportado'):
        st.session_state.pop(clave, None)
    controlador.iniciar()
    st.rerun()


def mostrar_presentacion(base):
    base = Path(base)
    st.html("""<style>
      [data-testid="stHeader"] {visibility:hidden;}
      [data-testid="stMainBlockContainer"] {padding-top:1.5rem;}
      [data-testid="stImage"] img {max-height:60vh; object-fit:contain;}
      [data-testid="stTable"] :is(th, td) {padding:.35rem .45rem;}
    </style>""")
    perfil = cargar_perfil(base)
    if perfil is None:
        st.warning('Guarda el inventario esperado en la pestaña Entrega antes de iniciar.')
        return
    controlador = st.session_state.get('directo_controlador')
    activo = bool(controlador and controlador.activo)
    if not activo:
        videos = listar_videos(base)
        fuente = st.selectbox(
            'Fuente', [None, CAMARA_USB, *videos],
            format_func=lambda p: str(p.relative_to(base/'datos/videos')) if isinstance(p, Path)
            else p or 'Cámara en directo',
            key='presentacion_fuente',
        )
        ruta = fuente if isinstance(fuente, Path) else None
        if fuente == CAMARA_USB:
            st.caption(AYUDA_USB)
        if st.button('Iniciar', type='primary', key='presentacion_iniciar'):
            iniciar_flujo(base, ajustes_de_fuente(base, ruta), perfil['esperadas'],
                          camara=indice_de_camara(base) if ruta is None else 1, video=ruta)
    if controlador is not None:
        refresco = st.fragment(run_every=.2 if activo else None)(_mostrar_flujo)
        refresco(base, controlador, '', False, activo, presentacion=True)


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
        fuente = st.radio('Fuente del directo', ['Cámara del Mac / iPhone', CAMARA_USB, 'Vídeo de prueba'],
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
            if fuente == CAMARA_USB:
                st.caption(AYUDA_USB)
            camara = st.number_input('Índice de cámara', min_value=0, max_value=20, value=indice_de_camara(base),
                                     step=1, disabled=activo)
            st.session_state['indice_camara_directo'] = camara
            st.caption('Presentación usa esta misma cámara.')
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
        sesion['valores'] = ajustes_de_fuente(base, ruta)
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
            destino = base/'datos/videos/ajustes'/f"{inspeccionar_video(ruta)['huella']}.json"
        guardar_configuracion(sesion['valores'], destino)
        if fuente != 'Vídeo de prueba':
            escribir_json(base/'config/camara.json', camara)
        st.sidebar.success('Ajustes guardados.')
    if not activo:
        if st.button('Iniciar', type='primary', disabled=fuente == 'Vídeo de prueba' and ruta is None):
            try:
                validar_nombre(nombre)
                perfil = cargar_perfil(base) if comparar else None
                iniciar_flujo(base, sesion['valores'], perfil['esperadas'] if perfil else None,
                              camara=camara, video=ruta)
            except (OSError, ValueError, RuntimeError, cv2.error) as error:
                st.error(str(error))
    mascara = st.toggle('Mostrar máscara', value=False, key='directo_mascara')
    if controlador is None:
        st.info('Elige cámara o un vídeo guardado y pulsa Iniciar. Aquí podrás guardar fotos y grabar nuevas pruebas.')
        return
    refresco = st.fragment(run_every=.2 if activo else None)(_mostrar_flujo)
    refresco(base, controlador, nombre, mascara, activo)


def _mostrar_flujo(base, controlador, nombre, mascara, estaba_activo, presentacion=False):
    controlador.latido()
    estado = controlador.estado()
    if estaba_activo and not estado['activo']:
        st.rerun()
    if presentacion and not estado['activo']:
        if estado['error']:
            st.error(estado['error'])
            if controlador.video is None:
                st.caption('Comprueba el permiso de Cámara de la Terminal y el índice en En directo → Fuente y captura.')
        return
    # Los botones operan sobre el último fotograma enviado al navegador.
    visible = st.session_state.get('directo_visible')
    acciones = st.columns(3 if presentacion else 4)
    if estado['activo'] and acciones[0].button('Detener', key='directo_detener'):
        controlador.detener()
        st.rerun()
    if controlador.video:
        pausado = estado['pausado']
        if acciones[1].button('Continuar' if pausado else 'Pausar', disabled=not estado['activo'],
                              key='directo_continuar' if pausado else 'directo_pausar'):
            controlador.pausar(not pausado)
        if acciones[2].button('Reiniciar vídeo', disabled=not estado['activo']):
            controlador.reiniciar()
    elif not presentacion:
        grabando = estado['grabar_solicitado']
        if acciones[1].button('Finalizar grabación' if grabando else 'Grabar vídeo',
                              disabled=not estado['activo'] or visible is None,
                              key='directo_fin_grabar' if grabando else 'directo_grabar'):
            controlador.grabar(not grabando)
    if not presentacion:
        foto = acciones[3].button('Guardar foto', disabled=visible is None, key='directo_guardar')
        _guardar_desde_flujo(base, controlador, nombre, estado, visible, foto)
    if estado['error']:
        st.error(estado['error'])
    if presentacion:
        if controlador.video and estado['pausado']:
            st.caption('Fin del vídeo' if estado['mensaje'].startswith('Fin del vídeo') else 'Vídeo de prueba · pausado')
        else:
            st.caption('Vídeo de prueba' if controlador.video else 'Cámara en directo')
    else:
        st.caption(estado['mensaje'] + (' · ● Grabando vídeo limpio' if estado['grabando'] else ''))
    paquete = estado['ultimo']
    if paquete is None or (presentacion and estado['mensaje'].startswith('Esperando imagen')):
        st.info('Esperando imagen…')
        return
    st.session_state['directo_visible'] = paquete
    imagen, resumen = st.columns([2, 1] if presentacion else [3, 1.25])
    with imagen:
        oclusiones = paquete.get('oclusiones', ()) if estado['activo'] else ()
        st.image(vista_video(paquete['resultado'], paquete['objetos'], presentacion=presentacion,
                            oclusiones=oclusiones),
                 channels='BGR', width='stretch')
        if mascara:
            st.image(paquete['resultado']['mascara'], caption='Máscara de objetos', width='stretch')
    with resumen:
        tapete = paquete['resultado']['tapete']
        if tapete['activo'] and not tapete['detectado']:
            st.warning('Inventario sin comprobar. El tapete está fuera de la zona visible o no se ha podido delimitar.')
        else:
            mostrar_inventario(paquete['inventario'])
        if not presentacion:
            st.caption(f"Procesamiento: {paquete['fps']:.1f} FPS" +
                       (f" · Fotograma {paquete['indice']}" if controlador.video else ''))
    if not presentacion:
        for aviso in paquete['resultado']['avisos']:
            st.warning(aviso)
        with st.expander('Por qué se reconoce cada herramienta'):
            st.dataframe([{'Pista': o['id_pista'], 'Herramienta': o['clase_predicha'],
                           'Regla': o['regla'], 'Explicación': o['explicacion']} for o in paquete['objetos']],
                         hide_index=True, width='stretch')
            st.caption('Predicciones por reglas clásicas. Guardar fotos o vídeo no confirma etiquetas.')


def _guardar_desde_flujo(base, controlador, nombre, estado, visible, foto):
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


def mostrar_inventario(inventario):
    st.subheader('Inventario')
    presentes = inventario['presentes']
    esperadas = inventario['esperadas']
    ocultables = inventario.get('posiblemente_ocultas', {})
    filas = []
    if esperadas is None:
        filas = [{'Herramienta': nombre, 'Vistas': cantidad} for nombre, cantidad in presentes.items()]
    else:
        if inventario['provisional']:
            st.warning('Inventario provisional')
        elif inventario['completo']:
            st.success('Inventario completo')
        else:
            st.warning('Hay diferencias en el inventario')
        for nombre in sorted(esperadas.keys() | presentes.keys()):
            vistas = presentes.get(nombre, 0)
            previstas = esperadas.get(nombre, 0)
            faltan = inventario['faltantes'].get(nombre, 0)
            sobran = inventario['repetidos'].get(nombre, 0)
            if faltan:
                inciertas = min(faltan, ocultables.get(nombre, 0))
                faltan_confirmadas = faltan - inciertas
                if inciertas:
                    estado = f'Posiblemente ocultas: {inciertas}'
                    if faltan_confirmadas:
                        estado += f' · faltan {faltan_confirmadas}'
                else:
                    estado = f'Ausente · faltan {faltan}' if vistas == 0 else f'Faltan {faltan}'
            elif sobran:
                estado = f'Sobran {sobran}' if previstas == 0 else f'Repetida · sobran {sobran}'
            else:
                estado = 'Correcto'
            filas.append({'Herramienta': nombre, 'Vistas': vistas, 'Esperadas': previstas, 'Estado': estado})
    if filas:
        st.table(filas, hide_index=True, border='horizontal')
    if ocultables:
        st.caption('Posible oclusión · ' + ', '.join(f'{nombre} ({cantidad})' for nombre, cantidad in ocultables.items()))
    st.caption(f"Detectadas: {inventario['total']} · Sin identificar: {inventario['desconocidos']}")
