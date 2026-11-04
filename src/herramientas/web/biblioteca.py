"""Biblioteca de fotos: títulos de organización y revisión verificable de etiquetas."""
from pathlib import Path
import re
import unicodedata

import cv2
import streamlit as st

from herramientas.datos.configuracion import cargar_configuracion, configuracion_para_imagen
from herramientas.datos.etiquetado import cargar_etiquetas_existentes, firma_deteccion, huella_imagen
from herramientas.datos.nombres import leer_nombre, guardar_nombre
from herramientas.datos.papelera import pareja_captura, retirar_captura, restaurar_captura
from herramientas.vision.vision import procesar_imagen, VERSION_PROCESADO
from herramientas.vision.geometria import VERSION_CARACTERISTICAS
from herramientas.vision.clasificacion import clasificar_objetos, VERSION_CLASIFICADOR

VERSION_BIBLIOTECA = 2


def resumen_foto(ruta, base):
    """No basta con que exista un JSON: verificar píxeles, ajustes, IDs y revisión."""
    ruta = Path(ruta)
    imagen = cv2.imread(str(ruta))
    if imagen is None:
        raise ValueError('Imagen ilegible')
    config = ruta.parent / 'configuracion.json'
    valores = (cargar_configuracion(config) if ruta.name == 'imagen_origen.png' and config.exists()
               else configuracion_para_imagen(ruta))
    resultado = procesar_imagen(imagen, valores)
    carga = cargar_etiquetas_existentes(ruta, imagen, valores, resultado, base=base)
    ids = {o['id'] for o in resultado['objetos']}
    confirmadas = {i for i in carga['revisadas'] if carga['etiquetas'].get(i)}
    completa = bool(ids) and ids == confirmadas and bool(carga['origen'])
    nombres = sorted({carga['etiquetas'][i] for i in confirmadas})
    sugeridas = sorted({o['clase_predicha'] for o in clasificar_objetos(resultado['objetos'])
                       if o['estado_clasificacion'] == 'identificada'})
    titulo = leer_nombre(ruta)
    if not titulo:
        titulo = ('Etiquetas: ' + ', '.join(nombres) if nombres else
                  'Predicción: ' + ', '.join(sugeridas) if sugeridas else 'Sin nombre')
    estado = ('Etiquetada y guardada' if completa else 'Sin detecciones · revisar' if not ids else
              'Revisar etiquetas' if carga['avisos'] else f'Pendiente · {len(confirmadas)}/{len(ids)} confirmadas')
    return dict(titulo=titulo, estado=estado, completa=completa,
                huella=huella_imagen(imagen), firma=firma_deteccion(imagen, valores, resultado))


def revision_archivos(rutas):
    revision = []
    for ruta in sorted(set(Path(p) for p in rutas)):
        try:
            info = ruta.stat()
            revision.append((str(ruta), info.st_mtime_ns, info.st_ctime_ns, info.st_size))
        except FileNotFoundError:
            revision.append((str(ruta), None))
    return tuple(revision)


@st.cache_data(show_spinner=False, max_entries=256)
def _resumen_cache(ruta, base, revision, globales, versiones):
    # revision incluye los archivos de entrada y de anotaciones; globales recoge
    # también los valores predeterminados. No se cachean revisiones del navegador.
    try:
        return resumen_foto(ruta, base)
    except (OSError, ValueError, TypeError, cv2.error):
        return dict(titulo=leer_nombre(ruta) or 'Sin nombre', estado='Error · revisar',
                    completa=False, huella='', firma='')


def normalizar_busqueda(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', texto.casefold())
                   if not unicodedata.combining(c))


def descripcion(ruta, ficha):
    fuente = ruta.parent.name if ruta.name == 'imagen_origen.png' else ruta.stem
    fechas = re.findall(r'(\d{8})_(\d{6})_(\d{6})', fuente)
    if fechas:
        fecha, hora, micros = fechas[-1]
        identidad = f'{fecha[6:]}/{fecha[4:6]} {hora[:2]}:{hora[2:4]}:{hora[4:]} · {micros}'
    else:
        identidad = fuente
    if ruta.name.startswith('original_'):
        identidad = 'Original · ' + identidad
    return f"{ficha['titulo']} — {ficha['estado']} — {identidad}"


