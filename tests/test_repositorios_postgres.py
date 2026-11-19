"""
Pruebas de integración con PostgreSQL.

Se ejecutan solo si existe la variable ``TAMALIO_BD_PRUEBAS`` con la cadena de
conexión a una base **desechable** (las tablas se vacían)::

    TAMALIO_BD_PRUEBAS=postgresql://tamalio:tamalio@localhost:5432/tamalio_pruebas uv run pytest
"""

import io
import os
from pathlib import Path

import pytest

from tamalio.controladores.controlador_sistema import ControladorSistema
from tamalio.modelos.caratula import Caratula
from tamalio.modelos.conjunto_datos import ConjuntoDatos
from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma
from tamalio.repositorios.conexion_postgres import ConexionPostgres
from tamalio.repositorios.repositorio_catalogo_postgres import RepositorioCatalogoPostgres
from tamalio.repositorios.repositorio_sesiones_postgres import RepositorioSesionesPostgres
from tamalio.repositorios.repositorio_tareas_postgres import RepositorioTareasPostgres
from tamalio.vistas.vista_consola import VistaConsola

URL = os.environ.get("TAMALIO_BD_PRUEBAS")
pytestmark = [pytest.mark.postgres, pytest.mark.skipif(not URL, reason="TAMALIO_BD_PRUEBAS no está definida")]


@pytest.fixture
def conexion():
    assert URL is not None  # Garantizado por el skipif; informa al verificador de tipos.
    bd = ConexionPostgres(URL)
    bd.migrar()
    bd.vaciar(list(ConjuntoDatos))
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
    assert leida is not None
    assert leida.titulo == "Lights (remaster)" and leida.artistas == ["Klaypex"] and leida.duracion == 248.322
    assert repositorio.listar(texto="klaypex")[0].id_externo == "20732176"
    assert repositorio.buscar_por_ruta(tmp_path / "Lights.m4a") is not None


def test_cola_evita_duplicados_activos(conexion, detector):
    repositorio = RepositorioTareasPostgres(conexion)
    fuente = detector.detectar("https://music.youtube.com/watch?v=FB9u24ZpDek", metadatos={"generos": ["X"]})
    tarea, nueva = repositorio.agregar(fuente)
    assert nueva and tarea.id is not None
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
    assert leida is not None
    assert leida.fuente.metadatos == {"generos": ["X"]} and leida.intentos == 1


def test_sesiones(conexion, tmp_path):
    repositorio = RepositorioSesionesPostgres(conexion)
    repositorio.guardar(Plataforma.YOUTUBE, tmp_path / "c.txt")
    repositorio.guardar(Plataforma.YOUTUBE, tmp_path / "d.txt")
    assert repositorio.listar() == {Plataforma.YOUTUBE: tmp_path / "d.txt"}
    assert repositorio.eliminar(Plataforma.YOUTUBE) and not repositorio.eliminar(Plataforma.YOUTUBE)


def test_borrar_bd_exige_la_palabra_exacta(conexion):
    RepositorioSesionesPostgres(conexion).guardar(Plataforma.YOUTUBE, Path("/tmp/c.txt"))
    vista = VistaConsola(salida=io.StringIO(), color=False)
    sistema = ControladorSistema(vista)
    assert sistema.borrar_bd(conexion, [ConjuntoDatos.SESIONES], "borrar") == 1  # minúsculas: no vale
    assert conexion.contar([ConjuntoDatos.SESIONES])[ConjuntoDatos.SESIONES] == 1
    assert sistema.borrar_bd(conexion, [ConjuntoDatos.SESIONES], "BORRAR") == 0
    assert conexion.contar([ConjuntoDatos.SESIONES])[ConjuntoDatos.SESIONES] == 0
