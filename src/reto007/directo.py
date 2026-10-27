"""Reconocimiento con cámara, vídeo como fuente simulada o fotografía guardada."""

import sys
from calibrador import main as calibrar


def main(argv=None):
    return calibrar(["--reconocer", *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    raise SystemExit(main())
