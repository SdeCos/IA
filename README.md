# Parcial de IA · Reconocimiento e inventario de herramientas

Este repositorio contiene exclusivamente el **Reto 07 del examen parcial**.
El código está organizado por función en `src/herramientas/`, los ajustes
globales en `config/` y los datos locales en `datos/`. Todos los comandos de este
README se ejecutan desde `/Users/sauldecos/git/IA` (o la carpeta donde lo clones).

Sistema de visión artificial clásica: cámara → segmentación del tapete verde →
contornos → características geométricas → reglas manuales → nombres e inventario.
No usa redes neuronales ni entrena clasificadores.

Empieza por la [checklist de entrega](docs/CHECKLIST_ENTREGA.md). También tienes
el [guion de pruebas en casa](docs/PRUEBAS_CASA.md), el [árbol detallado](docs/ARBOL_DECISION.md),
la [preparación de la defensa y vídeo](docs/DEFENSA_Y_VIDEO.md) y el
[enunciado actualizado](docs/ENUNCIADO.md). La programación permite trabajar
sin cámara; la validación física y las escenas nuevas siguen pendientes.

Si tenías la web abierta antes de esta actualización, guarda el trabajo pendiente,
detén su terminal con Ctrl+C y vuelve a ejecutar `./iniciar_web.command` para
cargar todos los módulos nuevos. No hace falta reinstalar las dependencias.

## Empezar desde la web

```bash
cd /Users/sauldecos/git/IA
./iniciar_web.command
```

Todo el flujo principal está disponible en la misma web:

| Vista | Uso |
|---|---|
| **En directo** | Cámara del Mac/iPhone o vídeo guardado como entrada. Reconocimiento, inventario, fotos, grabación y CSV. |
| **Fotografías** | Calibración, nombres de captura, etiquetas y comparación con las reglas. |
| **Vídeos** | Importar clips, buscar fotogramas y exportar intervalos de análisis. |
| **Entrega** | Perfil del inventario, árboles, referencias y evaluación. |

Para probar **sin cámara**: En directo → Fuente y captura → Vídeo de prueba →
elige el clip → Iniciar. Puedes pausar, continuar y reiniciar. Al finalizar el
archivo queda pausado en su última imagen; no se abre ninguna cámara.

Para la **cámara**: En directo → Cámara del Mac / iPhone → índice 1 → Iniciar.
Comprueba primero el iPhone en Photo Booth si tu montaje lo necesita. Usa
**Grabar vídeo / Finalizar grabación**, **Guardar foto** y **Detener**. El nombre
de las fotos se escribe en **Fuente y captura**. **Guardar medidas y revisar
capturas** contiene la exportación a CSV y el acceso a etiquetar la última foto.

Los ajustes avanzados están plegados en **Ajustes de imagen**. **Mostrar máscara**
es opcional en directo; las medidas y explicaciones se despliegan cuando hacen
falta. Guardar una foto no confirma ninguna etiqueta automáticamente.

La cámara pertenece al Mac que ejecuta Python, no al dispositivo que abre el
navegador. Cambiar de vista o pulsar Detener cierra la captura y finaliza la
grabación. Al cerrar/recargar el navegador se cierra tras unos 15 segundos sin
latidos de la vista (sujeto a que el controlador de cámara responda). Si recargas
y aparece «cámara abierta en otra sesión», espera ese intervalo. No abras el
modo nativo y el web sobre la misma cámara simultáneamente.

La interfaz refresca el directo aproximadamente cinco veces por segundo; el
procesamiento y la grabación continúan aparte. El contador FPS mide el bucle de
procesamiento, no la frecuencia de refresco del navegador. Un vídeo se analiza
secuencialmente: si el procesamiento tarda más, se reproduce más despacio.

## Alternativa: directo en ventanas de OpenCV

En este Mac el entorno ya está preparado. Abre una terminal y ejecuta:

```bash
cd /Users/sauldecos/git/IA
./iniciar_directo.command --camara 1
```

También puedes abrir `iniciar_directo.command` con doble clic: utiliza la cámara 1.
El lanzador común equivalente es:

```bash
./ejecutar.sh directo --camara 1
```

En el montaje probado anteriormente, el iPhone aparecía como cámara 1 al tener
Photo Booth abierto. Comprueba primero que el iPhone se ve allí. Si la numeración
cambia, prueba `--camara 0`. Si macOS solicita permiso de cámara para la terminal,
concédelo y vuelve a ejecutar el programa.

