"""Contrato de persistencia de los ficheros de sesión (cookies) por plataforma."""

from abc import ABC, abstractmethod
from pathlib import Path

from tamalio.modelos.plataforma import Plataforma


class RepositorioSesiones(ABC):
    """
    Recuerda dónde está el fichero de cookies (tokens de sesión) de cada plataforma.

    Solo se guarda la **ruta** al fichero, nunca su contenido, para no copiar
    credenciales a la base de datos.
    """

    @abstractmethod
    def obtener(self, plataforma: Plataforma) -> Path | None:
        """Ruta registrada para la plataforma o ``None``."""

    @abstractmethod
    def guardar(self, plataforma: Plataforma, ruta: Path) -> None:
        """Registra (o reemplaza) la ruta de cookies de la plataforma."""

    @abstractmethod
    def eliminar(self, plataforma: Plataforma) -> bool:
        """Olvida la ruta registrada. Devuelve ``True`` si existía."""

    @abstractmethod
    def listar(self) -> dict[Plataforma, Path]:
        """Todas las rutas registradas."""
