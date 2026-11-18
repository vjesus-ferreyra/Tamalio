"""Pruebas de servicios sin red: organizador, temporizador, control, sesiones y configuración."""

import random
import threading
import time
from pathlib import Path

import pytest

from dobles.repositorio_sesiones_memoria import RepositorioSesionesMemoria
from tamalio.configuracion.configuracion import Configuracion
from tamalio.excepciones.error_descarga_cancelada import ErrorDescargaCancelada
from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.modelos.alcance_cancelacion import AlcanceCancelacion
from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma
from tamalio.servicios.control_ejecucion import ControlEjecucion
from tamalio.servicios.gestor_sesiones import GestorSesiones
from tamalio.servicios.organizador_biblioteca import OrganizadorBiblioteca
from tamalio.servicios.temporizador_humano import TemporizadorHumano


# ---------------------------------------------------------------------- #
# Organizador de la biblioteca
# ---------------------------------------------------------------------- #
def pista(**cambios) -> Pista:
    datos = {
        "plataforma": Plataforma.YOUTUBE,
        "id_externo": "x",
        "url": "u",
        "titulo": "FIRESTARTER",
        "album": "FIRESTARTER",
        "artistas": ["K/DA"],
        "artistas_album": ["K/DA"],
        "numero_pista": 1,
        "total_pistas": 4,
        "anio": 2026,
    }
    datos.update(cambios)
    return Pista(**datos)


def test_estructura_de_carpetas(tmp_path):
    organizador = OrganizadorBiblioteca(tmp_path / "Música" / "quetzal")
    organizador.preparar()
    assert sorted(p.name for p in (tmp_path / "Música" / "quetzal").iterdir()) == ["Bandcamp", "SoundCloud", "YouTube"]
    ruta = organizador.ruta_para(pista(), "opus")
    assert ruta == tmp_path / "Música/quetzal/YouTube/K-DA/FIRESTARTER (2026)/01 - FIRESTARTER.opus"
    sencillo = organizador.ruta_para(pista(es_sencillo=True, titulo="Nightmare"), ".mp3")
    assert sencillo.parent.name == "Sencillos" and sencillo.name == "Nightmare.mp3"


@pytest.mark.parametrize(
    ("entrada", "salida"),
    [
        ('Otra: canción? <"x">', "Otra - canción ('x')"),
        ("CON", "_CON"),
        ("  puntos al final...  ", "puntos al final"),
        ("", "Sin nombre"),
        ("a" * 300, "a" * 120),
    ],
)
def test_sanear_nombres(entrada, salida):
    assert OrganizadorBiblioteca.sanear(entrada) == salida


def test_colocar_no_sobrescribe(tmp_path):
    organizador = OrganizadorBiblioteca(tmp_path)
    destino = tmp_path / "a" / "cancion.flac"
    for contenido in ("uno", "dos"):
        temporal = tmp_path / f"{contenido}.tmp"
        temporal.write_text(contenido)
        organizador.colocar(temporal, destino)
    assert sorted(p.name for p in destino.parent.iterdir()) == ["cancion (2).flac", "cancion.flac"]


# ---------------------------------------------------------------------- #
# Temporizador humano
# ---------------------------------------------------------------------- #
def test_esperas_dentro_del_rango_y_pausas_largas():
    temporizador = TemporizadorHumano(
        2.0, 6.0, pausa_larga_cada=(5, 5), pausa_larga=(30.0, 40.0), azar=random.Random(7)
    )
    esperas = [temporizador.siguiente_espera() for _ in range(20)]
    largas = [e for e in esperas if e >= 30]
    assert len(largas) == 4  # Una de cada cinco.
    assert all(2.0 <= e <= 6.0 for e in esperas if e < 30)
    assert len(set(esperas)) > 10  # Realmente aleatorias.


def test_backoff_crece_con_los_intentos():
    temporizador = TemporizadorHumano(azar=random.Random(1))
    assert 30 <= temporizador.espera_bloqueo(1) <= 90
    assert temporizador.espera_bloqueo(4, limite_peticiones=True) <= 30 + 1200