Se abren tres ventanas: **Controles HSV**, **Máscara Binaria** y
**Reconocimiento en directo**. Esta última muestra nombres automáticos, pistas
temporales, recuento del fotograma actual y FPS observados del bucle. La velocidad
depende del equipo y de la conexión: no se garantiza una frecuencia fija.

### Cómo comprobarlo en casa

1. Fija la cámara sobre el tapete. Coloca herramientas completas y separadas.
2. Comprueba que cada herramienta tenga una silueta blanca sobre fondo negro.
3. Gira y desplaza una herramienta; el nombre debería mantenerse cuando su
   silueta se vea completa. Retira la mano después de moverla.
4. Retira una herramienta: debe desaparecer del recuento. Añade otra y comprueba
   que aparezca. Las pistas P1, P2… son temporales, no nombres de herramientas.
5. Pulsa **R** para grabar la prueba, vuelve a pulsar **R** para guardarla y **Q**
   para salir. La grabación limpia aparecerá después en la web.

Las teclas se usan con una ventana de OpenCV seleccionada. Si estás editando un
número en Controles HSV, pulsa Enter para aplicar o Esc para cancelar antes de
usar un atajo. Ctrl+C en la terminal también termina el programa y libera la cámara.

| Tecla | Acción |
|---|---|
| Q | Salir y finalizar la grabación activa. |
| G | Guardar foto limpia y ajustes en `datos/capturas/`. |
| R | Iniciar/detener vídeo limpio, sin audio, en `datos/videos/`. |
| E | Guardar foto, medidas y predicciones del instante en `datos/resultados/`. |
| P | Guardar los ajustes del panel para la siguiente ejecución. |
| B | Mostrar/ocultar la máscara anterior a la limpieza morfológica. |

**Desconocido** indica que las reglas no pueden asignar un nombre. Las manos,
solapamientos, herramientas recortadas y cambios de apertura del alicate o del
calibre pueden alterar su silueta. Los nombres predichos nunca se confirman
automáticamente como etiquetas reales.

## Probar herramientas ausentes o sobrantes

Puedes guardar tu selección de 5–8 clases y sus cantidades desde **web → Entrega**.
Se escribe `config/entrega.json`, compartido por fotos, vídeos y nuevas ejecuciones del
modo Directo. Un `--inventario` explícito tiene prioridad sobre ese perfil.
`--sin-inventario` permite solo contar, sin comparación. El perfil conserva todas
las reglas: las clases fuera de la selección siguen visibles y pueden aparecer
como sobrantes; no se ocultan detecciones ni se borran etiquetas.

Edita `ejemplos/inventario.json` para indicar las cantidades que realmente
esperas. Incluye el inventario completo: las clases no incluidas se consideran
esperadas cero. El archivo incluido es solo un ejemplo con las seis herramientas
originales, y se utiliza únicamente si lo indicas:

```bash
./iniciar_directo.command --camara 1 --inventario ejemplos/inventario.json
```

El panel compara lo reconocido con lo esperado e indica cantidades que faltan
o sobran. Si hay desconocidos, la comparación es provisional. Una herramienta
no detectada también puede aparecer como ausente: revisa la imagen y la máscara.

## Ajustes y comprobación sin cámara

### Capturas con nombre y fotos pendientes

Para fotografiar una herramienta puedes dejarla sola sobre el tapete y dar un
nombre a las fotos de esa sesión:

```bash
./iniciar_directo.command --camara 1 --nombre "Alicate abierto"
```

Pulsa **G** para guardar. Se crean nombres como
`escena_20261103_150000_123456_alicate-abierto.png`, junto con los ajustes y un
archivo `.nombre.json` que conserva el título legible. El título es organizativo:
no confirma etiquetas, no entrena ni influye en el reconocimiento. La fecha
permanece al principio para conservar `--ultima` y la agrupación de capturas.
Con un vídeo como entrada, `--nombre` titula los fotogramas exportados sin cambiar
el nombre técnico que conserva la procedencia del clip.

En la web, el selector muestra nombre, estado y fecha. Utiliza **Estado de las
fotos → Pendientes** para ocultar las ya etiquetadas y guardadas; **Etiquetadas y
guardadas** para revisarlas, y **Todas** para volver a verlas juntas. **Buscar
foto** busca también por título o herramienta. Los filtros no mueven archivos.

Por defecto solo se muestra el recorte de cada captura; puedes activar
**Mostrar también originales sin recortar**. Original y recorte pueden tener
píxeles distintos: sus etiquetas no se transfieren automáticamente.

