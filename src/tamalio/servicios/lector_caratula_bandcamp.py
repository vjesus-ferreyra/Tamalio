# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Lee la carátula de un álbum de Bandcamp abriendo su página en un navegador real."""

import logging
import re
from typing import TYPE_CHECKING

from tamalio.interfaces.lector_caratula_pagina import LectorCaratulaPagina

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Playwright

registro = logging.getLogger(__name__)


class LectorCaratulaBandcamp(LectorCaratulaPagina):
    """
    Obtiene la carátula de un álbum de Bandcamp con Playwright.

    Solo se usa en el caso raro en que cada pista del álbum trae una carátula
    distinta y el JSON de ``yt-dlp`` no dice cuál es la del álbum. Se usa un
    navegador real (sin ventana) porque Bandcamp responde a los clientes
    automáticos con su «Client Challenge», que un navegador resuelve solo.

    La carátula está en este nodo de la página::

        #centerWrapper > #propOpenWrapper > #pgBd
          > div.trackView.leftMiddleColumns.has-art > div.middleColumn
            > #tralbumArt > a > picture > source / img

    Se toma, por orden: el ``href`` del enlace (la imagen a tamaño completo), el
    ``srcset`` de ``source`` y el ``src`` de ``img``. El extractor convierte
    después la URL a la versión original (``_0``).

    Args:
        tiempo_espera: Segundos máximos para cargar la página y encontrar la carátula.
        canales: Navegadores que se prueban en orden. ``None`` es el Chromium que
            instala ``playwright install chromium``; ``"chrome"`` es el Google
            Chrome del sistema, por si el primero no está instalado.
    """

    # Del más específico (la ruta exacta) al más general, por si Bandcamp
    # cambia los contenedores externos.
    _SELECTORES = (
        "#centerWrapper #propOpenWrapper #pgBd div.trackView.leftMiddleColumns.has-art div.middleColumn #tralbumArt",
        "#pgBd #tralbumArt",
        "#tralbumArt",
    )
    # Solo se aceptan imágenes del servidor de Bandcamp.
    _PATRON_IMAGEN = re.compile(r"^https?://[^/\s]*bcbits\.com/img/\S+\.(?:jpe?g|png)(?:\?\S*)?$", re.IGNORECASE)
    # Devuelve los posibles orígenes de la imagen dentro de #tralbumArt.
    _LEER_NODO = """(arte) => {
        const enlace = arte.querySelector('a');
        const fuente = arte.querySelector('picture source');
        const imagen = arte.querySelector('img');
        return [
            enlace ? enlace.href : null,
            fuente ? fuente.srcset : null,
            imagen ? (imagen.currentSrc || imagen.src) : null,
            imagen ? imagen.srcset : null,
        ];
    }"""

    def __init__(self, tiempo_espera: float = 45.0, canales: tuple[str | None, ...] = (None, "chrome")) -> None:
        self._milisegundos = int(tiempo_espera * 1000)
        self._canales = canales

    def url_caratula(self, url_pagina: str) -> str | None:
        """Ver :meth:`LectorCaratulaPagina.url_caratula`."""
        try:
            from playwright.sync_api import Error as ErrorPlaywright
            from playwright.sync_api import sync_playwright
        except ImportError:
            registro.warning(
                "No se pudo leer la carátula del álbum en su página: Playwright no está instalado. "
                "Instálalo con «uv add playwright» y «uv run playwright install chromium»."
            )
            return None

        try:
            with sync_playwright() as playwright:
                navegador = self._abrir_navegador(playwright, ErrorPlaywright)
                if navegador is None:
                    return None
                try:
                    return self._leer_pagina(navegador, url_pagina)
                finally:
                    navegador.close()
        except ErrorPlaywright as error:
            registro.warning("No se pudo leer la carátula del álbum en %s: %s", url_pagina, str(error).splitlines()[0])
            return None

    def _abrir_navegador(self, playwright: Playwright, tipo_error: type[Exception]) -> Browser | None:
        """Abre el primer navegador disponible de :attr:`_canales`, sin ventana."""
        for canal in self._canales:
            try:
                if canal is None:
                    return playwright.chromium.launch(headless=True)
                return playwright.chromium.launch(headless=True, channel=canal)
            except tipo_error as error:
                registro.debug("No se pudo abrir el navegador %s: %s", canal or "chromium", error)
        registro.warning(
            "No se pudo leer la carátula del álbum en su página: no hay un navegador para Playwright. "
            "Instálalo con «uv run playwright install chromium»."
        )
        return None

    def _leer_pagina(self, navegador: Browser, url_pagina: str) -> str | None:
        """Carga la página, espera la carátula y devuelve su URL."""
        contexto = navegador.new_context(locale="en-US")
        try:
            pagina = contexto.new_page()
            # El modo sin ventana se anuncia como «HeadlessChrome»; Bandcamp lo
            # trata como un robot, así que se usa el agente de un Chrome normal.
            agente = str(pagina.evaluate("navigator.userAgent"))
            if "HeadlessChrome" in agente:
                contexto.close()
                contexto = navegador.new_context(locale="en-US", user_agent=agente.replace("HeadlessChrome", "Chrome"))
                pagina = contexto.new_page()

            pagina.goto(url_pagina, wait_until="domcontentloaded", timeout=self._milisegundos)
            # Si aparece el «Client Challenge», la espera dura hasta que el navegador lo resuelve.
            pagina.wait_for_selector("#tralbumArt", state="attached", timeout=self._milisegundos)
            for selector in self._SELECTORES:
                nodo = pagina.query_selector(selector)
                if nodo is not None:
                    url = self._elegir_url(nodo.evaluate(self._LEER_NODO))
                    if url:
                        return url
            registro.warning("La página %s no muestra una carátula reconocible.", url_pagina)
            return None
        finally:
            contexto.close()

    @classmethod
    def _elegir_url(cls, candidatas: list[str | None]) -> str | None:
        """Primera URL de imagen de Bandcamp entre ``href``, ``src`` y ``srcset`` («url 1x, url 2x»)."""
        for texto in candidatas:
            for parte in (texto or "").split(","):
                url = parte.strip().split(" ")[0]
                if cls._PATRON_IMAGEN.match(url):
                    return url
        return None
