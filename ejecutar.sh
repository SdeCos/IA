#!/bin/bash
# Entrada común: encuentra el proyecto y sus módulos desde cualquier carpeta.
set -euo pipefail
cd -- "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ ! -x .venv-web/bin/python ]]; then
    echo "Prepara primero el entorno: bash configurar_web.sh"
    exit 1
fi

comando="${1:-ayuda}"
if [[ $# -gt 0 ]]; then shift; fi
case "$comando" in
    directo|calibrador|detector)
        exec .venv-web/bin/python -m "herramientas.cli.$comando" "$@" ;;
    arbol)
        exec .venv-web/bin/python -m herramientas.vision.arbol "$@" ;;
    respaldo)
        exec .venv-web/bin/python -m herramientas.datos.respaldo "$@" ;;
    pruebas)
        if [[ $# -eq 0 ]]; then set -- discover -s tests -t .; fi
        exec .venv-web/bin/python -m unittest "$@" ;;
    web)
        exec .venv-web/bin/python -m streamlit run src/herramientas/web/app_web.py \
            --server.address=127.0.0.1 --server.port=8501 \
            --server.headless=false --server.showEmailPrompt=false \
            --browser.gatherUsageStats=false "$@" ;;
    ayuda|--help|-h)
        echo "Uso: ./ejecutar.sh {web|directo|calibrador|detector|arbol|respaldo|pruebas} [opciones]"
        echo "Ejemplo: ./ejecutar.sh directo --ultimo-video" ;;
    *) echo "Comando desconocido: $comando. Consulta ./ejecutar.sh --help" >&2; exit 2 ;;
esac
