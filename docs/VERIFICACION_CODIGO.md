# Verificación del cierre de código

## Directo integrado y simplificación de la web · 3 de noviembre de 2026

- **149 pruebas superadas** en 14,8 s. Las cinco nuevas cubren vídeo secuencial,
  pausa/reinicio/fin, ajustes en pausa, exclusión entre sesiones, caducidad de
  cámara, cierre de grabaciones, recuperación tras errores, guardado del paquete
  mostrado y recorrido Streamlit de inicio, foto y salida de la vista.
- Prueba visual en navegador con el vídeo local: inicio, reconocimiento,
  inventario, pausa y continuación. No se abrió el iPhone durante esta revisión.
- La cámara simulada verifica el cierre de recursos y la grabación; queda
  comprobar la captura física desde la nueva vista web en el montaje del alumno.
- Se conservan las reglas, etiquetas y fuentes originales. Las opciones avanzadas
  se agrupan en desplegables y solo se construye la pestaña activa de Fotografías.
- La captura usa un hilo sin llamadas a Streamlit y la vista usa un fragmento.
  Referencias de implementación: [fragmentos](https://docs.streamlit.io/develop/concepts/architecture/fragments)
  y [hilos en Streamlit](https://docs.streamlit.io/develop/concepts/design/multithreading).

## Nombres de capturas y biblioteca · 3 de noviembre de 2026

- **144 pruebas superadas** en 11,9 s. Siete nuevas verifican títulos de captura,
  conservación de píxeles y predicciones, agrupación original/recorte, traslado
  del título con la sesión, estados pendientes/guardados, invalidación por cambios
  y recorridos web de búsqueda, filtros y cambios sin guardar.
- Inspección de la biblioteca real en modo lectura: 17 fotos, de las que 12
  tienen etiquetas vigentes guardadas, 4 están pendientes y 1 necesita revisión.
  No se modificaron las etiquetas reales para hacer esta comprobación.
- El nuevo argumento `--nombre` no entra en las características ni en las reglas.
  Los filtros solo alteran la lista visible; no trasladan ni eliminan archivos.
- No se añadió una cámara web en directo ni se abrió la cámara física.

## Organización en paquetes `src/` · 3 de noviembre de 2026

El código se agrupó en `src/herramientas/{vision,datos,media,web,cli}`.
Los ajustes globales están en `config/` y los archivos de trabajo en `datos/`.
Los lanzadores existentes delegan en `ejecutar.sh`, que prepara el entorno de
imports sin instalar el proyecto ni depender del directorio de invocación.

- **137 pruebas superadas** en 10,8 s, incluidos los recorridos de Streamlit,
  vídeo y cámara simulada. Las pruebas de respaldo comprueban ahora la inclusión
  de `src/`, `config/`, datos, lanzador y `.gitignore`.
- Las 55 referencias conservan todas sus medidas, etiquetas, grupos y avisos;
  la comparación del análisis antes y después solo normaliza las rutas trasladadas.
- Las 79 imágenes y vídeos coinciden byte a byte con el respaldo anterior al cambio.
- Se probaron los lanzadores y la exportación del detector desde otra carpeta:
  detectó seis objetos en la escena de referencia y exportó a un directorio temporal.
- Enlaces de documentación, sintaxis de los scripts y exclusión de vídeos en Git
  comprobados. No se abrió la cámara física.

El respaldo previo es `respaldos/reto007_20261103_092408_353213.zip`.
Las fechas de los metadatos se conservaron al actualizar sus rutas para no
alterar la prioridad entre versiones de las anotaciones.

## Traslado inicial a la raíz (estructura sustituida) · 3 de noviembre de 2026

El parcial se trasladó a la raíz de `IA/`. Se ejecutaron de nuevo las **137
pruebas**, todas superadas (10,9 s). También se comprobaron los lanzadores,
Streamlit, la activación del entorno Python y `pip check`.

Las 55 referencias mantienen etiquetas, predicciones y grupos de adquisición.
Se cotejaron 79 imágenes y vídeos con el respaldo previo: sus bytes no cambiaron.
Las rutas de los metadatos se actualizaron a la nueva ubicación; las firmas de
píxeles y detección permanecen intactas. Los enlaces de los README y documentos
se verificaron desde la nueva estructura. No se abrió la cámara física.

## Comprobación anterior al traslado

Fecha: **2 de noviembre de 2026**. Entorno local `.venv-web` del proyecto.

- Batería completa: **137 pruebas superadas** (11,1 s en la ejecución registrada).
- Pruebas nuevas: métricas con omisiones, falsos positivos, rechazos, duplicados
  reales, escenas vacías y denominadores cero; correspondencias inválidas;
  persistencia y firmas; separación por adquisición incluso con referencias
  obsoletas; perfil de 5–8 clases y recuperación; generación del árbol desde
  reglas; respaldo verificable que no sobrescribe; recorrido de Streamlit
  guardando perfil y referencia, evaluando y reabriendo; modo Directo que carga
  perfil y admite omitirlo.
- La batería existente cubre segmentación, clasificación, vídeo, reproducción,
  exportaciones, cámara simulada, etiquetas y regresiones de la interfaz.
- Comprobación en navegador local del modo Entrega y del renderizado del árbol
  principal y subárboles. No se cambiaron las etiquetas reales ni se eligió el
  alcance final del alumno durante esa inspección.
- El clasificador conserva sus intervalos y predicciones anteriores; los márgenes
  se centralizaron para generar diagramas consistentes. No se entrenó ningún modelo.

Las pruebas con imágenes sintéticas y grabaciones conocidas no son pruebas
independientes de reconocimiento ni una validación de la conexión del iPhone.
No se tomaron fotografías ni vídeos nuevos, ni se abrió la cámara física.

Para repetir:

```bash
cd /Users/sauldecos/git/IA
./ejecutar.sh pruebas
```

Algunas pruebas antiguas necesitan las capturas locales ignoradas por Git. Sin
ellas, se pueden ejecutar los módulos nuevos `tests.test_entrega` y
`tests.test_panel_entrega`, que crean sus propias escenas temporales. Los mensajes
`missing ScriptRunContext` de AppTest y los errores OpenCV de archivos corruptos
son esperados en los casos que comprueban esas situaciones.