Para una foto de una herramienta, selecciona el nombre y pulsa **Confirmar,
guardar y siguiente foto**. Guarda etiquetas, ajustes y CSV y abre la próxima
pendiente del filtro actual. En fotos con varios objetos, confirma cada uno y
usa ese botón en el último. **Guardar y siguiente foto** sirve si ya están todos
confirmados. El guardado ordinario permite borradores; no confirma etiquetas.
Los ajustes guardados se conservan también al reabrir la captura.

**Descartar foto → Mover captura a la papelera** retira el recorte, el original
y sus archivos de ajustes/nombre/procedencia. **Papelera → Restaurar captura**
los recupera sin sobrescribir archivos. No borra las copias de sesiones ya
exportadas: estas conservan sus etiquetas y pueden seguir en las evaluaciones.
La papelera está en `datos/papelera/`, excluida de Git como los demás datos.

Puedes nombrar una foto antigua desde **Nombre de la foto → Nombre para organizar
→ Guardar nombre**, incluso si el programa no reconoce ninguna herramienta.
Sin título manual, se muestran las etiquetas confirmadas o una sugerencia marcada
como **Predicción**. Confirmar sin guardar no termina el trabajo; cambios de
píxeles, ajustes o revisiones pueden devolver la foto a pendientes. Una foto sin
detecciones también queda pendiente: cero detecciones no demuestra una escena vacía.

Consulta [cómo comprobar el método clásico](docs/COMPROBAR_METODO_CLASICO.md)
para recorrer las medidas, las reglas y las pruebas de independencia de etiquetas.

### Usar el vídeo guardado como si fuera la cámara

En clase puedes ejecutar la misma vista de reconocimiento en directo con el
vídeo que ya grabaste, sin iPhone ni Photo Booth:

```bash
./iniciar_directo.command --ultimo-video
```

Para elegir otro archivo:

```bash
./iniciar_directo.command --video "datos/videos/mi_prueba.mp4"
```

El archivo se lee secuencialmente y pasa por la misma segmentación, reglas y
recuento que la cámara. Se intenta respetar sus FPS nominales; si el análisis
tarda más, se reproduce más despacio sin saltar fotogramas. La vista indica
**VIDEO SIMULADO**, la posición y el estado, para distinguirlo de una cámara real.

- **Espacio:** pausar o continuar. Puedes ajustar los números mientras está pausado.
- **R:** volver al principio; reinicia también las pistas de seguimiento.
- **G:** guardar ese fotograma con ajustes y procedencia, para etiquetarlo en la web.
- **E:** guardar el fotograma y sus medidas, predicciones e inventario.
- **P:** guardar ajustes para ese vídeo; se recuperan también en la web.
- **Q:** salir. Al llegar al final queda pausado; R permite repetir la prueba.

El vídeo original no se sobrescribe. R en este modo reinicia, no crea otra grabación.
Se cargan primero los ajustes guardados para ese clip; `--config` y `--zoom`
permiten sobrescribirlos explícitamente. También admite
`--inventario ejemplos/inventario.json`.
Los fotogramas extraídos conservan el vídeo y el índice originales: siguen siendo
datos del mismo grupo de desarrollo, no nuevas escenas independientes.

### Calibrar y probar fotografías

El reconocimiento utiliza `config/configuracion.json`; los cambios se hacen en los
controles numéricos. **P** guarda. Para usar otra configuración o zoom:

```bash
./iniciar_directo.command --camara 1 --config mi_configuracion.json --zoom 1.5
```

Para comprobar las mismas reglas sobre una foto, sin abrir cámara:

```bash
./ejecutar.sh directo --ultima
# O una foto concreta:
./ejecutar.sh directo --imagen datos/capturas/escena_20261016_113231_782061.png
```

El calibrador original continúa disponible, sin nombres automáticos:

```bash
./ejecutar.sh calibrador --camara 1
```

## Web: revisar fotos y vídeos en clase

```bash
./iniciar_web.command
```

Abre `http://127.0.0.1:8501`. Mantén esa terminal abierta; Ctrl+C detiene la web.
La web trabaja con archivos guardados; la cámara en directo se abre con el
comando anterior, en sus ventanas locales.

- **Fotografías:** ajustar segmentación, confirmar etiquetas y guardar sesiones.
- **Reconocimiento automático:** predicciones, inventario esperado y evaluación
  comparada con etiquetas reales guardadas.
