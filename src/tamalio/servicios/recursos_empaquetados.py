"""Acceso a los ficheros que viajan dentro del paquete (esquemas JSON y SQL)."""

import json
from functools import cache
from importlib import resources
from typing import Any


class RecursosEmpaquetados:
    """
    Lee los recursos de ``tamalio/recursos`` con :mod:`importlib.resources`.

    Así los esquemas y el SQL funcionan igual en el repositorio clonado, en un
    *wheel* instalado con ``uv tool install`` o dentro de un ZIP.
    """

    PAQUETE = "tamalio.recursos"

    @classmethod
    @cache
    def esquema(cls, nombre: str) -> dict[str, Any]:
        """Carga ``recursos/esquemas/<nombre>.schema.json`` (con caché en memoria)."""
        texto = resources.files(cls.PAQUETE).joinpath("esquemas", f"{nombre}.schema.json").read_text("utf-8")
        return json.loads(texto)

    @classmethod
    def sql(cls, nombre: str) -> str:
        """Devuelve el contenido de ``recursos/sql/<nombre>``."""
        return resources.files(cls.PAQUETE).joinpath("sql", nombre).read_text("utf-8")

    @classmethod
    def guiones_sql(cls) -> list[str]:
        """Nombres de los guiones SQL en orden (``001_…``, ``002_…``)."""
        carpeta = resources.files(cls.PAQUETE).joinpath("sql")
        return sorted(item.name for item in carpeta.iterdir() if item.name.endswith(".sql"))
