# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Contrato de los extractores de metadatos por plataforma."""

from abc import ABC, abstractmethod
from typing import Any

from tamalio.modelos.fuente import Fuente
from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma


class Extractor(ABC):
    """
    Traduce el diccionario de ``yt-dlp`` de **una** plataforma a entidades :class:`Pista`.

    Cada plataforma entrega los metadatos con nombres y particularidades
    distintas (por ejemplo, SoundCloud incluye «Artista - » en el título y
    Bandcamp mezcla géneros con la ciudad del artista en ``tags``). Cada
    implementación concreta encapsula esas reglas.
    """

    @property
    @abstractmethod
    def plataforma(self) -> Plataforma:
        """Plataforma que atiende este extractor."""

    @abstractmethod
    def normalizar(self, info: dict[str, Any], fuente: Fuente) -> list[Pista]:
        """
        Convierte la respuesta de ``yt-dlp`` en una lista de pistas.

        Args:
            info: Diccionario devuelto por ``YoutubeDL.extract_info`` (pista
                individual o ``_type: playlist`` con ``entries``).
            fuente: Fuente original, por si contiene metadatos a sobrescribir.

        Returns:
            Pistas en el orden del álbum o lista. Las entradas no disponibles
            (``None`` en ``entries``) se omiten.
        """
