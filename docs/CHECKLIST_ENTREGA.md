# Checklist de entrega · Reto 07

Revisada el **4 de noviembre de 2026** contra [el enunciado aportado](ENUNCIADO.md).
Una casilla de implementación no acredita una prueba física. La fecha de entrega
se consulta en Campus; no figura una fecha concreta en el enunciado.

## Código y preparación realizable en clase

- [x] Adquisición desde cámara, fotografía y vídeo guardado como flujo simulado.
- [x] Segmentación HSV, región del tapete y extracción de siluetas/características.
- [x] Clasificación con reglas geométricas manuales y salida desconocida/ambigua.
- [x] Árbol principal y subárboles con condiciones y umbrales generados desde las reglas (`arbol.py`, modo Entrega).
- [x] Explicación por objeto, valores observados, versión y exportación de reglas.
- [x] Conteo y comparación con inventario esperado: ausentes y sobrantes.
- [x] Editor de perfil de entrega de 5–8 clases, sin borrar las nueve clases disponibles.
- [x] Referencia completa de escenas: objetos reales, correspondencias, falsos positivos y omisiones.
- [x] Evaluación de detección, clasificación e inventario; matriz de confusión y exportación JSON/CSV.
- [x] Desarrollo y prueba reservada separados por adquisición; los fotogramas de un clip permanecen juntos.
- [x] Recuperación de referencias y revisión obligatoria si cambia la segmentación.
- [x] Respaldo verificable de código, ajustes, anotaciones y datos sin entornos Python.
- [x] README, organización, instrucciones y guion de pruebas/defensa.
- [ ] Ejecutar personalmente el flujo en la web con una escena y comprobar que entiendo los resultados.
- [x] Guardado perfil de siete clases en **Entrega**, sin cúter ni Allen, una unidad esperada de cada una. Validar las cantidades en la demostración.

## Montaje y pruebas físicas (requieren casa y móvil)

- [ ] Fotografiar el montaje y medir el tapete; documentar cobertura de aproximadamente 0,50 × 0,50 m conforme al enunciado y cualquier excepción acordada con el profesor.
- [ ] Anotar cámara/modelo, lente, resolución, altura y posición fija cenital.
- [ ] Medir escala espacial con una longitud conocida y comprobar el detalle discriminante más pequeño en la imagen procesada.
- [ ] Documentar encuadre/zoom y mantenerlos fijos en la serie de evaluación.
- [ ] Comprobar iluminación en todo el tapete: sombras, reflejos y partes verdes de herramientas. Añadir luz solo si la prueba lo exige.
- [ ] Probar conexión y reconocimiento real con iPhone; registrar fluidez observada y estabilidad.
- [ ] Recoger escenas con cantidades, orientaciones, posiciones y combinaciones diferentes.
- [ ] Incluir escena vacía, ausencias y repeticiones; el juego de Allen montado cuenta como una unidad.
- [ ] Reservar adquisiciones nuevas que no se usen para ajustar reglas o segmentación.
- [ ] Anotar referencias completas, incluidas omisiones, y guardar los resultados finales.
- [ ] Si se corrigen reglas con los fallos de una prueba, pasar todo ese grupo a desarrollo y hacer otra prueba nueva.

Consulta [PRUEBAS_CASA.md](PRUEBAS_CASA.md). Los 55/55 históricos son resultados
sobre datos conocidos, no una evaluación independiente. Las pruebas de software
con cámara simulada tampoco acreditan el reconocimiento físico.

## Trabajo escrito: diez elementos exigidos

| Estado | Requisito | Material disponible / tarea pendiente |
|---|---|---|
| [ ] | 1. Contextualización y requisitos | Revisar secciones iniciales de MEMORIA y fijar clases finales. |
| [ ] | 2. Montaje físico | Añadir fotografías y medidas reales. |
| [x] | 3. Diagrama del pipeline | MEMORIA, apartado 3. Revisar su coherencia final. |
| [x] | 4. Método de segmentación | MEMORIA y GUIA_USO. |
| [x] | 5. Tabla y definición de características | REGLAS y MEMORIA; mediciones descargables en Entrega. |
| [x] | 6. Árbol de decisión utilizado | ARBOL_DECISION y diagramas generados; incluirlos legibles en el escrito. |
| [ ] | 7. Justificación experimental de parámetros y umbrales de cada función | Completar PARAMETROS_Y_EVIDENCIAS con mediciones, incluidos HSV/morfología/área/ROI. |
| [ ] | 8. Resultados sobre pruebas | Añadir escenas nuevas, configuración congelada y ejemplos de fallos. |
| [ ] | 9. Medida cuantitativa de aciertos y errores | Exportar evaluación completa; informar TP, FP, FN, clasificación e inventario. |
| [x] | 10. Código funcional bien comentado | Código y pruebas disponibles; pendiente validación final en montaje real. |

- [ ] Revisar críticamente el texto, figuras y tablas creados con LLM (uso exigido por el enunciado).
- [ ] Explicar personalmente cada característica y por qué se eligió cada umbral.
- [ ] Sustituir los apartados pendientes del borrador por evidencia; no inventar medidas ni tasas.
- [ ] Generar/revisar el documento final y colocar el enlace de vídeo en la portada.

## Vídeo, demostración y entrega

- [ ] Grabar vídeo presentado por el alumno de aproximadamente **7–10 minutos**.
- [ ] Mostrar pruebas diseñadas por el alumno: detección, identificación e inventario, además de limitaciones.
- [ ] Subir el vídeo a **YouTube con la cuenta universitaria** y comprobar que el profesor puede abrir el enlace.
- [ ] Incluir el enlace en la primera página/portada del trabajo.
- [ ] Ensayar la demostración presencial con escenas propuestas por otra persona.
- [ ] Comprobar fecha/formato de entrega en Campus.
- [ ] Crear y verificar respaldo; copiarlo fuera de este ordenador.
- [ ] Entregar código, documento y evidencias requeridas. Git no contiene los datos locales ignorados.

No se exige aquí reconocer con una mano tapando una herramienta ni resolver
solapamientos arbitrarios. Se deben explicar las limitaciones sin confundirlas
con funcionamiento correcto en posiciones u orientaciones nuevas.

## Punto de reanudación tras la revisión v4 (4 de noviembre)

El núcleo de código está implementado. La revisión v4 reconoce las 120
referencias confirmadas usadas en desarrollo; falta probarla en directo.
No hace falta seguir ampliando funciones para poder pasar a la evaluación.

- [ ] Comprobar brevemente el metro con extensiones cortas, intermedias y largas en v4.
- [ ] Guardar trabajo y ejecutar `./ejecutar.sh respaldo`; copiar el ZIP fuera del equipo.
- [ ] En la próxima sesión, grabar un vídeo nuevo reservado: siete herramientas,
  distintas colocaciones, tapete vacío, ausencias y repeticiones si hay ejemplares.
- [ ] Anotar referencias completas y exportar métricas sin ajustar reglas con ese vídeo.
- [ ] Terminar medidas/fotos del montaje, memoria y vídeo de presentación.
