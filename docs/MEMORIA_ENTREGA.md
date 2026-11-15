# Inventario de herramientas mediante visión artificial clásica

**Reto 07 · Examen parcial de Inteligencia Artificial**

**Borrador para revisión · 15 de noviembre de 2026**

**Autor, grupo y centro** · Pendientes de completar

**Vídeo de demostración** · Pendiente de publicar en YouTube con la cuenta universitaria e insertar aquí su enlace.

**Datos de prueba** · Pendiente de incluir el enlace al Google Drive de la cuenta de alumno.

Una cámara cenital observa herramientas sobre un tapete verde. El programa separa las siluetas, identifica cada pieza con reglas geométricas y compara las cantidades observadas con un inventario esperado. La aplicación permite usar la cámara en directo y reproducir grabaciones para repetir una prueba.

<!-- pagina -->

## 1. Contexto y requisitos

El reto tiene tres niveles. El primero localiza los objetos del tapete. El segundo asigna un tipo a cada objeto a partir de su geometría. El tercero interpreta la escena con un inventario que señala ausencias y excesos respecto de las cantidades previstas.

El perfil de entrega espera una unidad de cada clase: **martillo, destornillador, alicate, calibre, nivel, metro o flexómetro y desbarbador manual**. Las pruebas deben variar la posición, la orientación, el número y la combinación de herramientas. Para comparar formas se usa el eje de la caja rotada. Colocar una pieza de canto o abrirla también puede cambiar su silueta, por lo que algunas posturas tienen reglas propias.

## 2. Hardware y montaje

| Elemento | Configuración y motivo |
|---|---|
| Cámara | Un iPhone en posición cenital fija, aproximadamente perpendicular al tapete. Así se reduce la perspectiva y se puede mover o girar una pieza conservando una vista comparable. Completar modelo, lente y altura desde el tapete. |
| Soporte | Soporte impreso en 3D adaptado para pasar el cable. Añadir fotografía lateral y cenital del montaje final. |
| Conexión y equipo | Mac con Cámara de Continuidad. La aplicación ofrece captura por USB y conexión inalámbrica a través de macOS. Completar modelo del Mac y modo usado en la evaluación final. |
| Fondo | Tapete verde mate para separar fondo y herramientas por HSV. Verificar cobertura aproximada de 0,50 × 0,50 m y encuadre con fondo uniforme. Anotar las medidas reales. |
| Iluminación | Anotar fuente, posición y condiciones de la prueba. Revisar sombras y reflejos, especialmente sobre el calibre y las partes metálicas finas. |
| Adquisición | Un vídeo de desarrollo está registrado a 1920 × 1080 y 15 fps nominales. El software procesa a 800 px de ancho. Medir la resolución efectiva, la escala en px/mm y el detalle más fino visible en el montaje final. |

## 3. Software y hoja de ruta

El entorno documentado usa Python 3.13, OpenCV 5.0 y NumPy. OpenCV se ocupa de la captura, el filtrado, las máscaras y los contornos. NumPy calcula y normaliza medidas geométricas. Streamlit sirve la interfaz local de calibración, evaluación y presentación. Los ajustes, etiquetas e informes se guardan en JSON y CSV. Las versiones se fijan en `requirements-web.txt`.

1. Se delimitó el tapete y se calibró su rango de color con imágenes propias.
2. Se etiquetaron ejemplos y se midieron rasgos para redactar reglas manuales.
3. Se añadieron variantes al observar fallos con herramientas abiertas, extendidas o de canto.
4. Se integraron la captura, el inventario y la vista de presentación. La evaluación reservada se realiza con el montaje y los ajustes definitivos.

<!-- pagina -->

## 4. Procesamiento y segmentación

![Figura 1. Secuencia desde la entrada hasta el inventario.](figuras_memoria/proceso.png)

La entrada de OpenCV se recibe en BGR. Tras el recorte central opcional y el redimensionado, el suavizado reduce variaciones locales y se convierte la imagen a HSV. `inRange` marca el verde. Se rellena el mayor contorno verde para delimitar el tapete y se toma como candidata la parte que difiere del verde dentro de esa región.

El cierre conecta pequeños cortes de la máscara. La apertura está desactivada en los ajustes guardados. Después se vuelve a aplicar la región útil, se extraen los contornos exteriores y se descartan las áreas pequeñas y los componentes que tocan el límite de la zona útil. Si falta una región válida del tapete, la interfaz avisa de que el inventario está sin comprobar.

