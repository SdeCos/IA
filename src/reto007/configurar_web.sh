#!/bin/bash
# Prepara exclusivamente el entorno de la interfaz web.
set -euo pipefail
cd -- "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [[ ! -x .venv-web/bin/python ]]; then
    if [[ -n "${PYTHON_WEB:-}" ]]; then
        interprete_web="$PYTHON_WEB"
    elif [[ -x /opt/homebrew/bin/python3.13 ]]; then
        interprete_web=/opt/homebrew/bin/python3.13
    elif command -v python3.13 >/dev/null 2>&1; then
        interprete_web="$(command -v python3.13)"
    else
        echo "Instala Python 3.13 o indica su ruta con PYTHON_WEB y vuelve a ejecutar este script."
        echo 'Ejemplo: PYTHON_WEB="/ruta/a/python3.13" ./configurar_web.sh'
        exit 1
    fi
    "$interprete_web" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else "Se necesita Python 3.13 para este entorno probado.")'
    "$interprete_web" -m venv .venv-web
fi

.venv-web/bin/python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else "El entorno .venv-web debe usar Python 3.13.")'
.venv-web/bin/python -m pip install --no-cache-dir -r requirements-web.txt
.venv-web/bin/python -m pip check
echo "Entorno listo. Abre iniciar_web.command para iniciar la interfaz."
