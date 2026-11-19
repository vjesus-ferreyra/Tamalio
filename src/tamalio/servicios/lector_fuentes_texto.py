# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Lector del formato de fuentes más simple: una URL por línea."""

from pathlib import Path

from tamalio.excepciones.error_formato_fuentes import ErrorFormatoFuentes
from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.interfaces.lector_fuentes import LectorFuentes
from tamalio.modelos.fuente import Fuente
from tamalio.servicios.detector_plataforma import DetectorPlataforma


class LectorFuentesTexto(LectorFuentes):
    """
    Lee ficheros ``.txt`` / ``.lista`` con este formato::

        # Comentario de línea completa
        https://ghostdata.bandcamp.com/album/symphony-of-the-shepherdess
        https://soundcloud.com/klaypex/sets/loosedirt   # comentario al final

    - Las líneas vacías se ignoran.
    - ``#`` inicia un comentario (al inicio o tras un espacio en la línea).
    - Las URL repetidas se cargan una sola vez.

    Args:
        detector: Clasificador de URL.
    """

    EXTENSIONES = frozenset({".txt", ".lista", ".list", ".urls"})

    def __init__(self, detector: DetectorPlataforma) -> None:
        self._detector = detector

    def admite(self, ruta: Path, contenido: str) -> bool:
        """Por extensión, o si el contenido no empieza con ``{`` (no es JSON)."""
        if ruta.suffix.lower() in self.EXTENSIONES:
            return True
        primera = next((linea.strip() for linea in contenido.splitlines() if linea.strip()), "")
        return not primera.startswith(("{", "//", "/*"))

    def leer(self, ruta: Path, contenido: str) -> list[Fuente]:
        """Ver :meth:`LectorFuentes.leer`."""
        fuentes: list[Fuente] = []
        errores: list[str] = []
        vistas: set[str] = set()
        for numero, linea in enumerate(contenido.splitlines(), start=1):
            # «#» solo es comentario al inicio o precedido de espacio (las URL pueden tener «#»).
            texto = linea.strip()
            if not texto or texto.startswith("#"):
                continue
            texto = texto.split(" #", 1)[0].split("\t#", 1)[0].strip()
            try:
                fuente = self._detector.detectar(texto)
            except ErrorTamalio as error:
                errores.append(f"línea {numero}: {error.mensaje}")
                continue
            if fuente.url not in vistas:
                vistas.add(fuente.url)
                fuentes.append(fuente)
        if errores:
            raise ErrorFormatoFuentes(ruta, errores)
        return fuentes
