"""Extractor de metadatos para Bandcamp."""

import re
from typing import Any

from tamalio.extractores.extractor_base import ExtractorBase
from tamalio.modelos.caratula import Caratula
from tamalio.modelos.plataforma import Plataforma


class ExtractorBandcamp(ExtractorBase):
    """
    Reglas particulares de Bandcamp.

    - ``track`` ya viene limpio y ``track_number`` es confiable.
    - ``tags`` mezcla géneros (siempre en minúsculas: «aether pop»,
      «electronic») con la ubicación del artista (con mayúsculas: «Houston»).
      Solo las etiquetas en minúsculas se toman como géneros y se escriben en
      formato título («Aether Pop»).
    - Las etiquetas que son sellos discográficos («Ed Banger Records»,
      «Monstercat Recordings»…) tampoco son géneros y se descartan.
    - El artista puede venir como un solo texto con varios nombres
      («Justice, Tame Impala, SZA, Grand Theft Auto VI & King Gizzard & the
      Lizard Wizard»). ``yt-dlp`` solo lo corta por comas, así que Tamalio
      vuelve a separar cada parte respetando los «& the …» de los nombres de banda.
    - La miniatura ``…_5.jpg`` mide 700 px; cambiando el sufijo a ``_0`` se
      obtiene la imagen **original** a máxima resolución (``_10`` = 1200 px).
    """

    # Sufijo de tamaño de las imágenes de Bandcamp: a1234567890_5.jpg
    _PATRON_TAMANO = re.compile(r"_(\d+)\.(jpg|png)$")
    # Etiquetas que nombran un sello discográfico, no un género.
    _PATRON_SELLO = re.compile(r"\b(?:records|recordings|rec\.|label|tapes|discos|disquera)$", re.IGNORECASE)

    @property
    def plataforma(self) -> Plataforma:
        """Ver :attr:`Extractor.plataforma`."""
        return Plataforma.BANDCAMP

    def _es_album(self, info: dict[str, Any], entradas: list[dict[str, Any]]) -> bool:
        """Las URL ``/album/…`` llegan con el extractor ``BandcampAlbum``."""
        return info.get("extractor_key") == "BandcampAlbum" or "/album/" in str(info.get("webpage_url", ""))

    def _artistas_crudos(self, entrada: dict[str, Any]) -> list[str]:
        """
        Separa cada artista declarado también por «&», «x» o «×».

        Los artistas del álbum se protegen para no partir nombres como
        «Simon & Garfunkel» cuando la plataforma los declara así.
        """
        protegidos = [str(a) for a in entrada.get("album_artists") or []]
        if entrada.get("album_artist"):
            protegidos.append(str(entrada["album_artist"]))
        separados: list[str] = []
        for nombre in super()._artistas_crudos(entrada):
            separados.extend(self._dividir_artistas(nombre, protegidos))
        return self._sin_duplicados(separados)

    def _generos(self, entrada: dict[str, Any]) -> list[str]:
        """Etiquetas en minúsculas (géneros), sin la ubicación ni sellos; máximo cinco."""
        generos = [
            etiqueta.title()
            for etiqueta in (entrada.get("tags") or [])
            if etiqueta and etiqueta == etiqueta.lower() and not self._PATRON_SELLO.search(etiqueta)
        ]
        return self._sin_duplicados(generos)[:5] or super()._generos(entrada)

    def _caratula(self, entrada: dict[str, Any]) -> Caratula | None:
        """Imagen original (``_0``) con 1200 px (``_10``) y la recibida como respaldo."""
        url = entrada.get("thumbnail") or next(
            (m["url"] for m in (entrada.get("thumbnails") or []) if m.get("url")), None
        )
        if not url:
            return None
        if not self._PATRON_TAMANO.search(url):
            return Caratula(url=url)
        original = self._PATRON_TAMANO.sub(r"_0.\2", url)
        grande = self._PATRON_TAMANO.sub(r"_10.\2", url)
        return Caratula(url=original, alternativas=(grande, url))

    def _caratula_coleccion(self, info: dict[str, Any], entradas: list[dict[str, Any]]) -> Caratula | None:
        """Bandcamp no trae miniaturas en la raíz del álbum: se usa la de la primera pista."""
        for datos in (info, *entradas[:1]):
            caratula = self._caratula(datos)
            if caratula:
                return caratula
        return None
