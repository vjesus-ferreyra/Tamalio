# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Excepción lanzada cuando una URL no pertenece a ninguna plataforma soportada."""

from tamalio.excepciones.error_tamalio import ErrorTamalio


class ErrorPlataformaNoSoportada(ErrorTamalio):
    """
    La fuente indicada no es de YouTube, YouTube Music, SoundCloud ni Bandcamp.

    Attributes:
        url: Enlace que no pudo clasificarse.
    """

    def __init__(self, url: str) -> None:
        super().__init__(
            f"La fuente «{url}» no pertenece a una plataforma soportada.",
            sugerencia=(
                "Plataformas admitidas: YouTube, YouTube Music, SoundCloud y Bandcamp. "
                "Si es un dominio propio de Bandcamp, indícalo con «plataforma» en el fichero."
            ),
        )
        self.url = url
