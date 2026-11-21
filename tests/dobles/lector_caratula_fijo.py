# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Lector de carátulas que no abre ningún navegador: devuelve una URL fija."""

from tamalio.interfaces.lector_caratula_pagina import LectorCaratulaPagina


class LectorCaratulaFijo(LectorCaratulaPagina):
    """
    Devuelve siempre ``url`` y anota en :attr:`consultadas` cada página pedida.

    Args:
        url: Lo que «muestra» la página; ``None`` simula que no se pudo leer.
    """

    def __init__(self, url: str | None) -> None:
        self._url = url
        self.consultadas: list[str] = []

    def url_caratula(self, url_pagina: str) -> str | None:
        """Ver :meth:`LectorCaratulaPagina.url_caratula`."""
        self.consultadas.append(url_pagina)
        return self._url
