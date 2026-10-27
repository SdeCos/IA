# Reto 07: herramientas

Esta es la guía detallada. Para empezar utiliza el [README principal](../README.md).
Todos los comandos de esta guía se ejecutan desde `reto007/`, la carpeta que
contiene los scripts, no desde `docs/`.

## Cámara con reconocimiento en directo

Ejecuta `./iniciar_directo.command --camara 1`. Abre la cámara con el flujo del
calibrador y añade nombres automáticos, pistas y recuento por fotograma.
Con `--inventario ejemplos/inventario.json` compara cantidades esperadas.
G guarda fotos, R graba vídeo limpio, P guarda ajustes y Q sale. E exporta también
`predicciones.csv`, `predicciones.json` (incluye reglas e inventario) y
`reconocimiento.png`; las etiquetas reales siguen sin confirmar.
`directo.py --ultima` permite probar la misma vista sin cámara sobre una foto.

Para usar tu grabación como si fuera la cámara, ejecuta
`./iniciar_directo.command --ultimo-video` (o `--video RUTA`). Espacio pausa o
continúa, R vuelve al inicio y Q sale. Al terminar se conserva la última imagen
en pausa. G/E guardan fotogramas con la procedencia del vídeo, sin convertirlos
en nuevas escenas independientes. P guarda un perfil del clip compatible con
la web; no modifica los ajustes originales de adquisición.

Programa de visión clásica en Python, OpenCV y NumPy. Detecta objetos, mide sus
contornos y predice el nombre de las herramientas mediante reglas geométricas
escritas a mano. Permite grabar y reconocer vídeos sin conectar después la
cámara, comparar predicciones con etiquetas manuales y revisar el inventario.
Las reglas y sus umbrales se explican en [REGLAS.md](REGLAS.md). No se entrena
ningún clasificador ni se utilizan redes neuronales. Falta evaluar el sistema
con escenas independientes de las utilizadas durante el desarrollo.

## Interfaz web local

Abre **`iniciar_web.command` con doble clic** o ejecuta desde esta carpeta:

```bash
./iniciar_web.command
```

Se abrirá `http://127.0.0.1:8501` en el navegador. Mantén la terminal abierta;
para detener la web pulsa **Ctrl+C** en ella. Solo escucha conexiones del propio
Mac. Una vez instaladas las dependencias, el trabajo con fotos y vídeos es local y no
requiere Internet. Si se indica que el puerto está ocupado, comprueba si ya
tienes esta web abierta antes de volver a iniciarla.

El entorno `.venv-web` ya está preparado en este Mac. Para instalarlo de nuevo
o preparar otro equipo con Python 3.13:

```bash
./configurar_web.sh
```

Este script instala las versiones de `requirements-web.txt` en un entorno
separado. El Python y el entorno `venv` que usabas para la cámara se mantienen.
`iniciar_web.command` usa explícitamente `.venv-web/bin/python`: no hace falta
activar el entorno y no depende de que el Python global tenga Streamlit.

### Flujo de etiquetado

1. En **Capturas guardadas**, elige una foto; **Otra foto** permite abrir PNG/JPG.
2. Compara **Foto y detecciones** con **Máscara de objetos**. Los controles
   laterales admiten números escritos y botones −/+. Pulsa **Aplicar ajustes**.
3. Elige **Objeto para revisar**: su silueta aparece resaltada en amarillo.
4. Selecciona la herramienta real y pulsa **Confirmar y siguiente**. El conjunto
   de llaves Allen cuenta como una unidad. **Dejar pendiente** conserva una
   propuesta sin darla por revisada.
5. Pulsa **Guardar sesión y CSV**. También puedes guardar un borrador incompleto.
6. Para continuar después, abre **Sesiones guardadas** y selecciona la versión
   que guardaste. Recuperará su foto, configuración y estado de cada etiqueta.

