# Configuración global

- `configuracion.json`: parámetros HSV, morfología, tapete y zoom predeterminados.
- `herramientas.json`: nombres disponibles para etiquetar. Añadir un nombre no crea una regla de reconocimiento.
- `entrega.json`: perfil opcional de 5–8 clases y sus cantidades esperadas. Se crea desde **web → Entrega**.

Estos archivos se pueden versionar en Git. La aplicación guarda aquí los ajustes
globales y mantiene los parámetros específicos de cada foto, sesión o vídeo junto
a sus datos, dentro de `datos/`. No traslades los JSON de una sesión a esta carpeta.

Para aplicar un fichero explícitamente:

```bash
./iniciar_directo.command --camara 1 --config config/configuracion.json
```

Los comandos se ejecutan desde la raíz. El inventario de las siete herramientas
se guarda en [`entrega.json`](entrega.json).
