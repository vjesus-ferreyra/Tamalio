"""Escribe los metadatos y la carátula dentro del fichero de audio con ``mutagen``."""

import base64
import logging
from pathlib import Path

from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, COMM, ID3, TALB, TCON, TDRC, TIT2, TPE1, TPE2, TRCK, TXXX, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.modelos.pista import Pista
from tamalio.servicios.descargador_caratulas import DescargadorCaratulas

registro = logging.getLogger(__name__)


class EtiquetadorAudio:
    """
    Etiqueta FLAC, Opus, Vorbis, MP3, M4A (AAC/ALAC) y WAV.

    Metadatos escritos en todos los formatos:

    - Nombre de la canción, álbum, artistas de la pista y del álbum.
      Varios artistas se escriben en **un solo texto separado por comas**
      («GHOST DATA, Skye Light»): si se guardaran como valores múltiples, muchos
      reproductores los mostrarían unidos con «/» («GHOST DATA/Skye Light»).
    - Número de pista / total, géneros y año.
    - Carátula frontal en alta resolución.
    - Origen (plataforma, ID y URL) para poder reconstruir el catálogo.

    Cada familia de formatos guarda las etiquetas de forma distinta:
    *Vorbis comments* (FLAC/Ogg), *ID3v2.4* (MP3/WAV) y átomos *iTunes* (MP4).
    """

    #: Separador entre varios artistas dentro de una misma etiqueta.
    SEPARADOR_ARTISTAS = ", "

    @classmethod
    def unir_artistas(cls, artistas: list[str]) -> str:
        """``["GHOST DATA", "Skye Light"]`` → ``"GHOST DATA, Skye Light"``."""
        return cls.SEPARADOR_ARTISTAS.join(artistas)

    def etiquetar(self, ruta: Path, pista: Pista, imagen: bytes | None) -> None:
        """
        Escribe las etiquetas en ``ruta``, reemplazando las existentes.

        Raises:
            ErrorTamalio: Si el formato no se puede etiquetar.
        """
        extension = ruta.suffix.lower()
        metodos = {
            ".flac": self._flac,
            ".opus": self._ogg,
            ".ogg": self._ogg,
            ".mp3": self._mp3,
            ".m4a": self._mp4,
            ".mp4": self._mp4,
            ".wav": self._wav,
        }
        metodo = metodos.get(extension)
        if metodo is None:
            registro.warning("El formato %s no admite etiquetas; se omite el etiquetado.", extension)
            return
        registro.debug(
            "Etiquetas %s → título=%r álbum=%r artistas=%r artistas_álbum=%r pista=%s/%s géneros=%r año=%s carátula=%s",
            ruta.name,
            pista.titulo,
            pista.album,
            pista.artistas,
            pista.artistas_album,
            pista.numero_pista,
            pista.total_pistas,
            pista.generos,
            pista.anio,
            f"{len(imagen)} bytes" if imagen else "sin imagen",
        )
        try:
            metodo(ruta, pista, imagen)
        except Exception as error:  # mutagen lanza varios tipos según el formato.
            raise ErrorTamalio(f"No se pudieron escribir las etiquetas en «{ruta.name}»: {error}") from error

    # ------------------------------------------------------------------ #
    # Vorbis comments (FLAC, Opus, Vorbis)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _comentarios_vorbis(pista: Pista) -> dict[str, list[str]]:
        """Diccionario de *Vorbis comments*; cada clave admite varios valores."""
        etiquetas: dict[str, list[str]] = {
            "TITLE": [pista.titulo],
            "ALBUM": [pista.album],
            # ARTIST/ALBUMARTIST: texto único separado por comas (lo que muestran los reproductores).
            "ARTIST": [EtiquetadorAudio.unir_artistas(pista.artistas)] if pista.artistas else [],
            # ARTISTS conserva la lista por separado (convención de MusicBrainz Picard) para
            # los reproductores que saben agrupar por cada artista.
            "ARTISTS": list(pista.artistas),
            "ALBUMARTIST": [EtiquetadorAudio.unir_artistas(pista.artistas_album)] if pista.artistas_album else [],
            "GENRE": list(pista.generos),
            "COMMENT": [f"Extraído con Tamalio desde {pista.url}"],
            "TAMALIO_PLATAFORMA": [pista.plataforma.value],
            "TAMALIO_ID": [pista.id_externo],
            "TAMALIO_URL": [pista.url],
        }
        if pista.numero_pista:
            etiquetas["TRACKNUMBER"] = [str(pista.numero_pista)]
        if pista.total_pistas:
            etiquetas["TRACKTOTAL"] = [str(pista.total_pistas)]
            etiquetas["TOTALTRACKS"] = [str(pista.total_pistas)]
        if pista.anio:
            etiquetas["DATE"] = [str(pista.anio)]
        # Se eliminan las claves vacías (p. ej. sin géneros).
        return {clave: valor for clave, valor in etiquetas.items() if valor}

    @staticmethod
    def _imagen_flac(imagen: bytes) -> Picture:
        """Bloque PICTURE (tipo 3 = portada frontal) para FLAC/Ogg."""
        imagen_flac = Picture()
        imagen_flac.type = 3
        imagen_flac.mime = DescargadorCaratulas.tipo_mime(imagen) or "image/jpeg"
        imagen_flac.desc = "Cover"
        imagen_flac.data = imagen
        return imagen_flac

    def _flac(self, ruta: Path, pista: Pista, imagen: bytes | None) -> None:
        """FLAC: comentarios Vorbis + bloque PICTURE nativo."""
        audio = FLAC(ruta)
        audio.delete()
        audio.clear_pictures()
        for clave, valores in self._comentarios_vorbis(pista).items():
            audio[clave] = valores
        if imagen:
            audio.add_picture(self._imagen_flac(imagen))
        audio.save()

    def _ogg(self, ruta: Path, pista: Pista, imagen: bytes | None) -> None:
        """Opus/Vorbis: comentarios Vorbis + imagen en ``METADATA_BLOCK_PICTURE`` (base64)."""
        try:
            audio = OggOpus(ruta)
        except Exception:
            audio = OggVorbis(ruta)
        audio.delete()
        for clave, valores in self._comentarios_vorbis(pista).items():
            audio[clave] = valores
        if imagen:
            bloque = self._imagen_flac(imagen).write()
            audio["METADATA_BLOCK_PICTURE"] = [base64.b64encode(bloque).decode("ascii")]
        audio.save()

    # ------------------------------------------------------------------ #
    # ID3v2.4 (MP3, WAV)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _marcos_id3(etiquetas: ID3, pista: Pista, imagen: bytes | None) -> None:
        """Agrega los marcos ID3v2.4 (``encoding=3`` = UTF-8)."""
        etiquetas.delall("APIC")
        etiquetas.add(TIT2(encoding=3, text=pista.titulo))
        etiquetas.add(TALB(encoding=3, text=pista.album))
        # Un solo texto con comas: ID3 mostraría los valores múltiples unidos con «/».
        etiquetas.add(TPE1(encoding=3, text=EtiquetadorAudio.unir_artistas(pista.artistas)))
        if pista.artistas_album:
            etiquetas.add(TPE2(encoding=3, text=EtiquetadorAudio.unir_artistas(pista.artistas_album)))
        if pista.numero_pista:
            numero = f"{pista.numero_pista}/{pista.total_pistas}" if pista.total_pistas else str(pista.numero_pista)
            etiquetas.add(TRCK(encoding=3, text=numero))
        if pista.generos:
            etiquetas.add(TCON(encoding=3, text=list(pista.generos)))
        if pista.anio:
            etiquetas.add(TDRC(encoding=3, text=str(pista.anio)))
        etiquetas.add(COMM(encoding=3, lang="spa", desc="", text=f"Extraído con Tamalio desde {pista.url}"))
        etiquetas.add(TXXX(encoding=3, desc="TAMALIO_PLATAFORMA", text=pista.plataforma.value))
        etiquetas.add(TXXX(encoding=3, desc="TAMALIO_ID", text=pista.id_externo))
        etiquetas.add(TXXX(encoding=3, desc="TAMALIO_URL", text=pista.url))
        if imagen:
            mime = DescargadorCaratulas.tipo_mime(imagen) or "image/jpeg"
            etiquetas.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=imagen))

    def _mp3(self, ruta: Path, pista: Pista, imagen: bytes | None) -> None:
        """MP3: ID3v2.4 desde cero."""
        try:
            etiquetas = ID3(ruta)
            etiquetas.clear()
        except ID3NoHeaderError:
            etiquetas = ID3()
        self._marcos_id3(etiquetas, pista, imagen)
        etiquetas.save(ruta, v2_version=4)

    def _wav(self, ruta: Path, pista: Pista, imagen: bytes | None) -> None:
        """WAV: fragmento ``id3 `` dentro del RIFF."""
        audio = WAVE(ruta)
        if audio.tags is None:
            audio.add_tags()
        etiquetas = audio.tags
        if etiquetas is None:  # add_tags() siempre las crea; esto informa al verificador de tipos.
            raise ErrorTamalio(f"No se pudieron crear etiquetas ID3 en «{ruta.name}».")
        etiquetas.clear()
        self._marcos_id3(etiquetas, pista, imagen)
        audio.save(v2_version=4)

    # ------------------------------------------------------------------ #
    # MP4 / iTunes (AAC, ALAC)
    # ------------------------------------------------------------------ #
    def _mp4(self, ruta: Path, pista: Pista, imagen: bytes | None) -> None:
        """M4A: átomos estándar de iTunes (``©nam``, ``aART``, ``trkn``, ``covr``…)."""
        audio = MP4(ruta)
        if audio.tags is None:
            audio.add_tags()
        if audio.tags is None:  # add_tags() siempre las crea; esto informa al verificador de tipos.
            raise ErrorTamalio(f"No se pudieron crear etiquetas MP4 en «{ruta.name}».")
        audio.tags.clear()
        audio["\xa9nam"] = [pista.titulo]
        audio["\xa9alb"] = [pista.album]
        audio["\xa9ART"] = [self.unir_artistas(pista.artistas)]
        if pista.artistas_album:
            audio["aART"] = [self.unir_artistas(pista.artistas_album)]
        if pista.numero_pista:
            audio["trkn"] = [(pista.numero_pista, pista.total_pistas or 0)]
        if pista.generos:
            audio["\xa9gen"] = list(pista.generos)
        if pista.anio:
            audio["\xa9day"] = [str(pista.anio)]
        audio["\xa9cmt"] = [f"Extraído con Tamalio desde {pista.url}"]
        for clave, valor in (
            ("TAMALIO_PLATAFORMA", pista.plataforma.value),
            ("TAMALIO_ID", pista.id_externo),
            ("TAMALIO_URL", pista.url),
        ):
            audio[f"----:com.apple.iTunes:{clave}"] = [MP4FreeForm(valor.encode("utf-8"))]
        if imagen:
            formato = MP4Cover.FORMAT_PNG if imagen.startswith(b"\x89PNG") else MP4Cover.FORMAT_JPEG
            audio["covr"] = [MP4Cover(imagen, imageformat=formato)]
        audio.save()