Si falta una herramienta en el desplegable, abre **Añadir herramienta** debajo
del formulario del objeto, escribe su nombre y pulsa **Añadir y seleccionar**.
Quedará seleccionada para ese objeto; pulsa **Confirmar y siguiente** para
validar la etiqueta y **Guardar sesión y CSV** para guardar el trabajo.
El nombre se conserva en `herramientas.json` para las siguientes fotos y sesiones.
Los espacios sobrantes y las diferencias de mayúsculas no crean duplicados.
Las nuevas clases también aparecen en **Análisis** cuando tienen etiquetas
confirmadas. Las sesiones guardadas conservan sus nombres aunque se trasladen
a otro equipo sin ese catálogo.

Añadir un nombre crea una etiqueta de referencia, **no una regla nueva** de
reconocimiento. Para reconocer otra clase hay que estudiar sus medidas y
escribir y justificar sus condiciones. El prototipo tiene reglas para nueve
clases; el enunciado pide entre cinco y ocho tipos. Antes de la entrega hay que
decidir cuáles se incluyen o consultarlo con el docente; no se borran clases ni
etiquetas existentes para resolver esa decisión.

Si una web que ya estaba abierta muestra «Nombre no reconocido» al guardar una
herramienta nueva, vuelve a pulsar **Guardar sesión y CSV** en la misma pestaña.
La app actualiza la validación antigua sin borrar las etiquetas pendientes;
no hace falta reiniciar el servidor ni recargar la página para este cambio.

**Para fotos con mesa u otros elementos alrededor**, deja activado **Limitar al
tapete**. El programa delimita la mayor región verde y excluye su exterior. El
control **Margen interior del tapete · px** deja 2 píxeles de separación por
defecto, medidos en la imagen procesada. En **Zona de análisis del tapete**
puedes comprobar la máscara de esa región: blanco indica la zona analizada.

Las herramientas deben estar completamente dentro del tapete y separadas de
su borde. Las detecciones que llegan al límite de la zona útil se descartan
porque podrían estar recortadas; la web avisa cuando su área supera el mínimo.
Si no puede delimitar una región verde suficiente, muestra un aviso y no
detecta objetos. Revisa los ajustes HSV y el encuadre. Desactivar **Limitar al
tapete** permite analizar de nuevo toda la imagen, incluido lo que quede fuera.

Las etiquetas antiguas de la foto actual se cargan como propuestas. Hay que
revisarlas una vez porque esos archivos no incluían una firma de la detección.
Las sesiones nuevas sí vinculan las etiquetas a los píxeles de la foto, los
parámetros, la máscara y los contornos. Una coincidencia exacta conserva las
confirmaciones; cambiar la segmentación o los ajustes marca los nombres para
revisión, aunque el número de objetos no cambie. Los IDs identifican posiciones
en una detección, no herramientas persistentes entre fotografías.

Los JSON anteriores que no contienen los nuevos ajustes usan **Limitar al
tapete activado** y **margen de 2 px**. El cambio de procesamiento invalida las
confirmaciones de sesiones antiguas: sus nombres pasan a revisión. Los
paquetes anteriores se conservan; al guardar se crea una versión nueva.

Cada guardado crea una carpeta nueva `resultados/sesion_.../` con:

- Los archivos habituales del detector: imagen numerada, máscaras de objetos
  y tapete, CSV, perfiles de anchura, configuración, etiquetas confirmadas y resumen.
- `imagen_origen.png`: copia limpia y completa de la fuente para reproducir el zoom.
- `anotaciones.json`: propuestas, confirmaciones y firmas que usa la web al reabrir.

**El CSV y `etiquetas.json` solo llevan nombres confirmados.** Los nombres
pendientes quedan vacíos en el CSV y se conservan en `anotaciones.json`; la tabla
de la web muestra ambas categorías indicando su estado. El ZIP descargable
contiene la última versión guardada, no los cambios posteriores sin guardar.
Los archivos originales y la configuración global de la cámara no se modifican.

