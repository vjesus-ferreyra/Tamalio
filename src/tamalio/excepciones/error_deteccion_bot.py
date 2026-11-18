"""Excepción para cuando la plataforma sospecha que somos un bot o exige sesión."""

from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.modelos.plataforma import Plataforma


class ErrorDeteccionBot(ErrorTamalio):
    """
    La plataforma bloqueó la petición (captcha, inicio de sesión o límite de peticiones).

    Attributes:
        plataforma: Plataforma que bloqueó la petición.
        limite_peticiones: ``True`` si fue un HTTP 429 (demasiadas peticiones); en
            ese caso conviene esperar más tiempo antes de reintentar.
    """

    def __init__(self, plataforma: Plataforma, detalle: str, limite_peticiones: bool = False) -> None:
        super().__init__(
            f"{plataforma.nombre_visible} bloqueó la petición: {detalle}",
            sugerencia=(
                "Exporta las cookies de tu sesión (formato Netscape) y registra el fichero con "
                f"«tamalio sesion establecer {plataforma.value} RUTA»."
            ),
        )
        self.plataforma = plataforma
        self.limite_peticiones = limite_peticiones
