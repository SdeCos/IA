#!/bin/bash
# Doble clic: cámara 1; desde terminal admite --camara, --config, --inventario.
set -euo pipefail
cd -- "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [[ ! -x .venv-web/bin/python ]]; then
    echo "Prepara primero el entorno: bash configurar_web.sh"
    exit 1
fi
exec .venv-web/bin/python directo.py "$@"
