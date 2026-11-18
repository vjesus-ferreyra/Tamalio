"""Pruebas del analizador JSONC, del validador de esquemas y de los lectores de fuentes."""

from pathlib import Path

import pytest

from conftest import RAIZ_PROYECTO
from tamalio.excepciones.error_formato_fuentes import ErrorFormatoFuentes
from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.plataforma import Plataforma
from tamalio.servicios.analizador_jsonc import AnalizadorJsonc
from tamalio.servicios.fabrica_lectores_fuentes import FabricaLectoresFuentes
from tamalio.servicios.recursos_empaquetados import RecursosEmpaquetados
from tamalio.servicios.validador_esquema import ValidadorEsquema

JSONC = AnalizadorJsonc()


# ---------------------------------------------------------------------- #
# JSONC
# ---------------------------------------------------------------------- #
def test_jsonc_comentarios_y_comas_finales():
    texto = """
    // comentario
    {
      "url": "https://ejemplo.com/a//b", /* bloque
      de varias líneas */
      "lista": [1, 2, 3,],
      "cita": "un \\"//\\" dentro",
    }
    """
    assert JSONC.cargar(texto) == {"url": "https://ejemplo.com/a//b", "lista": [1, 2, 3], "cita": 'un "//" dentro'}


def test_jsonc_error_conserva_numero_de_linea():
    with pytest.raises(ValueError, match="línea 4"):
        JSONC.cargar('{\n  // comentario\n  /* otro */\n  "a": }')


def test_jsonc_volcar_con_encabezado():
    texto = AnalizadorJsonc.volcar({"a": 1}, ["Hola"])
    assert texto.startswith("// Hola\n{")
    assert JSONC.cargar(texto) == {"a": 1}


# ---------------------------------------------------------------------- #
# Esquemas
# ---------------------------------------------------------------------- #
@pytest.mark.parametrize(("ejemplo", "esquema"), [("fuentes.jsonc", "fuentes"), ("catalogo.jsonc", "catalogo")])
def test_ejemplos_cumplen_su_esquema(ejemplo, esquema):
    documento = JSONC.cargar((RAIZ_PROYECTO / "ejemplos" / ejemplo).read_text(encoding="utf-8"))
    assert ValidadorEsquema(RecursosEmpaquetados.esquema(esquema)).validar(documento) == []


def test_validador_reporta_rutas_json():
    errores = ValidadorEsquema(RecursosEmpaquetados.esquema("fuentes")).validar(
        {"version": 2, "fuentes": [{"url": "https://youtu.be/x", "formato": "wma", "extra": 1}, 5]}
    )
    assert "$.version: debe valer 1." in errores
    assert any(e.startswith("$.fuentes[0].formato") for e in errores)
    assert any("propiedad desconocida «extra»" in e for e in errores)
    assert any(e.startswith("$.fuentes[1]") for e in errores)


# ---------------------------------------------------------------------- #
# Lectores de fuentes
# ---------------------------------------------------------------------- #
def test_lector_texto(tmp_path: Path, detector):
    fichero = tmp_path / "lista.txt"
    fichero.write_text(
        "# encabezado\n\nhttps://youtu.be/FB9u24ZpDek  # comentario\n"
        "https://music.youtube.com/watch?v=FB9u24ZpDek\n"  # Duplicada (misma pista).
        "https://soundcloud.com/klaypex/sets/loosedirt\n",
        encoding="utf-8",
    )
    fuentes = FabricaLectoresFuentes(detector).leer(fichero)
    assert [f.plataforma for f in fuentes] == [Plataforma.YOUTUBE, Plataforma.SOUNDCLOUD]


def test_lector_texto_reporta_lineas_invalidas(tmp_path: Path, detector):
    fichero = tmp_path / "lista.txt"
    fichero.write_text("https://youtu.be/FB9u24ZpDek\nhttps://vimeo.com/1\n", encoding="utf-8")
    with pytest.raises(ErrorFormatoFuentes) as error:
        FabricaLectoresFuentes(detector).leer(fichero)
    assert error.value.errores[0].startswith("línea 2")


def test_lector_jsonc_del_ejemplo(detector):
    fuentes = FabricaLectoresFuentes(detector).leer(RAIZ_PROYECTO / "ejemplos" / "fuentes.jsonc")
    assert len(fuentes) == 6  # La fuente con «omitir: true» no cuenta.
    album_youtube = fuentes[1]
    assert album_youtube.formato is FormatoAudio.FLAC
    assert album_youtube.metadatos == {"generos": ["K-Pop", "Pop"]}
    # Los predeterminados se aplican a quien no define formato.
    assert fuentes[0].formato is FormatoAudio.ORIGINAL


def test_lector_jsonc_combina_metadatos_predeterminados(tmp_path: Path, detector):
    fichero = tmp_path / "f.jsonc"
    fichero.write_text(
        '{"version": 1, "predeterminados": {"metadatos": {"generos": "Rock", "anio": 2000}},'
        ' "fuentes": [{"url": "https://youtu.be/FB9u24ZpDek", "metadatos": {"anio": 2001}}]}',
        encoding="utf-8",
    )
    (fuente,) = FabricaLectoresFuentes(detector).leer(fichero)
    assert fuente.metadatos == {"generos": "Rock", "anio": 2001}


def test_lector_jsonc_invalido(tmp_path: Path, detector):
    fichero = tmp_path / "f.jsonc"
    fichero.write_text('{"version": 1, "fuentes": []}', encoding="utf-8")
    with pytest.raises(ErrorFormatoFuentes, match="al menos 1"):
        FabricaLectoresFuentes(detector).leer(fichero)
