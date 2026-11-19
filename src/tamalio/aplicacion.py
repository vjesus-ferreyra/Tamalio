"""Composición de la aplicación: crea los objetos, los conecta y despacha el comando."""

import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from tamalio.configuracion.configuracion import Configuracion
from tamalio.controladores.controlador_catalogo import ControladorCatalogo
from tamalio.controladores.controlador_conversion import ControladorConversion
from tamalio.controladores.controlador_descargas import ControladorDescargas
from tamalio.controladores.controlador_sistema import ControladorSistema
from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.extractores.fabrica_extractores import FabricaExtractores
from tamalio.modelos.conjunto_datos import ConjuntoDatos
from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.plataforma import Plataforma
from tamalio.repositorios.conexion_postgres import ConexionPostgres
from tamalio.repositorios.repositorio_catalogo_postgres import RepositorioCatalogoPostgres
from tamalio.repositorios.repositorio_sesiones_postgres import RepositorioSesionesPostgres
from tamalio.repositorios.repositorio_tareas_postgres import RepositorioTareasPostgres
from tamalio.servicios.cliente_yt_dlp import ClienteYtDlp
from tamalio.servicios.conversor_audio import ConversorAudio
from tamalio.servicios.descargador_caratulas import DescargadorCaratulas
from tamalio.servicios.detector_plataforma import DetectorPlataforma
from tamalio.servicios.ejecutor_ffmpeg import EjecutorFfmpeg
from tamalio.servicios.etiquetador_audio import EtiquetadorAudio
from tamalio.servicios.fabrica_lectores_fuentes import FabricaLectoresFuentes
from tamalio.servicios.gestor_descargas import GestorDescargas
from tamalio.servicios.gestor_sesiones import GestorSesiones
from tamalio.servicios.organizador_biblioteca import OrganizadorBiblioteca
from tamalio.servicios.temporizador_humano import TemporizadorHumano
from tamalio.servicios.verificador_dependencias import VerificadorDependencias
from tamalio.vistas.analizador_argumentos import AnalizadorArgumentos
from tamalio.vistas.manejador_registro_consola import ManejadorRegistroConsola
from tamalio.vistas.vista_consola import VistaConsola


