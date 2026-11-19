# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""
Punto de entrada de la aplicación.

Permite ejecutar Tamalio de dos formas equivalentes:

- ``python -m tamalio …``  (gracias a este fichero ``__main__``).
- ``tamalio …``            (comando instalado por ``[project.scripts]`` en
  ``pyproject.toml``, que apunta a :func:`principal`).
"""

import sys

from tamalio.aplicacion import Aplicacion


def principal(argumentos: list[str] | None = None) -> int:
    """
    Crea la aplicación y la ejecuta con los argumentos de la línea de comandos.

    Args:
        argumentos: Lista de argumentos sin el nombre del programa. Si es
            ``None`` se usan los de ``sys.argv``.

    Returns:
        Código de salida del proceso (``0`` = éxito).
    """
    return Aplicacion().ejecutar(argumentos)


if __name__ == "__main__":
    # ``sys.exit`` propaga el código de salida al sistema operativo.
    sys.exit(principal())
