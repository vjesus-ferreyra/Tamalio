# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Diagnóstico del entorno (comando ``tamalio doctor``)."""

import importlib.metadata
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable

from tamalio.configuracion.configuracion import Configuracion
from tamalio.modelos.resultado_verificacion import ResultadoVerificacion
from tamalio.servicios.ejecutor_ffmpeg import EjecutorFfmpeg


class VerificadorDependencias:
    """
    Comprueba que todo lo necesario esté instalado y configurado.

    Comprobaciones: versión de Python, FFmpeg/ffprobe, QuickJS, ``yt-dlp`` y
    ``yt-dlp-ejs``, ``curl_cffi`` (suplantación de navegador), ``mutagen``,
    ``requests``, ``psycopg`` + conexión a PostgreSQL y permisos de escritura
    en la carpeta de destino.

    Args:
        config: Configuración vigente.
        probar_bd: Función que intenta conectar a PostgreSQL y devuelve la
            versión del servidor (la inyecta la aplicación).
    """

    def __init__(self, config: Configuracion, probar_bd: Callable[[], str] | None = None) -> None:
        self._config = config
        self._probar_bd = probar_bd

    def verificar(self) -> list[ResultadoVerificacion]:
        """Ejecuta todas las comprobaciones en orden."""
        comprobaciones = [
            self._python,
            self._ffmpeg,
            self._quickjs,
            lambda: self._paquete("yt-dlp", "yt_dlp", "uv sync"),
            lambda: self._paquete("yt-dlp-ejs", "yt_dlp_ejs", "Instala yt-dlp[default]."),
            self._curl_cffi,
            lambda: self._paquete("mutagen", "mutagen", "uv sync"),
            lambda: self._paquete("requests", "requests", "uv sync"),
            lambda: self._paquete("psycopg", "psycopg", "uv sync"),
            self._postgres,
            self._destino,
        ]
        resultados = []
        for comprobacion in comprobaciones:
            try:
                resultado = comprobacion()
            except Exception as error:  # Un diagnóstico nunca debe romper la aplicación.
                resultado = ResultadoVerificacion("?", False, str(error))
            resultados.append(resultado)
        return resultados

    # ------------------------------------------------------------------ #
    def _python(self) -> ResultadoVerificacion:
        version = ".".join(map(str, sys.version_info[:3]))
        return ResultadoVerificacion(
            "Python ≥ 3.15", sys.version_info >= (3, 15), version, "Instala Python 3.15 con «uv python install 3.15»."
        )

    def _ffmpeg(self) -> ResultadoVerificacion:
        ffmpeg = EjecutorFfmpeg()
        if not ffmpeg.disponible or shutil.which("ffprobe") is None:
            return ResultadoVerificacion("FFmpeg + ffprobe", False, "no encontrado", "apt/brew/winget install ffmpeg")
        # «ffmpeg version 7.1 Copyright…» → «7.1».
        partes = (ffmpeg.version() or "").split()
        return ResultadoVerificacion("FFmpeg + ffprobe", True, partes[2] if len(partes) > 2 else "instalado")

    def _quickjs(self) -> ResultadoVerificacion:
        """Busca ``qjs`` (o la ruta configurada) y lee su versión de ``--help``."""
        ruta = str(self._config.js_ruta) if self._config.js_ruta else shutil.which("qjs")
        nombre = f"Motor JS ({self._config.js_motor})"
        if self._config.js_motor != "quickjs":
            return ResultadoVerificacion(nombre, True, "otro motor configurado")
        if not ruta or not os.access(ruta, os.X_OK):
            return ResultadoVerificacion(
                nombre, False, "qjs no encontrado", "Instala QuickJS o QuickJS-ng y agrega «qjs» al PATH."
            )
        salida = subprocess.run([ruta, "--help"], capture_output=True, text=True, check=False)
        texto = salida.stdout + salida.stderr
        coincidencia = re.search(r"QuickJS(?:-ng)?\s+version\s+(\S+)", texto)
        return ResultadoVerificacion(nombre, True, coincidencia[0] if coincidencia else ruta)

    @staticmethod
    def _paquete(distribucion: str, modulo: str, sugerencia: str) -> ResultadoVerificacion:
        if importlib.util.find_spec(modulo) is None:
            return ResultadoVerificacion(distribucion, False, "no instalado", sugerencia)
        try:
            version = importlib.metadata.version(distribucion)
        except importlib.metadata.PackageNotFoundError:
            version = "instalado"
        return ResultadoVerificacion(distribucion, True, version)

    def _curl_cffi(self) -> ResultadoVerificacion:
        """Verifica que ``yt-dlp`` pueda suplantar el navegador configurado."""
        objetivo = (self._config.red_suplantar_navegador or "").strip().lower()
        nombre = f"Suplantación ({objetivo or 'desactivada'})"
        if objetivo in {"", "no", "ninguno"}:
            return ResultadoVerificacion(nombre, True, "desactivada en la configuración")
        # En «auto» basta con que curl_cffi ofrezca algún navegador (se prueba con chrome).
        objetivo = "chrome" if objetivo == "auto" else objetivo
        try:
            import curl_cffi  # noqa: F401  (solo se comprueba que cargue)
        except Exception as error:
            return ResultadoVerificacion(
                nombre, False, f"curl_cffi no carga: {error}", 'uv add "yt-dlp[default,curl-cffi]"'
            )
        from yt_dlp import YoutubeDL
        from yt_dlp.networking.impersonate import ImpersonateTarget

        try:
            with YoutubeDL({"quiet": True, "impersonate": ImpersonateTarget.from_str(objetivo)}):
                pass
        except Exception as error:
            return ResultadoVerificacion(nombre, False, str(error)[:60], "Actualiza curl_cffi.")
        return ResultadoVerificacion(nombre, True, importlib.metadata.version("curl_cffi"))

    def _postgres(self) -> ResultadoVerificacion:
        if self._probar_bd is None:
            return ResultadoVerificacion("PostgreSQL", False, "sin prueba configurada")
        try:
            return ResultadoVerificacion("PostgreSQL", True, self._probar_bd())
        except Exception as error:
            return ResultadoVerificacion(
                "PostgreSQL", False, str(error).splitlines()[0][:70], "Revisa [base_datos] url o TAMALIO_BD_URL."
            )

    def _destino(self) -> ResultadoVerificacion:
        raiz = self._config.raiz_biblioteca
        existente = next((p for p in (raiz, *raiz.parents) if p.exists()), None)
        escribible = existente is not None and os.access(existente, os.W_OK)
        return ResultadoVerificacion("Carpeta de destino", escribible, str(raiz), "Cambia [general] carpeta_destino.")
