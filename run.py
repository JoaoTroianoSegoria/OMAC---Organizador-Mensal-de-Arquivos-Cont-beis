"""Ponto de entrada do .exe (o PyInstaller precisa de um script, não de um pacote)."""

import sys

from omac.app import main

if __name__ == "__main__":
    sys.exit(main())
