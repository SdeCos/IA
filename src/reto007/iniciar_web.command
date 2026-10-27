#!/bin/bash
# Compatible con doble clic en Finder y ejecución desde cualquier carpeta.
set -euo pipefail
cd -- "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [[ ! -x .venv-web/bin/python ]]; then
    echo "Primero prepara el entorno web con:"
    printf '  bash "%s/configurar_web.sh"\n' "$PWD"
    if [[ -t 0 ]]; then read -r -p "Pulsa Intro para cerrar."; fi
    exit 1
fi
if ! .venv-web/bin/python -c 'import streamlit, cv2, numpy' >/dev/null 2>&1; then
    echo "Faltan dependencias. Ejecuta configurar_web.sh y vuelve a abrir este archivo."
    if [[ -t 0 ]]; then read -r -p "Pulsa Intro para cerrar."; fi
    exit 1
fi
if [[ ! -f app_web.py ]]; then
    echo "No se encuentra app_web.py en esta carpeta."
    exit 1
fi

echo "Abriendo la interfaz local en http://127.0.0.1:8501"
echo "Mantén esta terminal abierta. Pulsa Ctrl+C para detener la web."
exec .venv-web/bin/python -m streamlit run app_web.py \
    --server.address=127.0.0.1 \
    --server.port=8501 \
    --server.headless=false \
    --server.showEmailPrompt=false \
    --browser.gatherUsageStats=false
