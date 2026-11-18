"""Catálogo en memoria para pruebas unitarias (sin PostgreSQL)."""

from pathlib import Path

from tamalio.interfaces.repositorio_catalogo import RepositorioCatalogo
from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma


class RepositorioCatalogoMemoria(RepositorioCatalogo):
    """Guarda las pistas en un diccionario indexado por ``(plataforma, id_externo)``."""

    def __init__(self) -> None:
        self.pistas: dict[tuple[str, str], Pista] = {}

    def guardar(self, pista: Pista) -> None:
        self.pistas[pista.clave] = pista

    def obtener(self, plataforma: Plataforma, id_externo: str) -> Pista | None:
        return self.pistas.get((plataforma.value, id_externo))

    def buscar_por_ruta(self, ruta: Path) -> Pista | None:
        return next((p for p in self.pistas.values() if p.ruta_archivo == ruta), None)

    def listar(self, plataforma: Plataforma | None = None, texto: str | None = None) -> list[Pista]:
        return [
            p
            for p in self.pistas.values()
            if (plataforma is None or p.plataforma is plataforma)
            and (not texto or texto.lower() in f"{p.titulo} {p.album} {' '.join(p.artistas)}".lower())
        ]
