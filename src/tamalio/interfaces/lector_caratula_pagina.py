# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Contrato para obtener la carátula que muestra la página web de un álbum."""

from abc import ABC, abstractmethod


class LectorCaratulaPagina(ABC):
    """
    Lee la URL de la carátula directamente de la página de un álbum.

    Es el último recurso cuando el JSON de ``yt-dlp`` no permite saber cuál es
    la carátula del álbum (por ejemplo, en Bandcamp, cuando cada pista trae una
    imagen distinta y el álbum no trae ninguna).
    """

    @abstractmethod
    def url_caratula(self, url_pagina: str) -> str | None:
        """
        Devuelve la URL de la carátula que aparece en ``url_pagina``.

        Args:
            url_pagina: Dirección de la página del álbum.

        Returns:
            La URL de la imagen, o ``None`` si no se pudo obtener. Nunca lanza
            excepciones: un fallo aquí no debe detener la descarga.
        """
