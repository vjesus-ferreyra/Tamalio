"""Lectura de teclas sin bloquear (pausa, saltar, cancelar) en Windows, macOS y Linux."""

import contextlib
import os
import sys
import threading
import time
from collections.abc import Callable, Iterator


class LectorTeclado:
    """
    Escucha el teclado en un hilo secundario y avisa cada tecla pulsada.

    - En Unix pone la terminal en modo *cbreak* (las teclas llegan sin pulsar
      Enter y sin eco) y la restaura siempre al terminar.
    - En Windows usa ``msvcrt.kbhit``/``getwch``.
    - Si la entrada no es una terminal (tubería, CI, tarea programada) no hace nada.

    Args:
        al_pulsar: Función que recibe la tecla pulsada, ya en minúscula.
    """

    def __init__(self, al_pulsar: Callable[[str], None]) -> None:
        self._al_pulsar = al_pulsar
        self._hilo: threading.Thread | None = None
        self._detener = threading.Event()

    @property
    def activo(self) -> bool:
        """``True`` si el hilo de lectura está corriendo."""
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(self) -> bool:
        """Arranca el hilo. Devuelve ``False`` si no hay terminal interactiva."""
        if self.activo:
            return True
        try:
            interactiva = sys.stdin.isatty()
        except AttributeError, ValueError:
            interactiva = False
        if not interactiva:
            return False
        self._detener.clear()
        destino = self._bucle_windows if os.name == "nt" else self._bucle_unix
        self._hilo = threading.Thread(target=destino, name="tamalio-teclado", daemon=True)
        self._hilo.start()
        return True

    def detener(self) -> None:
        """Detiene el hilo y restaura la terminal."""
        self._detener.set()
        if self._hilo is not None:
            self._hilo.join(timeout=1.0)
        self._hilo = None

    @contextlib.contextmanager
    def suspendido(self) -> Iterator[None]:
        """Suspende la lectura temporalmente (p. ej. para usar ``input()``)."""
        estaba_activo = self.activo
        self.detener()
        try:
            yield
        finally:
            if estaba_activo:
                self.iniciar()

    # ------------------------------------------------------------------ #
    def _bucle_unix(self) -> None:
        """Lee teclas en modo *cbreak* usando ``select`` con tiempo límite."""
        import select
        import termios
        import tty

        descriptor = sys.stdin.fileno()
        original = termios.tcgetattr(descriptor)
        try:
            tty.setcbreak(descriptor)
            while not self._detener.is_set():
                legibles, _, _ = select.select([descriptor], [], [], 0.2)
                if legibles:
                    tecla = os.read(descriptor, 1).decode(errors="ignore")
                    if tecla:
                        self._al_pulsar(tecla.lower())
        finally:
            # Se restaura la configuración original pase lo que pase.
            termios.tcsetattr(descriptor, termios.TCSADRAIN, original)

    def _bucle_windows(self) -> None:
        """Lee teclas con ``msvcrt`` sondeando cada 50 ms."""
        import msvcrt  # Solo existe en Windows.

        while not self._detener.is_set():
            if msvcrt.kbhit():
                tecla = msvcrt.getwch()
                if tecla:
                    self._al_pulsar(tecla.lower())
            else:
                time.sleep(0.05)
