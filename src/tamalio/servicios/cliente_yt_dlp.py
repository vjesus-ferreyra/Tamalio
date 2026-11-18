"""Cliente de ``yt-dlp``: extracción de metadatos y descarga del mejor audio disponible."""

import copy
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.networking.impersonate import ImpersonateTarget
from yt_dlp.utils import DownloadCancelled, DownloadError, YoutubeDLError

from tamalio.configuracion.configuracion import Configuracion
from tamalio.excepciones.error_descarga_cancelada import ErrorDescargaCancelada
from tamalio.excepciones.error_deteccion_bot import ErrorDeteccionBot
from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.modelos.fase_proceso import FaseProceso
from tamalio.modelos.fuente import Fuente
from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma
from tamalio.modelos.progreso_descarga import ProgresoDescarga
from tamalio.servicios.registro_yt_dlp import RegistroYtDlp
from tamalio.servicios.temporizador_humano import TemporizadorHumano

registro = logging.getLogger(__name__)


class ClienteYtDlp:
    """
    Configura ``yt-dlp`` con las medidas anti-bloqueo del proyecto.

    - **Suplantación de navegador** (``impersonate``) mediante ``curl_cffi``,
      recomendada por la documentación de ``yt-dlp`` para sitios con
      *TLS fingerprinting*. Si ``curl_cffi`` no está disponible se continúa sin
      ella y se avisa en el registro.
    - **QuickJS** como intérprete de JavaScript para resolver los retos de
      YouTube (en lugar de Deno, el predeterminado de ``yt-dlp``).
    - **Esperas aleatorias** entre peticiones internas (``sleep_interval_requests``).
    - **Cookies** de sesión cuando la plataforma lo exige.
    - **Reanudación** de ficheros parciales (``continuedl``) y reintentos.

    Args:
        config: Configuración de la aplicación.
        carpeta_trabajo: Carpeta temporal para las descargas en bruto.
        temporizador: Fuente de esperas aleatorias.
        cookies: Fichero de cookies Netscape a usar, si lo hay.
    """

    #: Fragmentos de mensajes de error que indican bloqueo o sesión requerida.
    _PATRONES_BLOQUEO = re.compile(
        r"sign in to confirm|not a bot|captcha|login required|use --cookies|cookies for the authentication|"
        r"requires authentication|http error 429|too many requests|rate[- ]limit",
        re.IGNORECASE,
    )
    _PATRON_LIMITE = re.compile(r"http error 429|too many requests|rate[- ]limit", re.IGNORECASE)
    _PATRON_CADUCADO = re.compile(r"http error 403|forbidden|expired", re.IGNORECASE)

    #: Avisar una sola vez por proceso si la suplantación no está disponible.
    _aviso_suplantacion_emitido = False

    def __init__(
        self,
        config: Configuracion,
        carpeta_trabajo: Path,
        temporizador: TemporizadorHumano,
        cookies: Path | None = None,
    ) -> None:
        self._config = config
        self._carpeta_trabajo = carpeta_trabajo
        self._temporizador = temporizador
        self._cookies = cookies
        self._senal: ErrorDescargaCancelada | None = None

    # ================================================================== #
    # Opciones de yt-dlp
    # ================================================================== #
    def opciones(self, solo_pista: bool = False) -> dict[str, Any]:
        """Diccionario de opciones para ``YoutubeDL`` (útil también para depurar)."""
        self._carpeta_trabajo.mkdir(parents=True, exist_ok=True)
        runtime: dict[str, Any] = {}
        if self._config.js_ruta:
            runtime["path"] = str(self._config.js_ruta)
        opciones: dict[str, Any] = {
            # Salida silenciosa: la vista dibuja su propio progreso.
            "quiet": True,
            "noprogress": True,
            "logger": RegistroYtDlp(),
            # El mejor audio disponible; «best» como respaldo (se extrae el audio con FFmpeg).
            "format": "bestaudio/best",
            "outtmpl": {"default": "%(extractor_key)s-%(id)s.%(ext)s"},
            "paths": {"home": str(self._carpeta_trabajo), "temp": str(self._carpeta_trabajo)},
            "noplaylist": solo_pista,
            "continuedl": True,
            "overwrites": False,
            "retries": self._config.red_reintentos,
            "fragment_retries": self._config.red_reintentos,
            "extractor_retries": 3,
            "file_access_retries": 3,
            "socket_timeout": self._config.red_tiempo_espera,
            "concurrent_fragment_downloads": 1,
            "sleep_interval_requests": self._temporizador.espera_entre_peticiones(),
            "http_headers": {"Accept-Language": "es-MX,es;q=0.9,en;q=0.8"},
            "js_runtimes": {self._config.js_motor: runtime},
            "remote_components": list(self._config.js_componentes_remotos),
            "writethumbnail": False,
            "postprocessors": [],
        }
        if self._config.red_limite_velocidad:
            opciones["ratelimit"] = self._velocidad_en_bytes(self._config.red_limite_velocidad)
        if self._config.red_suplantar_navegador:
            opciones["impersonate"] = ImpersonateTarget.from_str(self._config.red_suplantar_navegador)
        if self._cookies:
            opciones["cookiefile"] = str(self._cookies)
        return opciones

    def _crear(self, opciones: dict[str, Any]) -> YoutubeDL:
        """Crea ``YoutubeDL``; si la suplantación no está disponible, reintenta sin ella."""
        try:
            return YoutubeDL(opciones)
        except YoutubeDLError as error:
            if "impersonate" not in opciones or "impersonate" not in str(error).lower():
                raise
            if not ClienteYtDlp._aviso_suplantacion_emitido:
                ClienteYtDlp._aviso_suplantacion_emitido = True
                registro.warning(
                    "La suplantación de navegador «%s» no está disponible (instala curl_cffi). Se continúa sin ella.",
                    self._config.red_suplantar_navegador,
                )
            sin_suplantar = {clave: valor for clave, valor in opciones.items() if clave != "impersonate"}
            return YoutubeDL(sin_suplantar)

    # ================================================================== #
    # Operaciones
    # ================================================================== #
    def extraer(self, fuente: Fuente) -> dict[str, Any]:
        """
        Obtiene los metadatos completos (sin descargar) de una pista o colección.

        Raises:
            ErrorDeteccionBot: Si la plataforma pidió verificación o sesión.
            ErrorTamalio: Para cualquier otro fallo de ``yt-dlp``.
        """
        with self._crear(self.opciones(fuente.solo_pista)) as ydl:
            try:
                info = ydl.extract_info(fuente.url, download=False)
            except (DownloadError, YoutubeDLError) as error:
                raise self._traducir(error, fuente.plataforma) from error
        if not info:
            raise ErrorTamalio(f"yt-dlp no devolvió información para «{fuente.url}».")
        return info

    def descargar(
        self,
        pista: Pista,
        al_progreso: Callable[[ProgresoDescarga], None] | None = None,
        punto_control: Callable[[], None] | None = None,
    ) -> tuple[Path, dict[str, Any]]:
        """
        Descarga el audio de la pista a la carpeta de trabajo.

        Usa la información ya extraída para no repetir peticiones. Si las URL de
        los formatos caducaron (HTTP 403, típico tras una pausa larga), vuelve a
        extraer la pista una sola vez.

        Returns:
            ``(ruta_del_fichero, info_final)``.

        Raises:
            ErrorDescargaCancelada: Si el usuario pausó/canceló durante la descarga.
            ErrorDeteccionBot: Si la plataforma bloqueó la descarga.
            ErrorTamalio: Para cualquier otro fallo.
        """
        self._senal = None
        opciones = self.opciones(solo_pista=True)
        opciones["progress_hooks"] = [self._crear_hook(al_progreso, punto_control)]
        info = pista.info_extraccion

        with self._crear(opciones) as ydl:
            try:
                if info and info.get("formats"):
                    resultado = ydl.process_ie_result(copy.deepcopy(info), download=True)
                else:
                    resultado = ydl.extract_info(pista.url, download=True)
            except (DownloadError, DownloadCancelled, YoutubeDLError) as error:
                if self._senal is not None:
                    raise self._senal from None
                if not (info and self._PATRON_CADUCADO.search(str(error))):
                    raise self._traducir(error, pista.plataforma) from error
                registro.info("Las URL de «%s» caducaron; se extrae de nuevo.", pista.titulo)
                try:
                    resultado = ydl.extract_info(pista.url, download=True)
                except (DownloadError, DownloadCancelled, YoutubeDLError) as segundo_error:
                    if self._senal is not None:
                        raise self._senal from None
                    raise self._traducir(segundo_error, pista.plataforma) from segundo_error

        descargas = resultado.get("requested_downloads") or []
        ruta = Path(descargas[0]["filepath"]) if descargas else None
        if ruta is None or not ruta.is_file():
            raise ErrorTamalio(f"yt-dlp terminó pero no se encontró el fichero de «{pista.titulo}».")
        return ruta, resultado

    # ================================================================== #
    # Auxiliares
    # ================================================================== #
    def _crear_hook(
        self,
        al_progreso: Callable[[ProgresoDescarga], None] | None,
        punto_control: Callable[[], None] | None,
    ) -> Callable[[dict[str, Any]], None]:
        """
        Construye el *hook* de progreso que ``yt-dlp`` llama varias veces por segundo.

        Dentro del *hook* se ejecuta el punto de control: si el usuario pausó, el
        hilo se bloquea aquí (la descarga se detiene sin cerrar el fichero
        parcial); si canceló, se guarda la señal y se lanza ``DownloadCancelled``,
        que es la forma oficial de abortar ``yt-dlp`` desde un *hook*.
        """

        def hook(estado: dict[str, Any]) -> None:
            if punto_control is not None:
                try:
                    punto_control()
                except ErrorDescargaCancelada as senal:
                    self._senal = senal
                    raise DownloadCancelled(str(senal)) from senal
            if al_progreso is None or estado.get("status") != "downloading":
                return
            al_progreso(
                ProgresoDescarga(
                    fase=FaseProceso.DESCARGANDO,
                    completado=float(estado.get("downloaded_bytes") or 0),
                    total=estado.get("total_bytes") or estado.get("total_bytes_estimate"),
                    velocidad=estado.get("speed"),
                    eta=estado.get("eta"),
                )
            )

        return hook

    def _traducir(self, error: Exception, plataforma: Plataforma) -> ErrorTamalio:
        """Convierte los errores de ``yt-dlp`` en excepciones propias con mensaje claro."""
        mensaje = re.sub(r"\x1b\[[0-9;]*m", "", str(error)).removeprefix("ERROR: ").strip()
        if self._PATRONES_BLOQUEO.search(mensaje):
            return ErrorDeteccionBot(plataforma, mensaje, limite_peticiones=bool(self._PATRON_LIMITE.search(mensaje)))
        return ErrorTamalio(f"yt-dlp: {mensaje}")

    @staticmethod
    def _velocidad_en_bytes(texto: str) -> int:
        """Convierte ``"2M"``, ``"500K"`` o ``"1048576"`` a bytes por segundo."""
        coincidencia = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMG]?)i?B?\s*", texto, re.IGNORECASE)
        if not coincidencia:
            raise ErrorTamalio(f"[red] limite_velocidad «{texto}» no es válido (ej.: «2M», «500K»).")
        factor = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3}[coincidencia[2].upper()]
        return int(float(coincidencia[1]) * factor)
