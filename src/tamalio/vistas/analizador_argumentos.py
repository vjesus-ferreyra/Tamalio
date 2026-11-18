"""Definición de los comandos y opciones de la línea de comandos."""

import argparse
from pathlib import Path

from tamalio import ALIAS_AUTOR, NOMBRE, __version__
from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.plataforma import Plataforma
from tamalio.vistas.parser_espanol import ParserEspanol


class AnalizadorArgumentos:
    """
    Construye el árbol de comandos de ``tamalio`` (parte de la **Vista**: es la
    forma en que el usuario «habla» con la aplicación).

    Comandos::

        tamalio descargar  FUENTE… [-a FICHERO] [-f FORMATO] [-d DESTINO]
        tamalio cola       [--estado E…]
        tamalio reanudar   [ID…]
        tamalio reintentar [ID…] [--incluir-canceladas]
        tamalio pausar     (ID… | --todas)
        tamalio cancelar   (ID… | --todas)
        tamalio catalogo   listar | exportar FICHERO | importar FICHERO [--descargar]
        tamalio convertir  [RUTA…] (-f FORMATO) [--plataforma P | --todo]
        tamalio sesion     establecer PLATAFORMA RUTA | listar | quitar PLATAFORMA
        tamalio bd         iniciar
        tamalio doctor

    Args:
        color: Activa el color en la ayuda (``argparse`` de Python ≥ 3.14).
    """

    def __init__(self, color: bool = True) -> None:
        self._color = color
        self._parser = self._construir()

    def analizar(self, argumentos: list[str] | None = None) -> argparse.Namespace:
        """Analiza los argumentos; sin comando, muestra la ayuda general."""
        espacio = self._parser.parse_args(argumentos)
        if not getattr(espacio, "comando", None):
            self._parser.print_help()
            self._parser.exit(0)
        return espacio

    # ------------------------------------------------------------------ #
    def _nuevo(self, subparsers: argparse._SubParsersAction, nombre: str, ayuda: str, **extra) -> ParserEspanol:
        """Crea un subcomando con ``-h/--ayuda`` en español."""
        parser = subparsers.add_parser(
            nombre, help=ayuda, description=ayuda, add_help=False, color=self._color, **extra
        )
        parser.add_argument("-h", "--ayuda", action="help", help="Muestra esta ayuda y termina.")
        return parser

    def _construir(self) -> ParserEspanol:
        formatos = [formato.value for formato in FormatoAudio]
        plataformas = [plataforma.value for plataforma in Plataforma]

        parser = ParserEspanol(
            prog="tamalio",
            description=f"{NOMBRE}: extractor de música Hi-Fi desde YouTube, YouTube Music, SoundCloud y Bandcamp.",
            epilog=f"Ejemplo: tamalio descargar https://youtu.be/FB9u24ZpDek -f flac   ·   por {ALIAS_AUTOR}",
            add_help=False,
            suggest_on_error=True,
            color=self._color,
        )
        parser.add_argument("-h", "--ayuda", action="help", help="Muestra esta ayuda y termina.")
        parser.add_argument(
            "--version", action="version", version=f"{NOMBRE} {__version__}", help="Muestra la versión."
        )
        parser.add_argument("-v", "--detallado", action="store_true", help="Muestra detalles y mensajes de depuración.")
        parser.add_argument("--sin-color", action="store_true", help="Desactiva los colores.")
        parser.add_argument("--config", type=Path, metavar="RUTA", help="Fichero tamalio.toml alternativo.")

        sub = parser.add_subparsers(dest="comando", title="comandos", metavar="COMANDO")

        # descargar ----------------------------------------------------------
        descargar = self._nuevo(sub, "descargar", "Descarga una o varias fuentes (pistas, álbumes o listas).")
        descargar.add_argument(
            "fuentes", nargs="*", metavar="FUENTE", help="URL de YouTube, YouTube Music, SoundCloud o Bandcamp."
        )
        descargar.add_argument(
            "-a",
            "--archivo",
            action="append",
            type=Path,
            default=[],
            metavar="FICHERO",
            help="Fichero .jsonc o .txt con fuentes agrupadas (se puede repetir).",
        )
        descargar.add_argument(
            "-f", "--formato", choices=formatos, help="Formato de salida (predeterminado: original)."
        )
        descargar.add_argument("-d", "--destino", type=Path, metavar="CARPETA", help="Carpeta de música alternativa.")
        descargar.add_argument(
            "--plataforma", choices=plataformas, help="Fuerza la plataforma (dominios propios de Bandcamp)."
        )
        descargar.add_argument("--solo-encolar", action="store_true", help="Agrega a la cola sin descargar todavía.")

        # cola ------------------------------------------------------------------
        cola = self._nuevo(sub, "cola", "Muestra la cola de descargas.")
        cola.add_argument(
            "--estado", nargs="+", choices=[estado.value for estado in EstadoDescarga], help="Filtra por estado."
        )

        # reanudar / reintentar / pausar / cancelar -----------------------------
        reanudar = self._nuevo(sub, "reanudar", "Reanuda las tareas pendientes o pausadas.")
        reanudar.add_argument("ids", nargs="*", type=int, metavar="ID", help="Tareas concretas (todas si se omite).")

        reintentar = self._nuevo(sub, "reintentar", "Vuelve a intentar las tareas fallidas.")
        reintentar.add_argument("ids", nargs="*", type=int, metavar="ID", help="Tareas concretas (todas si se omite).")
        reintentar.add_argument("--incluir-canceladas", action="store_true", help="También reintenta las canceladas.")

        for nombre, ayuda in (
            ("pausar", "Pausa tareas (también si se están descargando en otra terminal)."),
            ("cancelar", "Cancela tareas (también si se están descargando en otra terminal)."),
        ):
            comando = self._nuevo(sub, nombre, ayuda)
            grupo = comando.add_mutually_exclusive_group(required=True)
            grupo.add_argument("ids", nargs="*", type=int, default=[], metavar="ID", help="Tareas a afectar.")
            grupo.add_argument("--todas", action="store_true", help="Todas las tareas activas.")

        # catalogo -------------------------------------------------------------
        catalogo = self._nuevo(sub, "catalogo", "Consulta, exporta o importa tu catálogo personal.")
        acciones = catalogo.add_subparsers(dest="accion", title="acciones", metavar="ACCION", required=True)
        listar = self._nuevo(acciones, "listar", "Lista las pistas del catálogo.")
        listar.add_argument("--plataforma", choices=plataformas, help="Filtra por plataforma.")
        listar.add_argument("--buscar", metavar="TEXTO", help="Busca en título, álbum o artistas.")
        exportar = self._nuevo(acciones, "exportar", "Exporta el catálogo a un fichero .jsonc portable.")
        exportar.add_argument("fichero", type=Path, metavar="FICHERO", help="Destino, p. ej. mi-catalogo.jsonc.")
        exportar.add_argument("--plataforma", choices=plataformas, help="Exporta solo una plataforma.")
        importar = self._nuevo(acciones, "importar", "Importa un catálogo exportado en otro equipo.")
        importar.add_argument("fichero", type=Path, metavar="FICHERO", help="Fichero .jsonc exportado.")
        importar.add_argument("--descargar", action="store_true", help="Descarga en seguida las pistas que falten.")
        importar.add_argument("-f", "--formato", choices=formatos, help="Formato para las pistas descargadas.")

        # convertir -------------------------------------------------------------
        convertir = self._nuevo(sub, "convertir", "Convierte música ya descargada a otro formato.")
        convertir.add_argument("rutas", nargs="*", type=Path, metavar="RUTA", help="Ficheros o carpetas a convertir.")
        convertir.add_argument("-f", "--formato", choices=formatos[1:], required=True, help="Formato de destino.")
        convertir.add_argument(
            "--plataforma", choices=plataformas, help="Convierte todo el catálogo de una plataforma."
        )
        convertir.add_argument("--todo", action="store_true", help="Convierte todo el catálogo.")
        convertir.add_argument("--conservar-original", action="store_true", help="No borra el fichero original.")

        # sesion ---------------------------------------------------------------
        sesion = self._nuevo(sub, "sesion", "Administra los ficheros de cookies (tokens de sesión).")
        acciones_sesion = sesion.add_subparsers(dest="accion", title="acciones", metavar="ACCION", required=True)
        establecer = self._nuevo(acciones_sesion, "establecer", "Registra el fichero de cookies de una plataforma.")
        establecer.add_argument("plataforma", choices=plataformas)
        establecer.add_argument("ruta", type=Path, metavar="RUTA", help="Fichero cookies.txt (formato Netscape).")
        self._nuevo(acciones_sesion, "listar", "Muestra los ficheros registrados.")
        quitar = self._nuevo(acciones_sesion, "quitar", "Olvida el fichero de una plataforma.")
        quitar.add_argument("plataforma", choices=plataformas)

        # bd y doctor ---------------------------------------------------------
        bd = self._nuevo(sub, "bd", "Administra la base de datos PostgreSQL.")
        acciones_bd = bd.add_subparsers(dest="accion", title="acciones", metavar="ACCION", required=True)
        self._nuevo(acciones_bd, "iniciar", "Crea o actualiza las tablas (idempotente).")

        self._nuevo(sub, "doctor", "Revisa que FFmpeg, QuickJS, PostgreSQL y demás estén listos.")
        return parser
