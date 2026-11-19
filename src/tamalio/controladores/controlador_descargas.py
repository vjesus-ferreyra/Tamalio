# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Controlador de los comandos de descarga y de la cola (descargar, reanudar, pausar…)."""

import dataclasses
import logging
import signal
import time
from collections.abc import Iterable
from pathlib import Path
from types import FrameType

from tamalio.excepciones.error_descarga_cancelada import ErrorDescargaCancelada
from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.interfaces.repositorio_tareas import RepositorioTareas
from tamalio.interfaces.vista import Vista
from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.fuente import Fuente
from tamalio.modelos.plataforma import Plataforma
from tamalio.modelos.resumen_ejecucion import ResumenEjecucion
from tamalio.modelos.tarea_descarga import TareaDescarga
from tamalio.servicios.control_ejecucion import ControlEjecucion
from tamalio.servicios.detector_plataforma import DetectorPlataforma
from tamalio.servicios.fabrica_lectores_fuentes import FabricaLectoresFuentes
from tamalio.servicios.gestor_descargas import GestorDescargas
from tamalio.servicios.gestor_sesiones import GestorSesiones
from tamalio.servicios.lector_teclado import LectorTeclado

registro = logging.getLogger(__name__)


class ControladorDescargas:
    """
    Coordina vista y modelo para todo lo relacionado con descargas.

    Responsabilidades:

    - Convertir los argumentos (URL y ficheros) en tareas de la cola.
    - Procesar la cola con el :class:`GestorDescargas`, conectando el teclado
      (pausa/saltar/cancelar/salir) y ``Ctrl+C`` al :class:`ControlEjecucion`.
    - Cambiar estados de tareas desde otra terminal (pausar, cancelar, reintentar).

    Args:
        vista: Vista activa.
        gestor: Gestor de descargas (modelo).
        tareas: Repositorio de la cola.
        detector: Clasificador de URL.
        lectores: Fábrica de lectores de ficheros de fuentes.
        sesiones: Gestor de cookies (para conectarle la pregunta al usuario).
    """

    def __init__(
        self,
        vista: Vista,
        gestor: GestorDescargas,
        tareas: RepositorioTareas,
        detector: DetectorPlataforma,
        lectores: FabricaLectoresFuentes,
        sesiones: GestorSesiones,
    ) -> None:
        self._vista = vista
        self._gestor = gestor
        self._tareas = tareas
        self._detector = detector
        self._lectores = lectores
        self._sesiones = sesiones

    # ================================================================== #
    # Comandos
    # ================================================================== #
    def descargar(
        self,
        urls: list[str],
        archivos: list[Path],
        formato: FormatoAudio | None = None,
        plataforma: Plataforma | None = None,
        solo_encolar: bool = False,
    ) -> int:
        """``tamalio descargar``: encola las fuentes y (salvo ``--solo-encolar``) las procesa."""
        fuentes: list[Fuente] = [self._detector.detectar(url, plataforma=plataforma) for url in urls]
        for archivo in archivos:
            leidas = self._lectores.leer(archivo)
            self._vista.mostrar_info(f"{len(leidas)} fuente(s) leídas de «{archivo.name}».")
            fuentes.extend(leidas)
        if not fuentes:
            raise ErrorTamalio(
                "No indicaste ninguna fuente.", sugerencia="Usa «tamalio descargar URL» o «-a fichero.jsonc»."
            )
        return self.encolar_y_procesar(fuentes, formato, solo_encolar)

    def encolar_y_procesar(
        self, fuentes: Iterable[Fuente], formato: FormatoAudio | None = None, solo_encolar: bool = False
    ) -> int:
        """Encola las fuentes (sin duplicar las activas) y procesa las resultantes."""
        tareas: list[TareaDescarga] = []
        for fuente in fuentes:
            if formato is not None and fuente.formato is None:
                # El formato de la línea de comandos es el predeterminado; el del fichero gana.
                fuente = dataclasses.replace(fuente, formato=formato)
            registro.debug(
                "Fuente %s → plataforma=%s tipo=%s id=%s formato=%s metadatos=%r",
                fuente.url_original,
                fuente.plataforma.value,
                fuente.tipo.value,
                fuente.identificador,
                fuente.formato.value if fuente.formato else None,
                fuente.metadatos,
            )
            tarea, nueva = self._tareas.agregar(fuente)
            if not nueva:
                self._vista.mostrar_info(f"Ya estaba en la cola (tarea {tarea.id}): {fuente.url}")
            tareas.append(tarea)
        if solo_encolar:
            self._vista.mostrar_exito(f"{len(tareas)} tarea(s) en la cola. Procésalas con «tamalio reanudar».")
            return 0
        return self.procesar(tareas)

    def reanudar(self, ids: list[int]) -> int:
        """``tamalio reanudar``: procesa las tareas pendientes y pausadas (o las indicadas)."""
        if ids:
            tareas = self._obtener_varias(ids)
        else:
            tareas = self._tareas.listar([EstadoDescarga.PENDIENTE, EstadoDescarga.PAUSADA])
            colgadas = self._tareas.listar([EstadoDescarga.EN_PROCESO])
            if colgadas:
                lista = ", ".join(str(tarea.id) for tarea in colgadas)
                self._vista.mostrar_advertencia(
                    f"Tareas marcadas «en proceso» (¿en otra terminal o interrumpidas?): {lista}. "
                    "Si no se están descargando, reanúdalas con «tamalio reanudar ID»."
                )
        for tarea in tareas:
            if tarea.estado in {EstadoDescarga.FALLIDA, EstadoDescarga.CANCELADA, EstadoDescarga.COMPLETADA}:
                tarea.reintentar()
                self._tareas.actualizar(tarea)
        return self.procesar(tareas)

    def reintentar(self, ids: list[int], incluir_canceladas: bool = False) -> int:
        """``tamalio reintentar``: devuelve a la cola las fallidas (y canceladas) y las procesa."""
        if ids:
            tareas = self._obtener_varias(ids)
        else:
            estados = [EstadoDescarga.FALLIDA] + ([EstadoDescarga.CANCELADA] if incluir_canceladas else [])
            tareas = self._tareas.listar(estados)
        for tarea in tareas:
            if not tarea.estado.es_activo:
                tarea.reintentar()
                self._tareas.actualizar(tarea)
        return self.procesar(tareas)

    def pausar(self, ids: list[int], todas: bool) -> int:
        """``tamalio pausar``: el proceso que esté descargando lo detecta en segundos."""
        return self._cambiar_estado(ids, todas, EstadoDescarga.PAUSADA)

    def cancelar(self, ids: list[int], todas: bool) -> int:
        """``tamalio cancelar``: igual que pausar, pero la tarea no se reanuda sola."""
        return self._cambiar_estado(ids, todas, EstadoDescarga.CANCELADA)

    def mostrar_cola(self, estados: list[EstadoDescarga] | None) -> int:
        """``tamalio cola``: tabla con las tareas."""
        tareas = self._tareas.listar(estados)
        if not tareas:
            self._vista.mostrar_info("La cola está vacía.")
            return 0
        filas = [
            (
                tarea.id,
                tarea.estado.value.replace("_", " "),
                tarea.fuente.plataforma.nombre_visible,
                tarea.intentos,
                tarea.actualizado_en.astimezone().strftime("%Y-%m-%d %H:%M") if tarea.actualizado_en else None,
                tarea.ultimo_error or tarea.fuente.comentario or tarea.fuente.url,
            )
            for tarea in tareas
        ]
        self._vista.mostrar_tabla(("ID", "Estado", "Plataforma", "Intentos", "Actualizada", "URL / detalle"), filas)
        return 0

    # ================================================================== #
    # Procesamiento de la cola
    # ================================================================== #
    def procesar(self, tareas: list[TareaDescarga]) -> int:
        """
        Procesa las tareas una por una mostrando el progreso.

        Returns:
            ``0`` si no hubo pistas fallidas, ``1`` en caso contrario.
        """
        if not tareas:
            self._vista.mostrar_info("No hay tareas por procesar.")
            return 0

        control = ControlEjecucion()
        teclado = LectorTeclado(lambda tecla: self._al_pulsar(tecla, control))
        control.al_cambiar_pausa(self._vista.establecer_pausa)
        self._sesiones.establecer_solicitante(lambda plataforma, error: self._pedir_cookies(plataforma, error, teclado))

        resumen = ResumenEjecucion()
        inicio = time.monotonic()
        actual: TareaDescarga | None = None
        interrupciones = 0

        def al_ctrl_c(_numero: int, _marco: FrameType | None) -> None:
            # 1.er Ctrl+C: detención ordenada; 2.º: interrupción inmediata.
            nonlocal interrupciones
            interrupciones += 1
            if interrupciones > 1:
                raise KeyboardInterrupt
            control.detener_todo()
            self._vista.mostrar_advertencia("Deteniendo con cuidado… (Ctrl+C otra vez para forzar)")
            self._vista.mostrar_accion_pendiente("Saliendo")

        manejador_previo = signal.signal(signal.SIGINT, al_ctrl_c)
        self._vista.iniciar_lote(len(tareas))
        self._vista.establecer_ayuda_teclas(teclado.iniciar())
        try:
            for posicion, tarea in enumerate(tareas, start=1):
                if control.detenido:
                    break
                actual = tarea
                resumen.sumar(self._gestor.procesar(tarea, control, self._vista, posicion, len(tareas)))
            actual = None
        except ErrorDescargaCancelada:
            actual = None
            self._vista.mostrar_advertencia("Detenido. Continúa cuando quieras con «tamalio reanudar».")
        except KeyboardInterrupt:
            self._vista.mostrar_advertencia("Interrumpido. Continúa cuando quieras con «tamalio reanudar».")
        finally:
            teclado.detener()
            signal.signal(signal.SIGINT, manejador_previo)
            self._sesiones.establecer_solicitante(None)
            if actual is not None and actual.estado is EstadoDescarga.EN_PROCESO:
                actual.pausar()
                self._tareas.actualizar(actual)
            self._vista.terminar_lote()
        self._vista.mostrar_resumen(resumen, time.monotonic() - inicio)
        return 1 if resumen.fallidas else 0

    def _al_pulsar(self, tecla: str, control: ControlEjecucion) -> None:
        """Traduce teclas a órdenes del control de ejecución (se ejecuta en el hilo del teclado)."""
        if tecla == "p":
            control.alternar_pausa()
        elif tecla == "s":
            control.saltar_pista()
            self._vista.mostrar_info("Saltando la pista actual…")
            self._vista.mostrar_accion_pendiente("Saltando pista")
        elif tecla == "c":
            control.cancelar_tarea()
            self._vista.mostrar_advertencia("Cancelando la tarea actual…")
            self._vista.mostrar_accion_pendiente("Cancelando tarea")
        elif tecla == "q":
            control.detener_todo()
            self._vista.mostrar_advertencia("Deteniendo… la tarea actual quedará pausada.")
            self._vista.mostrar_accion_pendiente("Saliendo")

    def _pedir_cookies(self, plataforma: Plataforma, error: str | None, teclado: LectorTeclado) -> str | None:
        """Pregunta por el fichero de cookies suspendiendo la lectura de teclas."""
        with teclado.suspendido():
            if error:
                self._vista.mostrar_error(error)
            else:
                self._vista.mostrar_advertencia(
                    f"{plataforma.nombre_visible} necesita tu sesión. Exporta tus cookies en formato Netscape "
                    "(p. ej. con la extensión «Get cookies.txt LOCALLY»)."
                )
            return self._vista.preguntar(f"Ruta del fichero de cookies de {plataforma.nombre_visible} (Enter = omitir)")

    # ================================================================== #
    # Auxiliares
    # ================================================================== #
    def _obtener_varias(self, ids: list[int]) -> list[TareaDescarga]:
        """Obtiene las tareas por ID avisando de las que no existen."""
        tareas = []
        for id_tarea in ids:
            tarea = self._tareas.obtener(id_tarea)
            if tarea is None:
                self._vista.mostrar_advertencia(f"No existe la tarea {id_tarea}.")
            else:
                tareas.append(tarea)
        return tareas

    def _cambiar_estado(self, ids: list[int], todas: bool, destino: EstadoDescarga) -> int:
        """Aplica ``destino`` a las tareas activas indicadas."""
        tareas = self._tareas.listar([e for e in EstadoDescarga if e.es_activo]) if todas else self._obtener_varias(ids)
        cambiadas = 0
        for tarea in tareas:
            if not tarea.estado.puede_pasar_a(destino):
                self._vista.mostrar_advertencia(f"La tarea {tarea.id} está {tarea.estado.value}; no se puede cambiar.")
                continue
            tarea.pausar() if destino is EstadoDescarga.PAUSADA else tarea.cancelar()
            self._tareas.actualizar(tarea)
            cambiadas += 1
        self._vista.mostrar_exito(f"{cambiadas} tarea(s) ahora {destino.value}.")
        return 0
