# Datos locales

| Carpeta | Contenido |
|---|---|
| `capturas/` | Fotos originales, escenas y fotogramas extraídos; ajustes y procedencia asociados. |
| `videos/` | Clips grabados o importados y ajustes guardados por huella del vídeo. |
| `resultados/` | Paquetes de sesión: imagen, máscara, medidas CSV, etiquetas y predicciones. |
| `etiquetas/` | Anotaciones auxiliares de las primeras capturas. |
| `evaluaciones/` | Imágenes y referencias humanas completas para medir errores de detección e inventario. |
| `importadas/` | Ubicación lógica de las fotos subidas a la web; la copia persistente se incluye al guardar la sesión. |

Las carpetas opcionales se crean cuando se necesitan. Todo el contenido de esta
carpeta, excepto este README, está excluido de Git para evitar subir vídeos grandes
y fotografías. Clonar el repositorio no recupera tus etiquetas ni tus capturas.

Conserva cada paquete completo: sus JSON y CSV se corresponden con los píxeles y
parámetros guardados. No renombres archivos sueltos ni sustituyas imágenes de una
sesión. Al reorganizar este proyecto se actualizaron las rutas de los metadatos
conservando sus fechas, las etiquetas y las huellas de imagen.

Usa `./ejecutar.sh respaldo` desde la raíz para crear una copia verificada en
`respaldos/`. Consulta la [guía de respaldos](../docs/RESPALDOS.md).