def seleccionar_foto(opciones, base, sesiones=False):
    """Filtra fotos y ofrece retirada explícita y recuperable; no confirma etiquetas."""
    base = Path(base)
    if not sesiones:
        mostrar_originales = st.sidebar.checkbox('Mostrar también originales sin recortar', value=False)
        if not mostrar_originales:
            opciones = [p for p in opciones if not (
                p.name.startswith('original_') and pareja_captura(p) in opciones)]
    guardados = list((base/'datos'/'resultados').glob('*/*.json'))
    guardados += list((base/'datos'/'etiquetas').glob('*.json'))
    # Las anotaciones antiguas pueden referir fotos que hayan cambiado.
    guardados += list((base/'datos'/'capturas').glob('*'))
    revision = revision_archivos(guardados)
    globales = cargar_configuracion()
    fichas = {}
    for ruta in opciones:
        propios = [ruta, ruta.with_suffix('.json'), ruta.with_suffix('.nombre.json'),
                   ruta.parent/'configuracion.json']
        ficha = _resumen_cache(str(ruta), str(base),
                              (revision, revision_archivos(propios)), globales,
                              (VERSION_PROCESADO, VERSION_CARACTERISTICAS, VERSION_CLASIFICADOR))
        memoria = st.session_state.get('sesiones_trabajo', {}).get(f"{ficha['huella'][:16]}_{ruta}")
        if memoria and (memoria['modificada'] or memoria['firma'] != ficha['firma']):
            ficha.update(completa=False, estado='Cambios sin guardar · revisar')
        fichas[ruta] = ficha
    completas = sum(f['completa'] for f in fichas.values())
    st.sidebar.caption(f'{len(opciones) - completas} pendientes · {completas} etiquetadas y guardadas')
    filtro = st.sidebar.selectbox('Estado de las fotos', ['Todas', 'Pendientes', 'Etiquetadas y guardadas'],
                                  key='filtro_estado_fotos')
    texto = st.sidebar.text_input('Buscar foto', key='buscar_foto', placeholder='Alicate, Allen, fecha…')
    busqueda = normalizar_busqueda(texto.strip())
    visibles = [p for p in opciones if
                (filtro == 'Todas' or fichas[p]['completa'] == (filtro == 'Etiquetadas y guardadas'))
                and (not busqueda or busqueda in normalizar_busqueda(descripcion(p, fichas[p]) + ' ' + str(p)))]
    if not visibles:
        st.info('No hay fotos con estos filtros. Cambia el estado a «Todas» o borra la búsqueda.')
        st.stop()
    clave = 'sesion_elegida' if sesiones else 'foto_elegida'
    siguiente = st.session_state.pop('biblioteca_siguiente', None)
    if siguiente in visibles:
        st.session_state[clave] = siguiente
    if st.session_state.get(clave) not in visibles:
        st.session_state.pop(clave, None)
    elegida = st.sidebar.selectbox('Sesión' if sesiones else 'Foto guardada', visibles,
                                  format_func=lambda p: descripcion(p, fichas[p]), key=clave)
    st.sidebar.caption(elegida.name)
    st.session_state['biblioteca_visibles'] = visibles
    st.session_state['biblioteca_pendientes'] = [p for p in visibles if not fichas[p]['completa']]
    with st.sidebar.expander("Ayuda con los estados"):
        st.caption("Predicción = sugerencia. Solo se consideran terminadas las etiquetas confirmadas, guardadas y vigentes. Una foto sin detecciones queda pendiente.")
        st.caption('Por defecto se muestra el recorte de cada captura y se oculta su original. Son imágenes distintas: etiquetar una no confirma automáticamente la otra.')
    with st.sidebar.expander('Nombre de la foto'):
        with st.form(f'nombre_foto_{elegida}'):
            nombre = st.text_input('Nombre para organizar', value=leer_nombre(elegida), max_chars=80,
                                   help='Por ejemplo: Alicate abierto 45°. No modifica etiquetas ni reglas.')
            guardar = st.form_submit_button('Guardar nombre')
        if guardar:
            try:
                guardar_nombre(elegida, nombre)
            except (OSError, ValueError) as error:
                st.error(str(error))
            else:
                st.rerun()
    if not sesiones:
        with st.sidebar.expander('Descartar foto'):
            st.caption('Mueve esta captura, su original/recorte y sus ajustes a una papelera recuperable. Las sesiones ya exportadas y sus etiquetas se conservan.')
            if st.button('Mover captura a la papelera'):
                try:
                    retirar_captura(elegida, base)
                except (OSError, ValueError) as error:
                    st.error(str(error))
                else:
                    for token in list(st.session_state.get('sesiones_trabajo', {})):
                        if token.endswith('_' + str(elegida)) or token.endswith('_' + str(pareja_captura(elegida))):
                            del st.session_state['sesiones_trabajo'][token]
                    st.session_state['biblioteca_mensaje'] = 'Captura retirada. Puedes recuperarla desde Papelera.'
                    st.rerun()
    return elegida


def preparar_siguiente(origen):
    """Programa navegación para el siguiente rerun, antes de crear el selector."""
    visibles = st.session_state.get('biblioteca_visibles', [])
    pendientes = st.session_state.get('biblioteca_pendientes', [])
    if origen not in visibles:
        return
    indice = visibles.index(origen)
    orden = visibles[indice+1:] + visibles[:indice]
    siguiente = next((p for p in orden if p in pendientes), None)
    if siguiente:
        st.session_state['biblioteca_siguiente'] = siguiente


def mostrar_papelera(base):
    entradas = sorted((Path(base)/'datos/papelera').glob('*/papelera.json'), reverse=True)
    if not entradas:
        return
    import json
    with st.sidebar.expander(f'Papelera ({len(entradas)})'):
        opciones = {}
        for p in entradas:
            try:
                opciones[p.parent] = json.loads(p.read_text())['foto'] + ' · ' + p.parent.name[:15]
            except (OSError, ValueError, KeyError):
                continue
        if not opciones:
            return
        carpeta = st.selectbox('Captura para recuperar', list(opciones), format_func=opciones.get)
        if st.button('Restaurar captura'):
            try:
                restaurar_captura(carpeta, base)
            except (OSError, ValueError, KeyError) as error:
                st.error(str(error))
            else:
                st.session_state['biblioteca_mensaje'] = 'Captura restaurada con sus ajustes.'
                st.rerun()
