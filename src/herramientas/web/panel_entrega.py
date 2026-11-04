"""Preparación de entrega y evaluación completa con referencias humanas."""
import hashlib
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from herramientas.vision.arbol import diagrama_decision, diagrama_regla, tabla_umbrales
from herramientas.vision.clasificacion import CLASES_SOPORTADAS, GRUPOS_DESARROLLO, snapshot_reglas
from herramientas.datos.entrega import cargar_perfil, guardar_perfil
from herramientas.datos.evaluacion_escenas import (cargar_referencia, guardar_referencia, evaluar_guardadas,
                               evaluar_escena, csv_escenas)
from herramientas.datos.etiquetado import firma_deteccion, huella_imagen
from herramientas.datos.analisis import identificar_captura, reunir_datos


def mostrar_arbol():
    st.markdown('### Árbol de decisión y umbrales')
    st.caption('Cada regla tiene ocho condiciones. Una herramienta puede tener varias reglas para sus distintas vistas. Si coinciden clases diferentes o ninguna regla cumple fuera de sus márgenes, el sistema se abstiene.')
    st.graphviz_chart(diagrama_decision(), width='stretch')
    st.download_button('Descargar árbol principal · DOT', diagrama_decision(), 'arbol.dot', key='arbol_dot')
    reglas = snapshot_reglas()['reglas']
    codigo = st.selectbox('Subárbol de una herramienta', [r['regla'] for r in reglas],
                          format_func=lambda c: next(f"{c} · {r['clase']} — {r['descripcion']}" for r in reglas if r['regla']==c))
    st.graphviz_chart(diagrama_regla(codigo), width='stretch')
    st.download_button('Descargar subárbol · DOT', diagrama_regla(codigo), f'{codigo}.dot', key='subarbol_dot')
    st.caption('Los límites interiores excluyen las bandas de abstención. El diagrama se genera desde los mismos intervalos y márgenes que ejecuta el clasificador.')
    st.dataframe(tabla_umbrales(), hide_index=True, width='stretch')


def mostrar_preparacion(base):
    st.header('Preparar la entrega')
    st.write('Selecciona el alcance y el inventario, consulta las reglas y reúne las evidencias.')
    try:
        perfil = cargar_perfil(base)
    except (OSError, ValueError) as error:
        st.error(f'Perfil no válido: {error}')
        return
    with st.form('perfil_entrega'):
        clases = st.multiselect('Clases de la entrega (5–8)', list(CLASES_SOPORTADAS),
                                default=perfil['clases'] if perfil else [])
        st.caption('Las cantidades se aplican a las clases seleccionadas. Cero significa que esa clase no debería estar en la escena de referencia.')
        columnas = st.columns(3)
        cantidades = {}
        for i, c in enumerate(CLASES_SOPORTADAS):
            with columnas[i % 3]:
                cantidades[c] = st.number_input(f'Inventario esperado · {c}', min_value=0, max_value=100,
                                                value=(perfil or {}).get('esperadas', {}).get(c, 1))
        guardar = st.form_submit_button('Guardar perfil de entrega')
    if guardar:
        try:
            perfil = guardar_perfil(base, clases, {c: cantidades[c] for c in clases})
            st.success('Perfil guardado en config/entrega.json. Se utiliza en fotos, vídeos y nuevas ejecuciones del modo directo.')
        except (OSError, ValueError) as error:
            st.error(str(error))
    st.caption('El alcance no borra ni desactiva reglas: las otras clases siguen siendo visibles y cuentan como sobrantes si no se esperan. Así no se ocultan falsos positivos.')
    if perfil:
        st.download_button('Descargar inventario para --inventario', json.dumps(perfil['esperadas'], ensure_ascii=False, indent=2),
                           'inventario.json', 'application/json')
    with st.expander('Ver árbol y condiciones', expanded=False):
        mostrar_arbol()
    with st.expander('Mediciones que respaldan los umbrales'):
        st.caption('Mediciones descriptivas de referencias confirmadas. No se ajustan umbrales automáticamente ni se convierten estos datos en evaluación independiente.')
        if st.button('Reunir tabla de mediciones'):
            datos = reunir_datos(base)
            filas = datos['filas']
            from herramientas.vision.clasificacion import CARACTERISTICAS
            tabla = []
            for clase in CLASES_SOPORTADAS:
                for clave in CARACTERISTICAS:
                    valores = [f[clave] for f in filas if f.get('nombre_real') == clase and f.get(clave) is not None]
                    if valores:
                        tabla.append(dict(Clase=clase, Caracteristica=clave, Muestras=len(valores),
                                          Minimo=min(valores), Maximo=max(valores)))
            st.dataframe(tabla, hide_index=True, width='stretch')
            st.download_button('Descargar mediciones por clase', pd.DataFrame(tabla).to_csv(index=False, sep=';').encode('utf-8-sig'),
                               'mediciones_umbrales.csv', 'text/csv')
            for aviso in datos['avisos']:
                st.caption(aviso)
    st.info('Las pruebas físicas y la evaluación con escenas nuevas siguen pendientes. La checklist distingue esas tareas de las funciones ya implementadas.')
    with st.expander('Checklist y guiones para descargar'):
        for nombre, titulo in [('CHECKLIST_ENTREGA.md', 'Checklist de entrega'),
                               ('PRUEBAS_CASA.md', 'Guion de pruebas en casa'),
                               ('DEFENSA_Y_VIDEO.md', 'Guion de defensa y vídeo'),
                               ('RESPALDOS.md', 'Copias de seguridad')]:
            ruta = Path(base)/'docs'/nombre
            if ruta.exists():
                st.download_button(titulo, ruta.read_text(encoding='utf-8'), nombre, 'text/markdown')
    mostrar_informe_escenas(base)