Cambiar de foto conserva el trabajo durante la sesión del navegador. **Guarda
antes de recargar la página, cerrar la pestaña o parar el servidor.** Al abrir
una captura se usan sus ajustes asociados; para retomar exactamente una sesión
exportada, selecciónala en **Sesiones guardadas**.

Para reproducir una sesión con el detector, indica su copia de la fuente y sus
ajustes: `--imagen RUTA_SESION/imagen_origen.png --config RUTA_SESION/configuracion.json`.
Añade `--etiquetas RUTA_SESION/etiquetas.json` para incluir los nombres confirmados.

### Comparar herramientas en «Análisis»

Si la web estaba abierta durante esta actualización, guarda tu trabajo,
detén su terminal con Ctrl+C y vuelve a abrir `iniciar_web.command` para cargar
todos los módulos nuevos. Recargar solo el navegador puede conservar el
procesamiento anterior en el servidor.

La pestaña **Análisis** reúne las medidas de las sesiones guardadas y las
etiquetas confirmadas de la foto actual. Sirve para buscar características
que permitan justificar y revisar las reglas actuales. Los nombres siguen siendo
los que has confirmado: los gráficos no son predicciones automáticas. Una
firma válida garantiza que la etiqueta corresponde a esa detección, pero no
comprueba que hayas elegido el nombre correcto. Si una foto está girada, los
IDs de izquierda a derecha pueden corresponder a herramientas distintas.

1. Revisa la máscara y confirma los nombres en **Calibración y etiquetas**.
   Guarda la sesión para conservarla después de cerrar el navegador.
2. Abre **Análisis** y comprueba qué fotografías y etiquetas entran en la
   comparación. Las etiquetas pendientes o cuya detección ya no coincide se
   excluyen; **Qué datos se han incluido** muestra los motivos. Puedes desmarcar
   **Incluir etiquetas confirmadas de la foto abierta** para analizar solo lo
   guardado. **Revisar visualmente las etiquetas usadas** muestra cada objeto
   recortado junto a su nombre confirmado.
3. Elige **Herramientas a comparar**, **Captura de referencia** y las medidas
   de cada eje. Pasa el cursor sobre un punto para ver su foto y valores.
   Para calibre y martillo, observa especialmente el perfil de anchura.
4. Consulta **Rangos observados** y pulsa **Descargar comparación · CSV** para
   conservar las filas seleccionadas con sus medidas, perfiles y procedencia.
   No elijas un umbral definitivo a partir de una sola foto.

El análisis vuelve a obtener los descriptores desde la foto y la configuración
guardadas; no mezcla columnas de CSV generados con distintas definiciones.
Añadir descriptores no cambia la identidad de los contornos: se registra por
separado la versión de las características y la del procesamiento. Si los
píxeles, los ajustes y la detección siguen coincidiendo, se conservan las
confirmaciones.

Guardar varias veces una foto no aporta muestras nuevas: para cada huella de
imagen se utiliza la versión más reciente, aunque contenga etiquetas
pendientes. Si está incluida, la revisión visible de la foto actual tiene prioridad sobre los
guardados de sus mismos píxeles; no se recuperan confirmaciones anteriores
para sustituir lo que acabas de dejar pendiente. Los archivos `original_...` y
`escena_...` con el mismo sello temporal se agrupan como variantes de una
captura. Esta agrupación evita presentarlos como capturas independientes, pero
no demuestra que capturas con horas distintas correspondan a montajes
distintos. Las fotos disponibles proceden de la misma disposición de
herramientas y siguen siendo datos de desarrollo.

**Compara primero proporciones**, como relación de aspecto, solidez y los
descriptores normalizados. Área, perímetro y longitudes en píxeles cambian con
el zoom y el encuadre. Incluso las proporciones pueden variar por perspectiva,
resolución y errores de segmentación; no sustituyen las pruebas con nuevas
posiciones físicas.

## Grabar en casa y analizar vídeos en clase