![Figura 2. Contornos y máscara de una escena real de desarrollo. Incluye el juego de llaves Allen del conjunto inicial.](figuras_memoria/segmentacion.jpg)

## 5. Parámetros de imagen y justificación

Los números corresponden al archivo global guardado. Una foto o un vídeo pueden conservar ajustes propios.

| Operación | Valor guardado | Motivo y evidencia |
|---|---|---|
| Recorte y escala | Zoom 100 % y ancho 800 px | Conserva el campo visible y limita el coste por fotograma. Pendiente medir el detalle fino y el ritmo del montaje final. |
| Gaussiano | 3 × 3 | Suaviza el ruido del fondo con una ventana pequeña para conservar puntas finas. |
| Umbral HSV | H 80–100, S 100–255, V 40–255 | Rango ajustado manualmente al tapete usado durante el desarrollo, en la escala de OpenCV. Verificar con sombras y con la iluminación final. |
| Región y margen | Región ≥10 % del encuadre, ≥25 % de verde en ella y margen de 2 px | Excluye mesa y bordes dudosos. Activar la región evitó que el exterior se confundiera con un solo objeto en tomas amplias. |
| Apertura y cierre | 0 y 1 iteración, elemento elíptico 3 × 3 | El cierre tapa cortes pequeños. Mantener la apertura a cero evita erosionar de entrada las zonas estrechas. Verificar separación entre objetos cercanos. |
| Área y contornos | 1000 px², contornos exteriores | Filtra manchas pequeñas. En capturas iniciales el desbarbador quedó cerca del límite, con 1059–1097 px². La comprobación debe repetirse al fijar la altura. |

<!-- pagina -->

## 6. Características de la silueta

El detector obtiene también área, perímetro, centroide, orientación y las dimensiones de la caja mínima rotada. El centroide indica posición y ayuda a seguir la pieza en vídeo. Los ocho rasgos siguientes alimentan las reglas.

| Rasgo | Cálculo y utilidad |
|---|---|
| AR · Relación de aspecto | Lado largo / lado corto de la caja rotada. Separa cuerpos compactos de cuerpos alargados. |
| S · Solidez | Área / área de la envolvente convexa. Mide cuánto espacio dejan mordazas, ramas y otras concavidades. |
| C · Circularidad | 4π × área / perímetro². Distingue formas compactas de perfiles largos o irregulares. |
| E · Extensión | Área / área de la caja rotada. Distingue un rectángulo lleno de una figura con tramos estrechos. |
| K · Contraste de extremos | Diferencia entre las anchuras medias del primer y último 20 %, dividida por la mayor de las dos. Distingue un extremo grueso de uno fino. |
| F · Fracción ancha | Proporción de secciones con anchura normalizada de al menos 0,5. Mide cuánto se extiende la parte ancha. |
| A · Asimetría longitudinal | Media de las diferencias absolutas entre el perfil y el perfil invertido. Mide la diferencia entre ambas mitades. |
| W · Ancho central | Anchura media entre el 40 % y el 60 % del eje largo, normalizada por el lado corto. Ayuda a distinguir mangos, varillas y cintas. |

La anchura se mide entre los extremos visibles del contorno en 40 cortes perpendiculares al eje largo. La caja rotada y la normalización permiten comparar giros y tamaños. Los huecos interiores se quedan fuera de los rasgos de contorno exterior.

## 7. Diagrama de decisión

![Figura 3. Resumen de la decisión que ejecuta el clasificador.](figuras_memoria/decision.png)

Cada regla verifica ocho intervalos. Cerca de sus límites se distingue compatibilidad de aceptación interior mediante una banda de ±0,15 en AR y ±0,02 en los otros cocientes, con excepción de los extremos físicos. La clase se acepta cuando es la única compatible y al menos una de sus variantes cumple todos los límites interiores. Las etiquetas manuales sirven como referencia para medir los resultados. La decisión usa únicamente los rasgos geométricos calculados en cada detección.

<!-- pagina -->

## 8. Reglas, inventario y límites

