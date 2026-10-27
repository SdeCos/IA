# Reto 07 · Reconocimiento de herramientas

Sistema de visión artificial clásica: cámara → segmentación del tapete verde →
contornos → características geométricas → reglas manuales → nombres e inventario.
No usa redes neuronales ni entrena clasificadores.

## Prueba rápida en directo

En este Mac el entorno ya está preparado. Abre una terminal y ejecuta:

```bash
cd /Users/sauldecos/git/IA/src/reto007
./iniciar_directo.command --camara 1
```

También puedes abrir `iniciar_directo.command` con doble clic: utiliza la cámara 1.
El comando equivalente con Python es:

```bash
.venv-web/bin/python directo.py --camara 1
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
| G | Guardar foto limpia y ajustes en `capturas/`. |
| R | Iniciar/detener vídeo limpio, sin audio, en `videos/`. |
| E | Guardar foto, medidas y predicciones del instante en `resultados/`. |
| P | Guardar los ajustes del panel para la siguiente ejecución. |
| B | Mostrar/ocultar la máscara anterior a la limpieza morfológica. |

**Desconocido** indica que las reglas no pueden asignar un nombre. Las manos,
solapamientos, herramientas recortadas y cambios de apertura del alicate o del
calibre pueden alterar su silueta. Los nombres predichos nunca se confirman
automáticamente como etiquetas reales.

## Probar herramientas ausentes o sobrantes

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

### Usar el vídeo guardado como si fuera la cámara

En clase puedes ejecutar la misma vista de reconocimiento en directo con el
vídeo que ya grabaste, sin iPhone ni Photo Booth:

```bash
./iniciar_directo.command --ultimo-video
```

Para elegir otro archivo:

```bash
./iniciar_directo.command --video "videos/mi_prueba.mp4"
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

El reconocimiento utiliza `configuracion.json`; los cambios se hacen en los
controles numéricos. **P** guarda. Para usar otra configuración o zoom:

```bash
./iniciar_directo.command --camara 1 --config mi_configuracion.json --zoom 1.5
```

Para comprobar las mismas reglas sobre una foto, sin abrir cámara:

```bash
.venv-web/bin/python directo.py --ultima
# O una foto concreta:
.venv-web/bin/python directo.py --imagen capturas/escena_20261016_113231_782061.png
```

El calibrador original continúa disponible, sin nombres automáticos:

```bash
.venv-web/bin/python calibrador.py --camara 1
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

La [guía detallada](docs/GUIA_USO.md) explica guardados, etiquetas, procedencia,
exportaciones y funcionamiento de todos los controles.

## Organización y scripts

| Archivo o carpeta | Para qué sirve |
|---|---|
| `directo.py` / `iniciar_directo.command` | Reconocer con cámara, foto (`--imagen`, `--ultima`) o vídeo (`--video`, `--ultimo-video`). |
| `calibrador.py` | Adquisición, controles numéricos, fotos y grabación; `--reconocer` activa los nombres. |
| `app_web.py` / `iniciar_web.command` | Interfaz web de fotos y vídeos guardados. |
| `detector.py` | Exportar medidas de una foto sin interfaz: `.venv-web/bin/python detector.py --ultima`. |
| `configurar_web.sh` | Preparar el entorno común de cámara y web. |
| `configuracion.json` | Ajustes globales; las fotos y los vídeos pueden tener sus propios ajustes. |
| `herramientas.json` | Catálogo de etiquetas. Añadir un nombre no crea una regla nueva. |
| `capturas/`, `videos/`, `resultados/`, `etiquetas/` | Datos y trabajo guardado; sus rutas se conservan para mantener la procedencia. |
| `ejemplos/` | Inventario de ejemplo editable. |
| `tests/` | Pruebas automatizadas, con archivos temporales y cámaras simuladas. |
| `docs/` | Guía completa, memoria y reglas justificadas. |
| `.venv-web/` | Entorno Python utilizado por los lanzadores; no es código del proyecto. |

Los módulos internos permanecen junto a los scripts para mantener los imports:
`vision.py` y `geometria.py` procesan la imagen; `clasificacion.py` contiene las
reglas; `seguimiento.py` asocia pistas; `reconocimiento.py` compone el resultado
en directo; `reproduccion.py` usa un archivo como entrada; `evaluacion.py` cuenta y compara; `grabacion.py` y `video.py` gestionan
vídeos; `etiquetado.py`, `catalogo.py` y `analisis.py` gestionan referencias;
`panel_*.py` construyen las vistas web; `controles.py`, `configuracion.py` y
`actualizacion.py` mantienen controles, ajustes y sesiones abiertas.

## Instalación y pruebas

Solo si falta el entorno, desde esta carpeta:

```bash
bash configurar_web.sh
```

El instalador utiliza Python 3.13 y `requirements-web.txt`. El entorno antiguo
`venv/` se conserva por compatibilidad; los lanzadores usan `.venv-web/`.

Para ejecutar todas las pruebas desde esta carpeta:

```bash
.venv-web/bin/python -m unittest discover -s tests -t .
```

Estas pruebas verifican el programa y la captura simulada; la conexión y la
calidad de imagen del iPhone se comprueban físicamente con la prueba en directo.

## Estado de la entrega

### Archivos locales y Git

Git conserva el código, las pruebas, la documentación, `configuracion.json`,
`herramientas.json` y los ejemplos. Los entornos de Python, cachés, temporales
y las carpetas `capturas/`, `videos/`, `resultados/` y `etiquetas/` se excluyen.
Estas carpetas incluyen las anotaciones manuales y los ajustes asociados a cada
sesión: haz una copia aparte para conservarlos o trasladarlos a otro ordenador.
Clonar el repositorio no recupera esas grabaciones ni las sesiones etiquetadas.

### Pendiente de validar

Consulta la [memoria](docs/MEMORIA.md) y las [reglas](docs/REGLAS.md). Hay nueve
clases en el prototipo; el enunciado pide entre cinco y ocho para la entrega.
Los 55 aciertos sobre 55 objetos conocidos son resultados de desarrollo.
Falta evaluar escenas nuevas y documentar detección, identificación e inventario,
incluyendo herramientas omitidas y falsas detecciones. No basta con que el
vídeo utilizado para definir las reglas funcione bien.
