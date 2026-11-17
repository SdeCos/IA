"""Evaluación completa con correspondencias humanas uno a uno.

La referencia lista TODOS los objetos reales. Una detección no asociada es FP;
un objeto real no asociado es FN. No se utilizan nombres predichos para asociar.
Los archivos guardados incluyen la imagen y la firma de segmentación: si cambia
el procesamiento se exige revisar las correspondencias, nunca se heredan por ID.
"""
from collections import Counter
from datetime import datetime, timezone
import csv
from io import StringIO
import json
from pathlib import Path

import cv2

from herramientas.datos.analisis import identificar_captura
from herramientas.vision.clasificacion import GRUPOS_DESARROLLO, clasificar_objetos, snapshot_reglas
from herramientas.datos.entrega import escribir_json
from herramientas.datos.etiquetado import firma_deteccion, huella_imagen
from herramientas.datos.evaluacion import inventario_objetos
from herramientas.vision.vision import procesar_imagen


def evaluar_escena(objetos, referencias, asociaciones, esperadas=None):
    """Referencias: nombres por orden; asociaciones: ID detección -> índice desde 1.

    El valor cero declara una falsa detección. Exige revisar todas las detecciones.
    Una unión de dos herramientas no cuenta como dos aciertos: solo se asocia si
    representa una herramienta completa y separada, según el protocolo documentado.
    """
    if (not isinstance(referencias, list) or
            any(not isinstance(n, str) or not n.strip() for n in referencias)):
        raise ValueError("Cada objeto real necesita un nombre; se admite una escena vacía.")
    referencias = [n.strip() for n in referencias]
    ids = [o['id'] for o in objetos]
    if len(set(ids)) != len(ids):
        raise ValueError("Hay IDs de detección duplicados.")
    if not isinstance(asociaciones, dict):
        raise ValueError("Faltan las correspondencias manuales.")
    try:
        mapa = {int(k): v for k, v in asociaciones.items()}
    except (TypeError, ValueError) as error:
        raise ValueError("ID de detección inválido.") from error
    if len(mapa) != len(asociaciones) or set(mapa) != set(ids):
        raise ValueError("Revisa todas las detecciones actuales, incluidas las falsas.")
    if any(type(v) is not int or not 0 <= v <= len(referencias) for v in mapa.values()):
        raise ValueError("La correspondencia apunta a un objeto real inexistente.")
    usados = [v for v in mapa.values() if v]
    if len(set(usados)) != len(usados):
        raise ValueError("Un objeto real no puede asociarse a dos detecciones.")
    filas = []
    for o in objetos:
        indice = mapa[o['id']]
        predicha = o['clase_predicha'] if o['estado_clasificacion'] == 'identificada' else 'Desconocido'
        real = referencias[indice-1] if indice else 'Sin objeto'
        filas.append(dict(id_deteccion=o['id'], id_real=indice or None, nombre_real=real,
                          clase_predicha=predicha,
                          resultado='falso_positivo' if not indice else
                          'acierto' if real == predicha else 'rechazo' if predicha == 'Desconocido' else 'error'))
    for i, nombre in enumerate(referencias, 1):
        if i not in usados:
            filas.append(dict(id_deteccion=None, id_real=i, nombre_real=nombre,
                              clase_predicha='No detectado', resultado='omision'))
    # Una detección bien asociada cuenta como TP aunque su nombre sea erróneo.
    # El acierto de identificación exige además acertar la clase.
    tp, fp, fn = len(usados), len(objetos)-len(usados), len(referencias)-len(usados)
    aciertos = sum(f['resultado'] == 'acierto' for f in filas)
    predicho = inventario_objetos(objetos, esperadas)
    real = dict(Counter(referencias))
    # La comparación de ausencias/sobrantes se hace directamente, incluyendo
    # referencias de clases sin regla, que también deben contar como objetos reales.
    cantidades = predicho['esperadas']
    faltan = sobran = avisos_correctos = None
    if cantidades is not None:
        faltan = {n: c-real.get(n, 0) for n, c in cantidades.items() if c > real.get(n, 0)}
        sobran = {n: c-cantidades.get(n, 0) for n, c in real.items() if c > cantidades.get(n, 0)}
        avisos_correctos = (not predicho['provisional'] and predicho['faltantes'] == faltan
                           and predicho['repetidos'] == sobran)
    conteo = Counter((f['nombre_real'], f['clase_predicha']) for f in filas)
    return dict(reales=len(referencias), detectados=len(objetos), tp=tp, fp=fp, fn=fn,
                aciertos=aciertos, precision=tp/(tp+fp) if tp+fp else None,
                exhaustividad=tp/(tp+fn) if tp+fn else None,
                clasificacion=aciertos/tp if tp else None,
                identificacion_completa=aciertos/len(referencias) if referencias else None,
                inventario_real=real, inventario_predicho=predicho,
                inventario_exacto=not predicho['desconocidos'] and predicho['presentes'] == real,
                avisos_correctos=avisos_correctos, faltantes_reales=faltan, sobrantes_reales=sobran,
                filas=filas, matriz=[dict(nombre_real=a, clase_predicha=b, cantidad=c)
                                     for (a, b), c in sorted(conteo.items())])