class Aplicacion:
    """
    *Composition root*: el único lugar que conoce todas las clases concretas.

    Pasos de :meth:`ejecutar`:

    1. Analiza los argumentos (vista).
    2. Carga la configuración y aplica las opciones globales.
    3. Configura el registro (fichero rotativo + mensajes en la vista).
    4. Construye **solo** lo que el comando necesita (por ejemplo,
       ``doctor`` no exige que PostgreSQL esté disponible).
    5. Llama al controlador y traduce las excepciones a mensajes amables.
    """

    def __init__(self) -> None:
        self._config: Configuracion | None = None
        self._vista: VistaConsola | None = None
        self._conexion: ConexionPostgres | None = None

    # ================================================================== #
    def ejecutar(self, argumentos: list[str] | None = None) -> int:
        """Punto de entrada; devuelve el código de salida del proceso."""
        espacio = AnalizadorArgumentos().analizar(argumentos)
        try:
            self._config = Configuracion.cargar(espacio.config)
        except ErrorTamalio as error:
            VistaConsola(color=False if espacio.sin_color else None).mostrar_error(error.mensaje, error.sugerencia)
            return 1
        self._config.depuracion = self._config.depuracion or espacio.debug
        self._vista = VistaConsola(
            color=False if espacio.sin_color else None,
            detallado=espacio.detallado,
            depuracion=self._config.depuracion,
        )
        try:
            if getattr(espacio, "destino", None):
                self._config.carpeta_destino = espacio.destino.expanduser()
            self._configurar_registro(espacio.detallado, self._config.depuracion)
            if self._config.depuracion:
                registro = logging.getLogger("tamalio.aplicacion")
                registro.debug("Argumentos: %s", vars(espacio))
                registro.debug(
                    "Configuración (%s): %s", self._config.ruta_fichero or "predeterminada", self._config.resumen()
                )
            if espacio.comando not in {"cola", "pausar", "cancelar"}:
                self._vista.mostrar_encabezado()
            return self._despachar(espacio)
        except ErrorTamalio as error:
            self._vista.mostrar_error(error.mensaje, error.sugerencia)
            return 1
        except KeyboardInterrupt:
            self._vista.mostrar_advertencia("Operación interrumpida.")
            return 130
        finally:
            if self._conexion is not None:
                self._conexion.cerrar()

    def _despachar(self, espacio: argparse.Namespace) -> int:
        """Elige el controlador según el comando."""
        vista, config = self._vista, self._config
        assert vista is not None and config is not None
        comando = espacio.comando
        formato = FormatoAudio(espacio.formato) if getattr(espacio, "formato", None) else None
        plataforma = Plataforma(espacio.plataforma) if getattr(espacio, "plataforma", None) else None

        if comando == "doctor":
            verificador = VerificadorDependencias(config, lambda: self._bd().version_servidor())
            return ControladorSistema(vista).doctor(verificador)
        if comando == "bd":
            if espacio.accion == "borrar":
                conjuntos = [ConjuntoDatos(c) for c in (espacio.conjuntos or [])] or list(ConjuntoDatos)
                return ControladorSistema(vista).borrar_bd(self._bd(), conjuntos, espacio.confirmar)
            return ControladorSistema(vista).iniciar_bd(self._bd())
        if comando == "sesion":
            sistema = ControladorSistema(vista)
            repositorio = RepositorioSesionesPostgres(self._bd())
            if espacio.accion == "establecer":
                gestor = GestorSesiones(repositorio, config.sesiones)
                return sistema.establecer_sesion(gestor, Plataforma(espacio.plataforma), espacio.ruta)
            if espacio.accion == "listar":
                return sistema.listar_sesiones(repositorio, config.sesiones)
            return sistema.quitar_sesion(repositorio, Plataforma(espacio.plataforma))
        if comando == "convertir":
            # argparse exige «-f», pero se valida igual para que el tipo sea FormatoAudio.
            if formato is None:
                raise ErrorTamalio("Indica el formato de destino con «-f FORMATO».")
            return self._controlador_conversion().convertir(
                espacio.rutas, formato, plataforma, espacio.todo, espacio.conservar_original
            )

        descargas = self._controlador_descargas()
        if comando == "descargar":
            return descargas.descargar(espacio.fuentes, espacio.archivo, formato, plataforma, espacio.solo_encolar)
        if comando == "cola":
            estados = [EstadoDescarga(e) for e in espacio.estado] if espacio.estado else None
            return descargas.mostrar_cola(estados)
        if comando == "reanudar":
            return descargas.reanudar(espacio.ids)
        if comando == "reintentar":
            return descargas.reintentar(espacio.ids, espacio.incluir_canceladas)
        if comando == "pausar":
            return descargas.pausar(espacio.ids, espacio.todas)
        if comando == "cancelar":
            return descargas.cancelar(espacio.ids, espacio.todas)
        if comando == "catalogo":
            catalogo = ControladorCatalogo(
                vista, RepositorioCatalogoPostgres(self._bd()), config, descargas, DetectorPlataforma()
            )
            if espacio.accion == "listar":
                return catalogo.listar(plataforma, espacio.buscar)
            if espacio.accion == "exportar":
                return catalogo.exportar(espacio.fichero, plataforma)
            return catalogo.importar(espacio.fichero, espacio.descargar, formato)
        raise ErrorTamalio(f"Comando desconocido: {comando}")

    # ================================================================== #
    # Construcción de objetos
    # ================================================================== #
    def _bd(self) -> ConexionPostgres:
        """Conexión perezosa: solo se abre si el comando la necesita."""
        if self._conexion is None:
            assert self._config is not None
            self._conexion = ConexionPostgres(self._config.bd_url)
        return self._conexion

    def _controlador_descargas(self) -> ControladorDescargas:
        """Arma el grafo de objetos del flujo de descarga (inyección de dependencias manual)."""
        config, vista = self._config, self._vista
        assert config is not None and vista is not None
        conexion = self._bd()
        ffmpeg = EjecutorFfmpeg()
        temporizador = TemporizadorHumano(
            minimo=config.red_espera_minima,
            maximo=config.red_espera_maxima,
            pausa_larga_cada=config.red_pausa_larga_cada,
            pausa_larga=config.red_pausa_larga,
            peticiones=config.red_espera_entre_peticiones,
        )
        sesiones = GestorSesiones(RepositorioSesionesPostgres(conexion), config.sesiones)
        carpeta_trabajo = config.carpeta_cache / "trabajo"
        detector = DetectorPlataforma()
        gestor = GestorDescargas(
            config=config,
            fabrica_extractores=FabricaExtractores(
                config.agregar_invitados_a_artistas, config.caratula_recortar_videos
            ),
            fabrica_cliente=lambda cookies: ClienteYtDlp(config, carpeta_trabajo, temporizador, cookies),
            caratulas=DescargadorCaratulas(config.carpeta_cache, ffmpeg, config.caratula_calidad_jpeg),
            conversor=ConversorAudio(ffmpeg),
            etiquetador=EtiquetadorAudio(),
            organizador=OrganizadorBiblioteca(config.raiz_biblioteca),
            catalogo=RepositorioCatalogoPostgres(conexion),
            tareas=RepositorioTareasPostgres(conexion),
            sesiones=sesiones,
            temporizador=temporizador,
        )
        return ControladorDescargas(
            vista, gestor, RepositorioTareasPostgres(conexion), detector, FabricaLectoresFuentes(detector), sesiones
        )

    def _controlador_conversion(self) -> ControladorConversion:
        """Arma el controlador de conversión."""
        config, vista = self._config, self._vista
        assert config is not None and vista is not None
        ffmpeg = EjecutorFfmpeg()
        return ControladorConversion(
            vista,
            RepositorioCatalogoPostgres(self._bd()),
            ConversorAudio(ffmpeg),
            EtiquetadorAudio(),
            DescargadorCaratulas(config.carpeta_cache, ffmpeg, config.caratula_calidad_jpeg),
            ffmpeg,
        )

    def _configurar_registro(self, detallado: bool, depuracion: bool = False) -> None:
        """
        Registro en dos destinos:

        - Fichero rotativo (``tamalio.log``, 2 MB × 3) con todo el detalle, útil
          para diagnosticar bloqueos o errores de ``yt-dlp``.
        - La vista: advertencias siempre; mensajes informativos con ``--detallado``;
          **todo** (incluidas las peticiones HTTP de ``urllib3``) con ``--debug``.
        """
        assert self._config is not None and self._vista is not None
        raiz = logging.getLogger()
        raiz.setLevel(logging.DEBUG)
        for manejador in list(raiz.handlers):
            raiz.removeHandler(manejador)
        try:
            carpeta: Path = self._config.carpeta_estado
            carpeta.mkdir(parents=True, exist_ok=True)
            fichero = RotatingFileHandler(carpeta / "tamalio.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
            fichero.setLevel(logging.DEBUG)
            fichero.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
            raiz.addHandler(fichero)
        except OSError:
            pass  # Sin permisos de escritura: se sigue sin fichero de registro.
        nivel_consola = logging.DEBUG if depuracion else (logging.INFO if detallado else logging.WARNING)
        raiz.addHandler(ManejadorRegistroConsola(self._vista, nivel_consola))
        # Bibliotecas muy habladoras: solo advertencias (en depuración se ve urllib3,
        # útil para seguir la descarga de carátulas; el SQL ya lo registra Tamalio).
        for ruidoso in ("charset_normalizer", "psycopg", *(() if depuracion else ("urllib3",))):
            logging.getLogger(ruidoso).setLevel(logging.WARNING)
