"""Administra los ficheros de cookies (tokens de sesión) de cada plataforma."""

from collections.abc import Callable
from pathlib import Path

from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.interfaces.repositorio_sesiones import RepositorioSesiones
from tamalio.modelos.plataforma import Plataforma


class GestorSesiones:
    """
    Decide qué fichero de cookies usar y lo pide al usuario cuando hace falta.

    Prioridad de búsqueda:

    1. Ruta registrada en la base de datos (``tamalio sesion establecer`` o la
       respuesta que el usuario dio cuando la plataforma nos detectó como bot).
    2. Ruta escrita en la sección ``[sesiones]`` de ``tamalio.toml``.

    El fichero debe estar en **formato Netscape** (el que exportan extensiones
    como «Get cookies.txt LOCALLY» o ``yt-dlp --cookies-from-browser … --cookies``).

    Args:
        repositorio: Persistencia de rutas (``None`` si no hay base de datos).
        configuradas: Rutas de ``[sesiones]`` en la configuración.
        solicitante: Función ``(plataforma, error_previo) -> respuesta`` que pregunta
            al usuario por la ruta (la inyecta el controlador usando la vista).
            ``error_previo`` trae el motivo por el que la respuesta anterior no
            sirvió. Devuelve ``None`` si el usuario no responde.
    """

    def __init__(
        self,
        repositorio: RepositorioSesiones | None,
        configuradas: dict[Plataforma, Path] | None = None,
        solicitante: Callable[[Plataforma, str | None], str | None] | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._configuradas = dict(configuradas or {})
        self._solicitante = solicitante

    def establecer_solicitante(self, solicitante: Callable[[Plataforma, str | None], str | None] | None) -> None:
        """Cambia la función que pregunta al usuario (útil al cambiar de vista)."""
        self._solicitante = solicitante

    def ruta_cookies(self, plataforma: Plataforma) -> Path | None:
        """Ruta de cookies vigente para la plataforma, solo si el fichero existe."""
        candidatas = []
        if self._repositorio is not None:
            candidatas.append(self._repositorio.obtener(plataforma))
        candidatas.append(self._configuradas.get(plataforma))
        for ruta in candidatas:
            if ruta is not None and ruta.is_file():
                return ruta
        return None

    def solicitar(self, plataforma: Plataforma) -> Path | None:
        """
        Pregunta al usuario por el fichero de cookies, lo valida y lo registra.

        Returns:
            La ruta validada, o ``None`` si no hay forma de preguntar o el
            usuario dejó la respuesta vacía.
        """
        if self._solicitante is None:
            return None
        error_previo: str | None = None
        for _ in range(3):  # Tres oportunidades para escribir una ruta válida.
            respuesta = self._solicitante(plataforma, error_previo)
            if not respuesta:
                return None
            try:
                # Se quitan comillas por si el usuario arrastró el fichero a la terminal.
                return self.registrar(plataforma, Path(respuesta.strip().strip("'\"")))
            except ErrorTamalio as error:
                error_previo = error.mensaje
        return None

    def registrar(self, plataforma: Plataforma, ruta: Path) -> Path:
        """Valida y guarda la ruta para usos futuros."""
        validada = self.validar(ruta)
        if self._repositorio is not None:
            self._repositorio.guardar(plataforma, validada)
        else:
            self._configuradas[plataforma] = validada
        return validada

    @staticmethod
    def validar(ruta: Path) -> Path:
        """
        Comprueba que el fichero exista y parezca un ``cookies.txt`` de Netscape.

        Raises:
            ErrorTamalio: Con una explicación de qué está mal.
        """
        ruta = ruta.expanduser().resolve()
        if not ruta.is_file():
            raise ErrorTamalio(f"No existe el fichero «{ruta}».")
        with ruta.open(encoding="utf-8", errors="replace") as fichero:
            muestra = fichero.read(4096)
        encabezado_valido = "# Netscape HTTP Cookie File" in muestra or "# HTTP Cookie File" in muestra
        lineas_validas = any(
            len(linea.split("\t")) == 7 for linea in muestra.splitlines() if linea and not linea.startswith("#")
        )
        if not (encabezado_valido or lineas_validas):
            raise ErrorTamalio(
                f"«{ruta.name}» no parece un fichero de cookies en formato Netscape.",
                sugerencia="Expórtalo con una extensión «cookies.txt» o con yt-dlp --cookies-from-browser.",
            )
        return ruta
