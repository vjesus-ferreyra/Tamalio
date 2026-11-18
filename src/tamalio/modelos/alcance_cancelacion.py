"""Enumeración que indica qué tanto debe detenerse una interrupción del usuario."""

from enum import StrEnum


class AlcanceCancelacion(StrEnum):
    """Qué tanto debe detenerse cuando el usuario interrumpe una descarga."""

    #: Solo se salta la pista actual; la tarea continúa con la siguiente pista.
    PISTA = "pista"
    #: Se detiene la tarea actual (cancelada o pausada) y se sigue con la siguiente tarea.
    TAREA = "tarea"
    #: Se detiene todo el proceso; las tareas quedan pausadas para reanudarse luego.
    TODO = "todo"
