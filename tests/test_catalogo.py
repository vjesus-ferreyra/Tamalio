# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Pruebas de exportación e importación del catálogo entre «equipos»."""

import pytest

from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma
from tamalio.repositorios.repositorio_catalogo_postgres import RepositorioCatalogoPostgres
from tamalio.servicios.analizador_jsonc import AnalizadorJsonc
from tamalio.servicios.exportador_catalogo import ExportadorCatalogo
from tamalio.servicios.importador_catalogo import ImportadorCatalogo
from tamalio.servicios.recursos_empaquetados import RecursosEmpaquetados
from tamalio.servicios.validador_esquema import ValidadorEsquema
from tests.dobles.repositorio_catalogo_memoria import RepositorioCatalogoMemoria


def crear_pista(raiz, numero):
    ruta = raiz / "Bandcamp" / "GHOST DATA" / "Album (2022)" / f"0{numero} - Pista {numero}.flac"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(b"audio")
    return Pista(
        plataforma=Plataforma.BANDCAMP,
        id_externo=str(numero),
        url=f"https://ghostdata.bandcamp.com/track/pista-{numero}",
        titulo=f"Pista {numero}",
        album="Album",
        artistas=["GHOST DATA"],
        artistas_album=["GHOST DATA"],
        numero_pista=numero,
        total_pistas=2,
        anio=2022,
        formato="flac",
        ruta_archivo=ruta,
    )


def test_exportar_e_importar_entre_equipos(tmp_path):
    raiz_a, raiz_b = tmp_path / "equipo_a", tmp_path / "equipo_b"
    pistas = [crear_pista(raiz_a, 1), crear_pista(raiz_a, 2)]
    fichero = ExportadorCatalogo(raiz_a, "quetzal").exportar(pistas, tmp_path / "catalogo.jsonc")

    # El fichero exportado es JSONC válido según su $schema, con rutas relativas.
    documento = AnalizadorJsonc().cargar(fichero.read_text(encoding="utf-8"))
    assert ValidadorEsquema(RecursosEmpaquetados.esquema("catalogo")).validar(documento) == []
    assert documento["$schema"].endswith("catalogo.schema.json")
    assert documento["pistas"][0]["ruta_relativa"] == "Bandcamp/GHOST DATA/Album (2022)/01 - Pista 1.flac"

    # En el equipo B solo existe la primera pista (copiada a mano).
    copia = raiz_b / "Bandcamp" / "GHOST DATA" / "Album (2022)" / "01 - Pista 1.flac"
    copia.parent.mkdir(parents=True)
    copia.write_bytes(b"audio")
    catalogo_b = RepositorioCatalogoMemoria()
    resultado = ImportadorCatalogo(catalogo_b, raiz_b).importar(fichero)
    assert [p.titulo for p in resultado.vinculadas] == ["Pista 1"]
    assert [p.titulo for p in resultado.faltantes] == ["Pista 2"]
    primera, segunda_pista = catalogo_b.obtener(Plataforma.BANDCAMP, "1"), catalogo_b.obtener(Plataforma.BANDCAMP, "2")
    assert primera is not None and primera.descargada
    assert segunda_pista is not None and not segunda_pista.descargada

    # Importar de nuevo no duplica nada.
    segunda = ImportadorCatalogo(catalogo_b, raiz_b).importar(fichero)
    assert len(segunda.ya_existian) == 1 and len(catalogo_b.pistas) == 2


def test_metadatos_fijos_reproducen_la_pista(tmp_path):
    original = crear_pista(tmp_path, 1)
    nueva = Pista(Plataforma.BANDCAMP, "1", original.url, "otro", "otro", ["x"], ["x"], es_sencillo=True)
    nueva.aplicar_metadatos(original.metadatos_fijos())
    for campo in ("titulo", "album", "artistas", "artistas_album", "numero_pista", "total_pistas", "anio"):
        assert getattr(nueva, campo) == getattr(original, campo)
    assert not nueva.es_sencillo


@pytest.mark.parametrize(
    ("texto", "patron"),
    [
        ("klaypex", "%klaypex%"),
        ("100%", "%100\\%%"),
        ("mi_cancion", "%mi\\_cancion%"),
        ("AC\\DC", "%AC\\\\DC%"),
        ("%_%", "%\\%\\_\\%%"),
    ],
)
def test_busqueda_del_catalogo_escapa_comodines_like(texto, patron):
    assert RepositorioCatalogoPostgres._patron_contiene(texto) == patron
