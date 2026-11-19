# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Dibujo de barras de progreso y formateo de cantidades para la terminal."""

from tamalio.vistas.estilos_consola import EstilosConsola


class BarraProgreso:
    """
    Genera el texto de una barra de progreso con resolución de medio carácter.

    Ejemplo (con color, el tramo pendiente se ve atenuado)::

        ━━━━━━━━━━━━━━╸━━━━━━━━━   62%

    Si el total es desconocido se dibuja una barra «indeterminada»: un
    segmento brillante que se desplaza de un lado a otro.

    Args:
        estilos: Estilos de la consola.
    """

    #: Fotogramas del indicador giratorio (*spinner*).
    GIRO = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    GIRO_ASCII = "|/-\\"

    def __init__(self, estilos: EstilosConsola) -> None:
        self._estilos = estilos

    def dibujar(self, fraccion: float | None, ancho: int, fotograma: int = 0) -> str:
        """
        Devuelve la barra de ``ancho`` caracteres.

        Args:
            fraccion: Avance entre 0 y 1, o ``None`` si es indeterminado.
            ancho: Ancho en caracteres.
            fotograma: Contador para animar la barra indeterminada.
        """
        ancho = max(ancho, 4)
        lleno_u, medio_u, vacio_u = ("━", "╸", "━") if self._estilos.unicode else ("#", ">", "-")
        if fraccion is None:
            segmento = max(3, ancho // 5)
            recorrido = ancho - segmento
            posicion = fotograma % (2 * recorrido) if recorrido else 0
            inicio = posicion if posicion <= recorrido else 2 * recorrido - posicion
            return (
                self._estilos.tenue(vacio_u * inicio)
                + self._estilos.acento(lleno_u * segmento)
                + self._estilos.tenue(vacio_u * (ancho - inicio - segmento))
            )
        medios = round(max(0.0, min(1.0, fraccion)) * ancho * 2)
        completos, mitad = divmod(medios, 2)
        texto_lleno = lleno_u * completos + (medio_u if mitad else "")
        restantes = ancho - completos - mitad
        color = self._estilos.exito if fraccion >= 1 else self._estilos.acento
        return color(texto_lleno) + self._estilos.tenue(vacio_u * restantes)

    def giro(self, fotograma: int) -> str:
        """Carácter del *spinner* para el fotograma dado."""
        cuadros = self.GIRO if self._estilos.unicode else self.GIRO_ASCII
        return self._estilos.acento(cuadros[fotograma % len(cuadros)])

    # ------------------------------------------------------------------ #
    @staticmethod
    def formatear_bytes(cantidad: float | None) -> str:
        """``1536`` → ``"1.5 KB"`` (base 1024, unidades en español)."""
        if cantidad is None:
            return "?"
        valor = float(cantidad)
        for unidad in ("B", "KB", "MB", "GB"):
            if valor < 1024 or unidad == "GB":
                return f"{valor:.0f} {unidad}" if unidad == "B" else f"{valor:.1f} {unidad}"
            valor /= 1024
        return f"{valor:.1f} GB"

    @staticmethod
    def formatear_tiempo(segundos: float | None) -> str:
        """``75`` → ``"1:15"``; ``3725`` → ``"1:02:05"``."""
        if segundos is None or segundos < 0:
            return "--:--"
        total = round(segundos)
        horas, resto = divmod(total, 3600)
        minutos, seg = divmod(resto, 60)
        return f"{horas}:{minutos:02d}:{seg:02d}" if horas else f"{minutos}:{seg:02d}"