Los umbrales se eligieron comparando siluetas y mediciones de desarrollo. Por ejemplo, un nivel ocupa gran parte de su caja y mantiene una anchura bastante uniforme. En las primeras muestras de calibre y martillo, el ancho central normalizado fue aproximadamente 0,21 y 0,31, respectivamente. También se combina con el contraste de extremos. Las vistas de canto del nivel y el martillo y las extensiones del metro tienen intervalos propios. El expediente de mediciones y revisiones está en `docs/REGLAS.md`.

| Regla / clase | AR | S | C | E | K | F | A | W |
|---|---|---|---|---|---|---|---|---|
| R1 Metro | 1 a 2,2 | 0,9 a 1 | 0,65 a 0,9 | 0,75 a 1 | 0 a 0,25 | 0,85 a 1 | 0 a 0,2 | 0,8 a 1 |
| R2 Cuter | 2 a 3,8 | 0,85 a 1 | 0,4 a 0,65 | 0,65 a 0,88 | 0 a 0,25 | 0,8 a 1 | 0 a 0,2 | 0,8 a 1 |
| R3 Nivel | 4 a 6,5 | 0,9 a 1 | 0,25 a 0,5 | 0,85 a 1 | 0 a 0,15 | 0,9 a 1 | 0 a 0,12 | 0,8 a 1 |
| R4 Desbarbador | 8,5 a 14 | 0,7 a 0,95 | 0,1 a 0,25 | 0,55 a 0,85 | 0,55 a 0,95 | 0,65 a 0,9 | 0,15 a 0,5 | 0,7 a 1 |
| R5 Destornillador | 5,5 a 9 | 0,5 a 0,78 | 0,08 a 0,2 | 0,25 a 0,5 | 0,7 a 1 | 0,3 a 0,55 | 0,4 a 0,75 | 0,12 a 0,45 |
| R6 Calibre | 2,5 a 6 | 0,28 a 0,65 | 0,04 a 0,25 | 0,18 a 0,43 | 0,55 a 0,85 | 0,06 a 0,3 | 0,12 a 0,35 | 0,12 a 0,55 |
| R7 Martillo | 2,5 a 4,5 | 0,35 a 0,65 | 0,1 a 0,27 | 0,25 a 0,48 | 0,25 a 0,55 | 0,1 a 0,32 | 0,06 a 0,25 | 0,28 a 0,45 |
| R8 Llaves Allen | 2,3 a 4,3 | 0,6 a 0,82 | 0,07 a 0,22 | 0,4 a 0,65 | 0,2 a 0,55 | 0,65 a 0,9 | 0,07 a 0,28 | 0,55 a 0,85 |
| R9 Alicate | 1 a 4 | 0,28 a 0,78 | 0,08 a 0,25 | 0,18 a 0,65 | 0,55 a 0,85 | 0,5 a 0,82 | 0,3 a 0,6 | 0,54 a 0,95 |
| R10 Martillo | 6,5 a 12 | 0,6 a 0,84 | 0,12 a 0,24 | 0,48 a 0,8 | 0 a 0,3 | 0,55 a 1 | 0,07 a 0,21 | 0,43 a 0,75 |
| R11 Nivel | 7 a 15 | 0,88 a 1 | 0,14 a 0,3 | 0,8 a 0,96 | 0 a 0,2 | 0,85 a 1 | 0 a 0,14 | 0,85 a 1 |
| R12 Metro | 2,2 a 10 | 0,25 a 0,68 | 0,025 a 0,3 | 0,13 a 0,45 | 0,65 a 1 | 0,08 a 0,48 | 0,17 a 0,78 | 0 a 0,14 |
| R13 Metro | 1 a 2,2 | 0,78 a 0,91 | 0,45 a 0,61 | 0,55 a 0,72 | 0,88 a 1 | 0,65 a 0,82 | 0,32 a 0,57 | 0,85 a 1 |
| R14 Metro | 2,3 a 4,6 | 0,8 a 1 | 0,34 a 0,6 | 0,65 a 0,85 | 0,35 a 0,62 | 0,48 a 0,82 | 0,24 a 0,45 | 0,6 a 1 |
| R15 Metro | 3,8 a 20 | 0,63 a 0,9 | 0,04 a 0,44 | 0,4 a 0,72 | 0,35 a 0,68 | 0,07 a 0,65 | 0,1 a 0,45 | 0,34 a 0,84 |

