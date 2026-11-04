# Cómo comprobar el método clásico

Este sistema usa segmentación por color, características geométricas explícitas
y reglas escritas a mano. El método no entrena clasificadores y no usa redes
neuronales. Actualmente tampoco calcula esqueletos.

## Recorrido manual en la web

1. Abre una foto de una herramienta sola, completa y separada del borde.
2. Compara la foto con su máscara. La silueta debe corresponder al objeto, sin
   manchas de fondo ni uniones con otros objetos.
3. En **Reconocimiento automático**, abre **Por qué se ha elegido cada nombre**
   y selecciona **Decisión del objeto**.
4. Despliega la ruta de decisión. Para cada regla aparecen ocho medidas, los
   límites y el resultado: cumple, frontera o no cumple. Compara los números
   con **Entrega → árbol de decisión** o descarga **Reglas y umbrales · JSON**.
5. La identificación exige una sola regla compatible y cumplir todas sus
   condiciones fuera de las bandas de abstención. Cerca de límites o con reglas
   solapadas se devuelve «Desconocido». No es una probabilidad aprendida.

Puedes comprobar a mano un cociente: `relacion_aspecto = largo / corto` de la
caja girada que envuelve el objeto. La regla del alicate pide AR entre 2 y 4,
pero ese intervalo por sí solo no basta: debe cumplir también las otras siete
condiciones y quedar fuera de sus bandas de abstención.

## Qué revisar en el código

| Paso | Archivo y funciones |
|---|---|
| Segmentación | [`vision.py`](../src/herramientas/vision/vision.py): `procesar_imagen`, conversión a HSV, `inRange`, máscara del tapete y morfología. |
| Contorno y medidas | Mismo archivo: `findContours`, área, perímetro, caja girada, circularidad y solidez. |
| Perfil de anchura | [`geometria.py`](../src/herramientas/vision/geometria.py): `caracteristicas_forma`, 40 secciones normalizadas. |
| Clasificación | [`clasificacion.py`](../src/herramientas/vision/clasificacion.py): `_REGLAS`, `_comprobar_intervalo` y `clasificar_objeto`. |
| Referencias humanas | [`etiquetado.py`](../src/herramientas/datos/etiquetado.py): revisión y guardado para evaluación. |

`clasificar_objeto` lee ocho cocientes y comprueba intervalos fijos. No abre
fotos de ejemplo, no lee nombres de archivo y no consulta las etiquetas manuales.
Las etiquetas permiten estudiar medidas y evaluar los aciertos; al guardar
etiquetas nuevas no se modifican `_REGLAS` ni sus límites.

Desde la raíz puedes ejecutar:

```bash
./ejecutar.sh pruebas tests.test_clasificacion
./ejecutar.sh pruebas tests.test_biblioteca
```

La primera batería incluye una prueba que cambia etiquetas, nombres de fuente,
IDs y coordenadas manteniendo los ocho rasgos: la decisión debe ser idéntica.
La segunda comprueba que un título manual deliberadamente incorrecto no modifica
los píxeles, la firma ni la predicción. También comprueba los filtros y guardados.
Son comprobaciones complementarias a leer el código; que una app funcione sin
internet o devuelva explicaciones, por sí solo, no demuestra que sea clásica.

## Capturas de desarrollo y prueba

Puedes fotografiar una sola herramienta por imagen. Para estudiar los alicates,
varía apertura y orientación; para las Allen, gira el conjunto sin cambiar su
montaje. Usa iluminación normal y retira la mano antes de guardar. Etiqueta
solo detecciones que correspondan a una herramienta completa: no asignes el
nombre de una herramienta a una silueta que une varias.

Reserva otras adquisiciones para comprobar los cambios sin usarlas al ajustar
las reglas. Para la demostración final añade escenas con varias herramientas,
ausencias y repeticiones: las fotos individuales no validan por sí solas el
inventario. Los fotogramas del mismo vídeo comparten grupo de adquisición.

## Esqueletos y directo web

Un esqueleto reduce la silueta a líneas finas para estudiar extremos y
bifurcaciones. Sería una característica clásica adicional, no un requisito
implementado ni un sustituto de obtener una buena máscara. Podría combinarse
con las medidas actuales si ayuda a distinguir herramientas abiertas.

La vista web **En directo** reutiliza el mismo procesamiento de la cámara y
las mismas reglas. Permite iniciar/detener, grabar y guardar fotos, o utilizar un
vídeo como fuente. La captura se cierra al salir de la vista; un tiempo límite
de inactividad cubre el cierre del navegador. Usa la cámara del Mac donde se
ejecuta Python; no convierte el navegador de otro dispositivo en cámara remota.
La conexión física del iPhone y la latencia deben comprobarse en el montaje real.
