"""Carga y valida la configuración de Tamalio desde ``tamalio.toml`` y variables de entorno."""

import os
import re
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from tamalio.configuracion.rutas_sistema import RutasSistema
from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.plataforma import Plataforma

#: Cadena de conexión predeterminada a PostgreSQL.
URL_BD_PREDETERMINADA = "postgresql://tamalio:tamalio@localhost:5432/tamalio"


@dataclass(slots=True)
class Configuracion:
    """
    Todos los ajustes de la aplicación con valores predeterminados sensatos.

    Orden de prioridad (de menor a mayor):

    1. Valores predeterminados de esta clase.
    2. Fichero ``tamalio.toml`` (ver ``config/tamalio.ejemplo.toml``).
    3. Variables de entorno ``TAMALIO_*`` (útiles en servidores o CI).
    4. Opciones de la línea de comandos (las aplica el controlador).

    Los nombres de los atributos llevan el prefijo de su sección del TOML
    (``red_``, ``js_``…) para mantener una sola clase plana y fácil de usar.
    """

    # [general] ------------------------------------------------------------
    usuario: str = field(default_factory=RutasSistema.usuario_actual)
    carpeta_destino: Path = field(default_factory=lambda: RutasSistema().carpeta_musica())
    formato_salida: FormatoAudio = FormatoAudio.ORIGINAL
    agregar_invitados_a_artistas: bool = True

    # [red] ----------------------------------------------------------------
    red_suplantar_navegador: str = "auto"
    red_espera_minima: float = 3.0
    red_espera_maxima: float = 9.0
    red_pausa_larga_cada: tuple[int, int] = (8, 15)
    red_pausa_larga: tuple[float, float] = (25.0, 70.0)
    red_espera_entre_peticiones: tuple[float, float] = (0.6, 1.8)
    red_reintentos: int = 10
    red_reintentos_bloqueo: int = 2
    red_limite_velocidad: str | None = None
    red_tiempo_espera: float = 30.0

    # [javascript] ---------------------------------------------------------
    js_motor: str = "quickjs"
    js_ruta: Path | None = None
    js_componentes_remotos: list[str] = field(default_factory=list)

    # [caratula] -----------------------------------------------------------
    caratula_recortar_videos: bool = True
    caratula_calidad_jpeg: int = 2

    # [sesiones] -----------------------------------------------------------
    sesiones: dict[Plataforma, Path] = field(default_factory=dict)

    # [base_datos] ---------------------------------------------------------
    bd_url: str = URL_BD_PREDETERMINADA

    # Modo depuración (--debug o TAMALIO_DEBUG=1) ---------------------------
    depuracion: bool = False

    # Rutas derivadas ------------------------------------------------------
    carpeta_cache: Path = field(default_factory=lambda: RutasSistema().carpeta_cache())
    carpeta_estado: Path = field(default_factory=lambda: RutasSistema().carpeta_estado())
    ruta_fichero: Path | None = None

    # ------------------------------------------------------------------ #
    @property
    def raiz_biblioteca(self) -> Path:
        """``<carpeta_destino>/<usuario>``: raíz de la biblioteca personal."""
        return self.carpeta_destino / self.usuario

    def resumen(self) -> dict[str, Any]:
        """Configuración efectiva para el modo depuración (la contraseña de la BD se oculta)."""
        datos = {campo.name: getattr(self, campo.name) for campo in fields(self)}
        datos["bd_url"] = re.sub(r"(://[^:/@]+:)[^@]+@", r"\1****@", self.bd_url)
        return datos

    # ------------------------------------------------------------------ #
    @classmethod
    def cargar(cls, ruta: Path | None = None, rutas: RutasSistema | None = None) -> Configuracion:
        """
        Construye la configuración leyendo el TOML y el entorno.

        Args:
            ruta: Fichero explícito (opción ``--config``). Si es ``None`` se busca
                ``TAMALIO_CONFIG`` y luego ``<carpeta de configuración>/tamalio.toml``.
            rutas: Calculadora de carpetas del sistema (inyectable en pruebas).

        Raises:
            ErrorTamalio: Si el TOML tiene errores de sintaxis o valores inválidos.
        """
        rutas = rutas or RutasSistema()
        config = cls()
        candidata = ruta or (Path(os.environ["TAMALIO_CONFIG"]) if os.environ.get("TAMALIO_CONFIG") else None)
        candidata = candidata or rutas.carpeta_config() / "tamalio.toml"

        if candidata.is_file():
            try:
                datos = tomllib.loads(candidata.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as error:
                raise ErrorTamalio(f"Error de sintaxis en «{candidata}»: {error}") from error
            config._aplicar_toml(datos)
            config.ruta_fichero = candidata
        elif ruta is not None:
            raise ErrorTamalio(f"No existe el fichero de configuración «{ruta}».")

        config._aplicar_entorno()
        return config

    # ------------------------------------------------------------------ #
    def _aplicar_toml(self, datos: dict[str, Any]) -> None:
        """Copia los valores de cada sección del TOML a los atributos correspondientes."""
        general = datos.get("general", {})
        if general.get("usuario"):
            self.usuario = str(general["usuario"])
        if general.get("carpeta_destino"):
            self.carpeta_destino = Path(general["carpeta_destino"]).expanduser()
        if general.get("formato_salida"):
            self.formato_salida = self._formato(general["formato_salida"])
        if "agregar_invitados_a_artistas" in general:
            self.agregar_invitados_a_artistas = bool(general["agregar_invitados_a_artistas"])

        # Las secciones simples se mapean con un prefijo: [red] → red_*, etc.
        self._copiar_seccion(datos.get("red", {}), "red_")
        self._copiar_seccion(datos.get("caratula", {}), "caratula_")

        javascript = datos.get("javascript", {})
        if javascript.get("motor"):
            self.js_motor = str(javascript["motor"]).lower()
        if javascript.get("ruta"):
            self.js_ruta = Path(javascript["ruta"]).expanduser()
        if "componentes_remotos" in javascript:
            self.js_componentes_remotos = list(javascript["componentes_remotos"])

        for nombre, valor in datos.get("sesiones", {}).items():
            if valor:
                self.sesiones[Plataforma.desde_texto(nombre)] = Path(valor).expanduser()

        base_datos = datos.get("base_datos", {})
        if base_datos.get("url"):
            self.bd_url = str(base_datos["url"])

        self._validar()

    def _copiar_seccion(self, seccion: dict[str, Any], prefijo: str) -> None:
        """Asigna ``seccion[clave]`` a ``self.<prefijo><clave>`` respetando el tipo original."""
        nombres = {campo.name for campo in fields(self)}
        for clave, valor in seccion.items():
            atributo = f"{prefijo}{clave}"
            if atributo not in nombres:
                raise ErrorTamalio(f"Opción desconocida en la configuración: [{prefijo[:-1]}] {clave}")
            actual = getattr(self, atributo)
            # Las tuplas (rangos) llegan como listas desde TOML.
            if isinstance(actual, tuple):
                valor = tuple(valor)
            setattr(self, atributo, valor)

    def _aplicar_entorno(self) -> None:
        """Variables de entorno con prioridad sobre el TOML."""
        if os.environ.get("TAMALIO_BD_URL"):
            self.bd_url = os.environ["TAMALIO_BD_URL"]
        if os.environ.get("TAMALIO_DESTINO"):
            self.carpeta_destino = Path(os.environ["TAMALIO_DESTINO"]).expanduser()
        if os.environ.get("TAMALIO_USUARIO"):
            self.usuario = os.environ["TAMALIO_USUARIO"]
        if os.environ.get("TAMALIO_DEBUG", "").lower() in {"1", "true", "si", "sí", "yes"}:
            self.depuracion = True

    def _validar(self) -> None:
        """Comprueba la coherencia de los rangos numéricos."""
        if self.red_espera_minima < 0 or self.red_espera_maxima < self.red_espera_minima:
            raise ErrorTamalio("[red] espera_maxima debe ser mayor o igual que espera_minima (y ambas ≥ 0).")
        if self.js_motor not in {"quickjs", "deno", "node", "bun"}:
            raise ErrorTamalio(f"[javascript] motor «{self.js_motor}» no es válido.")

    @staticmethod
    def _formato(valor: str) -> FormatoAudio:
        """Convierte texto en :class:`FormatoAudio` con un mensaje claro si falla."""
        try:
            return FormatoAudio(str(valor).lower())
        except ValueError:
            validos = ", ".join(formato.value for formato in FormatoAudio)
            raise ErrorTamalio(f"Formato «{valor}» no válido. Usa uno de: {validos}.") from None
