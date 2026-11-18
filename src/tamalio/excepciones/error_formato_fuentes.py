"""Excepción para ficheros de fuentes o catálogos mal escritos."""

from pathlib import Path

from tamalio.excepciones.error_tamalio import ErrorTamalio


class ErrorFormatoFuentes(ErrorTamalio):
    """
    Un fichero de fuentes / catálogo no se pudo leer o no cumple su ``$schema``.

    Attributes:
        ruta: Fichero problemático.
        errores: Lista de errores encontrados (uno por línea, con su ruta JSON).
    """

    def __init__(self, ruta: Path, errores: list[str]) -> None:
        detalle = "\n".join(f"  • {error}" for error in errores)
        super().__init__(
            f"El fichero «{ruta}» no es válido:\n{detalle}",
            sugerencia="Revisa el fichero contra su $schema; tu editor puede validarlo en vivo.",
        )
        self.ruta = ruta
        self.errores = errores