El motor ejecuta las quince reglas de `reglas-manuales-v4`. Cúter y llaves Allen se conservan como clases históricas del clasificador. En el inventario de entrega su cantidad esperada es cero.

**Inventario.** Se cuentan las detecciones identificadas del fotograma y se comparan con las cantidades esperadas. Una diferencia negativa indica ausencia o falta de unidades y una positiva indica repetición o sobrante. Los objetos sin identificar dejan la comparación provisional.

**Seguimiento.** Las pistas se asocian por proximidad, con un máximo de 80 px, y por un cociente de áreas entre 0,5 y 2. El seguidor admite hasta 5 fotogramas perdidos. En la web, si la última silueta reconocida conserva evidencia en su zona y la identificación se interrumpe, se señala una posible oclusión en ámbar durante hasta 1,5 s. Se exige que la máscara ocupe al menos el 35 % de la silueta previa. Si hubo descartes en el borde, se permite comprobar un pequeño margen con una dilatación de 11 × 11 px. La detección actual y la estimación se cuentan por separado.

**Límites.** El contacto entre piezas, el recorte, los reflejos y la oclusión pueden alterar el contorno. Queda por medir cuánto afectan en escenas nuevas los parámetros de seguimiento y las bandas de abstención.

<!-- pagina -->

## 9. Pruebas y medidas de acierto

La revisión del 15 de noviembre reproduce **120 identificaciones correctas en 120 referencias confirmadas de desarrollo**, correspondientes a 68 imágenes y 56 grupos de captura. De ellas, 102 corresponden a las siete clases de entrega. Solo se cuentan objetos detectados y etiquetados. Estas cifras prueban la reproducción de las referencias que guiaron las reglas. La evaluación de escenas nuevas se presenta por separado.

| Herramienta | Referencias de desarrollo | Identificaciones correctas |
|---|---|---|
| Alicate | 9 | 9 |
| Calibre | 18 | 18 |
| Desbarbador manual | 15 | 15 |
| Destornillador | 9 | 9 |
| Martillo | 13 | 13 |
| Metro | 26 | 26 |
| Nivel | 12 | 12 |
| **Total del perfil** | **102** | **102** |

A fecha de este borrador hay **0 escenas independientes registradas**. Para completar el resultado, conservar escenas nuevas con ajustes fijos y variar número, posición, orientación y combinaciones. Incluir tapete vacío, una retirada, una reposición y, si hay dos ejemplares reconocibles de una misma clase, una repetición física. Anotar la realidad de cada escena, incluidas las piezas que el sistema omita.

| Medida de evaluación final | Cálculo o criterio | Resultado |
|---|---|---|
| Precisión de detección | Detectados correctos / total detectado | Pendiente |
| Exhaustividad de detección | Detectados correctos / total real | Pendiente |
| Acierto de clasificación | Clases correctas / detecciones asociadas | Pendiente |
| Acierto extremo a extremo | Clases correctas / objetos reales | Pendiente |
| Inventario y avisos | Escenas con inventario exacto y avisos correctos / escenas evaluables, por separado | Pendiente |

Registrar TP (detección real asociada), FP (detección sin correspondencia), FN (herramienta omitida), nombre incorrecto y resultado desconocido. Añadir uno o dos ejemplos de error y su causa observada. Reservar la adquisición completa, agrupando los fotogramas de cada clip para evitar que material usado al ajustar también se presente como prueba independiente.

## 10. Código fuente y otras tareas

El código fuente comentado se entrega junto al PDF. `vision/` implementa la segmentación, los rasgos y las reglas. `media/` gestiona la captura y el vídeo. `web/` presenta las detecciones y exporta informes. `datos/` conserva los ajustes, las referencias y las métricas.

Desde la raíz, `./iniciar_web.command` abre la aplicación. **Presentación** muestra nombres e inventario en directo. **Entrega** contiene la evaluación y los árboles. `./ejecutar.sh pruebas` comprueba el software, y `./ejecutar.sh arbol` regenera los diagramas detallados desde las reglas. 

En este entorno pasaron las 165 pruebas automáticas del repositorio. El recuento corresponde a pruebas de software.

Se usó un LLM como apoyo en la redacción, la organización de tablas y la preparación de figuras. Las decisiones, mediciones y evidencias deben revisarse contra el funcionamiento observado. Quedan por completar la fotografía y medidas del montaje, los resultados independientes y los enlaces de portada.
