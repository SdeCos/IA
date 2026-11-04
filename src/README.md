# Código del sistema

Todo el código Python de la aplicación vive en el paquete `herramientas`.
Las pruebas están fuera del paquete, en [`tests/`](../tests/README.md).

| Paquete | Responsabilidad y módulos |
|---|---|
| `herramientas.vision` | `vision`: segmentación y dibujo; `geometria`: características explícitas; `clasificacion`: reglas manuales; `seguimiento`: pistas temporales; `reconocimiento`: composición del reconocimiento e inventario; `arbol`: diagramas de reglas. |
| `herramientas.datos` | `configuracion`: rutas y parámetros; `catalogo`: nombres disponibles; `nombres`: títulos de fotos sin significado para el clasificador; `etiquetado`: sesiones y etiquetas; `analisis`: referencias confirmadas; `evaluacion` y `evaluacion_escenas`: métricas; `entrega`: perfil de la demostración; `respaldo`: copias verificadas. |
| `herramientas.media` | `grabacion`: vídeo limpio; `video`: lectura, extracción y exportación; `reproduccion`: vídeo como fuente del modo directo. |
| `herramientas.web` | `app_web`: entrada Streamlit; `biblioteca`: títulos, búsqueda y filtros de revisión; `panel_*`: vistas de análisis, clasificación, vídeo y entrega; `actualizacion`: recarga controlada de módulos. |
| `herramientas.cli` | `calibrador`: bucle de cámara/foto/vídeo; `directo`: activa reconocimiento; `detector`: mediciones y exportación sin web; `controles`: controles numéricos de OpenCV. |

`media.directo_web.DirectoWeb` mantiene la captura y el reconocimiento en un hilo
sin llamadas a Streamlit. `web.panel_directo` dibuja la vista mediante un fragmento,
envía órdenes al controlador y guarda el paquete que se mostraba al usuario.
Un bloqueo evita usar la cámara desde dos sesiones web simultáneas. El latido de
la vista caduca si el navegador se desconecta. La grabación y el cierre de recursos
pertenecen al hilo de captura. Véanse las pruebas en `tests/test_directo_web.py`.

Flujo principal: entrada de imagen → segmentación → características geométricas →
reglas manuales → inventario. La web y los comandos reutilizan ese procesamiento.
Las etiquetas humanas se guardan como referencias para evaluar; no entrenan las reglas.
Actualmente `cli.detector` contiene también las funciones de exportación compartidas
por el etiquetado. Los paquetes agrupan responsabilidades, no son capas aisladas.

## Ejecución

Desde la raíz del repositorio:

```bash
./ejecutar.sh web
./ejecutar.sh directo --ultimo-video
./ejecutar.sh detector --ultima
./ejecutar.sh calibrador --camara 1
./ejecutar.sh arbol
./ejecutar.sh respaldo
./ejecutar.sh pruebas
```

`ejecutar.sh` selecciona `.venv-web/bin/python` y añade `src/` al `PYTHONPATH`
solo para ese proceso. No instala paquetes globales ni requiere instalar el
proyecto. También funciona invocándolo mediante su ruta desde otra carpeta;
las opciones con rutas relativas se resuelven respecto a la raíz del repositorio.
Los accesos `iniciar_web.command` e `iniciar_directo.command` delegan en él.

Para ejecutar un módulo manualmente o configurar un IDE, usa la raíz como
directorio de trabajo, el intérprete `.venv-web/bin/python` y `PYTHONPATH=src`:

```bash
PYTHONPATH=src .venv-web/bin/python -m herramientas.cli.detector --ultima
```

No ejecutes los archivos internos por su ruta: sus imports utilizan el paquete
`herramientas`. No copies los módulos a la raíz para solucionar imports.
`datos.configuracion.BASE` identifica la raíz a partir de su ubicación, sin
depender del directorio desde el que se abra Python. Los datos persistentes
se escriben en `datos/` y la configuración global en `config/`, nunca en `src/`.

## Cambios y pruebas

Usa imports completos (`from herramientas.vision...`) para evitar colisiones
entre módulos. Conserva los `__init__.py` de cada paquete. Al añadir una regla,
actualiza sus pruebas y regenera los diagramas con `./ejecutar.sh arbol`.
Después ejecuta `./ejecutar.sh pruebas`. La reorganización de carpetas no cambia
las versiones del algoritmo ni invalida las etiquetas si los píxeles y ajustes
siguen siendo los mismos.
