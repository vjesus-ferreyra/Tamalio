# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Carpetas estándar del sistema operativo (música, configuración, caché, registros)."""

import getpass
import os
import sys
from pathlib import Path


class RutasSistema:
    """
    Calcula las carpetas que usa Tamalio según el sistema operativo.

    No depende de librerías externas: sigue las convenciones de cada sistema.

    ===========  ==========================  =====================================
    Sistema      Música (predeterminada)     Configuración
    ===========  ==========================  =====================================
    Linux/Unix   ``~/Música``                ``$XDG_CONFIG_HOME/tamalio``
    macOS        ``~/Música``                ``~/Library/Application Support/tamalio``
    Windows      ``~/Music``                 ``%APPDATA%\\tamalio``
    ===========  ==========================  =====================================

    Args:
        plataforma_so: Valor tipo ``sys.platform``; se inyecta para poder probar
            el comportamiento de otros sistemas en las pruebas unitarias.
        hogar: Carpeta personal del usuario (``Path.home()`` por defecto).
        entorno: Variables de entorno (``os.environ`` por defecto).
    """

    def __init__(
        self,
        plataforma_so: str | None = None,
        hogar: Path | None = None,
        entorno: dict[str, str] | None = None,
    ) -> None:
        self._so = plataforma_so or sys.platform
        self._hogar = hogar or Path.home()
        self._entorno = entorno if entorno is not None else dict(os.environ)

    # ------------------------------------------------------------------ #
    @property
    def es_windows(self) -> bool:
        """``True`` en Windows."""
        return self._so.startswith("win")

    @property
    def es_macos(self) -> bool:
        """``True`` en macOS."""
        return self._so == "darwin"

    # ------------------------------------------------------------------ #
    def carpeta_musica(self) -> Path:
        """
        Carpeta de música predeterminada: ``Music`` en Windows, ``Música`` en Unix y macOS.

        Nota: en macOS el sistema ya trae ``~/Music`` (que Finder muestra como
        «Música» en español). Tamalio respeta la especificación y usa
        ``~/Música``; puedes cambiarlo con ``carpeta_destino`` en la configuración.
        """
        return self._hogar / ("Music" if self.es_windows else "Música")

    def carpeta_config(self) -> Path:
        """Carpeta donde vive ``tamalio.toml``."""
        if self.es_windows:
            base = Path(self._entorno.get("APPDATA") or self._hogar / "AppData" / "Roaming")
        elif self.es_macos:
            base = self._hogar / "Library" / "Application Support"
        else:
            base = Path(self._entorno.get("XDG_CONFIG_HOME") or self._hogar / ".config")
        return base / "tamalio"

    def carpeta_cache(self) -> Path:
        """Carpeta para descargas temporales y carátulas en caché."""
        if self.es_windows:
            base = Path(self._entorno.get("LOCALAPPDATA") or self._hogar / "AppData" / "Local")
            return base / "tamalio" / "Cache"
        if self.es_macos:
            return self._hogar / "Library" / "Caches" / "tamalio"
        return Path(self._entorno.get("XDG_CACHE_HOME") or self._hogar / ".cache") / "tamalio"

    def carpeta_estado(self) -> Path:
        """Carpeta para el registro (log) de la aplicación."""
        if self.es_windows:
            base = Path(self._entorno.get("LOCALAPPDATA") or self._hogar / "AppData" / "Local")
            return base / "tamalio" / "Logs"
        if self.es_macos:
            return self._hogar / "Library" / "Logs" / "tamalio"
        return Path(self._entorno.get("XDG_STATE_HOME") or self._hogar / ".local" / "state") / "tamalio"

    @staticmethod
    def usuario_actual() -> str:
        """Nombre del usuario del sistema operativo (se usa como subcarpeta de la biblioteca)."""
        try:
            return getpass.getuser()
        except OSError:
            # getuser() puede fallar en contenedores sin variables de usuario.
            return "usuario"
