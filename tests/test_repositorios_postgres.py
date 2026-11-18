"""
Pruebas de integración con PostgreSQL.

Se ejecutan solo si existe la variable ``TAMALIO_BD_PRUEBAS`` con la cadena de
conexión a una base **desechable** (las tablas se vacían)::

    TAMALIO_BD_PRUEBAS=postgresql://tamalio:tamalio@localhost:5432/tamalio_pruebas uv run pytest
"""

import os

import pytest

from tamalio.modelos.caratula import Caratula
from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma
from tamalio.repositorios.conexion_postgres import ConexionPostgres
from tamalio.repositorios.repositorio_catalogo_postgres import RepositorioCatalogoPostgres
from tamalio.repositorios.repositorio_sesiones_postgres import RepositorioSesionesPostgres
from tamalio.repositorios.repositorio_tareas_postgres import RepositorioTareasPostgres

URL = os.environ.get("TAMALIO_BD_PRUEBAS")
pytestmark = [pytest.mark.postgres, pytest.mark.skipif(not URL, reason="TAMALIO_BD_PRUEBAS no está definida")]


@pytest.fixture
def conexion():
    bd = ConexionPostgres(URL)
    bd.migrar()
    bd.conexion.execute("TRUNCATE pistas, tareas_descarga, sesiones_plataforma RESTART IDENTITY")
    yield bd
    bd.cerrar()


def test_catalogo_upsert_y_busqueda(conexion, tmp_path):
    repositorio = RepositorioCatalogoPostgres(conexion)
    pista = Pista(
        plataforma=Plataforma.SOUNDCLOUD,
        id_externo="20732176",
        url="https://soundcloud.com/klaypex/lights",
        titulo="Lights",
        album="Loose Dirt",
        artistas=["Klaypex"],
        artistas_album=["Klaypex"],
        numero_pista=1,
        total_pistas=7,
        generos=["Dance"],
        anio=2011,
        duracion=248.322,
        caratula=Caratula("https://i1.sndcdn.com/a-original.png"),
        ruta_archivo=tmp_path / "Lights.m4a",
    )
    repositorio.guardar(pista)
    pista.titulo = "Lights (remaster)"
    repositorio.guardar(pista)  # Upsert: no duplica.
    assert len(repositorio.listar()) == 1
    leida = repositorio.obtener(Plataforma.SOUNDCLOUD, "20732176")
    assert leida.titulo == "Lights (remaster)" and leida.artistas == ["Klaypex"] and leida.duracion == 248.322
    assert repositorio.listar(texto="klaypex")[0].id_externo == "20732176"
    assert repositorio.buscar_por_ruta(tmp_path / "Lights.m4a") is not None


def test_cola_evita_duplicados_activos(conexion, detector):
    repositorio = RepositorioTareasPostgres(conexion)
    fuente = detector.detectar("https://music.youtube.com/watch?v=FB9u24ZpDek", metadatos={"generos": ["X"]})
    tarea, nueva = repositorio.agregar(fuente)
    assert nueva
    _, otra_vez = repositorio.agregar(detector.detectar("https://youtu.be/FB9u24ZpDek"))
    assert not otra_vez
    tarea.iniciar()
    tarea.completar()
    repositorio.actualizar(tarea)
    assert repositorio.estado_actual(tarea.id) is EstadoDescarga.COMPLETADA
    # Completada ya no es «activa»: se puede volver a encolar.
    _, nueva_otra_vez = repositorio.agregar(fuente)
    assert nueva_otra_vez
    leida = repositorio.obtener(tarea.id)
    assert leida.fuente.metadatos == {"generos": ["X"]} and leida.intentos == 1


def test_sesiones(conexion, tmp_path):
    repositorio = RepositorioSesionesPostgres(conexion)
    repositorio.guardar(Plataforma.YOUTUBE, tmp_path / "c.txt")
    repositorio.guardar(Plataforma.YOUTUBE, tmp_path / "d.txt")
    assert repositorio.listar() == {Plataforma.YOUTUBE: tmp_path / "d.txt"}
    assert repositorio.eliminar(Plataforma.YOUTUBE) and not repositorio.eliminar(Plataforma.YOUTUBE)
