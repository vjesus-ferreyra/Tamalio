# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Contrato del cliente que extrae metadatos y descarga audio de las plataformas."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tamalio.modelos.fuente import Fuente
from tamalio.modelos.pista import Pista
from tamalio.modelos.progreso_descarga import ProgresoDescarga


class ClienteMedios(ABC):
    """
    Lo que el :class:`~tamalio.servicios.gestor_descargas.GestorDescargas`
    necesita de un descargador.

    La implementación real es :class:`~tamalio.servicios.cliente_yt_dlp.ClienteYtDlp`;
    las pruebas usan un doble que no toca la red. Depender de esta abstracción
    (y no de ``yt-dlp``) es lo que permite probar el flujo completo sin internet.
    """

    @abstractmethod
    def extraer(self, fuente: Fuente, punto_control: Callable[[], None] | None = None) -> dict[str, Any]:
        """
        Obtiene los metadatos crudos de una pista o colección.

        Args:
            fuente: Enlace a analizar.
            punto_control: Función que puede pausar o cancelar (lanza
                :class:`ErrorDescargaCancelada`) durante la extracción.
        """

    @abstractmethod
    def descargar(
        self,
        pista: Pista,
        al_progreso: Callable[[ProgresoDescarga], None] | None = None,
        punto_control: Callable[[], None] | None = None,
    ) -> tuple[Path, dict[str, Any]]:
        """
        Descarga el audio de la pista.

        Returns:
            ``(fichero_descargado, info_final)``.
        """
