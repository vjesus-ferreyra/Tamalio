# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Observador que solo anota los eventos recibidos, para verificarlos en las pruebas."""

from tamalio.interfaces.observador_descargas import ObservadorDescargas


class ObservadorRegistrador(ObservadorDescargas):
    """Guarda en :attr:`eventos` una tupla ``(nombre, datos…)`` por cada llamada."""

    def __init__(self) -> None:
        self.eventos: list[tuple] = []

    def _anotar(self, *evento) -> None:
        self.eventos.append(evento)

    def nombres(self) -> list[str]:
        """Solo los nombres de los eventos, en orden."""
        return [evento[0] for evento in self.eventos]

    def al_iniciar_tarea(self, tarea, posicion, total):
        self._anotar("iniciar_tarea", tarea.id)

    def al_resolver_tarea(self, tarea, titulo, pistas):
        self._anotar("resolver_tarea", titulo, pistas)

    def al_iniciar_pista(self, pista, posicion, total):
        self._anotar("iniciar_pista", pista.titulo)

    def al_cambiar_fase(self, fase, detalle=None):
        self._anotar("fase", fase)

    def al_progreso(self, progreso):
        self._anotar("progreso", progreso.fase)

    def al_completar_pista(self, pista, tamano_bytes):
        self._anotar("completar_pista", pista.titulo)

    def al_omitir_pista(self, pista, motivo):
        self._anotar("omitir_pista", pista.titulo, motivo)

    def al_fallar_pista(self, pista, mensaje):
        self._anotar("fallar_pista", pista.titulo if pista else None, mensaje)

    def al_terminar_tarea(self, tarea, resumen):
        self._anotar("terminar_tarea", tarea.estado)

    def al_aviso(self, mensaje):
        self._anotar("aviso", mensaje)
