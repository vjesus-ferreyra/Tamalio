# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Contrato *Observer* con el que el modelo informa el avance sin conocer a la vista."""

from abc import ABC, abstractmethod

from tamalio.modelos.fase_proceso import FaseProceso
from tamalio.modelos.pista import Pista
from tamalio.modelos.progreso_descarga import ProgresoDescarga
from tamalio.modelos.resumen_ejecucion import ResumenEjecucion
from tamalio.modelos.tarea_descarga import TareaDescarga


class ObservadorDescargas(ABC):
    """
    Recibe los eventos del proceso de descarga.

    El servicio :class:`~tamalio.servicios.gestor_descargas.GestorDescargas`
    (modelo) llama a estos métodos; la vista de consola los implementa para
    dibujar las barras de progreso. Así el modelo nunca importa nada de la vista.
    """

    @abstractmethod
    def al_iniciar_tarea(self, tarea: TareaDescarga, posicion: int, total: int) -> None:
        """Empieza a procesarse la tarea ``posicion`` de ``total``."""

    @abstractmethod
    def al_resolver_tarea(self, tarea: TareaDescarga, titulo: str, pistas: int) -> None:
        """Se obtuvieron los metadatos: la fuente contiene ``pistas`` canciones."""

    @abstractmethod
    def al_iniciar_pista(self, pista: Pista, posicion: int, total: int) -> None:
        """Comienza el procesamiento de una pista."""

    @abstractmethod
    def al_cambiar_fase(self, fase: FaseProceso, detalle: str | None = None) -> None:
        """La pista actual pasó a otra fase (descargando, convirtiendo…)."""

    @abstractmethod
    def al_progreso(self, progreso: ProgresoDescarga) -> None:
        """Avance dentro de la fase actual."""

    @abstractmethod
    def al_completar_pista(self, pista: Pista, tamano_bytes: int) -> None:
        """La pista quedó guardada, etiquetada y registrada en el catálogo."""

    @abstractmethod
    def al_omitir_pista(self, pista: Pista, motivo: str) -> None:
        """La pista no se descargó (ya existía o el usuario la saltó)."""

    @abstractmethod
    def al_fallar_pista(self, pista: Pista | None, mensaje: str) -> None:
        """Falló una pista (o la extracción, si ``pista`` es ``None``)."""

    @abstractmethod
    def al_terminar_tarea(self, tarea: TareaDescarga, resumen: ResumenEjecucion) -> None:
        """La tarea terminó (en cualquier estado final o pausada)."""

    @abstractmethod
    def al_aviso(self, mensaje: str) -> None:
        """Mensaje informativo no crítico (reintentos, esperas largas, etc.)."""
