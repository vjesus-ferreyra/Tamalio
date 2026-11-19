# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Exporta el catálogo personal a un fichero JSONC portable entre equipos."""

import platform
from datetime import datetime
from pathlib import Path

from tamalio import NOMBRE, URL_ESQUEMAS, __version__
from tamalio.modelos.pista import Pista
from tamalio.servicios.analizador_jsonc import AnalizadorJsonc


class ExportadorCatalogo:
    """
    Escribe un fichero que cumple ``catalogo.schema.json``.

    El fichero **no contiene audio**: guarda los metadatos, la URL de origen y la
    ruta relativa de cada pista. En otro equipo, ``tamalio catalogo importar``
    vincula las pistas que ya existan en disco y descarga solo las que falten.

    Args:
        raiz_biblioteca: Carpeta de la biblioteca (las rutas se exportan relativas a ella).
        usuario: Nombre del usuario que exporta.
    """

    def __init__(self, raiz_biblioteca: Path, usuario: str) -> None:
        self._raiz = raiz_biblioteca
        self._usuario = usuario

    def documento(self, pistas: list[Pista]) -> dict:
        """Construye el diccionario a exportar."""
        return {
            "$schema": f"{URL_ESQUEMAS}/catalogo.schema.json",
            "version": 1,
            "aplicacion": {"nombre": NOMBRE, "version": __version__},
            "exportado_en": datetime.now().astimezone().isoformat(timespec="seconds"),
            "usuario": self._usuario,
            "equipo": platform.node() or "desconocido",
            "total": len(pistas),
            "pistas": [pista.a_diccionario(self._raiz) for pista in pistas],
        }

    def exportar(self, pistas: list[Pista], destino: Path) -> Path:
        """Escribe el fichero y devuelve su ruta."""
        destino.parent.mkdir(parents=True, exist_ok=True)
        encabezado = [
            f"Catálogo musical exportado por {NOMBRE} {__version__}.",
            "Contiene metadatos y enlaces de origen, no el audio.",
            "Impórtalo en otro equipo con:  tamalio catalogo importar <este fichero> --descargar",
        ]
        texto = AnalizadorJsonc.volcar(self.documento(pistas), encabezado)
        destino.write_text(texto, encoding="utf-8")
        return destino
