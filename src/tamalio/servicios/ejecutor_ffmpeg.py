"""Envoltura de los ejecutables ``ffmpeg`` y ``ffprobe``."""

import json
import shutil
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tamalio.excepciones.error_dependencia_faltante import ErrorDependenciaFaltante
from tamalio.excepciones.error_tamalio import ErrorTamalio


class EjecutorFfmpeg:
    """
    Ejecuta FFmpeg con reporte de progreso y posibilidad de cancelación.

    Se usa ``-progress pipe:1`` para que FFmpeg escriba en la salida estándar
    líneas ``clave=valor`` (por ejemplo ``out_time_us=12345678``), que se
    traducen a segundos procesados para la barra de progreso.

    Args:
        ruta_ffmpeg: Ruta al ejecutable; por defecto se busca en el ``PATH``.
        ruta_ffprobe: Ruta a ``ffprobe``; por defecto se busca en el ``PATH``.
    """

    def __init__(self, ruta_ffmpeg: str | None = None, ruta_ffprobe: str | None = None) -> None:
        self._ffmpeg = ruta_ffmpeg or shutil.which("ffmpeg")
        self._ffprobe = ruta_ffprobe or shutil.which("ffprobe")

    @property
    def disponible(self) -> bool:
        """``True`` si FFmpeg está instalado."""
        return self._ffmpeg is not None

    @property
    def ruta(self) -> str | None:
        """Ruta del ejecutable de FFmpeg."""
        return self._ffmpeg

    def version(self) -> str | None:
        """Primera línea de ``ffmpeg -version`` o ``None``."""
        if not self._ffmpeg:
            return None
        salida = subprocess.run([self._ffmpeg, "-version"], capture_output=True, text=True, check=False)
        return salida.stdout.splitlines()[0] if salida.stdout else None

    # ------------------------------------------------------------------ #
    def ejecutar(
        self,
        argumentos: list[str],
        duracion: float | None = None,
        al_progreso: Callable[[float, float | None], None] | None = None,
        punto_control: Callable[[], None] | None = None,
    ) -> None:
        """
        Ejecuta FFmpeg con los argumentos dados.

        Args:
            argumentos: Argumentos después de las opciones globales (``-i …``).
            duracion: Duración del audio en segundos, para calcular el porcentaje.
            al_progreso: Recibe ``(segundos_procesados, duracion)``.
            punto_control: Se llama en cada línea de progreso; si lanza una
                excepción, FFmpeg se detiene y la excepción se propaga.

        Raises:
            ErrorDependenciaFaltante: Si FFmpeg no está instalado.
            ErrorTamalio: Si FFmpeg termina con error.
        """
        if not self._ffmpeg:
            raise ErrorDependenciaFaltante("ffmpeg", "Instálalo y asegúrate de que esté en el PATH.")
        comando = [
            self._ffmpeg,
            "-hide_banner",
            "-nostdin",  # Imprescindible: así FFmpeg no «roba» las teclas de control.
            "-y",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            "-nostats",
            *argumentos,
        ]
        proceso = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        # stderr se lee en otro hilo para que no se llene el búfer y se bloquee FFmpeg.
        errores: list[str] = []
        lector = threading.Thread(target=lambda: errores.extend(proceso.stderr or []), daemon=True)
        lector.start()
        try:
            for linea in proceso.stdout or []:
                clave, _, valor = linea.strip().partition("=")
                if punto_control:
                    punto_control()
                if clave == "out_time_us" and valor.isdigit() and al_progreso:
                    al_progreso(int(valor) / 1_000_000, duracion)
        except BaseException:
            proceso.kill()
            proceso.wait()
            raise
        codigo = proceso.wait()
        lector.join(timeout=2)
        if codigo != 0:
            detalle = "".join(errores).strip().splitlines()[-3:]
            raise ErrorTamalio(f"FFmpeg falló (código {codigo}): {' '.join(detalle) or 'sin detalle'}")

    def sondear(self, ruta: Path) -> dict[str, Any]:
        """
        Devuelve la información de ``ffprobe`` (formato y flujos) como diccionario.

        Returns:
            Diccionario vacío si ``ffprobe`` no está disponible o falla.
        """
        if not self._ffprobe:
            return {}
        salida = subprocess.run(
            [self._ffprobe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(ruta)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        try:
            return json.loads(salida.stdout or "{}")
        except json.JSONDecodeError:
            return {}

    def codec_audio(self, ruta: Path) -> str | None:
        """Nombre del códec del primer flujo de audio (``opus``, ``aac``, ``mp3``…)."""
        for flujo in self.sondear(ruta).get("streams", []):
            if flujo.get("codec_type") == "audio":
                return flujo.get("codec_name")
        return None