El vídeo permite reunir nuevas posiciones y comprobar cómo cambia la
segmentación con el movimiento. **Reconoce automáticamente las herramientas
en cada fotograma mediante las reglas actuales**, muestra la explicación y
cuenta las clases visibles. Los números de seguimiento ayudan a relacionar
detecciones consecutivas; no son etiquetas de clase ni una garantía de
identidad. Los nombres son predicciones provisionales, no confirmaciones.

### Grabar desde el calibrador

En casa, conecta el iPhone como ya lo utilizas con Cámara de Continuidad y abre:

```bash
python calibrador.py --camara 1
```

Con una ventana del calibrador enfocada y sin editar un campo numérico,
pulsa **R** para empezar. Aparece un indicador **REC**. Pulsa **R** de nuevo
para detener y guardar; **Q** también finaliza la grabación antes de salir.
La terminal indica la ruta guardada. En modo fotografía, R solo muestra un
aviso y no intenta abrir la cámara.

Cada grabación crea `videos/grabacion_<fecha>_<id>/` con:

- `original.avi`: vídeo MJPEG a 15 fps, sin audio, a la resolución original
  recibida de la cámara. No incluye contornos, texto ni el recorte del zoom.
- `configuracion.json`: ajustes al **iniciar** la grabación. Si cambias un
  ajuste mientras grabas, cambia la vista del calibrador, pero no la imagen
  original guardada ni esa configuración inicial.
- `grabacion.json`: resolución, duración, muestras recibidas, fotogramas
  repetidos, estado de finalización y avisos.

Los 15 fps son el ritmo del archivo. Cuando la cámara o el procesamiento
entregan imágenes más despacio, se repite la última disponible para conservar
la duración; los duplicados quedan registrados y no aportan nuevas muestras.
Un cierre interrumpido conserva el vídeo si se puede validar. Si falla su
validación, la carpeta incompleta se conserva para revisión y se informa en
la terminal. Comprueba que el clip se abre antes de salir de casa.

### Revisar el clip sin cámara

Abre la web y cambia el modo de trabajo a **Vídeos**. En **Vídeos guardados**
selecciona la grabación. **Otro vídeo → Importar vídeo local** copia un archivo
al proyecto para revisarlo; para un archivo grande puedes escribir **Ruta del
vídeo** y pulsar **Abrir vídeo**, usando directamente ese archivo en el Mac.
El soporte del formato depende de
los códecs disponibles: las grabaciones AVI/MJPEG del calibrador están pensadas
para este flujo. Si un vídeo externo no se puede decodificar o no permite
confirmar el índice del fotograma, conviértelo a AVI/MJPEG o MP4/H.264.

Pulsa **Reproducir análisis** o **Pausar**; durante la reproducción se muestra
una barra de progreso. Para elegir una posición, pausa y escribe un índice en
**Fotograma · empieza en 0** o recorre **Línea de tiempo · fotograma**.
**Anterior/Siguiente** detiene la reproducción y retrocede o avanza un fotograma.
Los índices empiezan en **0**. Compara imagen y máscara y
ajusta los mismos parámetros numéricos que en fotografías con **Aplicar
ajustes**. La reproducción analítica
está limitada a 10 fotogramas por segundo y puede ser más lenta que la
grabación: su propósito es inspeccionar el resultado del procesamiento.

La imagen muestra el nombre predicho junto a **P1, P2…**. Debajo aparecen
**Herramientas en este fotograma**, sus cantidades actuales y la regla y
explicación de cada decisión. **Desconocido** indica que ninguna regla permite
identificar inequívocamente esa silueta. El conteo no suma pistas que ya no
están presentes. Una mano, un cruce o una segmentación incompleta pueden
cambiar tanto el nombre como la pista.

El vídeo utilizado para definir las reglas se señala como **desarrollo**.
Abrir otro vídeo permite estudiar nuevas escenas, pero no calcula por sí solo
una tasa de aciertos: para eso hace falta una referencia manual separada.

