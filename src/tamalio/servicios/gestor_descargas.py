"""Orquestador del modelo: lleva una tarea desde la URL hasta el fichero etiquetado."""

import glob
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from tamalio.configuracion.configuracion import Configuracion
from tamalio.excepciones.error_descarga_cancelada import ErrorDescargaCancelada
from tamalio.excepciones.error_deteccion_bot import ErrorDeteccionBot
from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.extractores.fabrica_extractores import FabricaExtractores
from tamalio.interfaces.observador_descargas import ObservadorDescargas
from tamalio.interfaces.repositorio_catalogo import RepositorioCatalogo
from tamalio.interfaces.repositorio_tareas import RepositorioTareas
from tamalio.modelos.alcance_cancelacion import AlcanceCancelacion
from tamalio.modelos.fase_proceso import FaseProceso
from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma
from tamalio.modelos.progreso_descarga import ProgresoDescarga
from tamalio.modelos.resumen_ejecucion import ResumenEjecucion
from tamalio.modelos.tarea_descarga import TareaDescarga
from tamalio.servicios.cliente_yt_dlp import ClienteYtDlp
from tamalio.servicios.control_ejecucion import ControlEjecucion
from tamalio.servicios.conversor_audio import ConversorAudio
from tamalio.servicios.descargador_caratulas import DescargadorCaratulas
from tamalio.servicios.etiquetador_audio import EtiquetadorAudio
from tamalio.servicios.gestor_sesiones import GestorSesiones
from tamalio.servicios.organizador_biblioteca import OrganizadorBiblioteca
from tamalio.servicios.temporizador_humano import TemporizadorHumano

registro = logging.getLogger(__name__)
Resultado = TypeVar("Resultado")


