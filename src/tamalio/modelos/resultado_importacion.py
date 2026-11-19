# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Resultado de importar un catálogo exportado desde otro equipo."""

from dataclasses import dataclass, field

from tamalio.modelos.pista import Pista


@dataclass(slots=True)
class ResultadoImportacion:
    """
    Clasificación de las pistas de un catálogo importado.

    Attributes:
        vinculadas: Pistas nuevas en el catálogo cuyo fichero ya existe en esta biblioteca.
        faltantes: Pistas sin fichero local (candidatas a descargarse).
        ya_existian: Pistas que ya estaban descargadas en el catálogo local.
    """

    vinculadas: list[Pista] = field(default_factory=list)
    faltantes: list[Pista] = field(default_factory=list)
    ya_existian: list[Pista] = field(default_factory=list)
