"""Validador ligero de JSON Schema (subconjunto de la versión 2020-12)."""

import re
from typing import Any, ClassVar


class ValidadorEsquema:
    """
    Valida documentos contra los esquemas propios de Tamalio sin dependencias externas.

    Implementa las palabras clave que usan ``fuentes.schema.json`` y
    ``catalogo.schema.json``: ``type``, ``properties``, ``required``,
    ``additionalProperties``, ``items``, ``enum``, ``const``, ``pattern``,
    ``minLength``, ``minimum``, ``maximum``, ``minItems``, ``oneOf``, ``anyOf``
    y ``$ref`` locales (``#/$defs/...``). Las palabras puramente descriptivas
    (``title``, ``description``, ``examples``, ``format``…) se ignoran.

    Args:
        esquema: Esquema raíz ya cargado como diccionario.
    """

    _TIPOS: ClassVar[dict[str, type]] = {
        "object": dict,
        "array": list,
        "string": str,
        "boolean": bool,
        "null": type(None),
    }

    def __init__(self, esquema: dict[str, Any]) -> None:
        self._raiz = esquema

    def validar(self, documento: Any) -> list[str]:
        """
        Devuelve la lista de errores (vacía si el documento es válido).

        Cada error indica la ruta JSON del problema, p. ej. ``$.fuentes[3].formato``.
        """
        errores: list[str] = []
        self._validar(documento, self._raiz, "$", errores)
        return errores

    # ------------------------------------------------------------------ #
    def _resolver(self, esquema: dict[str, Any]) -> dict[str, Any]:
        """Sigue ``$ref`` del tipo ``#/$defs/nombre`` dentro del esquema raíz."""
        while "$ref" in esquema:
            referencia = esquema["$ref"]
            if not referencia.startswith("#/"):
                raise ValueError(f"Solo se admiten referencias locales: {referencia}")
            nodo: Any = self._raiz
            for parte in referencia[2:].split("/"):
                nodo = nodo[parte]
            esquema = nodo
        return esquema

    def _es_tipo(self, valor: Any, tipo: str) -> bool:
        """Comprueba el tipo JSON (cuidando que ``bool`` no cuente como número)."""
        if tipo == "integer":
            return isinstance(valor, int) and not isinstance(valor, bool)
        if tipo == "number":
            return isinstance(valor, int | float) and not isinstance(valor, bool)
        return isinstance(valor, self._TIPOS[tipo])

    def _validar(self, valor: Any, esquema: dict[str, Any], ruta: str, errores: list[str]) -> None:
        """Validación recursiva de un nodo."""
        esquema = self._resolver(esquema)

        if "type" in esquema:
            tipos = esquema["type"] if isinstance(esquema["type"], list) else [esquema["type"]]
            if not any(self._es_tipo(valor, tipo) for tipo in tipos):
                errores.append(f"{ruta}: se esperaba {' o '.join(tipos)}, se encontró {type(valor).__name__}.")
                return

        if "const" in esquema and valor != esquema["const"]:
            errores.append(f"{ruta}: debe valer {esquema['const']!r}.")
        if "enum" in esquema and valor not in esquema["enum"]:
            opciones = ", ".join(repr(opcion) for opcion in esquema["enum"])
            errores.append(f"{ruta}: {valor!r} no es válido; opciones: {opciones}.")

        if isinstance(valor, str):
            if len(valor) < esquema.get("minLength", 0):
                errores.append(f"{ruta}: no puede estar vacío.")
            if "pattern" in esquema and not re.search(esquema["pattern"], valor):
                errores.append(f"{ruta}: «{valor}» no tiene el formato esperado.")

        if isinstance(valor, int | float) and not isinstance(valor, bool):
            if "minimum" in esquema and valor < esquema["minimum"]:
                errores.append(f"{ruta}: debe ser ≥ {esquema['minimum']}.")
            if "maximum" in esquema and valor > esquema["maximum"]:
                errores.append(f"{ruta}: debe ser ≤ {esquema['maximum']}.")

        if isinstance(valor, list):
            if len(valor) < esquema.get("minItems", 0):
                errores.append(f"{ruta}: debe tener al menos {esquema['minItems']} elemento(s).")
            if "items" in esquema:
                for indice, elemento in enumerate(valor):
                    self._validar(elemento, esquema["items"], f"{ruta}[{indice}]", errores)

        if isinstance(valor, dict):
            self._validar_objeto(valor, esquema, ruta, errores)

        if "oneOf" in esquema:
            self._validar_alternativas(valor, esquema["oneOf"], ruta, errores, exactamente_una=True)
        if "anyOf" in esquema:
            self._validar_alternativas(valor, esquema["anyOf"], ruta, errores, exactamente_una=False)

    def _validar_objeto(self, valor: dict[str, Any], esquema: dict[str, Any], ruta: str, errores: list[str]) -> None:
        """Reglas de objetos: requeridos, propiedades y propiedades adicionales."""
        for requerido in esquema.get("required", []):
            if requerido not in valor:
                errores.append(f"{ruta}: falta la propiedad obligatoria «{requerido}».")
        propiedades = esquema.get("properties", {})
        adicionales = esquema.get("additionalProperties", True)
        for clave, contenido in valor.items():
            ruta_hija = f"{ruta}.{clave}"
            if clave in propiedades:
                self._validar(contenido, propiedades[clave], ruta_hija, errores)
            elif adicionales is False:
                errores.append(f"{ruta}: propiedad desconocida «{clave}».")
            elif isinstance(adicionales, dict):
                self._validar(contenido, adicionales, ruta_hija, errores)

    def _validar_alternativas(
        self, valor: Any, opciones: list[dict[str, Any]], ruta: str, errores: list[str], exactamente_una: bool
    ) -> None:
        """``oneOf`` (exactamente una opción válida) y ``anyOf`` (al menos una)."""
        resultados = []
        for opcion in opciones:
            parciales: list[str] = []
            self._validar(valor, opcion, ruta, parciales)
            resultados.append(parciales)
        validas = sum(1 for parciales in resultados if not parciales)
        if validas == 0:
            # Se reporta la alternativa «más cercana»: primero las del mismo tipo
            # (si el valor es un objeto, los errores del esquema de objeto), y
            # entre ellas la de menos errores.
            mismo_tipo = [r for r in resultados if not any(e.startswith(f"{ruta}: se esperaba") for e in r)]
            errores.extend(min(mismo_tipo or resultados, key=len))
        elif exactamente_una and validas > 1:
            errores.append(f"{ruta}: coincide con más de una alternativa del esquema.")
