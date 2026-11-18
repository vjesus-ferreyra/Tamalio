"""Extractor de metadatos para YouTube y YouTube Music."""

from typing import Any

from tamalio.extractores.extractor_base import ExtractorBase
from tamalio.modelos.caratula import Caratula
from tamalio.modelos.plataforma import Plataforma


class ExtractorYoutube(ExtractorBase):
    """
    Reglas particulares de YouTube / YouTube Music.

    - Las pistas «Topic» (``Provided to YouTube by …``) traen ``track``,
      ``artists`` y ``album``; los videos oficiales no, así que el artista se
      deduce del prefijo del título y el álbum del contexto.
    - ``artists`` puede venir repetido (``["ABOKAI", "ABOKAI", "ABOKAI"]``);
      la clase base elimina los duplicados.
    - Un álbum de YouTube Music es una lista cuyo ID empieza con ``OLAK5uy_``.
    - **Carátula del álbum**: es el objeto **penúltimo** del arreglo raíz
      ``thumbnails`` (al mismo nivel que ``entries``); el último se usa como respaldo.
    - Carátula de una pista suelta: la miniatura de mayor preferencia,
      recortada a 1:1 porque YouTube la entrega en 16:9.
    """

    #: Prefijo de los IDs de listas que YouTube Music usa para álbumes y EP.
    PREFIJO_ALBUM = "OLAK5uy_"

    @property
    def plataforma(self) -> Plataforma:
        """Ver :attr:`Extractor.plataforma`."""
        return Plataforma.YOUTUBE

    def _titulo_crudo(self, entrada: dict[str, Any]) -> str:
        """Prioriza ``track`` y ``alt_title`` (datos musicales) sobre el título del video."""
        return str(entrada.get("track") or entrada.get("alt_title") or entrada.get("title") or "Sin título")

    def _artista_respaldo(self, entrada: dict[str, Any]) -> str:
        """Nombre del canal sin el sufijo « - Topic»."""
        canal = str(entrada.get("uploader") or entrada.get("channel") or "Artista desconocido")
        return canal.removesuffix(" - Topic")

    def _url_pista(self, entrada: dict[str, Any]) -> str:
        """URL canónica en ``www.youtube.com`` (igual para YouTube Music)."""
        return f"https://www.youtube.com/watch?v={entrada['id']}"

    def _es_album(self, info: dict[str, Any], entradas: list[dict[str, Any]]) -> bool:
        """Es álbum si el ID de la lista es de YouTube Music (``OLAK5uy_…``)."""
        return str(info.get("id") or "").startswith(self.PREFIJO_ALBUM)

    def _caratula_coleccion(self, info: dict[str, Any], entradas: list[dict[str, Any]]) -> Caratula | None:
        """Penúltima miniatura de la raíz (``len - 2``); las demás quedan como respaldo."""
        miniaturas = [m for m in (info.get("thumbnails") or []) if m.get("url")]
        if not miniaturas:
            return None
        if len(miniaturas) >= 2:
            principal = miniaturas[-2]
            respaldo = [miniaturas[-1], *reversed(miniaturas[:-2])]
        else:
            principal, respaldo = miniaturas[0], []
        return Caratula(url=principal["url"], alternativas=tuple(m["url"] for m in respaldo))

    def _caratula(self, entrada: dict[str, Any]) -> Caratula | None:
        """Miniatura de mayor preferencia/resolución del video, recortada a cuadrado."""
        miniaturas = [m for m in (entrada.get("thumbnails") or []) if m.get("url")]
        if not miniaturas:
            url = entrada.get("thumbnail")
            return Caratula(url=url, recortar_cuadrada=self._recortar_caratulas_video) if url else None

        def puntaje(miniatura: dict[str, Any]) -> tuple[int, int]:
            # yt-dlp ordena de peor a mejor con «preference»; el área desempata.
            area = int(miniatura.get("width") or 0) * int(miniatura.get("height") or 0)
            preferencia = miniatura.get("preference")
            # Ojo: la preferencia 0 es válida (la mejor); no usar «or» para el respaldo.
            return (int(preferencia) if preferencia is not None else -100, area)

        ordenadas = sorted(miniaturas, key=puntaje, reverse=True)
        return Caratula(
            url=ordenadas[0]["url"],
            alternativas=tuple(m["url"] for m in ordenadas[1:6]),
            recortar_cuadrada=self._recortar_caratulas_video,
        )
