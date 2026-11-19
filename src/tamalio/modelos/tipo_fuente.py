# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Clasificación de una fuente: pista individual o colección de pistas."""

from enum import StrEnum


class TipoFuente(StrEnum):
    """Qué contiene una URL antes de consultarla con ``yt-dlp``."""

    #: Una sola canción (``watch?v=``, ``/track/``, ``soundcloud.com/usuario/pista``).
    PISTA = "pista"
    #: Álbum, EP, lista de reproducción, *set* o discografía.
    COLECCION = "coleccion"
    #: No se puede saber solo con la URL (enlaces cortos, dominios propios…).
    DESCONOCIDO = "desconocido"
