# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Extractor de metadatos para Bandcamp."""

import logging
import re
from collections import Counter
from typing import Any

from tamalio.extractores.extractor_base import ExtractorBase
from tamalio.interfaces.lector_caratula_pagina import LectorCaratulaPagina
from tamalio.modelos.caratula import Caratula
from tamalio.modelos.plataforma import Plataforma

registro = logging.getLogger(__name__)


class ExtractorBandcamp(ExtractorBase):
    """
    Reglas particulares de Bandcamp.

    - ``track_number`` es confiable, pero ``track`` a veces trae el número de
      pista pegado al título («01 - Opening Credits», «06 -X-CaliBR8»). Ese
      prefijo se quita: «Opening Credits», «X-CaliBR8».
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
    - Las pistas de un mismo álbum pueden traer carátulas distintas (álbumes que
      reúnen sencillos). Todas reciben una sola: la que más se repite (en un
      empate, la primera de las empatadas), o la que muestra la página del
      álbum si todas son distintas (ver :meth:`_caratula_coleccion`).

    Args:
        agregar_invitados: Ver :class:`ExtractorBase`.
        recortar_caratulas_video: Ver :class:`ExtractorBase`.
        lector_caratulas: Lee la carátula de la página del álbum en el caso raro
            descrito arriba. Si es ``None``, se usa la carátula de la primera pista.
    """

    # Sufijo de tamaño de las imágenes de Bandcamp: a1234567890_5.jpg
    _PATRON_TAMANO = re.compile(r"_(\d+)\.(jpg|png)$")
    # Etiquetas que nombran un sello discográfico, no un género.
    _PATRON_SELLO = re.compile(r"\b(?:records|recordings|rec\.|label|tapes|discos|disquera)$", re.IGNORECASE)
    # Número de pista pegado al título: «01 - Título», «06 -Título», «3. Título».
    # Con punto se exige un espacio después, para no partir «3.14 - Pi».
    _PATRON_NUMERO_TITULO = re.compile(r"^(?P<numero>\d{1,3})\s*(?:[-–—]|\.(?=\s))\s*(?P<titulo>\S.*)$")
    # Identificador de la imagen: «…/img/a3054183310_5.jpg» → «a3054183310».
    _PATRON_ID_IMAGEN = re.compile(r"/img/(?P<id>[^/_]+)_\d+\.(?:jpg|png)$")

    def __init__(
        self,
        agregar_invitados: bool = True,
        recortar_caratulas_video: bool = True,
        lector_caratulas: LectorCaratulaPagina | None = None,
    ) -> None:
        super().__init__(agregar_invitados, recortar_caratulas_video)
        self._lector_caratulas = lector_caratulas

    @property
    def plataforma(self) -> Plataforma:
        """Ver :attr:`Extractor.plataforma`."""
        return Plataforma.BANDCAMP

    def _es_album(self, info: dict[str, Any], entradas: list[dict[str, Any]]) -> bool:
        """Las URL ``/album/…`` llegan con el extractor ``BandcampAlbum``."""
        return info.get("extractor_key") == "BandcampAlbum" or "/album/" in str(info.get("webpage_url", ""))

    def _titulo_crudo(self, entrada: dict[str, Any]) -> str:
        """
        Título sin el número de pista que Bandcamp a veces le pega delante.

        El prefijo solo se quita si coincide con el número de la pista o si viene
        con ceros a la izquierda («01», «006»). Así se respetan títulos que de
        verdad empiezan con un número, como «100 - Gecs» en la pista 3.
        """
        titulo = super()._titulo_crudo(entrada).strip()
        coincidencia = self._PATRON_NUMERO_TITULO.match(titulo)
        if coincidencia is None:
            return titulo
        numero = coincidencia["numero"]
        if int(numero) == self._numero_pista(entrada) or (len(numero) > 1 and numero.startswith("0")):
            return coincidencia["titulo"].strip()
        return titulo

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
        """
        Elige **una** carátula para todas las pistas del álbum.

        1. La de la raíz del álbum, si ``yt-dlp`` la trae (normalmente no).
        2. La que más se repite entre las pistas. Se compara el identificador de
           la imagen (``a3054183310``) y no la URL completa, porque la misma
           imagen puede llegar con otro tamaño (``_5``, ``_10``) o servidor.
           Si hay empate entre las que más se repiten, se usa la primera de las
           empatadas en el orden de las pistas; no se consulta la página.
        3. Si todas son distintas (ninguna se repite), la que muestra la página
           del álbum, leída con ``lector_caratulas``.
        4. Si eso falla, la de la primera pista.
        """
        propia = self._caratula(info)
        if propia:
            return propia

        conteo: Counter[str] = Counter()
        representantes: dict[str, Caratula] = {}
        for entrada in entradas:
            caratula = self._caratula(entrada)
            if caratula is not None:
                clave = self._clave_imagen(caratula.url)
                conteo[clave] += 1
                representantes.setdefault(clave, caratula)

        if conteo:
            # most_common() respeta el orden de inserción entre iguales: en un
            # empate devuelve la empatada que aparece primero en el álbum.
            ((clave, veces),) = conteo.most_common(1)
            if veces > 1 or len(conteo) == 1:
                return representantes[clave]

        de_pagina = self._caratula_de_pagina(info, len(conteo))
        if de_pagina is not None:
            return de_pagina
        # Las claves conservan el orden de las pistas: la primera es la de la pista 1.
        return next(iter(representantes.values()), None)

    def _caratula_de_pagina(self, info: dict[str, Any], distintas: int) -> Caratula | None:
        """Carátula que muestra la página del álbum (último recurso de :meth:`_caratula_coleccion`)."""
        url_album = info.get("webpage_url") or info.get("original_url")
        if self._lector_caratulas is None or not url_album:
            return None
        registro.info(
            "Las pistas de «%s» traen %d carátulas distintas; se lee la del álbum en su página.",
            info.get("title") or url_album,
            distintas,
        )
        url = self._lector_caratulas.url_caratula(str(url_album))
        return self._caratula({"thumbnail": url}) if url else None

    @classmethod
    def _clave_imagen(cls, url: str) -> str:
        """Identificador de la imagen de Bandcamp, o la URL si no tiene el formato conocido."""
        coincidencia = cls._PATRON_ID_IMAGEN.search(url)
        return coincidencia["id"] if coincidencia else url
