# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Elige el lector adecuado para un fichero de fuentes."""

from pathlib import Path

from tamalio.excepciones.error_formato_fuentes import ErrorFormatoFuentes
from tamalio.interfaces.lector_fuentes import LectorFuentes
from tamalio.modelos.fuente import Fuente
from tamalio.servicios.detector_plataforma import DetectorPlataforma
from tamalio.servicios.lector_fuentes_jsonc import LectorFuentesJsonc
from tamalio.servicios.lector_fuentes_texto import LectorFuentesTexto


class FabricaLectoresFuentes:
    """
    Patrón *Factory* + *Chain of Responsibility*: pregunta a cada lector si
    admite el fichero y usa el primero que diga que sí.

    El orden importa: JSONC va primero porque su detección es más estricta;
    el lector de texto acepta cualquier cosa que no parezca JSON.

    Args:
        detector: Clasificador de URL que se comparte con los lectores.
    """

    def __init__(self, detector: DetectorPlataforma) -> None:
        self._lectores: list[LectorFuentes] = [LectorFuentesJsonc(detector), LectorFuentesTexto(detector)]

    def leer(self, ruta: Path) -> list[Fuente]:
        """
        Lee el fichero con el lector correspondiente.

        Raises:
            ErrorFormatoFuentes: Si no existe, no es legible o tiene errores.
        """
        try:
            contenido = ruta.read_text(encoding="utf-8-sig")
        except OSError as error:
            raise ErrorFormatoFuentes(ruta, [f"no se pudo leer: {error.strerror or error}"]) from error
        for lector in self._lectores:
            if lector.admite(ruta, contenido):
                return lector.leer(ruta, contenido)
        raise ErrorFormatoFuentes(ruta, ["formato no reconocido (usa .jsonc o .txt)"])