def ruta_referencia(base, imagen):
    return Path(base) / "datos" / 'evaluaciones' / huella_imagen(imagen) / 'referencia.json'


def guardar_referencia(base, origen, imagen, valores, resultado, referencias, asociaciones,
                       esperadas, reservada):
    """Conserva los píxeles, los ajustes y las correspondencias revisadas."""
    # Validar TODO antes de escribir. Las predicciones no se convierten en verdad.
    informe = evaluar_escena(clasificar_objetos(resultado['objetos']), referencias, asociaciones, esperadas)
    huella = huella_imagen(imagen)
    grupo = identificar_captura(origen, huella, base)
    if reservada and grupo in GRUPOS_DESARROLLO:
        raise ValueError('Esta adquisición ya se utilizó en desarrollo; no es una prueba independiente.')
    ruta = ruta_referencia(base, imagen)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    png = ruta.parent / 'imagen.png'
    if png.exists():
        if huella_imagen(cv2.imread(str(png))) != huella:
            raise ValueError('La imagen guardada ha cambiado; revisa el paquete de evaluación.')
    else:
        if not cv2.imwrite(str(png), imagen):
            raise OSError('No se pudo guardar la imagen de referencia.')
    datos = dict(version=1, fecha=datetime.now(timezone.utc).isoformat(), origen=str(origen),
                 huella=huella, grupo=grupo, reservada=bool(reservada), confirmada=True,
                 firma=firma_deteccion(imagen, valores, resultado), valores=dict(valores),
                 referencias=referencias, asociaciones=asociaciones, esperadas=esperadas,
                 reglas=snapshot_reglas(), resultado_al_guardar=informe)
    # Si estos píxeles ya se usaron para desarrollo, una nueva marca no los hace
    # independientes. Se conserva también su primera procedencia.
    if ruta.exists():
        anterior = json.loads(ruta.read_text(encoding='utf-8'))
        if anterior.get('huella') != huella:
            raise ValueError('La referencia anterior no corresponde a esta imagen.')
        datos['grupo'] = anterior['grupo']
        datos['reservada'] = bool(reservada and anterior.get('reservada'))
    escribir_json(ruta, datos)
    return ruta


def cargar_referencia(base, imagen, valores, resultado):
    ruta = ruta_referencia(base, imagen)
    if not ruta.exists():
        return None, False
    datos = json.loads(ruta.read_text(encoding='utf-8'))
    if datos.get('version') != 1 or datos.get('huella') != huella_imagen(imagen):
        raise ValueError('Referencia incompatible con la fotografía.')
    return datos, datos.get('firma') == firma_deteccion(imagen, valores, resultado)


