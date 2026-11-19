# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Analizador de JSONC: JSON con comentarios y comas finales, legible por humanos y máquinas."""

import json
from typing import Any


class AnalizadorJsonc:
    """
    Convierte texto JSONC en objetos de Python usando solo la biblioteca estándar.

    JSONC es JSON con dos comodidades extra (las mismas que acepta VS Code en
    ``settings.json``):

    - Comentarios de línea ``// …`` y de bloque ``/* … */``.
    - Comas finales opcionales: ``[1, 2, 3,]`` o ``{"a": 1,}``.

    El análisis respeta las cadenas: ``"https://ejemplo.com"`` contiene ``//``
    pero no es un comentario. Los comentarios se reemplazan por espacios (y se
    conservan los saltos de línea) para que los números de línea y columna de
    los errores coincidan con el fichero original.
    """

    def cargar(self, texto: str) -> Any:
        """
        Analiza ``texto`` y devuelve el objeto resultante.

        Raises:
            ValueError: Con línea y columna del error, en español.
        """
        limpio = self.quitar_comas_finales(self.quitar_comentarios(texto.lstrip("﻿")))
        try:
            return json.loads(limpio)
        except json.JSONDecodeError as error:
            raise ValueError(f"JSON inválido en la línea {error.lineno}, columna {error.colno}: {error.msg}") from None

    @staticmethod
    def quitar_comentarios(texto: str) -> str:
        """Sustituye los comentarios por espacios respetando cadenas y saltos de línea."""
        resultado: list[str] = []
        i, n = 0, len(texto)
        en_cadena = False
        while i < n:
            caracter = texto[i]
            siguiente = texto[i + 1] if i + 1 < n else ""
            if en_cadena:
                resultado.append(caracter)
                if caracter == "\\" and siguiente:
                    # Carácter escapado (\" o \\): se copia tal cual y se salta.
                    resultado.append(siguiente)
                    i += 2
                    continue
                if caracter == '"':
                    en_cadena = False
                i += 1
            elif caracter == '"':
                en_cadena = True
                resultado.append(caracter)
                i += 1
            elif caracter == "/" and siguiente == "/":
                # Comentario de línea: hasta el salto de línea (que se conserva).
                fin = texto.find("\n", i)
                fin = n if fin == -1 else fin
                resultado.append(" " * (fin - i))
                i = fin
            elif caracter == "/" and siguiente == "*":
                fin = texto.find("*/", i + 2)
                if fin == -1:
                    raise ValueError("Comentario de bloque «/*» sin cerrar.")
                bloque = texto[i : fin + 2]
                # Se conservan los saltos de línea del bloque para no alterar la numeración.
                resultado.append("".join("\n" if c == "\n" else " " for c in bloque))
                i = fin + 2
            else:
                resultado.append(caracter)
                i += 1
        return "".join(resultado)

    @staticmethod
    def quitar_comas_finales(texto: str) -> str:
        """Elimina las comas que van justo antes de ``]`` o ``}`` (fuera de cadenas)."""
        resultado: list[str] = []
        en_cadena = escapado = False
        for caracter in texto:
            if en_cadena:
                resultado.append(caracter)
                if escapado:
                    escapado = False
                elif caracter == "\\":
                    escapado = True
                elif caracter == '"':
                    en_cadena = False
                continue
            if caracter == '"':
                en_cadena = True
            elif caracter in "]}":
                # Retrocede sobre espacios y quita una coma colgante si la hay.
                j = len(resultado) - 1
                while j >= 0 and resultado[j].isspace():
                    j -= 1
                if j >= 0 and resultado[j] == ",":
                    resultado[j] = " "
            resultado.append(caracter)
        return "".join(resultado)

    @staticmethod
    def volcar(datos: Any, encabezado: list[str] | None = None) -> str:
        """
        Serializa ``datos`` como JSONC con sangría y comentarios de encabezado.

        Args:
            datos: Objeto a serializar.
            encabezado: Líneas de comentario que se escriben al inicio (sin ``//``).
        """
        lineas = [f"// {linea}".rstrip() for linea in (encabezado or [])]
        lineas.append(json.dumps(datos, ensure_ascii=False, indent=2))
        return "\n".join(lineas) + "\n"
