# Árbol de decisión ejecutado

El método es un sistema experto de **reglas manuales sobre características
explícitas**, sin aprendizaje de un clasificador. El árbol principal valida
la entrada, evalúa todos los subárboles y resuelve coincidencias. Cada subárbol
comprueba secuencialmente los ocho intervalos de una herramienta.

Los diagramas completos se consultan en **web → Entrega → Ver árbol y condiciones**.
El panel permite descargar DOT, un formato de diagramas editable/renderizable
con Graphviz. La web lo renderiza sin instalar el ejecutable Graphviz.

- [Árbol principal](arboles/principal.dot).
- [R1 Metro](arboles/R1.dot), [R2 Cúter](arboles/R2.dot), [R3 Nivel](arboles/R3.dot).
- [R4 Desbarbador](arboles/R4.dot), [R5 Destornillador](arboles/R5.dot).
- [R6 Calibre](arboles/R6.dot), [R7 Martillo](arboles/R7.dot).
- [R8 Juego de Allen](arboles/R8.dot), [R9 Alicate](arboles/R9.dot).
- [R10 Martillo de canto](arboles/R10.dot), [R11 Nivel de canto](arboles/R11.dot).
- [R12 Metro con cinta fina](arboles/R12.dot), [R13 Metro con cinta fina corta](arboles/R13.dot).
- [R14 Metro con cinta plana corta](arboles/R14.dot), [R15 Metro con cinta plana larga](arboles/R15.dot).
- [Especificación con versión, condiciones y márgenes](arboles/reglas.json).

## Cómo leerlo

1. La entrada debe tener ocho valores finitos, dominios físicos correctos,
   versión de geometría compatible y extensión no superior a solidez + 0,02.
2. Para cada regla se parte de `Interior = sí`. Si una condición no entra
   siquiera en el intervalo compatible, la regla queda descartada.
3. Si cumple compatibilidad pero queda en una banda fronteriza, se conserva
   compatibilidad y se marca `Interior = no`. Las condiciones restantes se
   siguen comprobando. Un sí posterior no vuelve a poner Interior a sí.
4. Tras evaluar todas las reglas, se agrupan por clase: ninguna compatible →
   desconocida; varias clases compatibles → ambigua. Si solo hay una clase
   compatible, se identifica cuando al menos una de sus reglas es interior.
   Varias variantes compatibles de una misma clase no generan ambigüedad entre
   clases. Se conserva la traza completa y se explica la primera regla interior.

Los nodos muestran los límites **ya aplicados los márgenes** y distinguen `<`
de `≤`. Por ejemplo, un límite superior de AR de 1,6 tiene compatibilidad hasta
1,75 e interior estrictamente por debajo de 1,45, salvo las excepciones físicas.
Las bandas son tolerancias elegidas manualmente, no probabilidades.

La ejecución calcula los ocho detalles incluso si uno falla, para explicar la
predicción; el subárbol representa una lógica de decisión equivalente. No es un
árbol aprendido ni un clasificador que acepta la primera regla coincidente.

## Mantener código y documento sincronizados

Los diagramas se generan desde `snapshot_reglas()` y los mismos márgenes usados
por el clasificador. Si cambias reglas, regenera los archivos desde la raíz del repositorio `IA/`:

```bash
./ejecutar.sh arbol
```

Las exportaciones de reconocimiento fotográfico y del modo Directo incluyen
árbol y subárboles. La justificación geométrica y los intervalos base están en
[REGLAS.md](REGLAS.md); las comprobaciones experimentales pendientes están en
[PARAMETROS_Y_EVIDENCIAS.md](PARAMETROS_Y_EVIDENCIAS.md). Un diagrama correcto no
sustituye la validación con escenas nuevas.
