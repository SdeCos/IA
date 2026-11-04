# Clasificador geométrico manual: reglas-manuales-v4

Este clasificador asigna nombres mediante **reglas escritas a mano sobre medidas
explícitas de la silueta**. No entrena un árbol, no usa redes neuronales, vecinos,
prototipos, clasificación por color ni búsqueda automática de umbrales.
La entrada es una detección ya segmentada; la etiqueta manual es únicamente la
referencia para estudiar y evaluar las reglas. No se consulta al predecir.

## Qué decisiones toma

1. Comprueba que los ocho descriptores son finitos, están en su dominio físico
   y corresponden a `geometria-v1`. Si faltan, se abstiene. Comprueba también
   que la extensión no supere la solidez salvo una tolerancia de 0,02.
2. Evalúa las quince reglas de la tabla. Cada fila es una conjunción: **deben
   cumplirse sus ocho intervalos**. Las familias corresponden a cuerpo compacto
   y convexo (metro/cúter/nivel), mango y punta muy alargados
   (destornillador/desbarbador), cabeza y cuerpo estrecho (calibre/martillo) y
   cuerpo ramificado (Allen/alicate). No hay prioridad que permita a una regla
   ocultar la coincidencia de otra.
3. Solo asigna nombre cuando hay una única **clase** compatible y al menos
   una de sus reglas queda fuera de todas las bandas de abstención. Varias
   vistas de la misma clase pueden coincidir; se conserva toda la traza.
4. Si solo hay fronteras o varias clases compatibles devuelve
   `Desconocido`, estado `ambigua`. Si ninguna es compatible, devuelve
   `Desconocido`, estado `desconocida`.

La ruta de decisión guarda las condiciones, valores observados y resultado de
cada regla. `snapshot_reglas()` permite exportar su especificación completa
junto con los resultados. No existe una probabilidad o porcentaje de confianza.

## Descriptores y umbrales

- **AR:** lado largo / lado corto de la caja mínima rotada.
- **S:** área / área de la envolvente convexa (solidez).
- **C:** 4π × área / perímetro² (circularidad).
- **E:** área / área de la caja mínima (extensión).
- **K:** diferencia relativa entre las anchuras medias del primer y último
  20 % del perfil (contraste de extremos).
- **F:** fracción del perfil que ocupa al menos la mitad del lado corto.
- **A:** diferencia absoluta media entre el perfil y su inverso longitudinal.
- **W:** anchura media normalizada del 40 al 60 % del perfil (centro).

Las medidas del perfil se obtienen de 40 secciones del contorno exterior;
incluyen el espacio entre ramas y no descuentan los huecos interiores. Sus
definiciones completas están en `geometria.py`.

| Regla y nombre | AR | S | C | E | K | F | A | W |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1 Metro | 1–2,2 | 0,9–1 | 0,65–0,9 | 0,75–1 | 0–0,25 | 0,85–1 | 0–0,2 | 0,8–1 |
| R2 Cuter | 2–3,8 | 0,85–1 | 0,4–0,65 | 0,65–0,88 | 0–0,25 | 0,8–1 | 0–0,2 | 0,8–1 |
| R3 Nivel | 4–6,5 | 0,9–1 | 0,25–0,5 | 0,85–1 | 0–0,15 | 0,9–1 | 0–0,12 | 0,8–1 |
| R4 Desbarbador manual | 8,5–14 | 0,7–0,95 | 0,1–0,25 | 0,55–0,85 | 0,55–0,95 | 0,65–0,9 | 0,15–0,5 | 0,7–1 |
| R5 Destornillador | 5,5–9 | 0,5–0,78 | 0,08–0,2 | 0,25–0,5 | 0,7–1 | 0,3–0,55 | 0,4–0,75 | 0,12–0,45 |
| R6 Calibre | 2,5–6 | 0,28–0,65 | 0,04–0,25 | 0,18–0,43 | 0,55–0,85 | 0,06–0,3 | 0,12–0,35 | 0,12–0,55 |
| R7 Martillo | 2,5–4,5 | 0,35–0,65 | 0,1–0,27 | 0,25–0,48 | 0,25–0,55 | 0,1–0,32 | 0,06–0,25 | 0,28–0,45 |
| R8 Juego de llaves Allen | 2,3–4,3 | 0,6–0,82 | 0,07–0,22 | 0,4–0,65 | 0,2–0,55 | 0,65–0,9 | 0,07–0,28 | 0,55–0,85 |
| R9 Alicate | 1–4 | 0,28–0,78 | 0,08–0,25 | 0,18–0,65 | 0,55–0,85 | 0,5–0,82 | 0,3–0,6 | 0,54–0,95 |
| R10 Martillo | 6,5–12 | 0,6–0,84 | 0,12–0,24 | 0,48–0,8 | 0–0,3 | 0,55–1 | 0,07–0,21 | 0,43–0,75 |
| R11 Nivel | 7–15 | 0,88–1 | 0,14–0,3 | 0,8–0,96 | 0–0,2 | 0,85–1 | 0–0,14 | 0,85–1 |
| R12 Metro | 2,2–10 | 0,25–0,68 | 0,025–0,3 | 0,13–0,45 | 0,65–1 | 0,08–0,48 | 0,17–0,78 | 0–0,14 |
| R13 Metro | 1–2,2 | 0,78–0,91 | 0,45–0,61 | 0,55–0,72 | 0,88–1 | 0,65–0,82 | 0,32–0,57 | 0,85–1 |
| R14 Metro | 2,3–4,6 | 0,8–1 | 0,34–0,6 | 0,65–0,85 | 0,35–0,62 | 0,48–0,82 | 0,24–0,45 | 0,6–1 |
| R15 Metro | 3,8–20 | 0,63–0,9 | 0,04–0,44 | 0,4–0,72 | 0,35–0,68 | 0,07–0,65 | 0,1–0,45 | 0,34–0,84 |