- **Vídeos:** reproducir el reconocimiento, extraer fotogramas para etiquetar
  y exportar intervalos. Pausa para elegir una posición numérica o con la barra.
- **Entrega:** guardar el perfil, visualizar/exportar el árbol y sus subárboles,
  consultar las mediciones por clase y evaluar referencias completas.

### Evaluar la escena entera

En Fotografías → Reconocimiento automático abre **Evaluar la escena completa**.
Escribe todas las herramientas reales, una por línea, incluidas las omitidas.
Relaciona cada detección con un objeto real o márcala como falsa detección.
Confirma y guarda. Esta referencia es independiente del etiquetado de calibración,
que solo tiene filas para lo que el detector encontró.

**Evaluar escenas completas** calcula TP, FP, FN, identificación e inventario,
separando desarrollo y prueba reservada; permite exportar JSON y dos CSV.
Los parámetros guardados y las firmas protegen las correspondencias ante cambios.
Si la segmentación cambia, abre la escena y revisa de nuevo. Las referencias
incluyen sus píxeles en `datos/evaluaciones/`. Consulta el [protocolo y las fórmulas](docs/PRUEBAS_CASA.md).

La [guía detallada](docs/GUIA_USO.md) explica guardados, etiquetas, procedencia,
exportaciones y funcionamiento de todos los controles.

## Organización y scripts

```text
IA/
├── README.md                  # Guía principal y comandos
├── iniciar_web.command        # Acceso rápido a la web (también doble clic)
├── iniciar_directo.command    # Acceso rápido a la cámara o vídeo
├── ejecutar.sh                # Comandos comunes, incluido ejecutar pruebas
├── configurar_web.sh          # Preparar el entorno Python
├── requirements-web.txt       # Dependencias fijadas
├── src/
│   ├── README.md              # Mapa del código y convenciones
│   └── herramientas/          # Paquete Python
│       ├── vision/            # Segmentación, geometría, reglas, seguimiento
│       ├── datos/             # Configuración, etiquetas, métricas, respaldos
│       ├── media/             # Grabación y reproducción de vídeos
│       ├── web/               # Aplicación Streamlit y sus paneles
│       └── cli/               # Comandos y controles de OpenCV
├── config/                    # configuracion.json, herramientas.json, entrega.json opcional
├── datos/                     # Archivos locales, excluidos de Git salvo su README
│   ├── capturas/              # Fotos y fotogramas con ajustes y procedencia
│   ├── videos/                # Grabaciones y ajustes por clip
│   ├── resultados/            # Sesiones, medidas y predicciones
│   ├── etiquetas/             # Etiquetas auxiliares anteriores
│   └── evaluaciones/          # Referencias completas, creadas al guardar
├── docs/                      # Enunciado, memoria, checklist, guías y árboles
├── ejemplos/                  # Inventario de ejemplo
├── tests/                     # Pruebas automatizadas
├── respaldos/                 # Copias locales verificables, excluidas de Git
└── .venv-web/                 # Entorno Python local, excluido de Git
```

Los datos locales y los entornos están excluidos de Git. Las carpetas opcionales
se crean cuando se utilizan. Consulta el [mapa del código](src/README.md),
los [ajustes globales](config/README.md) y la [organización de datos](datos/README.md). La [documentación](docs/README.md) y las
[pruebas](tests/README.md) tienen sus propios índices.

| Archivo o carpeta | Para qué sirve |
|---|---|
| `src/herramientas/cli/directo.py` / `iniciar_directo.command` | Reconocer con cámara, foto (`--imagen`, `--ultima`) o vídeo (`--video`, `--ultimo-video`). |
| `src/herramientas/cli/calibrador.py` | Adquisición, controles numéricos, fotos y grabación; `--reconocer` activa los nombres. |
| `src/herramientas/web/app_web.py` / `iniciar_web.command` | Interfaz web de fotos y vídeos guardados. |
| `src/herramientas/cli/detector.py` | Exportar medidas de una foto sin interfaz: `./ejecutar.sh detector --ultima`. |
| `configurar_web.sh` | Preparar el entorno común de cámara y web. |
| `config/configuracion.json` | Ajustes globales; las fotos y los vídeos pueden tener sus propios ajustes. |
| `config/herramientas.json` | Catálogo de etiquetas. Añadir un nombre no crea una regla nueva. |
| `datos/capturas/`, `datos/videos/`, `datos/resultados/`, `datos/etiquetas/` | Datos y trabajo guardado; conservan la identidad de las imágenes y la procedencia de las sesiones. |
| `ejemplos/` | Inventario de ejemplo editable. |
| `tests/` | Pruebas automatizadas, con archivos temporales y cámaras simuladas. |
| `docs/` | Guía completa, memoria y reglas justificadas. |
| `src/herramientas/datos/entrega.py` / `config/entrega.json` | Validación y perfil opcional de clases y cantidades, creado al guardar en Entrega. |
| `src/herramientas/vision/arbol.py` / `docs/arboles/` | Generación de diagramas desde las reglas actuales. |
| `src/herramientas/datos/evaluacion_escenas.py` | Métricas completas, referencias y separación por adquisición. |
| `src/herramientas/web/panel_entrega.py` | Perfil, árbol, revisión de referencias y evaluación en la web. |
| `datos/evaluaciones/` | Referencias completas con imagen, parámetros y correspondencias humanas; datos locales. |
| `src/herramientas/datos/respaldo.py` / `respaldos/` | Copia ZIP con manifiesto SHA-256 y verificación; datos locales. |
| `.venv-web/` | Entorno Python utilizado por los lanzadores; no es código del proyecto. |

