"""``ArgumentParser`` con textos de ayuda y errores en español."""

import argparse
import sys
from typing import ClassVar, NoReturn


class ParserEspanol(argparse.ArgumentParser):
    """
    Traduce al español los textos fijos de :mod:`argparse`.

    ``argparse`` genera algunas frases en inglés («usage:», «options:», «the
    following arguments are required»…). Esta subclase las sustituye al
    formatear la ayuda y los mensajes de error.
    """

    #: Frases de argparse → traducción.
    TRADUCCIONES: ClassVar[dict[str, str]] = {
        "usage:": "uso:",
        "positional arguments:": "argumentos:",
        "options:": "opciones:",
        "the following arguments are required:": "faltan los argumentos obligatorios:",
        "invalid choice:": "opción no válida:",
        "choose from": "elige entre",
        "unrecognized arguments:": "argumentos no reconocidos:",
        "expected one argument": "se esperaba un valor",
        "expected at least one argument": "se esperaba al menos un valor",
        "not allowed with argument": "no se permite junto con",
        "one of the arguments": "uno de los argumentos",
        "is required": "es obligatorio",
        "invalid int value:": "número entero no válido:",
        "maybe you meant": "¿quisiste decir",
        "argument ": "argumento ",
    }

    def _traducir(self, texto: str) -> str:
        for original, traducido in self.TRADUCCIONES.items():
            texto = texto.replace(original, traducido)
        return texto

    def format_usage(self, formatter: argparse.HelpFormatter | None = None) -> str:
        """Uso abreviado en español (misma firma que ``ArgumentParser`` en Python ≥ 3.14)."""
        return self._traducir(super().format_usage(formatter))

    def format_help(self, formatter: argparse.HelpFormatter | None = None) -> str:
        """Ayuda completa en español (misma firma que ``ArgumentParser`` en Python ≥ 3.14)."""
        return self._traducir(super().format_help(formatter))

    def error(self, message: str) -> NoReturn:
        """Muestra el uso y el error traducido; termina con código 2 (convención POSIX)."""
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {self._traducir(message)}\n")
