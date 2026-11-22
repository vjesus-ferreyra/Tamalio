# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""
Pruebas del lector de carátulas de Bandcamp con Playwright.

Las que abren un navegador usan una página local con la misma estructura que
la de Bandcamp (no salen a internet) y se omiten si no hay Playwright o
ningún navegador instalado.
"""

import builtins
import shutil
from pathlib import Path

import pytest

from tamalio.servicios.lector_caratula_bandcamp import LectorCaratulaBandcamp

IMAGEN_GRANDE = "https://f4.bcbits.com/img/a2468013579_10.jpg"
IMAGEN_MEDIANA = "https://f4.bcbits.com/img/a2468013579_16.jpg"

# Misma ruta que la página real:
# #centerWrapper > #propOpenWrapper > #pgBd > div.trackView… > div.middleColumn > #tralbumArt > a > picture
PAGINA_ALBUM = f"""<!DOCTYPE html>
<html><body>
<div id="centerWrapper"><div id="propOpenWrapper"><div id="pgBd">
  <div class="trackView leftMiddleColumns has-art">
    <div class="middleColumn">
      <div id="tralbumArt">
        <a class="popupImage" href="{IMAGEN_GRANDE}">
          <picture>
            <source srcset="{IMAGEN_MEDIANA} 1x, {IMAGEN_GRANDE} 2x">
            <img src="{IMAGEN_MEDIANA}" alt="Reunidos">
          </picture>
        </a>
      </div>
    </div>
  </div>
</div></div></div>
</body></html>
"""


def hay_navegador() -> bool:
    """``True`` si Playwright está instalado y tiene su Chromium o Google Chrome."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as playwright:
            if Path(playwright.chromium.executable_path).exists():
                return True
    except Exception:  # Un Playwright roto equivale a no tenerlo: se omiten las pruebas.
        return False
    return any(shutil.which(nombre) for nombre in ("google-chrome", "google-chrome-stable", "chrome"))


con_navegador = pytest.mark.skipif(not hay_navegador(), reason="Playwright o su navegador no están instalados")


# ---------------------------------------------------------------------- #
# Sin navegador
# ---------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("candidatas", "esperada"),
    [
        ([IMAGEN_GRANDE, None, IMAGEN_MEDIANA, None], IMAGEN_GRANDE),  # El enlace va primero.
        ([None, f"{IMAGEN_MEDIANA} 1x, {IMAGEN_GRANDE} 2x", None, None], IMAGEN_MEDIANA),
        (["https://x.bandcamp.com/album/reunidos", None, IMAGEN_MEDIANA, None], IMAGEN_MEDIANA),
        (["javascript:void(0)", "", None, "data:image/gif;base64,R0lG 1x"], None),
    ],
)
def test_elige_la_primera_imagen_de_bandcamp(candidatas, esperada):
    assert LectorCaratulaBandcamp._elegir_url(candidatas) == esperada


def test_sin_playwright_devuelve_none_y_avisa(monkeypatch, caplog):
    importar = builtins.__import__

    def importar_sin_playwright(nombre, *args, **kwargs):
        if nombre.startswith("playwright"):
            raise ImportError(nombre)
        return importar(nombre, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", importar_sin_playwright)
    assert LectorCaratulaBandcamp().url_caratula("https://x.bandcamp.com/album/reunidos") is None
    assert "Playwright no está instalado" in caplog.text


# ---------------------------------------------------------------------- #
# Con navegador real
# ---------------------------------------------------------------------- #
@con_navegador
def test_lee_la_caratula_de_la_pagina_del_album(tmp_path):
    pagina = tmp_path / "album.html"
    pagina.write_text(PAGINA_ALBUM, encoding="utf-8")
    assert LectorCaratulaBandcamp(tiempo_espera=20).url_caratula(pagina.as_uri()) == IMAGEN_GRANDE


@con_navegador
def test_sin_enlace_usa_la_imagen(tmp_path):
    pagina = tmp_path / "album.html"
    pagina.write_text(PAGINA_ALBUM.replace(f'href="{IMAGEN_GRANDE}"', ""), encoding="utf-8")
    assert LectorCaratulaBandcamp(tiempo_espera=20).url_caratula(pagina.as_uri()) == IMAGEN_MEDIANA


@con_navegador
def test_pagina_sin_caratula_devuelve_none(tmp_path, caplog):
    pagina = tmp_path / "otra.html"
    pagina.write_text("<!DOCTYPE html><html><body><p>Client Challenge</p></body></html>", encoding="utf-8")
    assert LectorCaratulaBandcamp(tiempo_espera=2).url_caratula(pagina.as_uri()) is None
    assert "No se pudo leer la carátula" in caplog.text
