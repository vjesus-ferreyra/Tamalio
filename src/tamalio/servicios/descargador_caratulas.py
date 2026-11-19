"""Descarga, recorta y guarda en caché las carátulas en alta resolución."""

import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

import requests

from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.modelos.caratula import Caratula
from tamalio.servicios.ejecutor_ffmpeg import EjecutorFfmpeg

registro = logging.getLogger(__name__)


class DescargadorCaratulas:
    """
    Obtiene la carátula de una pista como JPEG listo para incrustarse.

    Pasos:

    1. Busca la imagen en la caché local (las pistas de un mismo álbum comparten
       carátula, así que solo se descarga una vez por álbum).
    2. Prueba cada URL candidata (la de mayor calidad primero) con ``requests``.
    3. Con FFmpeg convierte WebP/PNG a JPEG de alta calidad y, si se pide,
       recorta al centro en 1:1 **sin reducir la resolución**.

    Args:
        carpeta_cache: Carpeta donde se guardan las imágenes procesadas.
        ffmpeg: Ejecutor para convertir/recortar.
        calidad_jpeg: Escala ``-q:v`` de FFmpeg (2 = casi sin pérdida, 31 = peor).
        tiempo_espera: Segundos máximos por petición.
        sesion: Sesión HTTP reutilizable (inyectable en pruebas).
    """

    #: Cabeceras de un navegador de escritorio común.
    CABECERAS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    }

    def __init__(
        self,
        carpeta_cache: Path,
        ffmpeg: EjecutorFfmpeg,
        calidad_jpeg: int = 2,
        tiempo_espera: float = 20.0,
        sesion: requests.Session | None = None,
    ) -> None:
        self._carpeta = carpeta_cache / "caratulas"
        self._ffmpeg = ffmpeg
        self._calidad = calidad_jpeg
        self._tiempo_espera = tiempo_espera
        self._sesion = sesion or requests.Session()
        self._sesion.headers.update(self.CABECERAS)

    def obtener(self, caratula: Caratula, punto_control: Callable[[], None] | None = None) -> bytes | None:
        """
        Devuelve los bytes JPEG/PNG de la carátula o ``None`` si ninguna URL funcionó.

        Args:
            caratula: Carátula con sus URL candidatas.
            punto_control: Se ejecuta antes de probar cada URL (permite cancelar).
        """
        clave = hashlib.sha256(f"{caratula.url}|{caratula.recortar_cuadrada}".encode()).hexdigest()[:32]
        en_cache = self._carpeta / f"{clave}.jpg"
        if en_cache.is_file():
            return en_cache.read_bytes()

        crudo = self._descargar_primera(caratula.candidatas(), punto_control)
        if crudo is None:
            return None
        self._carpeta.mkdir(parents=True, exist_ok=True)
        try:
            return self._procesar(crudo, en_cache, caratula.recortar_cuadrada)
        except ErrorTamalio as error:
            registro.warning("No se pudo procesar la carátula (%s); se usa la imagen original.", error)
            return crudo if self.tipo_mime(crudo) else None

    def _descargar_primera(self, urls: list[str], punto_control: Callable[[], None] | None = None) -> bytes | None:
        """Descarga la primera URL que responda con una imagen válida."""
        for url in urls:
            if punto_control is not None:
                punto_control()
            registro.debug("Carátula: probando %s", url)
            try:
                respuesta = self._sesion.get(url, timeout=self._tiempo_espera)
                respuesta.raise_for_status()
            except requests.RequestException as error:
                registro.debug("Carátula no disponible en %s: %s", url, error)
                continue
            datos = respuesta.content
            registro.debug(
                "Carátula: HTTP %s · %d bytes · %s", respuesta.status_code, len(datos), self.tipo_mime(datos, True)
            )
            # Se descartan respuestas diminutas (marcadores de «imagen no disponible»).
            if len(datos) > 2048 and self.tipo_mime(datos, permitir_webp=True):
                return datos
        return None

    def _procesar(self, crudo: bytes, destino: Path, recortar: bool) -> bytes:
        """Convierte a JPEG (y recorta si aplica) usando FFmpeg."""
        if not self._ffmpeg.disponible:
            if self.tipo_mime(crudo):
                destino.write_bytes(crudo)
                return crudo
            raise ErrorTamalio("Se necesita FFmpeg para convertir la carátula WebP.")
        entrada = destino.with_suffix(".origen")
        entrada.write_bytes(crudo)
        try:
            argumentos = ["-i", str(entrada)]
            if recortar:
                # Recorte centrado al lado menor: 1920×1080 → 1080×1080.
                argumentos += ["-vf", "crop='min(iw,ih)':'min(iw,ih)'"]
            argumentos += ["-frames:v", "1", "-q:v", str(self._calidad), "-f", "image2", str(destino)]
            self._ffmpeg.ejecutar(argumentos)
        finally:
            entrada.unlink(missing_ok=True)
        return destino.read_bytes()

    @staticmethod
    def tipo_mime(datos: bytes, permitir_webp: bool = False) -> str | None:
        """Detecta el tipo de imagen por su «firma» (primeros bytes)."""
        if datos.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if datos.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if permitir_webp and datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
            return "image/webp"
        return None