Pulsa **Guardar ajustes del vídeo** antes de cerrar para continuar otro día.
Los ajustes se guardan en `videos/ajustes/<huella_SHA256>.json`, asociados al
contenido del clip. Tienen prioridad sobre los ajustes de adquisición cuando
vuelves a abrir ese mismo vídeo, aunque cambie de nombre. No modifican la
configuración global de la cámara ni el paquete original de grabación.

Para recoger medidas de una pausa, pulsa **Guardar fotograma como foto**. Se guarda en `capturas/`
como PNG completo y limpio, acompañado de los ajustes en un JSON y de un
archivo `.origen.json` con el vídeo, su huella, el índice y el tiempo nominal.
Pulsa **Abrir foto guardada para etiquetar**, confirma las etiquetas en
**Fotografías** y guarda la sesión habitual.
El zoom se aplica al procesar esa copia, una sola vez. La predicción y la pista
del vídeo no crean ni confirman etiquetas manuales de la foto extraída.

Con el vídeo pausado, abre **Exportar medidas de un intervalo**, indica el
principio, el final y el paso y pulsa **Exportar intervalo a CSV**. Se crea una
carpeta nueva en `resultados/videos/` con:

- `caracteristicas.csv`: una fila por objeto y fotograma seleccionado, con
  medidas, ID local, ID de pista y estado de la asociación temporal; también
  clase predicha, estado de clasificación, regla, explicación, ruta de decisión
  y versión del clasificador.
- `fotogramas.csv`: una fila por fotograma seleccionado, también cuando no hay
  objetos; recoge el recuento por clase en JSON, la detección del tapete y los avisos.
- `configuracion.json`: parámetros utilizados para todo el intervalo.
- `resumen.json`: vídeo y huella SHA-256, intervalo, paso, versiones y límites
  del seguimiento, copia completa de las reglas y procedencia de desarrollo.
  Indica que las etiquetas no están confirmadas y que esta exportación no es
  una evaluación independiente. El vídeo original se conserva en su ubicación.

**Descargar análisis del vídeo · ZIP** reúne esos archivos. El ZIP no incluye
el vídeo original: conserva también el clip para reproducir el análisis.

Se procesa desde el principio hasta el final del intervalo, ambos incluidos.
Se exportan el inicio, el inicio más el paso y las siguientes muestras que
quepan en ese intervalo. Un paso mayor que 1 reduce las filas exportadas, pero
los fotogramas intermedios también se procesan para mantener la continuidad
de las pistas. Los tiempos son
`índice / fps`; con vídeos externos de velocidad variable son aproximados.

**Los IDs de pista se reinician al saltar o retroceder y al cambiar el
contexto.** Una exportación empieza sus propias pistas en el inicio del
intervalo. No compares sus números con los de otra exportación ni los sumes
como si fueran herramientas diferentes. La misma herramienta puede recibir
otro número tras una pérdida o una asociación dudosa.

### Preparar dos clips útiles

Mantén la cámara fija, cenital, con toda la zona útil del tapete visible. Usa
el mismo encuadre durante cada clip y procura que las herramientas estén
separadas entre sí y del borde. Con 30–60 segundos por clip puedes recoger
varias posiciones sin generar una grabación difícil de revisar.

1. **Clip de desarrollo:** empieza unos segundos con el tapete vacío y añade
   las herramientas. Cambia sus posiciones y gira cada una. Haz movimientos
   lentos y deja pausas de 2–3 segundos con las manos fuera del tapete: esos
   fotogramas permiten medir y etiquetar siluetas completas. Incluye el calibre
   y el martillo en varias orientaciones para comparar sus perfiles.
2. **Clip reservado para evaluación:** usa otras distribuciones, rotaciones,
   ausencias y cantidades; incluye repeticiones si dispones de otro ejemplar
   de una clase. Anota el inventario real de cada pausa y conserva el clip
   separado. No lo uses para elegir parámetros ni umbrales del árbol.

