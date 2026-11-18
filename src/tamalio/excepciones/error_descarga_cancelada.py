"""Excepción usada internamente para interrumpir una descarga en curso."""

from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.modelos.alcance_cancelacion import AlcanceCancelacion


class ErrorDescargaCancelada(ErrorTamalio):
    """
    Señal de control (no es un fallo) que viaja desde el *hook* de progreso.

    Se lanza dentro del *hook* de ``yt-dlp`` o del temporizador cuando el usuario
    pulsa una tecla de control o cuando otra terminal pausa/cancela la tarea en la
    base de datos. Quien la captura decide qué hacer según su :attr:`alcance`.

    Attributes:
        alcance: Nivel de la cancelación (pista, tarea o todo).
        pausar: ``True`` si la tarea debe quedar *pausada* en lugar de *cancelada*.
    """

    def __init__(self, alcance: AlcanceCancelacion, pausar: bool = False) -> None:
        super().__init__(f"Descarga interrumpida por el usuario (alcance: {alcance.value}).")
        self.alcance = alcance
        self.pausar = pausar
