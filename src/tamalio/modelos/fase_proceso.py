"""Fases por las que pasa cada pista; la vista las usa para mostrar el avance."""

from enum import StrEnum


class FaseProceso(StrEnum):
    """Etapas del procesamiento de una pista, en orden."""

    EXTRAYENDO = "extrayendo"
    ESPERANDO = "esperando"
    DESCARGANDO = "descargando"
    CARATULA = "caratula"
    CONVIRTIENDO = "convirtiendo"
    ETIQUETANDO = "etiquetando"
    ORGANIZANDO = "organizando"

    @property
    def descripcion(self) -> str:
        """Texto corto en español para la barra de progreso."""
        return _DESCRIPCIONES[self]


_DESCRIPCIONES: dict[FaseProceso, str] = {
    FaseProceso.EXTRAYENDO: "Analizando fuente",
    FaseProceso.ESPERANDO: "Pausa humana",
    FaseProceso.DESCARGANDO: "Descargando",
    FaseProceso.CARATULA: "Carátula",
    FaseProceso.CONVIRTIENDO: "Convirtiendo",
    FaseProceso.ETIQUETANDO: "Etiquetando",
    FaseProceso.ORGANIZANDO: "Organizando",
}