def test_esperar_llama_al_punto_de_control():
    reloj = iter(x * 0.1 for x in range(100))
    llamadas = []
    temporizador = TemporizadorHumano(reloj=lambda: next(reloj), dormir=lambda _s: None)
    temporizador.esperar(0.5, punto_control=lambda: llamadas.append(1), al_avanzar=lambda h, t: None)
    assert llamadas


# ---------------------------------------------------------------------- #
# Control de ejecución
# ---------------------------------------------------------------------- #
def test_pausa_bloquea_hasta_reanudar():
    control = ControlEjecucion()
    estados = []
    control.al_cambiar_pausa(estados.append)
    control.alternar_pausa()
    threading.Timer(0.3, control.alternar_pausa).start()
    inicio = time.monotonic()
    control.punto_control()
    assert time.monotonic() - inicio >= 0.25
    assert estados == [True, False]


def test_saltar_y_detener():
    control = ControlEjecucion()
    control.saltar_pista()
    with pytest.raises(ErrorDescargaCancelada) as senal:
        control.punto_control()
    assert senal.value.alcance is AlcanceCancelacion.PISTA
    control.limpiar_pista()
    control.punto_control()  # Ya no lanza.
    control.detener_todo()
    with pytest.raises(ErrorDescargaCancelada) as senal:
        control.punto_control()
    assert senal.value.alcance is AlcanceCancelacion.TODO and senal.value.pausar


def test_pausa_desde_otra_terminal():
    estado = {"valor": EstadoDescarga.EN_PROCESO}
    control = ControlEjecucion(intervalo_consulta=0)
    control.preparar_tarea(lambda: estado["valor"])
    control.punto_control()
    estado["valor"] = EstadoDescarga.PAUSADA
    with pytest.raises(ErrorDescargaCancelada) as senal:
        control.punto_control()
    assert senal.value.alcance is AlcanceCancelacion.TAREA and senal.value.pausar


# ---------------------------------------------------------------------- #
# Sesiones
# ---------------------------------------------------------------------- #
def test_sesiones_validan_formato_netscape(tmp_path: Path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tabc\n")
    invalido = tmp_path / "otro.txt"
    invalido.write_text("hola")
    respuestas = iter([str(invalido), f'"{cookies}"'])
    errores = []

    def solicitante(_plataforma, error):
        errores.append(error)
        return next(respuestas)

    repositorio = RepositorioSesionesMemoria()
    gestor = GestorSesiones(repositorio, solicitante=solicitante)
    assert gestor.solicitar(Plataforma.YOUTUBE) == cookies.resolve()
    assert errores[0] is None and "Netscape" in errores[1]
    assert gestor.ruta_cookies(Plataforma.YOUTUBE) == cookies.resolve()
    with pytest.raises(ErrorTamalio):
        GestorSesiones.validar(tmp_path / "no-existe.txt")


# ---------------------------------------------------------------------- #
# Configuración
# ---------------------------------------------------------------------- #
def test_configuracion_toml_y_entorno(tmp_path, monkeypatch):
    fichero = tmp_path / "tamalio.toml"
    fichero.write_text(
        '[general]\nusuario = "quetzal"\nformato_salida = "FLAC"\n'
        "[red]\nespera_minima = 1.0\nespera_maxima = 2.0\npausa_larga_cada = [3, 4]\n"
        '[sesiones]\nyoutube_music = "~/c.txt"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("TAMALIO_BD_URL", "postgresql://otra")
    config = Configuracion.cargar(fichero)
    assert config.usuario == "quetzal"
    assert config.formato_salida.value == "flac"
    assert config.red_pausa_larga_cada == (3, 4)
    assert Plataforma.YOUTUBE in config.sesiones
    assert config.bd_url == "postgresql://otra"
    assert config.raiz_biblioteca.name == "quetzal"


def test_configuracion_rechaza_opciones_desconocidas(tmp_path):
    fichero = tmp_path / "tamalio.toml"
    fichero.write_text("[red]\nvelocidad_luz = 1\n", encoding="utf-8")
    with pytest.raises(ErrorTamalio, match="velocidad_luz"):
        Configuracion.cargar(fichero)
