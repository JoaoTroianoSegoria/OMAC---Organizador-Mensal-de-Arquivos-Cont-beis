"""Camada de dados: o único lugar que lê e grava os arquivos em %APPDATA%\\OMAC."""

from .armazem import Armazem
from .arquivo import DadosIlegiveis

__all__ = ["Armazem", "DadosIlegiveis"]