def mostrar_informe_escenas(base):
    st.markdown('### Evaluación completa de escenas guardadas')
    st.caption('Recalcula con las reglas actuales. Un cambio de segmentación obliga a revisar las correspondencias. No se mezclan escenas del mismo grupo entre desarrollo y prueba.')
    if st.button('Evaluar escenas completas', key='evaluar_completas'):
        st.session_state['informe_escenas_completas'] = (str(base), evaluar_guardadas(base))
    anterior = st.session_state.get('informe_escenas_completas')
    if not anterior or anterior[0] != str(base):
        return
    informe = anterior[1]
    st.caption('Resultado de la última evaluación. Repite la evaluación tras guardar referencias o cambiar reglas.')
    for parte, titulo in [('desarrollo', 'Desarrollo'), ('prueba', 'Prueba reservada')]:
        resumen = informe[parte]
        st.markdown(f'**{titulo}: {resumen["escenas"]} escenas · {resumen["grupos"]} grupos**')
        st.dataframe([{k: resumen[k] for k in ('tp','fp','fn','precision','exhaustividad','clasificacion',
                                               'identificacion_completa','inventario_exacto','avisos_correctos')}], hide_index=True)
        if resumen['matriz']:
            st.dataframe(pd.DataFrame(resumen['matriz']).pivot(index='nombre_real', columns='clase_predicha', values='cantidad').fillna(0).astype(int))
    st.caption('Proporciones entre 0 y 1; vacío = no aplicable. La matriz incluye «No detectado» y «Sin objeto». Los fotogramas de un clip no son pruebas independientes.')
    for problema in informe['excluidas']:
        st.warning(f"Excluida {problema['archivo']}: {problema['motivo']}")
    st.download_button('Descargar evaluación completa · JSON', json.dumps(informe, ensure_ascii=False, indent=2), 'evaluacion_completa.json', 'application/json')
    st.download_button('Descargar métricas por escena · CSV', csv_escenas(informe), 'escenas.csv', 'text/csv')
    st.download_button('Descargar correspondencias · CSV', csv_escenas(informe, detalle=True), 'objetos_evaluados.csv', 'text/csv')


