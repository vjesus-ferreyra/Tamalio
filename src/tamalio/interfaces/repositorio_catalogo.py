"""Contrato de persistencia del catálogo musical personal."""

from abc import ABC, abstractmethod
from pathlib import Path

from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma


class RepositorioCatalogo(ABC):
    """Almacén de las pistas del usuario (implementado sobre PostgreSQL)."""

    @abstractmethod
    def guardar(self, pista: Pista) -> None:
        """Inserta o actualiza la pista (clave: plataforma + id_externo)."""

    @abstractmethod
    def obtener(self, plataforma: Plataforma, id_externo: str) -> Pista | None:
        """Devuelve la pista o ``None`` si no existe."""

    @abstractmethod
    def buscar_por_ruta(self, ruta: Path) -> Pista | None:
        """Busca la pista cuyo fichero está en ``ruta``."""

    @abstractmethod
    def listar(self, plataforma: Plataforma | None = None, texto: str | None = None) -> list[Pista]:
        """
        Lista el catálogo ordenado por artista del álbum, álbum y número de pista.

        Args:
            plataforma: Filtra por plataforma si se indica.
            texto: Filtra por coincidencia parcial en título, álbum o artistas.
        """
