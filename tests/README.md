# Pruebas del sistema de herramientas

Desde la raíz del repositorio:

```bash
./ejecutar.sh pruebas
```

La batería cubre segmentación, geometría, reglas, seguimiento, cámara simulada,
lectura de vídeo, controles, etiquetas, referencias completas, exportaciones,
respaldo y flujos de Streamlit. No abre la cámara física ni confirma etiquetas
reales automáticamente. Las escrituras de prueba se realizan en carpetas temporales.

`tests.test_directo_web` comprueba el controlador de captura con cámara simulada,
vídeo temporal, cierre por inactividad, exclusión entre sesiones, grabación y
el recorrido de la vista En directo. Se puede ejecutar de forma independiente:

```bash
./ejecutar.sh pruebas tests.test_directo_web
```

Algunas pruebas de regresión utilizan las capturas locales del proyecto. No están
en Git: para ejecutar toda la batería después de clonar, recupera los datos del
respaldo. Sin esas capturas puedes ejecutar las pruebas nuevas con imágenes sintéticas:

```bash
./ejecutar.sh pruebas tests.test_entrega tests.test_panel_entrega
```

`tests.test_entrega` comprueba métricas, perfiles, árboles y respaldos;
`tests.test_panel_entrega` recorre la interfaz de preparación y evaluación.
Los mensajes sobre archivos de vídeo corruptos y `missing ScriptRunContext`
son esperados en los casos que simulan esos errores.

Superar las pruebas de software no sustituye la validación del iPhone ni el
reconocimiento con escenas nuevas. Consulta la [checklist](../docs/CHECKLIST_ENTREGA.md).
