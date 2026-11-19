"""Mecanismo de pausa, salto y cancelación compartido entre hilos."""

import logging
import threading
import time
from collections.abc import Callable

from tamalio.excepciones.error_descarga_cancelada import ErrorDescargaCancelada
from tamalio.modelos.alcance_cancelacion import AlcanceCancelacion
from tamalio.modelos.estado_descarga import EstadoDescarga

registro = logging.getLogger(__name__)


class ControlEjecucion:
    """
    «Mando a distancia» de la descarga en curso.

    El hilo del teclado (o el manejador de Ctrl+C) llama a :meth:`alternar_pausa`,
    :meth:`saltar_pista`, :meth:`cancelar_tarea` o :meth:`detener_todo`. El hilo
    principal, que está descargando, llama con frecuencia a
    :meth:`punto_control` (desde el *hook* de progreso de ``yt-dlp``, desde
    FFmpeg y desde las esperas), y ahí:

    - si hay **pausa**, se queda bloqueado hasta que se reanude;
    - si hay **cancelación**, lanza :class:`ErrorDescargaCancelada`.

    Además, cada ``intervalo_consulta`` segundos consulta el estado de la tarea
    en PostgreSQL. Así ``tamalio pausar`` o ``tamalio cancelar`` ejecutados desde
    **otra terminal** también detienen la descarga.

    Args:
        intervalo_consulta: Segundos mínimos entre consultas a la base de datos.
        reloj: Función de tiempo monótono (inyectable en pruebas).
    """

    def __init__(self, intervalo_consulta: float = 2.0, reloj: Callable[[], float] = time.monotonic) -> None:
        self._candado = threading.Lock()
        self._pausado = threading.Event()
        self._alcance: AlcanceCancelacion | None = None
        self._intervalo = intervalo_consulta
        self._reloj = reloj
        self._consultar: Callable[[], EstadoDescarga | None] | None = None
        self._ultima_consulta = float("-inf")
        self._oyentes_pausa: list[Callable[[bool], None]] = []

    # ------------------------------------------------------------------ #
    # Órdenes (pueden llegar desde cualquier hilo)
    # ------------------------------------------------------------------ #
    def al_cambiar_pausa(self, oyente: Callable[[bool], None]) -> None:
        """Registra una función que recibe ``True``/``False`` al pausar/reanudar."""
        self._oyentes_pausa.append(oyente)

    def alternar_pausa(self) -> bool:
        """Pausa si está corriendo o reanuda si está pausado. Devuelve el nuevo estado."""
        with self._candado:
            if self._pausado.is_set():
                self._pausado.clear()
            else:
                self._pausado.set()
            pausado = self._pausado.is_set()
        for oyente in self._oyentes_pausa:
            oyente(pausado)
        return pausado

    def saltar_pista(self) -> None:
        """Abandona la pista actual y continúa con la siguiente."""
        self._solicitar(AlcanceCancelacion.PISTA)

    def cancelar_tarea(self) -> None:
        """Cancela la tarea actual y continúa con la siguiente de la cola."""
        self._solicitar(AlcanceCancelacion.TAREA)

    def detener_todo(self) -> None:
        """Detiene todo; la tarea actual queda pausada para reanudarla luego."""
        self._solicitar(AlcanceCancelacion.TODO)

    def _solicitar(self, alcance: AlcanceCancelacion) -> None:
        """Guarda la petición de cancelación (gana la de mayor alcance) y quita la pausa."""
        orden = list(AlcanceCancelacion)
        registro.debug("Orden del usuario: detener (alcance=%s)", alcance.value)
        with self._candado:
            if self._alcance is None or orden.index(alcance) > orden.index(self._alcance):
                self._alcance = alcance
        # Si estaba en pausa, se libera para que el hilo principal vea la cancelación.
        if self._pausado.is_set():
            self.alternar_pausa()

    # ------------------------------------------------------------------ #
    # Estado
    # ------------------------------------------------------------------ #
    @property
    def pausado(self) -> bool:
        """``True`` mientras la descarga está en pausa."""
        return self._pausado.is_set()

    @property
    def detenido(self) -> bool:
        """``True`` si el usuario pidió detener todo."""
        return self._alcance is AlcanceCancelacion.TODO

    def preparar_tarea(self, consultar_estado: Callable[[], EstadoDescarga | None] | None) -> None:
        """Configura la consulta externa para la nueva tarea y limpia cancelaciones previas."""
        with self._candado:
            self._consultar = consultar_estado
            self._ultima_consulta = float("-inf")
            if self._alcance is not AlcanceCancelacion.TODO:
                self._alcance = None

    def limpiar_pista(self) -> None:
        """Olvida un «saltar pista» ya atendido."""
        with self._candado:
            if self._alcance is AlcanceCancelacion.PISTA:
                self._alcance = None

    # ------------------------------------------------------------------ #
    # Punto de control (hilo principal)
    # ------------------------------------------------------------------ #
    def punto_control(self) -> None:
        """
        Bloquea si hay pausa y lanza la cancelación pendiente, si la hay.

        Raises:
            ErrorDescargaCancelada: Con el alcance solicitado.
        """
        self._revisar_externo()
        self._lanzar_si_cancelado()
        while self._pausado.is_set():
            time.sleep(0.15)
            self._lanzar_si_cancelado()
            self._revisar_externo()

    def _lanzar_si_cancelado(self) -> None:
        """Lanza :class:`ErrorDescargaCancelada` si hay una cancelación pendiente."""
        alcance = self._alcance
        if alcance is not None:
            raise ErrorDescargaCancelada(alcance, pausar=alcance is AlcanceCancelacion.TODO)

    def _revisar_externo(self) -> None:
        """Consulta (con límite de frecuencia) si otra terminal pausó o canceló la tarea."""
        if self._consultar is None:
            return
        ahora = self._reloj()
        if ahora - self._ultima_consulta < self._intervalo:
            return
        self._ultima_consulta = ahora
        estado = self._consultar()
        if estado is EstadoDescarga.PAUSADA:
            registro.debug("Otra terminal pausó la tarea.")
            raise ErrorDescargaCancelada(AlcanceCancelacion.TAREA, pausar=True)
        if estado is EstadoDescarga.CANCELADA:
            registro.debug("Otra terminal canceló la tarea.")
            raise ErrorDescargaCancelada(AlcanceCancelacion.TAREA, pausar=False)