Cada extremo de intervalo tiene una banda de abstención de **±0,15 en AR** y
**±0,02 en los otros cocientes**. No se aplica banda en los límites físicos
0/1 ni en el mínimo físico AR=1. Por ejemplo, para el máximo AR=6,5 del nivel,
6,36–6,64 queda en la banda: no se identifica. Una coincidencia muy lejos de
todos los intervalos es desconocida. Las bandas no son intervalos estadísticos;
son una decisión manual para no dar un nombre cerca de los cortes.

## Justificación geométrica

- **Metro:** el ejemplar es un flexómetro recogido: cuerpo compacto casi
  cuadrado, convexo y de extremos similares. La circularidad superior evita
  tratar un disco perfectamente circular como este ejemplar. R1 describe el cuerpo recogido; R12–R15 añaden vistas con cinta extendida.
- **Cuter:** el ejemplar fotografiado es una herramienta plegada de cuerpo
  convexo, más larga que ancha, con centro ancho y extremos parecidos. La
  extensión es menor que la de un nivel rectangular. Se conserva para compatibilidad, fuera del perfil de entrega. El nombre conserva la
  etiqueta escrita por el usuario. No se ha demostrado que funcione abierta.
- **Nivel:** combina alta extensión y solidez con cuerpo alargado, anchura
  uniforme y simetría longitudinal. R11 describe su vista de canto, más estrecha. Los huecos interiores no son necesarios.
- **Desbarbador:** tiene AR mayor que el destornillador, pero el mango ocupa
  mucha más longitud y el centro es ancho; el extremo fino ocupa una parte
  corta. Por eso no basta con comparar el área en píxeles.
- **Destornillador:** mango y vástago crean gran asimetría; aproximadamente
  media longitud es estrecha, y la caja contiene bastante fondo.
- **Calibre y martillo:** AR y solidez por sí solos son insuficientes. El
  calibre observado tiene centro normalizado 0,208–0,213 y contraste
  0,630–0,691; el martillo, centro 0,307–0,315 y contraste 0,443–0,455. Se
  conserva el contraste alto del calibre para distinguirlo del martillo. En v3
  se amplía su centro admitido al abrir las mordazas; las aperturas no
  observadas todavía pueden salir del dominio.
- **Allen y alicate:** ambos son ramificados y anchos en el centro. El juego
  observado presenta asimetría 0,168–0,193 y contraste 0,353–0,457; el alicate
  de las referencias iniciales, asimetría 0,413–0,416 y contraste
  0,661–0,663. Los intervalos separados codifican esa diferencia.
  En v2 se admiten distintas aperturas del mismo alicate: al separar los
  mangos disminuyen AR, solidez, extensión y anchura central normalizada.
  Se amplían únicamente esos cuatro intervalos; se conservan circularidad,
  contraste, fracción ancha y asimetría. Esto evita exigir la proporción de
  un alicate casi cerrado a su silueta abierta. No garantiza todas las
  aperturas, perspectivas o modelos. El juego de Allen montado cuenta como
  un objeto; separarlo requiere otra definición de clase.

Los rangos son amplios respecto a las medidas observadas y redondeados a mano.
No se han calculado mediante optimización de aciertos. La combinación de
varios rasgos busca rechazar siluetas incompatibles, pero **no garantiza
detectar toda mala segmentación ni rechazar cualquier objeto ajeno**: una
regla rectangular puede parecerse a un nivel y una caja cuadrada a un metro.

## Revisión v4: continuidad de las extensiones del flexómetro

