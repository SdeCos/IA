# Sesión de pruebas en casa

## Antes de grabar

1. Elige 5–8 clases en la web, modo **Entrega**, y guarda el inventario esperado.
   Un conjunto montado de Allen cuenta como una herramienta. La selección no elimina
   reglas: una clase reconocida fuera del inventario se mostrará como sobrante.
2. Fija cámara, tapete y encuadre. Fotografía el montaje, mide altura y tapete,
   anota resolución/lente y una longitud conocida para medir píxeles/mm.
3. Comprueba que se ve toda la zona útil y que las herramientas finas conservan
   detalle en la imagen procesada. El zoom digital recorta; no añade resolución.
4. En el montaje previo, el iPhone aparecía como cámara 1 con Photo Booth abierto.
   Verifica la imagen allí y lanza, desde la raíz del repositorio `IA/`:

```bash
./iniciar_directo.command --camara 1
```

El perfil `config/entrega.json` se carga si existe. Para otro inventario usa
`--inventario ejemplos/inventario.json`; para contar sin comparar,
`--sin-inventario`. No son compatibles entre sí.

## Clip de desarrollo

Pulsa R para empezar y R para terminar. Cambia posición y orientación, deja
pausas de 2–3 segundos sin manos. Prueba centro y bordes interiores, con los
objetos completos y separados. Ajusta segmentación y reglas solo con este material.
Comprueba especialmente vástagos finos, reflejos, mordazas y zonas verdes.
Anota ajustes y fallos. Las etiquetas manuales no entrenan el programa.

## Prueba final reservada

Congela parámetros y reglas. Graba otro clip o toma fotos de **disposiciones
nuevas**. Como propuesta práctica, 10–15 escenas distintas; no es un mínimo
exigido para herramientas. Incluye:

| Escena | Cambio | Qué comprobar |
|---|---|---|
| Vacía | Sin herramientas | Cero detecciones e inventario con faltantes correctos. |
| Completa | Una unidad de cada clase prevista | Identificación e inventario exactos. |
| Rotaciones | Herramientas giradas en varias direcciones | Clases estables, sin usar coordenadas. |
| Traslaciones | Distribución distinta sobre el tapete | Sin omitir herramientas finas o próximas al borde útil. |
| Subconjuntos | Retirar diferentes herramientas | Avisos de ausencia correctos. |
| Repetidas | Dos ejemplares reconocibles de una clase | Cantidad dos y sobrante cuando se esperaba uno. |
| Mixta | Cambiar cantidad y combinación | Detección, nombres y comparación independientes. |
| Limitaciones | Contacto, mano, reflejo o recorte | Registrar el fallo; evaluar aparte de las escenas con siluetas completas. |

No simules repeticiones contando dos veces la misma pista de vídeo. Si no tienes
dos ejemplares, deja la prueba física de repetidos pendiente; una prueba sintética
solo demuestra la lógica de conteo.

## En clase: anotar y evaluar

1. Abre la web. En Vídeos, pausa en una disposición estable y extrae una foto.
2. En Fotografías → Reconocimiento automático revisa el resultado y el inventario esperado.
3. Abre **Evaluar la escena completa**. Escribe todas las herramientas reales,
   una por línea, incluso si no tienen contorno. Repite nombres si hay duplicados.
4. Para cada detección selecciona qué objeto real representa. Una herramienta
   real solo puede asociarse una vez. Un contorno de sombra, fragmento o unión
   de herramientas se marca como falsa detección; las herramientas sin una
   silueta completa y separada asociada son omisiones. Aplica el mismo criterio
   en todas las escenas; no emparejes solo por el nombre predicho.
5. Una escena vacía tiene lista vacía. Revisa también todas las falsas detecciones.
6. Marca reserva de prueba solo si todo el grupo de adquisición se apartó antes
   del ajuste. No basta con que el nombre del archivo sea nuevo.
7. Confirma y guarda. Las etiquetas del calibrador y esta referencia son distintas:
   la segunda permite registrar lo que el detector NO encontró.
8. Pulsa **Evaluar escenas completas** y descarga JSON, CSV por escena y CSV de
   objetos. Repite la evaluación tras cualquier cambio; no es un informe en vivo.

Las referencias se recuperan al abrir los mismos píxeles. Si cambias los ajustes,
las correspondencias se proponen de nuevo sin confirmación. El evaluador utiliza
los ajustes guardados en cada referencia y excluye la que ya no reproduzca su firma.
Cambiar reglas recalcula las predicciones; guarda una nueva exportación con su versión.

Si un fallo se usa para retocar el sistema, desmarca la reserva de esa adquisición:
todo su grupo pasa a desarrollo. Esta operación es conservadora: volver a marcar
una imagen como prueba no borra su uso previo para desarrollo. Recoge otra adquisición.

## Interpretar las métricas

- TP: objeto real asociado a una detección completa; FP: detección no asociada;
  FN: objeto real sin detección asociada.
- Precisión = TP/(TP+FP); exhaustividad = TP/(TP+FN).
- Clasificación = nombres correctos/TP. Incluye desconocidos como no acertados.
- Identificación completa = nombres correctos/objetos reales; penaliza omisiones.
- Inventario exacto: todas las cantidades predichas coinciden con las reales,
  sin desconocidos. Puede acertar por compensación de errores: lee también FP/FN.
- Avisos correctos: ausencias/sobrantes predichos coinciden con los reales respecto
  al inventario esperado; no aplicable si no se definió ese inventario.
- Denominador cero: no aplicable, nunca un 100 % inventado.

Los informes agrupados suman TP/FP/FN y aciertos (no promedian porcentajes de
escenas de tamaños distintos). Informan número de escenas y grupos. Un vídeo
con muchos fotogramas sigue siendo una sola adquisición relacionada.
