# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Controlador de los comandos del catálogo (listar, exportar e importar)."""

from pathlib import Path

from tamalio.configuracion.configuracion import Configuracion
from tamalio.controladores.controlador_descargas import ControladorDescargas
from tamalio.interfaces.repositorio_catalogo import RepositorioCatalogo
from tamalio.interfaces.vista import Vista
from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.plataforma import Plataforma
from tamalio.servicios.detector_plataforma import DetectorPlataforma
from tamalio.servicios.exportador_catalogo import ExportadorCatalogo
from tamalio.servicios.importador_catalogo import ImportadorCatalogo


class ControladorCatalogo:
    """
    Casos de uso del catálogo personal.

    Args:
        vista: Vista activa.
        catalogo: Repositorio del catálogo.
        config: Configuración (raíz de la biblioteca y usuario).
        descargas: Controlador de descargas (para bajar lo que falte al importar).
        detector: Clasificador de URL.
    """

    def __init__(
        self,
        vista: Vista,
        catalogo: RepositorioCatalogo,
        config: Configuracion,
        descargas: ControladorDescargas,
        detector: DetectorPlataforma,
    ) -> None:
        self._vista = vista
        self._catalogo = catalogo
        self._config = config
        self._descargas = descargas
        self._detector = detector

    def listar(self, plataforma: Plataforma | None, texto: str | None) -> int:
        """``tamalio catalogo listar``."""
        pistas = self._catalogo.listar(plataforma, texto)
        if not pistas:
            self._vista.mostrar_info("No hay pistas que coincidan." if texto else "Tu catálogo está vacío.")
            return 0
        filas = [
            (
                pista.plataforma.nombre_visible,
                pista.artista_album_principal,
                pista.album,
                pista.numero_pista,
                pista.anio,
                pista.formato or "—",
                "sí" if pista.descargada else "no",
                pista.titulo,
            )
            for pista in pistas
        ]
        self._vista.mostrar_tabla(
            ("Plataforma", "Artista", "Álbum", "#", "Año", "Formato", "En disco", "Título"), filas
        )
        descargadas = sum(1 for pista in pistas if pista.descargada)
        self._vista.mostrar_info(f"{len(pistas)} pista(s) · {descargadas} en disco.")
        return 0

    def exportar(self, fichero: Path, plataforma: Plataforma | None) -> int:
        """``tamalio catalogo exportar``."""
        pistas = self._catalogo.listar(plataforma)
        exportador = ExportadorCatalogo(self._config.raiz_biblioteca, self._config.usuario)
        ruta = exportador.exportar(pistas, fichero.expanduser())
        self._vista.mostrar_exito(f"{len(pistas)} pista(s) exportadas a «{ruta}».")
        return 0

    def importar(self, fichero: Path, descargar: bool, formato: FormatoAudio | None) -> int:
        """``tamalio catalogo importar``: vincula lo existente y opcionalmente descarga lo que falte."""
        importador = ImportadorCatalogo(self._catalogo, self._config.raiz_biblioteca)
        resultado = importador.importar(fichero.expanduser())
        self._vista.mostrar_exito(
            f"Importado: {len(resultado.vinculadas)} vinculada(s) con ficheros existentes, "
            f"{len(resultado.faltantes)} por descargar, {len(resultado.ya_existian)} ya estaban."
        )
        if not resultado.faltantes:
            return 0
        if not descargar:
            self._vista.mostrar_info("Descarga las faltantes con «tamalio catalogo importar FICHERO --descargar».")
            return 0
        # Cada pista se descarga suelta; sus metadatos originales se fijan para que queden idénticos.
        fuentes = [
            self._detector.detectar(
                pista.url,
                plataforma=pista.plataforma,
                formato=formato or (FormatoAudio(pista.formato) if pista.formato else None),
                metadatos=pista.metadatos_fijos(),
                comentario=f"Importada: {pista.titulo}",
            )
            for pista in resultado.faltantes
        ]
        return self._descargas.encolar_y_procesar(fuentes)
