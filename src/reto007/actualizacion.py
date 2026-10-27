"""Actualiza módulos de servidores abiertos sin borrar su trabajo pendiente."""

import importlib
import sys
from threading import RLock


_bloqueo = RLock()
_VERSION_ETIQUETADO = 2
VERSION_ACTUALIZACION = 4


def actualizar_modulos_etiquetado():
    """Migra validación y reproductor antiguos una sola vez por versión.

    Un rerun de Streamlit relee app_web.py, pero puede conservar los módulos
    importados anteriormente. Actualizamos también a sus consumidores antes de
    que la app importe sus funciones. Los píxeles, firmas, revisiones y widgets
    de session_state no se modifican, de modo que se puede guardar lo pendiente.
    """
    with _bloqueo:
        modulo = importlib.import_module("etiquetado")
        actualizado = False
        if getattr(modulo, "VERSION_ETIQUETADO", None) != _VERSION_ETIQUETADO:
            importlib.reload(modulo)
            for nombre in ("analisis", "panel_analisis"):
                consumidor = sys.modules.get(nombre)
                if consumidor is not None:
                    importlib.reload(consumidor)
            actualizado = True
        # La dependencia debe recargarse antes que el panel que importa sus
        # funciones. Las sesiones y las etiquetas pendientes siguen intactas.
        recargar_panel = False
        for nombre, version, esperada in (("video", "VERSION_VIDEO", 2), ("panel_video", "VERSION_PANEL_VIDEO", 4)):
            modulo = sys.modules.get(nombre)
            if modulo is not None and (getattr(modulo, version, None) != esperada or recargar_panel):
                importlib.reload(modulo)
                actualizado = recargar_panel = True
        return actualizado