def resumen_escenas(escenas):
    """Agrega aciertos y errores por objeto y comprueba inventario por escena."""
    tp = sum(e['tp'] for e in escenas)
    fp = sum(e['fp'] for e in escenas)
    fn = sum(e['fn'] for e in escenas)
    aciertos = sum(e['aciertos'] for e in escenas)
    matriz = Counter()
    for e in escenas:
        for fila in e['matriz']:
            matriz[fila['nombre_real'], fila['clase_predicha']] += fila['cantidad']
    comparables = [e for e in escenas if e['avisos_correctos'] is not None]
    return dict(escenas=len(escenas), grupos=len({e['grupo'] for e in escenas}), tp=tp, fp=fp, fn=fn,
                precision=tp/(tp+fp) if tp+fp else None,
                exhaustividad=tp/(tp+fn) if tp+fn else None,
                clasificacion=aciertos/tp if tp else None,
                identificacion_completa=aciertos/(tp+fn) if tp+fn else None,
                inventario_exacto=sum(e['inventario_exacto'] for e in escenas)/len(escenas) if escenas else None,
                avisos_correctos=sum(e['avisos_correctos'] for e in comparables)/len(comparables) if comparables else None,
                matriz=[dict(nombre_real=a, clase_predicha=b, cantidad=c) for (a,b),c in sorted(matriz.items())])


def evaluar_guardadas(base):
    """Recalcula las referencias válidas y separa los resultados por procedencia."""
    escenas, excluidas = [], []
    desarrollo = set(GRUPOS_DESARROLLO)
    for ruta in sorted((Path(base)/"datos" / 'evaluaciones').glob('*/referencia.json')):
        try:
            datos = json.loads(ruta.read_text(encoding='utf-8'))
            if datos.get('version') != 1 or datos.get('confirmada') is not True:
                raise ValueError('Referencia sin confirmación compatible.')
            if not isinstance(datos.get('grupo'), str) or not datos['grupo'] or type(datos.get('reservada')) is not bool:
                raise ValueError('Falta la procedencia y declaración de reserva de la adquisición.')
            # Una referencia obsoleta sigue siendo evidencia de que se usó el
            # grupo para desarrollar; excluir sus métricas no borra ese hecho.
            if not datos['reservada']:
                desarrollo.add(datos['grupo'])
            imagen = cv2.imread(str(ruta.parent/'imagen.png'))
            if huella_imagen(imagen) != datos['huella']:
                raise ValueError('La imagen ha cambiado.')
            resultado = procesar_imagen(imagen, datos['valores'])
            if firma_deteccion(imagen, datos['valores'], resultado) != datos['firma']:
                raise ValueError('Segmentación distinta: revisar correspondencias antes de evaluar.')
            informe = evaluar_escena(clasificar_objetos(resultado['objetos']), datos['referencias'],
                                     datos['asociaciones'], datos['esperadas'])
            escenas.append(dict(informe, huella=datos['huella'], grupo=datos['grupo'],
                                reservada=datos['reservada'], origen=datos['origen']))
        except (OSError, ValueError, KeyError, TypeError, cv2.error) as error:
            excluidas.append(dict(archivo=str(ruta), motivo=str(error)))
    # Cualquier uso de desarrollo de un clip contamina TODAS sus escenas.
    vistos, unicas = set(), []
    for e in escenas:
        if e['huella'] in vistos:
            continue
        vistos.add(e['huella'])
        e['particion'] = 'desarrollo' if e['grupo'] in desarrollo else 'prueba'
        unicas.append(e)
    return dict(version=1, reglas=snapshot_reglas(), escenas=unicas, excluidas=excluidas,
                desarrollo=resumen_escenas([e for e in unicas if e['particion']=='desarrollo']),
                prueba=resumen_escenas([e for e in unicas if e['particion']=='prueba']))


def csv_escenas(informe, detalle=False):
    campos = (['huella', 'grupo', 'particion', 'id_deteccion', 'id_real', 'nombre_real', 'clase_predicha', 'resultado']
              if detalle else ['huella', 'grupo', 'particion', 'reales', 'detectados', 'tp', 'fp', 'fn',
                               'aciertos', 'precision', 'exhaustividad', 'clasificacion',
                               'identificacion_completa', 'inventario_exacto', 'avisos_correctos'])
    salida = StringIO(newline='')
    escritor = csv.DictWriter(salida, fieldnames=campos, delimiter=';', extrasaction='ignore')
    escritor.writeheader()
    for escena in informe['escenas']:
        for fila in escena['filas'] if detalle else [escena]:
            escritor.writerow({**escena, **fila})
    return salida.getvalue().encode('utf-8-sig')