Los módulos se importan mediante el paquete `herramientas`. `ejecutar.sh`
configura la ruta de `src/` para cada ejecución, por lo que no tienes que mover
archivos ni instalar el proyecto como paquete. El [mapa del código](src/README.md)
describe cada módulo y cómo ejecutarlo manualmente o desde un IDE.

## Instalación y pruebas

Solo si falta el entorno, desde esta carpeta:

```bash
bash configurar_web.sh
```

El instalador utiliza Python 3.13 y `requirements-web.txt` para cámara y web.
Los lanzadores comparten `.venv-web/`; no se necesita otro entorno.

Para ejecutar todas las pruebas desde esta carpeta:

```bash
./ejecutar.sh pruebas
```

Estas pruebas verifican el programa y la captura simulada; la conexión y la
calidad de imagen del iPhone se comprueban físicamente con la prueba en directo.

Algunas pruebas antiguas utilizan las capturas reales del proyecto, que Git no
incluye. Tras clonar puedes ejecutar las pruebas nuevas con datos sintéticos:

```bash
./ejecutar.sh pruebas tests.test_entrega tests.test_panel_entrega
```

Para la batería completa, recupera antes los datos de tu respaldo. No descargues
un entorno virtual de otro ordenador: vuelve a crearlo con el instalador.

## Estado de la entrega

### Archivos locales y Git

Git conserva el código, las pruebas, la documentación, `config/configuracion.json`,
`config/herramientas.json` y los ejemplos. Los entornos de Python, cachés, temporales
y las carpetas `datos/capturas/`, `datos/videos/`, `datos/resultados/`, `datos/etiquetas/`, `datos/evaluaciones/`
y `respaldos/` se excluyen.
Estas carpetas incluyen las anotaciones manuales y los ajustes asociados a cada
sesión: haz una copia aparte para conservarlos o trasladarlos a otro ordenador.
Clonar el repositorio no recupera esas grabaciones ni las sesiones etiquetadas.

Desde esta carpeta, `./ejecutar.sh respaldo` crea y verifica una copia
ZIP en `respaldos/`. Cópiala a otro dispositivo. [Detalles y recuperación](docs/RESPALDOS.md).

### Pendiente de validar

Consulta la [memoria](docs/MEMORIA.md) y las [reglas](docs/REGLAS.md). El perfil
actual de entrega contiene siete clases, una unidad de cada una: martillo,
destornillador, alicate, calibre, nivel, metro y desbarbador. Cúter y Allen quedan
fuera del inventario esperado; sus reglas y referencias históricas se conservan.

Con `reglas-manuales-v4`, la comprobación del 4 de noviembre da 120 aciertos
sobre 120 referencias confirmadas de 68 imágenes; 102 corresponden a las siete
clases de entrega. Son resultados de desarrollo, no una evaluación independiente.
La versión amplía las extensiones del flexómetro y cubre la transición entre
cinta corta y larga, conservando las variantes de canto y calibre abierto. No cambia la segmentación.
Tras guardar el trabajo, reinicia la web con `Ctrl+C` y
`./iniciar_web.command`; comprueba `reglas-manuales-v4` en En directo y activa
«Usar inventario de Entrega». Etiquetar no modifica las reglas automáticamente.

Falta evaluar escenas nuevas y documentar detección, identificación e inventario,
incluyendo herramientas omitidas y falsas detecciones. No basta con que el
vídeo utilizado para definir las reglas funcione bien.