Las manos, los objetos en contacto, los solapamientos y el desenfoque de
movimiento pueden unir o romper siluetas. El programa no promete resolver
esos casos. El enunciado pide orientación arbitraria e inventario en escenas
nuevas; no exige reconocer continuamente una herramienta mientras una mano
la tapa. Las pausas sin manos son una forma práctica de obtener esas escenas.

Los fotogramas vecinos de un vídeo están muy relacionados. No repartas
fotogramas del mismo clip entre desarrollo y prueba ni presentes cientos de
fotogramas casi idénticos como cientos de escenas independientes. Selecciona
poses diferentes y conserva la procedencia del vídeo y el número de fotograma.
La pestaña **Análisis** agrupa los fotogramas extraídos de un mismo clip por
su huella SHA-256 como una sola captura de origen y avisa de esa dependencia.
Cada fotograma conserva sus propias etiquetas confirmadas; no las hereda de
otros fotogramas ni de los IDs de seguimiento.

### Siguiente paso: comprobar escenas nuevas

Las reglas ya están implementadas. Conserva un segundo clip con distribuciones
y orientaciones diferentes, sin utilizarlo para cambiar los umbrales. Extrae
y etiqueta pausas representativas, guarda sus sesiones y evalúalas desde
**Fotografías → Reconocimiento automático**. Revisa por separado las omisiones
de la máscara: una herramienta no detectada no tiene fila que el clasificador
pueda evaluar. Si usas los fallos del nuevo clip para modificar las reglas,
pasa a ser desarrollo y necesitarás otro clip para la evaluación final.

## Reconocimiento automático en fotografías

1. En **Fotografías**, abre una foto o sesión guardada y revisa su máscara.
2. Abre **Reconocimiento automático**. El sistema calcula las predicciones a
   partir de las medidas, sin consultar los nombres que hayas etiquetado.
   Revisa las reglas y explicaciones; una abstención aparece como
   **Desconocido**, con estado desconocido o ambiguo.
3. Si quieres comprobar ausencias y repeticiones, configura el inventario
   esperado opcional en **Comparar con un inventario esperado → Definir
   cantidades esperadas**. Selecciona todas las herramientas esperadas e indica
   las cantidades. Sin esa opción se muestra únicamente lo observado: no se
   supone que deba haber una unidad de cada clase.
4. Pulsa **Descargar reconocimiento · ZIP** para conservar la foto limpia, la
   máscara, la imagen anotada, predicciones CSV/JSON, configuración y reglas.
   Esto no modifica ni confirma tus etiquetas de referencia. **Por qué se ha
   elegido cada nombre** muestra las condiciones examinadas para cada objeto.
5. Pulsa **Evaluar sesiones guardadas** para comparar predicciones y nombres
   confirmados. En **Muestras para comprobar** elige **Desarrollo** o **Grupos
   nuevos**. Usa **Descargar comparación · CSV** y **Descargar evaluación ·
   JSON** para conservar los resultados. Vuelve a pulsar Evaluar cuando guardes
   nuevas etiquetas: se muestra el resultado de la última pulsación.

La evaluación solo utiliza referencias confirmadas y verificables. Omite
etiquetas pendientes, asociaciones desactualizadas y duplicados de los mismos
píxeles; mantiene juntos los fotogramas de un mismo vídeo. Un grupo nuevo
señala una procedencia distinta de las registradas como desarrollo, pero
también debes comprobar que no usaste esa escena para ajustar el sistema.

**Resultado de desarrollo del 19 de octubre de 2026:** 55 objetos confirmados
de 12 imágenes, agrupadas en cuatro procedencias, con 55 nombres acertados.
Todas esas procedencias se usaron para definir las reglas: **hay cero muestras
de evaluación independiente**. Este resultado no demuestra que el sistema
generalice a herramientas nuevas, otras aperturas, perspectiva u oclusiones.
La evaluación de clasificación tampoco mide objetos omitidos por la
segmentación ni sustituye una referencia completa del inventario de la escena.

## Trabajar en clase sin cámara

