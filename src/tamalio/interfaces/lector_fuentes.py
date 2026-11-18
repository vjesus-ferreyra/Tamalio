"""Contrato de los lectores de ficheros con fuentes agrupadas (descarga en masa)."""

from abc import ABC, abstractmethod
from pathlib import Path

from tamalio.modelos.fuente import Fuente


class LectorFuentes(ABC):
    """Lee un fichero con varias fuentes y devuelve las :class:`Fuente` ya clasificadas."""

    @abstractmethod
    def admite(self, ruta: Path, contenido: str) -> bool:
        """
        Indica si este lector entiende el fichero.

        Args:
            ruta: Ruta del fichero (se usa la extensión como primera pista).
            contenido: Texto completo, por si hay que «olfatear» el formato.
        """

    @abstractmethod
    def leer(self, ruta: Path, contenido: str) -> list[Fuente]:
        """
        Interpreta el contenido y devuelve las fuentes en el orden del fichero.

        Raises:
            ErrorFormatoFuentes: Si el fichero tiene errores de sintaxis o de esquema.
        """
