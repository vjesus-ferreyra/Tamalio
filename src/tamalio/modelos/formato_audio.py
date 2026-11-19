# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Formatos de audio de salida y cómo producirlos con FFmpeg."""

from enum import StrEnum


class FormatoAudio(StrEnum):
    """
    Formatos a los que Tamalio puede guardar o convertir la música.

    ``ORIGINAL`` es el predeterminado y el de **mayor fidelidad**: conserva el
    flujo de audio tal cual lo entrega la plataforma (sin recodificar) y solo lo
    cambia a un contenedor que admite etiquetas (``.opus``, ``.m4a``, ``.mp3``…).
    Convertir algo con pérdida (Opus/AAC/MP3) a FLAC **no** recupera calidad:
    solo garantiza que no se pierda más en futuras ediciones.
    """

    ORIGINAL = "original"
    FLAC = "flac"
    ALAC = "alac"
    WAV = "wav"
    MP3 = "mp3"
    OPUS = "opus"
    AAC = "aac"
    VORBIS = "vorbis"

    @property
    def extension(self) -> str:
        """
        Extensión del fichero resultante (sin punto).

        Raises:
            ValueError: Para ``ORIGINAL``, cuya extensión depende del códec de origen;
                usa :meth:`extension_para_codec` en ese caso.
        """
        if self is FormatoAudio.ORIGINAL:
            raise ValueError("La extensión de ORIGINAL depende del códec; usa extension_para_codec().")
        return _EXTENSIONES[self]

    @property
    def es_sin_perdida(self) -> bool:
        """``True`` para FLAC, ALAC y WAV."""
        return self in {FormatoAudio.FLAC, FormatoAudio.ALAC, FormatoAudio.WAV}

    @property
    def codec(self) -> str | None:
        """Nombre del códec tal como lo reporta ``ffprobe`` (``None`` para ORIGINAL)."""
        return _CODECS.get(self)

    @property
    def argumentos_ffmpeg(self) -> list[str]:
        """
        Argumentos de códec para FFmpeg.

        Para ``ORIGINAL`` se copia el flujo sin recodificar (``-c:a copy``). Los
        formatos con pérdida usan tasas altas para minimizar la pérdida generacional.
        """
        return list(_ARGUMENTOS_FFMPEG[self])

    @staticmethod
    def extension_para_codec(codec: str | None) -> str:
        """
        Extensión adecuada para guardar un códec **sin recodificarlo**.

        Args:
            codec: Nombre del códec tal como lo reportan ``yt-dlp`` o ``ffprobe``
                (``"opus"``, ``"mp4a.40.2"``, ``"aac"``, ``"mp3"``, ``"vorbis"``…).

        Returns:
            Extensión sin punto. Si el códec es desconocido se usa ``"mka"``
            (Matroska Audio), que acepta prácticamente cualquier flujo.
        """
        codec = (codec or "").lower()
        if codec.startswith("opus"):
            return "opus"
        if codec.startswith(("mp4a", "aac")):
            return "m4a"
        if codec.startswith("mp3"):
            return "mp3"
        if codec.startswith("vorbis"):
            return "ogg"
        if codec.startswith("flac"):
            return "flac"
        if codec.startswith("alac"):
            return "m4a"
        return "mka"

    @staticmethod
    def codec_es_sin_perdida(codec: str | None) -> bool:
        """Indica si el códec de origen es sin pérdida (FLAC, ALAC, PCM)."""
        codec = (codec or "").lower()
        return codec.startswith(("flac", "alac", "pcm"))


# Extensiones por formato (excepto ORIGINAL, que depende del códec).
_EXTENSIONES: dict[FormatoAudio, str] = {
    FormatoAudio.FLAC: "flac",
    FormatoAudio.ALAC: "m4a",
    FormatoAudio.WAV: "wav",
    FormatoAudio.MP3: "mp3",
    FormatoAudio.OPUS: "opus",
    FormatoAudio.AAC: "m4a",
    FormatoAudio.VORBIS: "ogg",
}

# Códec resultante de cada formato según ffprobe (sirve para no convertir dos veces).
_CODECS: dict[FormatoAudio, str] = {
    FormatoAudio.FLAC: "flac",
    FormatoAudio.ALAC: "alac",
    FormatoAudio.WAV: "pcm_s24le",
    FormatoAudio.MP3: "mp3",
    FormatoAudio.OPUS: "opus",
    FormatoAudio.AAC: "aac",
    FormatoAudio.VORBIS: "vorbis",
}

# Parámetros de códec de FFmpeg para cada formato.
_ARGUMENTOS_FFMPEG: dict[FormatoAudio, tuple[str, ...]] = {
    FormatoAudio.ORIGINAL: ("-c:a", "copy"),
    FormatoAudio.FLAC: ("-c:a", "flac", "-compression_level", "8"),
    FormatoAudio.ALAC: ("-c:a", "alac"),
    FormatoAudio.WAV: ("-c:a", "pcm_s24le"),
    FormatoAudio.MP3: ("-c:a", "libmp3lame", "-b:a", "320k"),
    FormatoAudio.OPUS: ("-c:a", "libopus", "-b:a", "256k", "-vbr", "on"),
    FormatoAudio.AAC: ("-c:a", "aac", "-b:a", "320k"),
    FormatoAudio.VORBIS: ("-c:a", "libvorbis", "-q:a", "9"),
}