Desde esta carpeta:

```bash
python detector.py --ultima
```

Produce una carpeta nueva en `resultados/` sin abrir cámaras ni ventanas:

- `objetos.png`: objetos numerados y tabla de medidas.
- `caracteristicas.csv`: una fila por objeto; se puede abrir en una hoja de cálculo.
- `perfiles.json`: 40 posiciones y anchuras normalizadas por objeto, con la
  versión de las características y la convención del sentido del perfil.
- `mascara.png`: segmentación usada.
- `tapete.png`: región de análisis; el exterior queda negro.
- `configuracion.json`: parámetros exactos con los que se obtuvo el resultado.
- `etiquetas.json`: nombres reales para completar manualmente.
- `resumen.json`: procedencia, dimensiones, versión del procesamiento,
  versión de las características, región de análisis y observaciones.

Añade `--mostrar` si quieres que abra las imágenes. También puedes usar
`--imagen RUTA`, `--config RUTA`, `--zoom 1.5` o `--salida CARPETA`.
Una exportación nunca sobrescribe un resultado anterior.

Ya hay un ejemplo etiquetado en `resultados/primera_medicion/` obtenido de
`capturas/escena_20261016_113231_782061.png`. Para repetirlo con otra carpeta nueva:

```bash
python detector.py --imagen capturas/escena_20261016_113231_782061.png --etiquetas etiquetas/escena_20261016_113231_782061.json
```

Los IDs de esta foto son: 1 destornillador, 2 calibre, 3 desbarbador manual,
4 martillo, 5 juego de llaves Allen y 6 nivel. Se asignan por centroide de
izquierda a derecha, **no reconocen clases**. Si cambia la foto o su
segmentación, comprueba los IDs de nuevo antes de reutilizar etiquetas.

## Calibrar

```bash
python calibrador.py --ultima
```

Para cámara, usa `python calibrador.py --camara 1`. En el montaje del usuario
el iPhone está disponible con Photo Booth abierto. El índice puede cambiar
según los dispositivos visibles para macOS.

En el panel: clic en el número, escribir y pulsar **Enter**. **Esc** cancela,
**Tab** pasa al siguiente campo y los botones **−/+** afinan el valor. Los
atajos siguientes actúan cuando no se está editando un número:

| Tecla | Acción |
|---|---|
| P | Guardar los parámetros confirmados. |
| E | Exportar a CSV las medidas del fotograma actual y su imagen numerada. |
| G | Guardar foto original, encuadre limpio y sus ajustes JSON. |
| R | Iniciar o detener una grabación de vídeo limpio de la cámara. |
| B | Mostrar u ocultar la máscara anterior a la morfología. |
| Q | Finalizar la grabación activa, salir y liberar la cámara. |

**Destino de P:** en cámara, `configuracion.json`; con una foto, un JSON del
mismo nombre junto a ella; con `--config`, el archivo indicado. Los valores que
se estén escribiendo no se aplican hasta confirmar con Enter.

**Orden de carga:** `--config` explícito, JSON asociado a la foto, configuración
general y, si ésta no existe, valores iniciales. `--zoom` prevalece sobre el
zoom guardado. Los archivos `escena_*.png` ya llevan el recorte: cuando no
tienen JSON asociado se abren a 1×. Al pulsar G se guarda zoom 100 en el JSON
de la escena y el zoom usado en el JSON del original, para reproducir ambos
sin duplicar el recorte. Un `--config` explícito aplica también su zoom:
comprueba que corresponde a la imagen que abres.

**E en cámara:** guarda el fotograma original y su encuadre para que los
resultados tengan una imagen fuente reproducible. E con una foto usa el
archivo fuente existente. Las exportaciones de E quedan sin etiquetas;
rellena los nombres reales después.

## Completar y comparar mediciones

