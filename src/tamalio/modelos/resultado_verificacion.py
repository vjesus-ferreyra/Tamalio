"""Resultado de una comprobación del diagnóstico ``tamalio doctor``."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResultadoVerificacion:
    """
    Una fila del diagnóstico del entorno.

    Attributes:
        nombre: Qué se comprobó (``"FFmpeg + ffprobe"``…).
        correcto: ``True`` si pasó la comprobación.
        detalle: Versión encontrada o motivo del fallo.
        sugerencia: Cómo resolverlo cuando falla.
    """

    nombre: str
    correcto: bool
    detalle: str
    sugerencia: str = ""
