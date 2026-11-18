"""Conversión y re-empaquetado de audio entre formatos con FFmpeg."""

from collections.abc import Callable
from pathlib import Path

from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.servicios.ejecutor_ffmpeg import EjecutorFfmpeg


class ConversorAudio:
    """
    Convierte un fichero de audio al :class:`FormatoAudio` solicitado.

    - ``ORIGINAL``: copia el flujo sin recodificar (``-c:a copy``) a un
      contenedor etiquetable. Es instantáneo y **sin pérdida adicional**.
    - Otros formatos: recodifica con los parámetros de :attr:`FormatoAudio.argumentos_ffmpeg`.

    Siempre se descarta el video (``-vn``) y los metadatos de origen
    (``-map_metadata -1``), porque Tamalio escribe sus propias etiquetas limpias.

    Args:
        ffmpeg: Ejecutor de FFmpeg.
    """

    def __init__(self, ffmpeg: EjecutorFfmpeg) -> None:
        self._ffmpeg = ffmpeg

    def extension_resultante(self, formato: FormatoAudio, codec_origen: str | None) -> str:
        """Extensión que tendrá el fichero convertido."""
        if formato is FormatoAudio.ORIGINAL:
            return FormatoAudio.extension_para_codec(codec_origen)
        return formato.extension

    @staticmethod
    def pierde_calidad(formato: FormatoAudio, codec_origen: str | None) -> bool:
        """
        ``True`` si se recodificará de un formato con pérdida a otro con pérdida.

        Ejemplo: Opus → MP3. Cada recodificación con pérdida degrada el audio,
        por eso la vista muestra una advertencia.
        """
        if formato is FormatoAudio.ORIGINAL or formato.es_sin_perdida:
            return False
        # Si el origen ya tiene pérdida, recodificar (incluso opus → opus) la acumula.
        return not FormatoAudio.codec_es_sin_perdida(codec_origen)

    def convertir(
        self,
        origen: Path,
        formato: FormatoAudio,
        destino_sin_extension: Path,
        codec_origen: str | None = None,
        duracion: float | None = None,
        al_progreso: Callable[[float, float | None], None] | None = None,
        punto_control: Callable[[], None] | None = None,
        conservar_metadatos: bool = False,
    ) -> Path:
        """
        Convierte ``origen`` y devuelve la ruta del fichero resultante.

        Args:
            origen: Fichero descargado (``.webm``, ``.m4a``, ``.mp3``…).
            formato: Formato de destino.
            destino_sin_extension: Ruta de salida sin extensión (se agrega la correcta).
            codec_origen: Códec de origen; si es ``None`` se detecta con ``ffprobe``.
            duracion: Segundos de audio (para el porcentaje de avance).
            al_progreso: Recibe ``(segundos_procesados, duracion)``.
            punto_control: Permite pausar/cancelar a mitad de la conversión.
            conservar_metadatos: ``True`` para copiar las etiquetas del origen
                (se usa en ``tamalio convertir`` cuando la pista no está en el catálogo).
        """
        codec = codec_origen or self._ffmpeg.codec_audio(origen)
        extension = self.extension_resultante(formato, codec)
        destino = Path(f"{destino_sin_extension}.{extension}")
        # FFmpeg elige el contenedor por la extensión, así que el temporal debe terminar igual.
        temporal = destino.with_name(f"{destino.stem}.parcial.{extension}")

        argumentos = ["-i", str(origen), "-map", "0:a:0", "-vn", "-sn", "-dn"]
        argumentos += ["-map_metadata", "0" if conservar_metadatos else "-1"]
        argumentos += formato.argumentos_ffmpeg
        if extension == "m4a":
            # Coloca el índice al inicio: los reproductores empiezan a sonar más rápido.
            argumentos += ["-movflags", "+faststart"]
        argumentos.append(str(temporal))

        try:
            self._ffmpeg.ejecutar(argumentos, duracion, al_progreso, punto_control)
        except BaseException:
            # Si falla o se cancela, no se deja basura en la carpeta de trabajo.
            temporal.unlink(missing_ok=True)
            raise
        temporal.replace(destino)  # Reemplazo atómico: nunca queda un fichero a medias.
        return destino
