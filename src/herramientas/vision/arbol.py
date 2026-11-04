"""Diagramas DOT derivados de las reglas ejecutadas, sin duplicar umbrales.

Cada regla es un subárbol de ocho comprobaciones. El árbol principal evalúa
todas: aceptar la primera coincidencia ocultaría ambigüedades del clasificador.
"""

import json
from herramientas.vision.clasificacion import snapshot_reglas, NOMBRES


def diagrama_decision():
    datos = snapshot_reglas()
    lineas = ['digraph Decision {', 'rankdir=TB;', 'node [shape=box];',
              'entrada [label="Ocho medidas finitas, dominio físico, versión y coherencia", shape=diamond];',
              'invalido [label="Desconocido: datos inválidos / versión / geometría"];',
              'entrada -> invalido [label="No"];']
    anterior = 'entrada'
    for regla in datos['reglas']:
        codigo = regla['regla']
        etiqueta = f"{codigo}: {regla['clase']}\nEvaluar subárbol: compatible e interior"
        lineas += [f'{codigo} [label={json.dumps(etiqueta, ensure_ascii=False)}];',
                   f'{anterior} -> {codigo};']
        anterior = codigo
    lineas += [f'{anterior} -> contar;',
               'contar [label="Número de clases distintas compatibles", shape=diamond];',
               'contar -> desconocido [label="0"];',
               'contar -> ambiguo [label=">1"];',
               'contar -> interior [label="1"];',
               'interior [label="¿Alguna regla de esa clase tiene sus ocho condiciones interiores?", shape=diamond];',
               'interior -> nombre [label="Sí"];', 'interior -> ambiguo [label="No"];',
               'nombre [label="Única clase compatible; explicar una regla interior"];',
               'ambiguo [label="Desconocido: frontera o solapamiento"];',
               'desconocido [label="Desconocido: sin coincidencia"];', '}']
    return '\n'.join(lineas)


def diagrama_regla(codigo):
    datos = snapshot_reglas()
    regla = next((r for r in datos['reglas'] if r['regla'] == codigo), None)
    if regla is None:
        raise ValueError("Regla inexistente.")
    lineas = ['digraph Regla {', 'rankdir=TB;', 'node [shape=diamond];',
              'inicio [shape=box,label="Interior = sí"];',
              'rechazo [shape=box,label="Regla incompatible; continuar con las otras reglas"];',
              'acepta [shape=box,label="Regla compatible; conservar indicador Interior"];']
    anterior = 'inicio'
    for i, c in enumerate(regla['condiciones']):
        clave, minimo, maximo = c['caracteristica'], c['minimo'], c['maximo']
        margen = datos['banda_abstencion']['relacion_aspecto' if clave == 'relacion_aspecto' else 'otros_cocientes']
        fisico = 1 if clave == 'relacion_aspecto' else 0
        mi = 0 if minimo == fisico else margen
        ma = 0 if maximo == 1 and clave != 'relacion_aspecto' else margen
        compatible = f"{minimo-mi:g} ≤ {NOMBRES[clave]} ≤ {maximo+ma:g}"
        interior = f"{minimo+mi:g} {'≤' if mi == 0 else '<'} {NOMBRES[clave]} {'≤' if ma == 0 else '<'} {maximo-ma:g}"
        lineas += [f'c{i} [label={json.dumps(compatible, ensure_ascii=False)}];',
                   f'{anterior} -> c{i};', f'c{i} -> rechazo [label="No"];',
                   f'c{i} -> i{i} [label="Sí"];',
                   f'i{i} [label={json.dumps(interior, ensure_ascii=False)}];',
                   f'f{i} [shape=box,label="Interior = no"];',
                   f'i{i} -> f{i} [label="No (frontera)"];',
                   f'i{i} -> s{i} [label="Sí"];',
                   f'f{i} -> s{i};', f's{i} [shape=point];']
        anterior = f's{i}'
    lineas += [f'{anterior} -> acepta;', '}']
    return '\n'.join(lineas)


def tabla_umbrales():
    return [{"Regla": r['regla'], "Clase": r['clase'], "Característica": c['caracteristica'],
             "Mínimo": c['minimo'], "Máximo": c['maximo']}
            for r in snapshot_reglas()['reglas'] for c in r['condiciones']]


def exportar_arboles(destino):
    """Regenera los diagramas de documentación desde la fuente de verdad."""
    from pathlib import Path
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    (destino/'principal.dot').write_text(diagrama_decision()+'\n', encoding='utf-8')
    for regla in snapshot_reglas()['reglas']:
        (destino/f"{regla['regla']}.dot").write_text(diagrama_regla(regla['regla'])+'\n', encoding='utf-8')
    (destino/'reglas.json').write_text(json.dumps(snapshot_reglas(), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    from pathlib import Path
    from herramientas.datos.configuracion import BASE
    exportar_arboles(BASE/'docs'/'arboles')
    print('Diagramas regenerados en docs/arboles/. Se visualizan en la web → Entrega.')
