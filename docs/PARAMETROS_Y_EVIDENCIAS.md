# Parámetros, umbrales y evidencia pendiente

El enunciado exige justificación experimental de parámetros y umbrales **de cada
función**, no solamente los cortes de clasificación. Esta tabla es un registro
para completar con mediciones reales, no una afirmación de que se hayan probado
todas las opciones. La iluminación física permanece pendiente de verificar.

| Parámetro / etapa | Función y motivo | Evidencia disponible | Comprobación que falta |
|---|---|---|---|
| Resolución y ancho procesado (800 px) | Detalle frente a coste por fotograma | Procesamiento común en `vision.py` | Medir escala y detalle más fino; FPS del montaje real. |
| Zoom/encuadre | Recorte digital de la zona útil | Control numérico y configuración guardada | Confirmar cobertura completa y fijar escala. |
| H, S, V mínimos/máximos | Separar el verde del tapete | Calibración visual en escenas de desarrollo | Registrar intervalos del fondo iluminado/sombreado; comprobar partes verdes de objetos. |
| Suavizado gaussiano | Reducir ruido antes de segmentar | Control de kernel impar | Comparar sin suavizado y kernel pequeño: pérdida de vástagos y ruido. |
| Apertura | Eliminar puntos pequeños | Iteraciones configurables, cero permite desactivar | Contar falsos positivos frente a pérdida de partes finas. |
| Cierre | Tapar discontinuidades pequeñas | Kernel e iteraciones configurables | Verificar que no une herramientas ni cambia rasgos útiles. |
| Región del tapete | Excluir mesa y exterior | Corrección comprobada en fotografías amplias de desarrollo | Probar tapete completo, zonas sombreadas y objetos próximos al borde. |
| Margen del tapete | Evitar bordes mal segmentados | Margen en píxeles procesados | Medir descartes y documentar distancia útil al borde. |
| Área mínima | Filtrar componentes demasiado pequeños | Desbarbador antiguo cercano al mínimo de 1000 px² | Medir mínimo de cada herramienta en distintas posiciones; no fijarlo por comodidad. |
| Contornos externos | Geometría del borde exterior | Definido en visión/geometría | Justificar por qué huecos interiores no se usan; no confundir área de contorno y píxeles blancos. |
| Perfil de 40 secciones | Describir anchura a lo largo del eje principal | `geometria.py`, descriptores en REGLAS | Estabilidad ante rotaciones físicas y aperturas de alicate/calibre. |
| Intervalos R1–R9 | Identificar una única clase por ocho rasgos | REGLAS y tabla descargable de medidas por clase | Ampliar desarrollo y documentar separaciones/solapamientos; luego validar sin retocar. |
| Bandas AR ±0,15 y otros ±0,02 | Abstención cerca de fronteras | Decisión manual explícita | Medir rechazos y confusiones; no interpretarlas como probabilidad. |
| Seguimiento: distancia 80 px, área 0,5–2, pérdida 5 fotogramas | Asociar pistas temporalmente | Pruebas de lógica; no determina nombres | Revisar movimientos/cruces. Los ID temporales no son identidades garantizadas. |

Para cada experimento anota: grupo de adquisición, parámetros, medición,
observación, decisión y motivo. Compara opciones con el mismo material de
**desarrollo**. No cambies parámetros usando escenas reservadas para prueba.
La tabla de mediciones del modo Entrega muestra mínimo/máximo y número de
muestras confirmadas; no es por sí sola una justificación de generalización.

La base histórica tiene 55 objetos de 12 imágenes y cuatro procedencias
relacionadas, todas de desarrollo. El 55/55 no justifica automáticamente cada
parámetro de preprocesamiento. Si un umbral cambia, actualiza su versión,
procedencia de desarrollo y discusión de efectos antes del informe final.
