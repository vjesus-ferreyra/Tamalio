"""Entidad que describe la imagen de portada de una pista o álbum."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Caratula:
    """
    Carátula en alta resolución y sus URL de respaldo.

    Attributes:
        url: URL preferida (la de mayor calidad conocida).
        alternativas: URL de respaldo, de mejor a peor, por si la preferida falla
            (por ejemplo, ``maxresdefault`` no siempre existe en YouTube).
        recortar_cuadrada: ``True`` si la imagen suele venir en 16:9 y conviene
            recortarla al centro en 1:1 (miniaturas de videos de YouTube).
    """

    url: str
    alternativas: tuple[str, ...] = field(default_factory=tuple)
    recortar_cuadrada: bool = False

    def candidatas(self) -> list[str]:
        """Devuelve todas las URL en orden de preferencia y sin duplicados."""
        vistas: set[str] = set()
        resultado: list[str] = []
        for url in (self.url, *self.alternativas):
            if url and url not in vistas:
                vistas.add(url)
                resultado.append(url)
        return resultado
