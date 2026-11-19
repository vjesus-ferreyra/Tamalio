# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Extractor de metadatos para SoundCloud."""

from typing import Any

from tamalio.extractores.extractor_base import ExtractorBase
from tamalio.modelos.caratula import Caratula
from tamalio.modelos.plataforma import Plataforma


class ExtractorSoundcloud(ExtractorBase):
    """
    Reglas particulares de SoundCloud.

    - El título suele incluir el artista («Klaypex - Lights»); la clase base
      quita el prefijo cuando coincide con ``artists``.
    - El usuario que sube (``uploader``) no siempre es el artista: en
      «John Kenza - Nightmare» lo subió «Ryleo», pero ``artists`` dice «John Kenza».
    - Un *set* es álbum si ``album_type`` lo indica o si sus pistas declaran ``album``.
    - La carátula de mayor resolución es la miniatura con ``id == "original"``.
    """

    #: Valores de ``album_type`` que representan un lanzamiento (no una lista personal).
    TIPOS_ALBUM = frozenset({"album", "ep", "single", "compilation"})

    @property
    def plataforma(self) -> Plataforma:
        """Ver :attr:`Extractor.plataforma`."""
        return Plataforma.SOUNDCLOUD

    def _es_album(self, info: dict[str, Any], entradas: list[dict[str, Any]]) -> bool:
        """Álbum si ``album_type`` es de lanzamiento o si las pistas traen ``album``."""
        if str(info.get("album_type") or "").lower() in self.TIPOS_ALBUM:
            return True
        return bool(entradas) and all(entrada.get("album") for entrada in entradas)

    def _caratula(self, entrada: dict[str, Any]) -> Caratula | None:
        """Miniatura ``original`` con ``t500x500`` y ``crop`` de respaldo."""
        return self._mejor_miniatura(entrada)

    def _caratula_coleccion(self, info: dict[str, Any], entradas: list[dict[str, Any]]) -> Caratula | None:
        """Carátula del *set*; si no tiene, la de la primera pista."""
        return self._mejor_miniatura(info) or (self._mejor_miniatura(entradas[0]) if entradas else None)

    @staticmethod
    def _mejor_miniatura(datos: dict[str, Any]) -> Caratula | None:
        """Elige ``original`` → ``t500x500`` → ``crop`` → ``thumbnail``."""
        por_id = {m.get("id"): m["url"] for m in (datos.get("thumbnails") or []) if m.get("url")}
        orden = [por_id.get("original"), por_id.get("t500x500"), por_id.get("crop"), datos.get("thumbnail")]
        urls = [url for url in orden if url]
        if not urls:
            return None
        return Caratula(url=urls[0], alternativas=tuple(urls[1:]))