class GestorDescargas:
    """
    Ejecuta el flujo completo de una :class:`TareaDescarga`.

    Flujo (ver diagrama de secuencia en ``docs/arquitectura.md``)::

        extraer metadatos → por cada pista:
            ¿ya está en el catálogo? → omitir
            pausa humana aleatoria → descargar → carátula → convertir
            → etiquetar → mover a la biblioteca → registrar en el catálogo

    Además gestiona los **bloqueos**: si la plataforma detecta un bot, pide al
    usuario su fichero de cookies (una sola vez) y reintenta; si persiste,
    espera con *backoff* exponencial antes de rendirse.

    Todas las dependencias se inyectan por el constructor (inversión de
    dependencias), lo que permite probar el gestor con dobles de prueba.

    Args:
        config: Configuración.
        fabrica_extractores: Proveedor de extractores por plataforma.
        fabrica_cliente: Crea un :class:`ClienteYtDlp` con el fichero de cookies dado.
        caratulas: Descargador de carátulas.
        conversor: Conversor de audio.
        etiquetador: Etiquetador de metadatos.
        organizador: Organizador de la biblioteca.
        catalogo: Repositorio del catálogo.
        tareas: Repositorio de la cola.
        sesiones: Gestor de cookies.
        temporizador: Esperas aleatorias.
    """

    def __init__(
        self,
        config: Configuracion,
        fabrica_extractores: FabricaExtractores,
        fabrica_cliente: Callable[[Path | None], ClienteYtDlp],
        caratulas: DescargadorCaratulas,
        conversor: ConversorAudio,
        etiquetador: EtiquetadorAudio,
        organizador: OrganizadorBiblioteca,
        catalogo: RepositorioCatalogo,
        tareas: RepositorioTareas,
        sesiones: GestorSesiones,
        temporizador: TemporizadorHumano,
    ) -> None:
        self._config = config
        self._extractores = fabrica_extractores
        self._fabrica_cliente = fabrica_cliente
        self._caratulas = caratulas
        self._conversor = conversor
        self._etiquetador = etiquetador
        self._organizador = organizador
        self._catalogo = catalogo
        self._tareas = tareas
        self._sesiones = sesiones
        self._temporizador = temporizador
        # Cuenta las peticiones «pesadas» para no esperar antes de la primera.
        self._operaciones = 0
        self._carpeta_trabajo = config.carpeta_cache / "trabajo"
        self._pista_actual: Pista | None = None

    # ================================================================== #
    # Tarea
    # ================================================================== #
    def procesar(
        self,
        tarea: TareaDescarga,
        control: ControlEjecucion,
        observador: ObservadorDescargas,
        posicion: int = 1,
        total: int = 1,
    ) -> ResumenEjecucion:
        """
        Procesa la tarea y deja su estado final guardado en la base de datos.

        Raises:
            ErrorDescargaCancelada: Solo con alcance ``TODO``, para que el
                controlador detenga la cola completa (la tarea queda pausada).
        """
        resumen = ResumenEjecucion()
        tarea.iniciar()
        self._tareas.actualizar(tarea)
        id_tarea = tarea.id
        control.preparar_tarea((lambda: self._tareas.estado_actual(id_tarea)) if id_tarea is not None else None)
        observador.al_iniciar_tarea(tarea, posicion, total)
        self._organizador.preparar()
        self._carpeta_trabajo.mkdir(parents=True, exist_ok=True)

        try:
            titulo, pistas = self._extraer(tarea, control, observador)
            observador.al_resolver_tarea(tarea, titulo, len(pistas))
            formato = tarea.fuente.formato or self._config.formato_salida
            for indice, pista in enumerate(pistas, start=1):
                control.punto_control()
                observador.al_iniciar_pista(pista, indice, len(pistas))
                self._procesar_pista_segura(pista, formato, control, observador, resumen)
            self._cerrar_tarea(tarea, resumen)
        except ErrorDescargaCancelada as senal:
            if senal.pausar:
                tarea.pausar()  # Se conservan los ficheros .part para reanudar.
            else:
                tarea.cancelar()
                self._limpiar_parciales(self._pista_actual)
            self._tareas.actualizar(tarea)
            observador.al_terminar_tarea(tarea, resumen)
            if senal.alcance is AlcanceCancelacion.TODO:
                raise
            return resumen
        except ErrorTamalio as error:
            tarea.fallar(error.mensaje)
            resumen.errores.append(error.mensaje)
            observador.al_fallar_pista(None, error.mensaje)

        self._tareas.actualizar(tarea)
        observador.al_terminar_tarea(tarea, resumen)
        return resumen

    def _cerrar_tarea(self, tarea: TareaDescarga, resumen: ResumenEjecucion) -> None:
        """
        Decide el estado final. Si alguna pista falló, la tarea queda *fallida*:
        al reintentarla, las pistas ya descargadas se omiten y solo se bajan las que faltan.
        """
        if resumen.fallidas:
            tarea.fallar(f"{resumen.fallidas} de {resumen.total} pista(s) fallaron.")
        elif resumen.saltadas and resumen.completadas == 0 and resumen.omitidas == resumen.saltadas:
            # El usuario saltó todas las pistas: no se considera completada.
            tarea.cancelar()
        else:
            tarea.completar()

    # ================================================================== #
    # Extracción
    # ================================================================== #
    def _extraer(
        self, tarea: TareaDescarga, control: ControlEjecucion, observador: ObservadorDescargas
    ) -> tuple[str, list[Pista]]:
        """Obtiene y normaliza los metadatos de la fuente."""
        fuente = tarea.fuente
        self._pausa_humana(control, observador)
        observador.al_cambiar_fase(FaseProceso.EXTRAYENDO, fuente.url)
        info = self._con_reintento_bloqueo(
            fuente.plataforma, lambda cliente: cliente.extraer(fuente), control, observador
        )
        pistas = self._extractores.obtener(fuente.plataforma).normalizar(info, fuente)
        if not pistas:
            raise ErrorTamalio("La fuente no contiene pistas disponibles.")
        titulo = str(info.get("title") or pistas[0].titulo)
        return titulo, pistas

    # ================================================================== #
    # Pista
    # ================================================================== #
    def _procesar_pista_segura(
        self,
        pista: Pista,
        formato: FormatoAudio,
        control: ControlEjecucion,
        observador: ObservadorDescargas,
        resumen: ResumenEjecucion,
    ) -> None:
        """Procesa una pista y acumula el resultado sin detener la tarea si falla."""
        existente = self._catalogo.obtener(pista.plataforma, pista.id_externo)
        if existente is not None and existente.descargada:
            resumen.omitidas += 1
            observador.al_omitir_pista(pista, "ya está en tu catálogo")
            return
        self._pista_actual = pista
        try:
            tamano = self._procesar_pista(pista, formato, control, observador)
        except ErrorDescargaCancelada as senal:
            if senal.alcance is not AlcanceCancelacion.PISTA:
                raise
            control.limpiar_pista()
            self._limpiar_parciales(pista)
            resumen.omitidas += 1
            resumen.saltadas += 1
            observador.al_omitir_pista(pista, "la saltaste")
        except ErrorTamalio as error:
            resumen.fallidas += 1
            resumen.errores.append(f"{pista.titulo}: {error.mensaje}")
            observador.al_fallar_pista(pista, error.mensaje)
            registro.debug("Falló la pista %s", pista.url, exc_info=True)
        else:
            resumen.completadas += 1
            resumen.bytes_totales += tamano

    def _procesar_pista(
        self, pista: Pista, formato: FormatoAudio, control: ControlEjecucion, observador: ObservadorDescargas
    ) -> int:
        """Descarga, convierte, etiqueta y guarda una pista. Devuelve su tamaño en bytes."""
        self._pausa_humana(control, observador)

        # 1) Descarga del audio en bruto.
        observador.al_cambiar_fase(FaseProceso.DESCARGANDO)
        descargado, info_final = self._con_reintento_bloqueo(
            pista.plataforma,
            lambda cliente: cliente.descargar(pista, observador.al_progreso, control.punto_control),
            control,
            observador,
        )
        pista.codec_origen = info_final.get("acodec") or pista.codec_origen
        pista.bitrate_origen = info_final.get("abr") or pista.bitrate_origen

        try:
            # 2) Carátula (un fallo aquí no debe impedir guardar la canción).
            imagen = None
            if pista.caratula is not None:
                observador.al_cambiar_fase(FaseProceso.CARATULA)
                try:
                    imagen = self._caratulas.obtener(pista.caratula)
                except ErrorTamalio as error:
                    observador.al_aviso(f"Sin carátula para «{pista.titulo}»: {error.mensaje}")
                if imagen is None:
                    observador.al_aviso(f"No se encontró carátula para «{pista.titulo}».")

            # 3) Conversión / re-empaquetado.
            if ConversorAudio.pierde_calidad(formato, pista.codec_origen):
                observador.al_aviso(
                    f"Recodificar {pista.codec_origen} → {formato.value} pierde calidad; "
                    "usa «original» o un formato sin pérdida para máxima fidelidad."
                )
            observador.al_cambiar_fase(FaseProceso.CONVIRTIENDO, formato.value)
            convertido = self._conversor.convertir(
                descargado,
                formato,
                self._carpeta_trabajo / f"{pista.plataforma.value}-{pista.id_externo}-final",
                codec_origen=pista.codec_origen,
                duracion=pista.duracion,
                al_progreso=lambda hecho, total: observador.al_progreso(
                    ProgresoDescarga(FaseProceso.CONVIRTIENDO, hecho, total)
                ),
                punto_control=control.punto_control,
            )

            # 4) Etiquetas y carátula incrustada.
            observador.al_cambiar_fase(FaseProceso.ETIQUETANDO)
            self._etiquetador.etiquetar(convertido, pista, imagen)

            # 5) Ubicación final y registro en el catálogo.
            observador.al_cambiar_fase(FaseProceso.ORGANIZANDO)
            destino = self._organizador.ruta_para(pista, convertido.suffix)
            final = self._organizador.colocar(convertido, destino)
        finally:
            descargado.unlink(missing_ok=True)

        pista.ruta_archivo = final
        pista.formato = formato.value
        self._catalogo.guardar(pista)
        tamano = final.stat().st_size
        observador.al_completar_pista(pista, tamano)
        return tamano

    def _limpiar_parciales(self, pista: Pista | None) -> None:
        """Borra los ficheros temporales (``.part``, ``-final``…) de una pista abandonada."""
        if pista is None or not self._carpeta_trabajo.is_dir():
            return
        patrones = (
            f"*-{glob.escape(pista.id_externo)}.*",
            f"{pista.plataforma.value}-{glob.escape(pista.id_externo)}-final*",
        )
        for patron in patrones:
            for fichero in self._carpeta_trabajo.glob(patron):
                fichero.unlink(missing_ok=True)

    # ================================================================== #
    # Anti-bloqueo
    # ================================================================== #
    def _pausa_humana(self, control: ControlEjecucion, observador: ObservadorDescargas) -> None:
        """Espera aleatoria antes de cada operación pesada (excepto la primera)."""
        if self._operaciones > 0:
            segundos = self._temporizador.siguiente_espera()
            observador.al_cambiar_fase(FaseProceso.ESPERANDO, f"{segundos:.1f} s")
            self._temporizador.esperar(
                segundos,
                control.punto_control,
                lambda hecho, total: observador.al_progreso(ProgresoDescarga(FaseProceso.ESPERANDO, hecho, total)),
            )
        self._operaciones += 1

    def _con_reintento_bloqueo(
        self,
        plataforma: Plataforma,
        operacion: Callable[[ClienteYtDlp], Resultado],
        control: ControlEjecucion,
        observador: ObservadorDescargas,
    ) -> Resultado:
        """
        Ejecuta ``operacion`` y, si la plataforma nos bloquea:

        1. Si no hay cookies, las pide al usuario una vez y reintenta.
        2. Si ya había cookies (o no se dieron), espera con *backoff* y reintenta
           hasta ``[red] reintentos_bloqueo`` veces.
        """
        bloqueos = 0
        ya_se_pidio = False
        while True:
            cookies = self._sesiones.ruta_cookies(plataforma)
            cliente = self._fabrica_cliente(cookies)
            try:
                return operacion(cliente)
            except ErrorDeteccionBot as error:
                registro.info("Bloqueo en %s: %s", plataforma.value, error.mensaje)
                if cookies is None and not ya_se_pidio:
                    ya_se_pidio = True
                    observador.al_aviso(f"{plataforma.nombre_visible} pide verificar que no eres un bot.")
                    if self._sesiones.solicitar(plataforma) is not None:
                        observador.al_aviso("Sesión registrada; reintentando con tus cookies…")
                        continue
                bloqueos += 1
                if bloqueos > self._config.red_reintentos_bloqueo:
                    raise
                espera = self._temporizador.espera_bloqueo(bloqueos, error.limite_peticiones)
                observador.al_aviso(
                    f"{plataforma.nombre_visible} pidió calma; reintento {bloqueos}/"
                    f"{self._config.red_reintentos_bloqueo} en {espera:.0f} s."
                )
                observador.al_cambiar_fase(FaseProceso.ESPERANDO, f"{espera:.0f} s")
                self._temporizador.esperar(
                    espera,
                    control.punto_control,
                    lambda hecho, total: observador.al_progreso(ProgresoDescarga(FaseProceso.ESPERANDO, hecho, total)),
                )
