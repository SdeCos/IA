# Defensa y vídeo de demostración

El enunciado actualizado pide una demo presentada por el alumno de **7–10 minutos**,
subida a **YouTube con la cuenta universitaria**, con enlace en la **portada** del
trabajo. La demostración presencial será con escenas propuestas por el profesor.
No se ha grabado ni publicado nada automáticamente.

## Guion orientativo (9 minutos)

| Tiempo | Mostrar y explicar |
|---|---|
| 0:00–1:00 | Problema, clases elegidas y resultado: inventario con ausentes/repetidas. |
| 1:00–2:00 | Montaje físico, medidas, cámara fija, cobertura e iluminación. |
| 2:00–3:00 | Pipeline y máscara; cómo se excluye la mesa y se detectan contornos. |
| 3:00–4:30 | Características, árbol/subárbol de una herramienta y una decisión concreta con valores. |
| 4:30–6:30 | Escenas diferentes: giros, cambios de posición, retirar una herramienta, añadir una repetida si se dispone de ella. |
| 6:30–8:00 | Resultados de prueba reservada: detección, clasificación, inventario y al menos un fallo explicado. |
| 8:00–9:00 | Limitaciones, conclusiones y cómo reproducir el programa. |

Identifica explícitamente vídeo guardado y cámara real. No presentes fotogramas
conocidos como evaluación independiente. Para registrar pantalla puedes utilizar
la grabación del sistema; R en el programa guarda vídeo limpio de adquisición,
**sin audio ni superposiciones**, y no sustituye la demo narrada.

## Preguntas para ensayar

- ¿Qué hace la segmentación HSV? Busca el fondo verde; la máscara de objetos es
  su complemento dentro de la región útil, con limpieza y filtrado.
- ¿Cómo se calcula la relación de aspecto? Lado largo/lado corto de la caja
  mínima rotada; no ancho/alto fijo de la pantalla.
- ¿Qué son solidez y circularidad? Área/envolvente convexa y 4π·área/perímetro².
  Explica con las siluetas del proyecto qué aporta cada una.
- ¿Cómo separas calibre y martillo? Combinando ocho medidas; en los ejemplares
  de desarrollo ayudan el ancho central y el contraste de extremos. No basta AR.
- ¿Por qué hay etiquetas manuales? Son referencias humanas para medir y evaluar;
  el clasificador no consulta sus nombres ni se entrena al guardarlas.
- ¿Qué ocurre si dos reglas coinciden? Se abstiene. No selecciona arbitrariamente
  la primera; muestra desconocido/ambigua.
- ¿Qué es una pista P1? Asociación temporal por geometría/proximidad, no una clase.
- ¿Cómo sabes qué falta? Comparando el recuento actual con cantidades esperadas
  definidas explícitamente. Una omisión de detección también puede parecer ausencia.
- ¿Cómo calculas el acierto? Distingue detección, nombre correcto e inventario.
  Incluye herramientas omitidas y falsas detecciones, no solo las etiquetadas que encontró.
- ¿Qué no has demostrado? Generalización a cualquier ejemplar, oclusiones,
  solapamientos o aperturas diferentes. Las pruebas nuevas determinan el alcance real.

## Revisión crítica del trabajo asistido por LLM

El uso de LLM para texto, figuras y tablas es obligatorio según el enunciado;
la revisión humana también. Comprueba fórmulas, unidades, umbrales, nombres de
archivos, diagramas y afirmaciones contra el programa y las mediciones. No
conviertas sugerencias en resultados. Conserva ejemplos de revisión/corrección
si te ayudan a explicar cómo verificaste el material.
