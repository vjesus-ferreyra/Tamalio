# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Importa un catálogo exportado desde otro equipo."""

from pathlib import Path

from tamalio.excepciones.error_formato_fuentes import ErrorFormatoFuentes
from tamalio.interfaces.repositorio_catalogo import RepositorioCatalogo
from tamalio.modelos.pista import Pista
from tamalio.modelos.resultado_importacion import ResultadoImportacion
from tamalio.servicios.analizador_jsonc import AnalizadorJsonc
from tamalio.servicios.recursos_empaquetados import RecursosEmpaquetados
from tamalio.servicios.validador_esquema import ValidadorEsquema


class ImportadorCatalogo:
    """
    Lee un fichero ``catalogo.schema.json`` y lo fusiona con el catálogo local.

    Para cada pista:

    1. Si ya está en el catálogo local con su fichero → se deja igual.
    2. Si su ``ruta_relativa`` existe dentro de esta biblioteca → se registra
       como descargada (vinculada) sin bajar nada.
    3. En otro caso → se registra sin fichero y queda como **faltante**; el
       controlador puede encolar su URL para descargarla.

    Args:
        repositorio: Catálogo local.
        raiz_biblioteca: Biblioteca de este equipo.
        analizador: Analizador JSONC.
    """

    def __init__(
        self,
        repositorio: RepositorioCatalogo,
        raiz_biblioteca: Path,
        analizador: AnalizadorJsonc | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._raiz = raiz_biblioteca
        self._analizador = analizador or AnalizadorJsonc()

    def leer(self, ruta: Path) -> list[Pista]:
        """
        Analiza y valida el fichero; devuelve las pistas que contiene.

        Raises:
            ErrorFormatoFuentes: Si el fichero no es legible o no cumple el esquema.
        """
        try:
            documento = self._analizador.cargar(ruta.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as error:
            raise ErrorFormatoFuentes(ruta, [str(error)]) from error
        errores = ValidadorEsquema(RecursosEmpaquetados.esquema("catalogo")).validar(documento)
        if errores:
            raise ErrorFormatoFuentes(ruta, errores)
        return [Pista.desde_diccionario(datos, self._raiz) for datos in documento["pistas"]]

    def importar(self, ruta: Path) -> ResultadoImportacion:
        """Fusiona el fichero con el catálogo local (ver la descripción de la clase)."""
        resultado = ResultadoImportacion()
        for pista in self.leer(ruta):
            existente = self._repositorio.obtener(pista.plataforma, pista.id_externo)
            if existente is not None and existente.descargada:
                resultado.ya_existian.append(existente)
                continue
            if pista.ruta_archivo is not None and pista.ruta_archivo.is_file():
                resultado.vinculadas.append(pista)
            else:
                pista.ruta_archivo = None
                resultado.faltantes.append(pista)
            self._repositorio.guardar(pista)
        return resultado