def mostrar_referencia_escena(base, resultado, objetos, sesion, origen, imagen, token, esperadas):
    with st.expander('Evaluar la escena completa: incluir omisiones y falsas detecciones'):
        st.write('Lista TODAS las herramientas reales de la foto, una por línea. Repite el nombre si hay dos ejemplares. Después relaciona los números de detección con esa lista.')
        st.caption('Asocia solo una silueta completa y separada con un objeto real. Marca sombras, fragmentos y uniones de herramientas como falsa detección; sus objetos reales quedan omitidos. Una escena realmente vacía tiene la lista vacía.')
        anterior, vigente = cargar_referencia(base, imagen, sesion['valores'], resultado)
        firma = firma_deteccion(imagen, sesion['valores'], resultado)
        clave = f'escena_{token}_{firma[:12]}'
        if anterior and not vigente:
            st.warning('La segmentación ha cambiado. Se conservan los nombres reales como propuesta, pero debes revisar de nuevo todas las correspondencias.')
        texto = st.text_area('Objetos reales (uno por línea)', '\n'.join(anterior['referencias']) if anterior else '', key=clave+'_reales')
        referencias = [n.strip() for n in texto.splitlines() if n.strip()]
        sufijo = hashlib.sha256(texto.encode()).hexdigest()[:10]
        asociaciones = {}
        for objeto in objetos:
            guardado = (anterior or {}).get('asociaciones', {}).get(str(objeto['id'])) if vigente and referencias == anterior['referencias'] else None
            opciones = list(range(len(referencias)+1))
            asociaciones[objeto['id']] = st.selectbox(f'Detección {objeto["id"]} corresponde a', opciones,
                index=opciones.index(guardado) if guardado in opciones else None,
                format_func=lambda i: 'Falsa detección / fragmento / unión' if i == 0 else f'Real {i}: {referencias[i-1]}',
                key=clave+f'_mapa_{objeto["id"]}_{sufijo}')
        grupo = identificar_captura(origen, huella_imagen(imagen), base)
        st.caption(f'Grupo de adquisición: {grupo}. Inventario esperado: {esperadas if esperadas is not None else "no definido"}.')
        reservada = st.checkbox('Esta adquisición se reservó para prueba y no se utilizó para ajustar el sistema',
                               value=bool(anterior and anterior.get('reservada')), disabled=grupo in GRUPOS_DESARROLLO,
                               key=clave+'_reservada')
        if grupo in GRUPOS_DESARROLLO:
            reservada = False
            st.caption('Este grupo ya consta como desarrollo; no puede marcarse como prueba.')
        revision = hashlib.sha256(json.dumps([referencias, asociaciones, esperadas, reservada], sort_keys=True).encode()).hexdigest()[:12]
        confirmada = st.checkbox('He revisado todos los objetos reales y todas las correspondencias', key=clave+'_confirmada_'+revision)
        if st.button('Guardar referencia completa de la escena', key=clave+'_guardar', disabled=not confirmada):
            try:
                ruta = guardar_referencia(base, origen, imagen, sesion['valores'], resultado,
                                           referencias, asociaciones, esperadas, reservada)
                st.success(f'Referencia guardada: {ruta}')
                st.session_state.pop('informe_escenas_completas', None)
                informe = evaluar_escena(objetos, referencias, asociaciones, esperadas)
                st.write({k: informe[k] for k in ('tp', 'fp', 'fn', 'identificacion_completa', 'inventario_exacto')})
            except (OSError, ValueError) as error:
                st.error(str(error))
        st.caption('El guardado conserva los píxeles, ajustes, reglas y referencia humana. No modifica las etiquetas de calibración. Si usas una prueba para retocar reglas, desmarca su reserva; todo su grupo pasa a desarrollo.')
    mostrar_informe_escenas(base)
