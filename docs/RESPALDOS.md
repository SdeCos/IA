# Copias de seguridad y traslado

Git excluye `datos/capturas/`, `datos/videos/`, `datos/resultados/`, `datos/etiquetas/`, `datos/evaluaciones/`,
`respaldos/` y los entornos Python. Las etiquetas manuales y las pruebas reales
no se recuperan clonando el repositorio.

Detén grabaciones y evita guardar sesiones durante la copia. Desde la raíz del repositorio `IA/`:

```bash
./ejecutar.sh respaldo
```

Crea un ZIP nuevo en `respaldos/` con código, documentación, configuración,
perfil de entrega si existe, datos y anotaciones. No incluye entornos, cachés,
credenciales ni otras copias de seguridad. El respaldo histórico de Git se
conserva aparte en `respaldos/historial_git/`.
Cada archivo tiene un hash SHA-256 en el manifiesto; se verifica al finalizar.
No se sobrescriben copias previas. Si se interrumpe, no des por bueno un ZIP
parcial: verifícalo o crea otro con un nombre nuevo.

También puedes indicar un destino nuevo o verificar una copia existente:

```bash
./ejecutar.sh respaldo --salida "/ruta/permitida/reto007_copia.zip"
./ejecutar.sh respaldo --verificar "/ruta/reto007_copia.zip"
```

Copia el ZIP a un disco externo o almacenamiento personal. Contiene tus imágenes;
no lo publiques en Git por accidente. Comprueba espacio libre: la grabación
original ocupa unos 164 MiB y las imágenes/sesiones añaden más datos.

Para recuperar: verifica y extrae en una **carpeta nueva**, conserva la estructura,
y ejecuta `bash configurar_web.sh`. Los datos que usan rutas absolutas antiguas
pueden requerir abrir la copia de la imagen desde el nuevo destino. Las referencias
completas de `datos/evaluaciones/` incluyen su propia imagen y grupo, por lo que la
revisión de esos paquetes no necesita la ruta antigua. No borres el respaldo
hasta comprobar tus fotos, sesiones y evaluaciones.
