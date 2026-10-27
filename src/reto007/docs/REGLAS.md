# Clasificador geométrico manual: reglas-manuales-v1

Este clasificador asigna nombres mediante **reglas escritas a mano sobre medidas
explícitas de la silueta**. No entrena un árbol, no usa redes neuronales, vecinos,
prototipos, clasificación por color ni búsqueda automática de umbrales.
La entrada es una detección ya segmentada; la etiqueta manual es únicamente la
referencia para estudiar y evaluar las reglas. No se consulta al predecir.

## Qué decisiones toma

1. Comprueba que los ocho descriptores son finitos, están en su dominio físico
   y corresponden a `geometria-v1`. Si faltan, se abstiene. Comprueba también
   que la extensión no supere la solidez salvo una tolerancia de 0,02.
2. Evalúa las nueve reglas de la tabla. Cada fila es una conjunción: **deben
   cumplirse sus ocho intervalos**. Las familias corresponden a cuerpo compacto
   y convexo (metro/cúter/nivel), mango y punta muy alargados
   (destornillador/desbarbador), cabeza y cuerpo estrecho (calibre/martillo) y
   cuerpo ramificado (Allen/alicate). No hay prioridad que permita a una regla
   ocultar la coincidencia de otra.
3. Solo asigna nombre cuando existe una única regla compatible y queda fuera
   de las bandas de abstención de todos sus umbrales.
4. Si hay una frontera próxima o varias reglas compatibles devuelve
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
| R1 Metro | 1–1,6 | 0,90–1 | 0,65–0,90 | 0,75–1 | 0–0,25 | 0,85–1 | 0–0,20 | 0,80–1 |
| R2 Cuter | 2–3,8 | 0,85–1 | 0,40–0,65 | 0,65–0,88 | 0–0,25 | 0,80–1 | 0–0,20 | 0,80–1 |
| R3 Nivel | 4–6,5 | 0,90–1 | 0,25–0,50 | 0,85–1 | 0–0,15 | 0,90–1 | 0–0,12 | 0,80–1 |
| R4 Desbarbador manual | 8,5–14 | 0,70–0,95 | 0,10–0,25 | 0,55–0,85 | 0,55–0,95 | 0,65–0,90 | 0,15–0,50 | 0,75–1 |
| R5 Destornillador | 5,5–9 | 0,50–0,78 | 0,08–0,20 | 0,25–0,50 | 0,70–1 | 0,30–0,55 | 0,40–0,75 | 0,12–0,45 |
| R6 Calibre | 2,5–4,5 | 0,40–0,65 | 0,10–0,25 | 0,22–0,43 | 0,55–0,85 | 0,10–0,30 | 0,12–0,35 | 0,12–0,25 |
| R7 Martillo | 2,5–4,5 | 0,35–0,65 | 0,10–0,27 | 0,25–0,48 | 0,25–0,55 | 0,10–0,32 | 0,06–0,25 | 0,28–0,45 |
| R8 Juego de llaves Allen | 2,3–4,3 | 0,60–0,82 | 0,07–0,22 | 0,40–0,65 | 0,20–0,55 | 0,65–0,90 | 0,07–0,28 | 0,55–0,85 |
| R9 Alicate | 2–4 | 0,50–0,78 | 0,08–0,25 | 0,30–0,65 | 0,55–0,85 | 0,50–0,82 | 0,30–0,60 | 0,60–0,95 |

Cada extremo de intervalo tiene una banda de abstención de **±0,15 en AR** y
**±0,02 en los otros cocientes**. No se aplica banda en los límites físicos
0/1 ni en el mínimo físico AR=1. Por ejemplo, para el máximo AR=6,5 del nivel,
6,36–6,64 queda en la banda: no se identifica. Una coincidencia muy lejos de
todos los intervalos es desconocida. Las bandas no son intervalos estadísticos;
son una decisión manual para no dar un nombre cerca de los cortes.

## Justificación geométrica

- **Metro:** el ejemplar es un flexómetro recogido: cuerpo compacto casi
  cuadrado, convexo y de extremos similares. La circularidad superior evita
  tratar un disco perfectamente circular como este ejemplar. No describe una
  cinta extendida.
- **Cuter:** el ejemplar fotografiado es una herramienta plegada de cuerpo
  convexo, más larga que ancha, con centro ancho y extremos parecidos. La
  extensión es menor que la de un nivel rectangular. El nombre conserva la
  etiqueta escrita por el usuario. No se ha demostrado que funcione abierta.
- **Nivel:** combina alta extensión y solidez con cuerpo alargado, anchura
  uniforme y simetría longitudinal. Los huecos interiores no son necesarios.
- **Desbarbador:** tiene AR mayor que el destornillador, pero el mango ocupa
  mucha más longitud y el centro es ancho; el extremo fino ocupa una parte
  corta. Por eso no basta con comparar el área en píxeles.
- **Destornillador:** mango y vástago crean gran asimetría; aproximadamente
  media longitud es estrecha, y la caja contiene bastante fondo.
- **Calibre y martillo:** AR y solidez por sí solos son insuficientes. El
  calibre observado tiene centro normalizado 0,208–0,213 y contraste
  0,630–0,691; el martillo, centro 0,307–0,315 y contraste 0,443–0,455. Se
  exige coherencia en ambos rasgos, con un hueco entre los centros admitidos.
  Las mordazas del calibre abiertas de otra forma pueden salir del dominio.
- **Allen y alicate:** ambos son ramificados y anchos en el centro. El juego
  observado presenta asimetría 0,168–0,193 y contraste 0,353–0,457; el alicate
  abierto, asimetría 0,413–0,416 y contraste 0,661–0,663. Los intervalos
  separados codifican esa diferencia; cerrar el alicate o separar las Allen
  puede requerir reglas nuevas. El juego montado cuenta como un objeto.

Los rangos son amplios respecto a las medidas observadas y redondeados a mano.
No se han calculado mediante optimización de aciertos. La combinación de
varios rasgos busca rechazar siluetas incompatibles, pero **no garantiza
detectar toda mala segmentación ni rechazar cualquier objeto ajeno**: una
regla rectangular puede parecerse a un nivel y una caja cuadrada a un metro.

## Procedencia y validación pendiente

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