1. Abre `objetos.png` y relaciona cada ID con la herramienta real.
2. Escribe los nombres en `etiquetas.json`, por ejemplo `"3": "Desbarbador manual"`.
3. Vuelve a ejecutar el detector con la misma imagen, el JSON de configuración
   exportado y `--etiquetas` apuntando al archivo que acabas de completar.
4. Compara área, relación de aspecto, solidez y circularidad entre clases.

El CSV tiene codificación UTF-8 con BOM, separador `;` y punto decimal.
Si una hoja de cálculo no interpreta las cifras como números, impórtalo
indicando separador punto y coma y punto decimal. Las unidades aparecen en
los encabezados. Área y perímetro se calculan sobre el contorno exterior
(sin restar huecos), en la imagen procesada a 800 píxeles de ancho; no son mm.
La delimitación del tapete no cambia esa escala ni corrige la perspectiva.
Por ello, una herramienta en una foto amplia y en un recorte cercano puede
tener áreas distintas aunque ambas segmentaciones sean correctas.

Las nuevas columnas `extension`, `contraste_extremos`, `fraccion_ancha`,
`asimetria_longitudinal` y `ancho_central` son proporciones entre 0 y 1. El
perfil sitúa primero el extremo de mayor anchura media y normaliza la longitud
por el lado largo y la anchura por el lado corto de la caja mínima. Mide la
extensión exterior de cada sección, incluidos los espacios entre ramas, y no
resta huecos internos. Las definiciones completas están en el apartado 5 de
`MEMORIA.md`.

Calibre y martillo tienen medidas globales cercanas; las reglas actuales usan
también el ancho central y el contraste entre extremos. **Análisis** permite
inspeccionar esa separación con referencias manuales. Las tres capturas
iniciales y los fotogramas del vídeo actual se utilizaron durante el desarrollo;
la evaluación independiente requiere otras escenas.

## Archivos del programa

- `calibrador.py`: cámara o foto, ajustes y guardado interactivo.
- `grabacion.py`: grabación limpia de la cámara con configuración y tiempos.
- `detector.py`: detección y exportación de fotos sin interfaz obligatoria.
- `vision.py`: único pipeline compartido, extracción y dibujo.
- `geometria.py`: descriptores de forma y perfil de anchura normalizado.
- `clasificacion.py`: reglas manuales, abstención y explicación de cada predicción.
- `evaluacion.py`: comparación con referencias y recuento del inventario.
- `panel_clasificacion.py`: reconocimiento en fotos, inventario esperado y
  evaluación con referencias confirmadas.
- `REGLAS.md`: condiciones, umbrales, justificación y límites del clasificador.
- `configuracion.py`: validación, carga y guardado de parámetros.
- `controles.py`: panel numérico.
- `app_web.py`: interfaz local Streamlit para fotos, sesiones y vídeos.
- `panel_video.py`: controles de reproducción, parámetros y exportación de vídeo.
- `video.py`: lectura de clips, extracción de fotogramas y exportación de intervalos.
- `seguimiento.py`: asociación temporal de detecciones por geometría.
- `panel_analisis.py`: filtros, tablas, gráficos y descarga de la comparación.
- `etiquetado.py`: asociación verificable de etiquetas y exportación de sesiones.
- `analisis.py`: mediciones confirmadas, procedencia y comparación sin duplicar
  los guardados de una misma imagen.
- `MEMORIA.md`: borrador con pipeline, fórmulas, reglas, resultados de desarrollo
  y pruebas independientes pendientes.

El calibrador y el detector mantienen sus dependencias: `opencv-python` y
`numpy`. La web añade Streamlit y sus dependencias en `.venv-web`.

## Comprobaciones

Desde esta carpeta:

```bash
.venv-web/bin/python -m unittest discover -s tests -t .
```

Las comprobaciones automáticas no activan la cámara. La validación final con
otras posiciones, orientaciones y combinaciones de herramientas debe hacerse
con nuevas escenas físicas, reservadas de los ajustes de desarrollo.

Para comprobar solo el flujo original con tu Python habitual:
`python -m unittest tests.test_flujo`.