Once capturas adicionales muestran extensiones intermedias y más largas. V3
identificaba una y se abstenía en diez. Solo se revisan R12–R15; no se cambian
la segmentación, los descriptores, las bandas de abstención ni las reglas de
otras herramientas.

- R12 admite cinta estrecha más larga (AR hasta 10). La carcasa ocupa menor
  proporción del perfil al extenderse: bajan fracción ancha, circularidad y
  asimetría. Si la cinta se inclina respecto a su canto, gana anchura visible
  y baja el contraste. Se mantienen centro muy estrecho y baja solidez.
- R13 admite menor asimetría en las extensiones muy cortas (mínimo 0,32).
- R14/R15 cubren la transición entre cinta plana corta y larga: sus intervalos
  se solapan incluso después de descontar las bandas. R14 admite AR hasta 4,6
  y R15 parte de 3,8. Se amplía también la transición de centro, fracción ancha,
  solidez y circularidad para evitar huecos artificiales entre ambas variantes.
- R15 admite las nuevas extensiones largas (AR hasta 20), con menor
  circularidad/extensión y mayor contraste. Sigue exigiendo una transición
  entre carcasa y cinta: un rectángulo uniforme no basta para identificar Metro.

La revisión manual usa 120 referencias confirmadas de 68 imágenes y 56 grupos:
v3 acertaba 110; v4 acierta 120, incluidos 26 flexómetros. Las 109 referencias
anteriores mantienen sus nombres. Las siete clases de entrega representan 102
referencias. **Todo es desarrollo**, no una evaluación independiente ni una
medición de omisiones. No se garantiza cualquier longitud, cinta curva,
oclusiones o siluetas ajenas parecidas. El sistema no mide centímetros.

Además de comprobar los datos guardados, las pruebas interpolan sintéticamente
medidas entre dos extensiones cercanas para verificar que las reglas no dejen
un hueco; esto no simula imágenes ni demuestra continuidad física universal.
Las once medidas nuevas están en `tests/fixtures/referencias_metro_v4.json`,
un archivo exclusivo de pruebas que el reconocedor no consulta.

Tras guardar tu trabajo, reinicia la web y comprueba `reglas-manuales-v4`.
La siguiente tarea es una adquisición nueva reservada con varias herramientas,
retiradas y repeticiones, sin retocar reglas con ese mismo conjunto.

## Histórico v3: aperturas y vistas de canto

El perfil de entrega queda en siete clases: martillo, destornillador, alicate,
calibre, nivel, metro y desbarbador, una unidad esperada de cada una. Cúter y
Allen conservan sus reglas y referencias históricas, pero no se esperan en el
inventario. No se modifican HSV, morfología, región del tapete, resolución ni
la definición de los ocho descriptores.

Cambios manuales justificados por las siluetas y medidas nuevas:

- R1 admite la cara estrecha del flexómetro recogido, hasta AR 2,2.
- R4 baja el mínimo de anchura central de 0,75 a 0,70. Los nuevos desbarbadores
  completos presentan valores entre aproximadamente 0,737 y 0,763, que antes
  caían en la banda de abstención. Se conserva el resto de su regla.
- R6 admite aperturas del calibre: AR hasta 6, solidez desde 0,28,
  circularidad desde 0,04, extensión desde 0,18, fracción ancha desde 0,06
  y centro hasta 0,55. La varilla saliente y las mordazas separadas reducen
  solidez/circularidad y cambian el perfil. Su contraste alto lo distingue
  del martillo; no basta con que sea alargado.
- R10 describe el martillo de canto con baja asimetría y contraste pequeño,
  distinto del desbarbador. No amplía la regla de la vista frontal.
- R11 describe el nivel de canto, más estrecho pero sólido y de ancho uniforme.
- R12/R13 distinguen cinta de canto larga/corta; R14/R15, cinta plana
  corta/larga. Una cinta fina tiene centro casi nulo y contraste muy alto;
  una cinta plana mantiene anchura central intermedia. Las variantes cortas
  conservan más cuerpo de la carcasa. Se separan para no admitir todas las
  combinaciones intermedias ni confundirlas con las Allen.

Se han recalculado 109 referencias confirmadas de 57 imágenes y 45 grupos.
V2 acertaba 72 y se abstenía en 37; v3 acierta 109 sin confusiones ni
abstenciones en estas referencias. Las siete clases del perfil suman 91
referencias. **Todo este conjunto es desarrollo**, incluidos originales y
recortes de una captura agrupados bajo la misma procedencia. No es una tasa
esperada en escenas nuevas ni mide herramientas omitidas por la segmentación.
Los seis objetos pendientes no se han confirmado automáticamente.

