# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Esperas aleatorias que imitan el ritmo de una persona para evitar bloqueos (HTTP 403/429)."""

import random
import time
from collections.abc import Callable


class TemporizadorHumano:
    """
    Genera y ejecuta pausas aleatorias entre peticiones.

    Las plataformas limitan «N peticiones por minuto»; un programa que pide
    canciones a intervalos exactos es fácil de detectar. Este temporizador:

    1. Usa :class:`random.SystemRandom` (azar del sistema operativo, no predecible).
    2. Sortea cada espera con una distribución **triangular** sesgada hacia el
       mínimo (casi siempre esperas cortas, a veces largas) más un ruido gaussiano.
    3. Cada cierto número de pistas (también aleatorio) hace una **pausa larga**,
       como alguien que se detiene a leer o cambia de pestaña.
    4. Ante un bloqueo aplica *backoff* exponencial con *jitter* completo.

    Args:
        minimo: Segundos mínimos entre pistas.
        maximo: Segundos máximos entre pistas.
        pausa_larga_cada: Rango ``(a, b)``: cada cuántas pistas hacer una pausa larga.
        pausa_larga: Rango en segundos de la pausa larga.
        peticiones: Rango de espera entre peticiones internas de ``yt-dlp``.
        azar: Generador inyectable (en pruebas se usa ``random.Random(semilla)``).
        reloj: Función de tiempo monótono (inyectable).
        dormir: Función para dormir (inyectable, para no esperar en las pruebas).
    """

    def __init__(
        self,
        minimo: float = 3.0,
        maximo: float = 9.0,
        pausa_larga_cada: tuple[int, int] = (8, 15),
        pausa_larga: tuple[float, float] = (25.0, 70.0),
        peticiones: tuple[float, float] = (0.6, 1.8),
        azar: random.Random | None = None,
        reloj: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self._minimo = minimo
        self._maximo = max(maximo, minimo)
        self._pausa_larga_cada = pausa_larga_cada
        self._pausa_larga = pausa_larga
        self._peticiones = peticiones
        self._azar = azar or random.SystemRandom()
        self._reloj = reloj
        self._dormir = dormir
        self._contador = 0
        self._proxima_pausa_larga = self._azar.randint(*pausa_larga_cada)

    # ------------------------------------------------------------------ #
    def siguiente_espera(self) -> float:
        """Sortea la espera (en segundos) antes de la siguiente pista."""
        self._contador += 1
        if self._contador >= self._proxima_pausa_larga:
            # Reinicia el contador y sortea cuándo será la próxima pausa larga.
            self._contador = 0
            self._proxima_pausa_larga = self._azar.randint(*self._pausa_larga_cada)
            return round(self._azar.uniform(*self._pausa_larga), 3)

        rango = self._maximo - self._minimo
        moda = self._minimo + rango * 0.35
        base = self._azar.triangular(self._minimo, self._maximo, moda)
        ruido = self._azar.gauss(0.0, rango * 0.05) if rango else 0.0
        return round(min(self._maximo, max(self._minimo, base + ruido)), 3)

    def espera_entre_peticiones(self) -> float:
        """Valor aleatorio para ``sleep_interval_requests`` de ``yt-dlp``."""
        return round(self._azar.uniform(*self._peticiones), 3)

    def espera_bloqueo(self, intento: int, limite_peticiones: bool = False) -> float:
        """
        *Backoff* exponencial con *jitter* para cuando la plataforma nos bloquea.

        Args:
            intento: Número de intento (``1``, ``2``…).
            limite_peticiones: ``True`` ante un HTTP 429; se espera el doble.

        Returns:
            Segundos a esperar (entre 30 s y unos 10 minutos).
        """
        techo = min(600.0, 30.0 * (2**intento)) * (2.0 if limite_peticiones else 1.0)
        return round(30.0 + self._azar.uniform(0.0, techo), 3)

    # ------------------------------------------------------------------ #
    def esperar(
        self,
        segundos: float,
        punto_control: Callable[[], None] | None = None,
        al_avanzar: Callable[[float, float], None] | None = None,
    ) -> None:
        """
        Espera ``segundos`` en tramos cortos para responder rápido al usuario.

        Args:
            segundos: Duración total.
            punto_control: Se llama en cada tramo; puede bloquear (pausa) o
                lanzar :class:`ErrorDescargaCancelada` (cancelación).
            al_avanzar: Recibe ``(transcurrido, total)`` para dibujar una cuenta regresiva.
        """
        fin = self._reloj() + segundos
        while (restante := fin - self._reloj()) > 0:
            if punto_control:
                punto_control()
            if al_avanzar:
                al_avanzar(segundos - restante, segundos)
            self._dormir(min(0.2, restante))
        if al_avanzar:
            al_avanzar(segundos, segundos)
