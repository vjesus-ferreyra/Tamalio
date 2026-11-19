# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Fábrica que entrega el extractor adecuado para cada plataforma."""

from tamalio.extractores.extractor_bandcamp import ExtractorBandcamp
from tamalio.extractores.extractor_soundcloud import ExtractorSoundcloud
from tamalio.extractores.extractor_youtube import ExtractorYoutube
from tamalio.interfaces.extractor import Extractor
from tamalio.modelos.plataforma import Plataforma


class FabricaExtractores:
    """
    Patrón *Factory*: centraliza la creación de extractores.

    Agregar una plataforma nueva consiste en crear su extractor y registrarlo
    aquí, sin modificar al resto de la aplicación (principio abierto/cerrado).

    Args:
        agregar_invitados: Se pasa a cada extractor (ver :class:`ExtractorBase`).
        recortar_caratulas_video: Se pasa a cada extractor.
    """

    def __init__(self, agregar_invitados: bool = True, recortar_caratulas_video: bool = True) -> None:
        opciones = {"agregar_invitados": agregar_invitados, "recortar_caratulas_video": recortar_caratulas_video}
        # Se crean una sola vez: los extractores no guardan estado entre llamadas.
        self._extractores: dict[Plataforma, Extractor] = {
            Plataforma.YOUTUBE: ExtractorYoutube(**opciones),
            Plataforma.SOUNDCLOUD: ExtractorSoundcloud(**opciones),
            Plataforma.BANDCAMP: ExtractorBandcamp(**opciones),
        }

    def obtener(self, plataforma: Plataforma) -> Extractor:
        """Devuelve el extractor registrado para ``plataforma``."""
        return self._extractores[plataforma]