La lista completa de procedencias consultadas está en `grupos_desarrollo` de
[reglas.json](arboles/reglas.json). Las medidas portables de regresión están en
`tests/fixtures/referencias_reglas_v3.json`; el clasificador nunca lee ese archivo.
No se han optimizado umbrales automáticamente ni entrenado un clasificador.
Se necesitan nuevas adquisiciones reservadas. Cintas curvas, otras longitudes,
vistas intermedias, objetos ajenos parecidos y oclusiones pueden fallar.

Para probar la revisión, guarda tu trabajo, detén la web con `Ctrl+C` y ejecuta
`./iniciar_web.command`. Comprueba `reglas-manuales-v3` en En directo y reinicia
el flujo; activa «Usar inventario de Entrega» para las siete clases.

## Histórico v2 del 4 de noviembre de 2026

Se han recalculado las medidas de las sesiones guardadas desde sus píxeles:
65 objetos confirmados, 18 imágenes, 10 grupos de adquisición. Con v1 había
59 aciertos y 6 abstenciones; con v2 hay **64 aciertos, 1 abstención y ninguna
confusión de nombre**. Las únicas cinco predicciones que cambian corresponden
a las nuevas aperturas del alicate, que ahora cumplen R9. El calibre que ya
se rechazaba sigue siendo desconocido. Hay 9 referencias de alicate acertadas,
pero esto no demuestra reconocimiento fiable en vídeos nuevos.

Además de las cuatro procedencias originales enumeradas debajo, se han
consultado estas seis capturas para el ajuste y su comprobación; todas pasan
a **desarrollo**, incluidas sus otras herramientas:

- `20261103_105450_737590`
- `20261104_094956_247121`
- `20261104_095003_821991`
- `20261104_095010_020653`
- `20261104_095013_401274`
- `20261104_095023_630156`

La ampliación de R9 es manual y conserva los ocho descriptores de
`geometria-v1`. No hay entrenamiento, aprendizaje con etiquetas ni cambios
en la segmentación o la cámara. Las etiquetas anteriores siguen siendo
referencias; los resultados exportados anteriormente conservan su versión.

Para cargar el nuevo código, detén la web con `Ctrl+C` en su terminal y
ejecuta `./iniciar_web.command` desde la raíz del proyecto. En «En directo»
y «Reconocimiento automático» debe aparecer `reglas-manuales-v2`. Reinicia
la reproducción del vídeo y vuelve a pulsar «Evaluar sesiones guardadas»
para actualizar la comparación. Guardar más etiquetas no cambia las reglas.

## Procedencia inicial y validación pendiente

Se inspeccionaron 55 objetos confirmados de 12 imágenes, agrupadas en estas
cuatro procedencias, **todas de desarrollo**:

1. `20261016_113207_730520`
2. `20261016_113218_711279`
3. `20261016_113231_782061`
4. `video_2eaa614e1f7fa5ba99870b79f3a729103af094aabe85cf620c98fa42b98aca91`

Las tres primeras capturas comparten la disposición de las herramientas. Las
imágenes de un mismo vídeo no son observaciones independientes. Se excluyeron
sesiones antiguas no verificables, confirmaciones desactualizadas y duplicados
de los mismos píxeles. Recuento: calibre 11, Allen 11, destornillador 7,
martillo 6, desbarbador 5, nivel 5, cúter 5, alicate 3 y metro 2.

La primera comprobación de las reglas da 55 coincidencias de nombre sobre esos
55 objetos. **Es únicamente una comprobación de desarrollo**, pues se usaron
para redactar las reglas; no es una medida de generalización ni una prueba
independiente. Solo hay dos ejemplos casi idénticos del metro y tres del
alicate. La aparente perfección de este resultado no justifica prometer
fiabilidad en otras escenas.

La siguiente evaluación requiere fotos o un vídeo nuevos, con otras
colocaciones, rotaciones y distancias, etiquetados como referencia, sin cambiar
las reglas a partir de ellos. Si después se modifican las reglas consultando
esa evaluación, esas escenas pasan a desarrollo y hace falta otra prueba.
Se deben contar por separado aciertos, confusiones, abstenciones y errores de
segmentación. No dividir fotogramas del mismo vídeo entre desarrollo y prueba.

Las pruebas automáticas comprueban el contrato, errores, abstención, que los
nombres manuales y coordenadas no intervengan y la invariancia a escala/giro/
reflejo de una figura sintética. No demuestran reconocimiento bajo perspectiva,
desenfoque, manos u oclusiones. La silueta necesita verse completa y separada.

El catálogo actual contiene **nueve** clases. El enunciado indica entre cinco
y ocho tipos: hay que acordar cuáles entran en la entrega final o consultar al
docente. Añadir un nombre al etiquetador no crea automáticamente su regla.
