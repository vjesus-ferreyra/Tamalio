# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Vista de línea de comandos con barras de progreso en vivo."""

import logging
import shutil
import sys
import threading
import time
from collections.abc import Sequence
from typing import TextIO

from tamalio import NOMBRE, __version__
from tamalio.interfaces.vista import Vista
from tamalio.modelos.estado_descarga import EstadoDescarga
from tamalio.modelos.fase_proceso import FaseProceso
from tamalio.modelos.pista import Pista
from tamalio.modelos.progreso_descarga import ProgresoDescarga
from tamalio.modelos.resumen_ejecucion import ResumenEjecucion
from tamalio.modelos.tarea_descarga import TareaDescarga
from tamalio.vistas.barra_progreso import BarraProgreso
from tamalio.vistas.estilos_consola import EstilosConsola


class VistaConsola(Vista):
    """
    Interfaz de terminal de Tamalio.

    Divide la salida en dos zonas:

    - **Zona permanente**: líneas que quedan en el historial (pista completada,
      omitida, errores, avisos, resúmenes).
    - **Zona en vivo**: las últimas tres líneas, que se redibujan en el mismo
      lugar unas ocho veces por segundo::

          ↓ 02/15  Adagio For Souls (feat. COR!S & dreamiecloud) — GHOST DATA
            ━━━━━━━━━━━━━━━━╸━━━━━━━━━  62%  3.1 MB / 5.0 MB · 1.2 MB/s · 0:02
          Lote ━━━━━━━━╸━━━━━━━━━━━━━━━  1/3 · [p] pausa  [s] saltar  [c] cancelar  [q] salir

    Si la salida no es una terminal (redirección a fichero, CI) solo se escribe
    la zona permanente, sin secuencias de control.

    Un hilo «refrescador» anima el *spinner* durante las fases sin progreso
    medible (por ejemplo, mientras ``yt-dlp`` analiza la fuente).

    Args:
        salida: Flujo de salida (``sys.stdout`` por defecto).
        color: Forzar/deshabilitar color (``None`` = automático).
        detallado: Muestra mensajes informativos y detalles extra.
        depuracion: Muestra **todo** lo que registra cada componente (yt-dlp,
            FFmpeg, SQL, carátulas, etiquetas…) con hora y origen.
    """

    _LINEAS_VIVAS = 3

    def __init__(
        self,
        salida: TextIO | None = None,
        color: bool | None = None,
        detallado: bool = False,
        depuracion: bool = False,
    ) -> None:
        self._salida = salida or sys.stdout
        self._estilos = EstilosConsola(self._salida, color)
        self._barra = BarraProgreso(self._estilos)
        self._detallado = detallado or depuracion
        self._depuracion = depuracion
        self._pendiente: str | None = None
        self._inicio_pendiente = 0.0
        self._candado = threading.RLock()
        self._en_vivo = self._estilos.es_terminal
        self._lineas_dibujadas = 0
        self._suspendida = False
        self._fotograma = 0
        # Estado que se dibuja en la zona en vivo.
        self._tarea_pos = (0, 0)
        self._tareas_terminadas = 0
        self._pista: Pista | None = None
        self._pista_pos = (0, 0)
        self._fase: FaseProceso | None = None
        self._detalle_fase: str | None = None
        self._progreso: ProgresoDescarga | None = None
        self._inicio_fase = time.monotonic()
        self._pausada = False
        self._ayuda_teclas = False
        self._activa = False
        self._refrescador: threading.Thread | None = None
        self._detener_refresco = threading.Event()

    # ================================================================== #
    # Utilidades de dibujo
    # ================================================================== #
    @property
    def estilos(self) -> EstilosConsola:
        """Estilos en uso (los comparte el analizador de argumentos)."""
        return self._estilos

    def _ancho(self) -> int:
        return max(40, shutil.get_terminal_size((100, 24)).columns - 1)

    def _escribir(self, texto: str) -> None:
        self._salida.write(texto)
        self._salida.flush()

    def _borrar_vivo(self) -> None:
        """Borra la zona en vivo y deja el cursor al inicio de su primera línea."""
        if self._lineas_dibujadas:
            secuencia = "\r\x1b[2K" + "\x1b[1A\x1b[2K" * (self._lineas_dibujadas - 1)
            self._escribir(secuencia)
            self._lineas_dibujadas = 0

    def _dibujar_vivo(self) -> None:
        """Redibuja la zona en vivo (solo en terminales y con un lote activo)."""
        if not (self._en_vivo and self._activa) or self._suspendida:
            return
        lineas = self._lineas_vivas()
        self._borrar_vivo()
        self._escribir("\n".join(lineas))
        self._lineas_dibujadas = len(lineas)

    def _permanente(self, texto: str) -> None:
        """Escribe una línea en el historial respetando la zona en vivo."""
        with self._candado:
            self._borrar_vivo()
            self._escribir(texto + "\n")
            self._dibujar_vivo()

    def _recortar(self, texto: str, maximo: int) -> str:
        """Recorta texto plano a ``maximo`` caracteres con «…»."""
        if len(texto) <= maximo:
            return texto
        if maximo <= 1:
            return texto[: max(maximo, 0)]
        return texto[: maximo - 1] + self._estilos.simbolo("…", "~")

    # ------------------------------------------------------------------ #
    def _lineas_vivas(self) -> list[str]:
        """Construye las tres líneas de la zona en vivo."""
        e, ancho = self._estilos, self._ancho()
        # Línea 1: pista actual.
        if self._pista is not None:
            n, total = self._pista_pos
            digitos = len(str(total))
            numero = f"{n:0{digitos}d}/{total}"
            icono = e.aviso("⏸") if self._pausada and e.unicode else e.acento(e.simbolo("↓", ">"))
            artista = f" — {self._pista.artista_principal}"
            disponible = ancho - len(numero) - 6
            titulo = self._recortar(self._pista.titulo + artista, disponible)
            linea1 = f"  {icono} {e.tenue(numero)}  {e.negrita(titulo)}"
        else:
            linea1 = f"  {self._barra.giro(self._fotograma)} {e.tenue('Preparando…')}"

        # Línea 2: fase + barra + cifras (o la orden pendiente del usuario).
        if self._pendiente:
            transcurrido = BarraProgreso.formatear_tiempo(time.monotonic() - self._inicio_pendiente)
            detalle = self._recortar(
                f"{self._pendiente} · esperando a que termine la petición en curso · {transcurrido}", ancho - 8
            )
            linea2 = f"    {self._barra.giro(self._fotograma)} {e.aviso(detalle)}"
            return [linea1, linea2, self._linea_lote()]
        fase = self._fase.descripcion if self._fase else "Esperando"
        if self._pausada:
            fase = "En pausa"
        cifras = self._cifras()
        ancho_barra = max(10, min(40, ancho - len(fase) - len(cifras) - 10))
        fraccion = self._progreso.fraccion if self._progreso else None
        barra = self._barra.dibujar(fraccion, ancho_barra, self._fotograma)
        etiqueta = e.aviso(fase) if self._pausada else e.info(fase)
        linea2 = f"    {etiqueta:<{14 + (len(etiqueta) - len(fase))}} {barra}  {e.tenue(cifras)}"

        return [linea1, linea2, self._linea_lote()]

    def _linea_lote(self) -> str:
        """Línea 3: avance del lote y atajos de teclado."""
        e = self._estilos
        hechas, total_tareas = self._tareas_terminadas, max(self._tarea_pos[1], 1)
        lote = self._barra.dibujar(hechas / total_tareas, 20)
        atajos = ""
        if self._ayuda_teclas:
            pausa = "reanudar" if self._pausada else "pausa"
            atajos = " · " + "  ".join(
                f"{e.acento(f'[{t}]')} {e.tenue(d)}"
                for t, d in (("p", pausa), ("s", "saltar"), ("c", "cancelar"), ("q", "salir"))
            )
        return f"  {e.tenue('Lote')} {lote}  {e.tenue(f'{hechas}/{total_tareas}')}{atajos}"

    def _cifras(self) -> str:
        """Texto de cifras según la fase: bytes y velocidad, segundos o tiempo transcurrido."""
        progreso = self._progreso
        if progreso is None or progreso.fase is not self._fase:
            transcurrido = time.monotonic() - self._inicio_fase
            detalle = (
                f"{self._detalle_fase} · " if self._detalle_fase and self._fase is FaseProceso.CONVIRTIENDO else ""
            )
            return f"{detalle}{BarraProgreso.formatear_tiempo(transcurrido)}"
        fraccion = progreso.fraccion
        porcentaje = f"{fraccion * 100:5.1f}%" if fraccion is not None else "  ?  "
        if progreso.fase is FaseProceso.DESCARGANDO:
            partes = [
                porcentaje,
                f"{BarraProgreso.formatear_bytes(progreso.completado)} / {BarraProgreso.formatear_bytes(progreso.total)}",
            ]
            if progreso.velocidad:
                partes.append(f"{BarraProgreso.formatear_bytes(progreso.velocidad)}/s")
            if progreso.eta is not None:
                partes.append(BarraProgreso.formatear_tiempo(progreso.eta))
            return " · ".join(partes)
        if progreso.fase is FaseProceso.ESPERANDO and progreso.total:
            return f"{porcentaje} · faltan {BarraProgreso.formatear_tiempo(progreso.total - progreso.completado)}"
        return porcentaje

    # ------------------------------------------------------------------ #
    def _iniciar_refresco(self) -> None:
        """Arranca el hilo que redibuja la zona en vivo periódicamente."""
        if not self._en_vivo or (self._refrescador and self._refrescador.is_alive()):
            return
        self._detener_refresco.clear()

        def bucle() -> None:
            while not self._detener_refresco.wait(0.12):
                with self._candado:
                    self._fotograma += 1
                    self._dibujar_vivo()

        self._refrescador = threading.Thread(target=bucle, name="tamalio-refresco", daemon=True)
        self._refrescador.start()

    def _detener_refrescador(self) -> None:
        self._detener_refresco.set()
        if self._refrescador is not None:
            self._refrescador.join(timeout=1)
        self._refrescador = None

    def iniciar_lote(self, total_tareas: int) -> None:
        """Activa la zona en vivo para un lote de ``total_tareas`` tareas."""
        with self._candado:
            self._activa = True
            self._tarea_pos = (0, total_tareas)
            self._tareas_terminadas = 0
            if self._en_vivo:
                self._escribir("\x1b[?25l")  # Oculta el cursor mientras hay barras.
        self._iniciar_refresco()

    def terminar_lote(self) -> None:
        """Desactiva la zona en vivo y restaura el cursor."""
        self._detener_refrescador()
        with self._candado:
            self._borrar_vivo()
            self._activa = False
            self._pendiente = None
            if self._en_vivo:
                self._escribir("\x1b[?25h")

    # ================================================================== #
    # Vista
    # ================================================================== #
    def mostrar_encabezado(self) -> None:
        """Ver :meth:`Vista.mostrar_encabezado`."""
        e = self._estilos
        logo = e.simbolo("🫔 ", "")
        self._permanente(
            f"\n  {logo}{e.negrita(e.acento(NOMBRE))} {e.tenue(__version__)}  {e.tenue('· Extractor de música Hi-Fi')}"
        )

    def mostrar_info(self, mensaje: str) -> None:
        """Ver :meth:`Vista.mostrar_info`."""
        self._permanente(f"  {self._estilos.info(self._estilos.simbolo('•', '*'))} {mensaje}")

    def mostrar_exito(self, mensaje: str) -> None:
        """Ver :meth:`Vista.mostrar_exito`."""
        self._permanente(f"  {self._estilos.exito(self._estilos.simbolo('✔', 'OK'))} {mensaje}")

    def mostrar_advertencia(self, mensaje: str) -> None:
        """Ver :meth:`Vista.mostrar_advertencia`."""
        self._permanente(f"  {self._estilos.aviso(self._estilos.simbolo('▲', '!'))} {self._estilos.aviso(mensaje)}")

    def mostrar_error(self, mensaje: str, sugerencia: str | None = None) -> None:
        """Ver :meth:`Vista.mostrar_error`."""
        e = self._estilos
        self._permanente(f"  {e.error(e.simbolo('✖', 'X'))} {e.error(mensaje)}")
        if sugerencia:
            self._permanente(f"    {e.tenue(e.simbolo('↳', '->'))} {e.tenue(sugerencia)}")

    def mostrar_registro(self, nivel: int, origen: str, mensaje: str) -> None:
        """Muestra un mensaje del módulo ``logging`` (lo llama el manejador de registro)."""
        e = self._estilos
        if self._depuracion:
            self._mostrar_depuracion(nivel, origen, mensaje)
            return
        if nivel >= logging.ERROR:
            self._permanente(f"    {e.error('error')} {e.tenue(origen)} {mensaje}")
        elif nivel >= logging.WARNING:
            self._permanente(f"    {e.aviso('aviso')} {e.tenue(mensaje)}")
        elif self._detallado:
            self._permanente(f"    {e.tenue(f'· {origen}: {mensaje}')}")

    def _mostrar_depuracion(self, nivel: int, origen: str, mensaje: str) -> None:
        """
        Formato del modo ``--debug``::

            22:50:13.418 DEBUG cliente_yt_dlp │ Opciones de yt-dlp: {…}
            22:50:14.002 DEBUG ffmpeg         │ FFmpeg $ ffmpeg -hide_banner …
                                              │ (líneas siguientes alineadas)
        """
        e = self._estilos
        hora = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
        componente = origen.removeprefix("tamalio.").split(".")[-1]
        componente = "yt-dlp" if componente == "yt_dlp" else componente
        componente = "ffmpeg" if componente == "ejecutor_ffmpeg" else componente
        colores = {logging.DEBUG: e.tenue, logging.INFO: e.info, logging.WARNING: e.aviso}
        color = colores.get(nivel, e.error)
        etiqueta = f"{logging.getLevelName(nivel):<7}"
        barra = e.tenue(e.simbolo("│", "|"))
        prefijo = f"  {e.tenue(hora)} {color(etiqueta)} {e.info(f'{componente:<22}')} {barra} "
        sangria = " " * (2 + 12 + 1 + 7 + 1 + 22 + 1) + barra + " "
        lineas = mensaje.splitlines() or [""]
        self._permanente(prefijo + lineas[0] + "".join(f"\n{sangria}{linea}" for linea in lineas[1:]))

    def mostrar_tabla(self, encabezados: Sequence[str], filas: Sequence[Sequence[object]]) -> None:
        """Ver :meth:`Vista.mostrar_tabla`. La última columna se recorta al ancho de la terminal."""
        e = self._estilos
        texto = [[str(celda) if celda is not None else "—" for celda in fila] for fila in filas]
        anchos = [len(encabezado) for encabezado in encabezados]
        for fila in texto:
            for indice, celda in enumerate(fila):
                anchos[indice] = max(anchos[indice], len(celda))
        fijo = sum(anchos[:-1]) + 2 * (len(anchos) - 1) + 2
        anchos[-1] = max(10, min(anchos[-1], self._ancho() - fijo))
        separador = e.simbolo("─", "-")

        def renglon(celdas: Sequence[str]) -> str:
            return "  " + "  ".join(self._recortar(c, anchos[i]).ljust(anchos[i]) for i, c in enumerate(celdas))

        self._permanente(e.negrita(renglon(list(encabezados))))
        self._permanente(e.tenue("  " + "  ".join(separador * ancho for ancho in anchos)))
        for fila in texto:
            self._permanente(renglon(fila))

    def mostrar_resumen(self, resumen: ResumenEjecucion, segundos: float) -> None:
        """Ver :meth:`Vista.mostrar_resumen`."""
        e = self._estilos
        linea = e.simbolo("─", "-") * min(56, self._ancho() - 2)
        self._permanente(f"\n  {e.tenue(linea)}")
        partes = [
            e.exito(f"{resumen.completadas} descargada(s)"),
            e.info(f"{resumen.omitidas} omitida(s)"),
            (e.error if resumen.fallidas else e.tenue)(f"{resumen.fallidas} fallida(s)"),
        ]
        self._permanente(f"  {e.negrita('Resumen')}  " + e.tenue(" · ").join(partes))
        self._permanente(
            f"  {e.tenue('Tamaño')}   {BarraProgreso.formatear_bytes(resumen.bytes_totales)}"
            f"   {e.tenue('Tiempo')} {BarraProgreso.formatear_tiempo(segundos)}"
        )
        for error in resumen.errores[:10]:
            self._permanente(f"  {e.error(e.simbolo('✖', 'X'))} {e.tenue(error)}")
        if len(resumen.errores) > 10:
            self._permanente(e.tenue(f"    … y {len(resumen.errores) - 10} error(es) más (ver el registro)."))

    def preguntar(self, pregunta: str, predeterminado: str | None = None) -> str | None:
        """Ver :meth:`Vista.preguntar`."""
        try:
            interactiva = sys.stdin.isatty()
        except AttributeError, ValueError:
            interactiva = False
        if not interactiva:
            return None
        e = self._estilos
        with self._candado:
            self._suspendida = True
            self._borrar_vivo()
            if self._en_vivo:
                self._escribir("\x1b[?25h")
        try:
            sufijo = f" {e.tenue(f'[{predeterminado}]')}" if predeterminado else ""
            respuesta = input(f"  {e.acento('?')} {pregunta}{sufijo}: ").strip()
        except EOFError:
            respuesta = ""
        finally:
            with self._candado:
                self._suspendida = False
                if self._en_vivo and self._activa:
                    self._escribir("\x1b[?25l")
                self._dibujar_vivo()
        return respuesta or predeterminado

    def confirmar(self, pregunta: str, predeterminado: bool = False) -> bool:
        """Ver :meth:`Vista.confirmar`."""
        respuesta = self.preguntar(f"{pregunta} (s/n)", "s" if predeterminado else "n")
        if respuesta is None:
            return predeterminado
        return respuesta.strip().lower() in {"s", "si", "sí", "y", "yes"}

    def establecer_ayuda_teclas(self, activa: bool) -> None:
        """Ver :meth:`Vista.establecer_ayuda_teclas`."""
        with self._candado:
            self._ayuda_teclas = activa
            self._dibujar_vivo()

    def mostrar_accion_pendiente(self, mensaje: str | None) -> None:
        """Ver :meth:`Vista.mostrar_accion_pendiente`."""
        with self._candado:
            self._pendiente = mensaje
            self._inicio_pendiente = time.monotonic()
            self._dibujar_vivo()

    def establecer_pausa(self, pausada: bool) -> None:
        """Ver :meth:`Vista.establecer_pausa`."""
        with self._candado:
            self._pausada = pausada
        mensaje = "Pausado. Pulsa [p] para reanudar." if pausada else "Reanudado."
        (self.mostrar_advertencia if pausada else self.mostrar_info)(mensaje)

    # ================================================================== #
    # ObservadorDescargas
    # ================================================================== #
    def al_iniciar_tarea(self, tarea: TareaDescarga, posicion: int, total: int) -> None:
        """Ver :meth:`ObservadorDescargas.al_iniciar_tarea`."""
        e = self._estilos
        with self._candado:
            self._tarea_pos = (posicion, total)
            self._pista = None
            self._progreso = None
        plataforma = tarea.fuente.plataforma.nombre_visible
        self._permanente(
            f"\n  {e.acento(e.simbolo('▶', '>'))} {e.tenue(f'[{posicion}/{total}]')} "
            f"{e.negrita(plataforma)} {e.tenue('·')} {e.tenue(tarea.fuente.url)}"
        )

    def al_resolver_tarea(self, tarea: TareaDescarga, titulo: str, pistas: int) -> None:
        """Ver :meth:`ObservadorDescargas.al_resolver_tarea`."""
        e = self._estilos
        self._permanente(f"    {e.negrita(titulo)} {e.tenue(f'· {pistas} pista(s)')}")

    def al_iniciar_pista(self, pista: Pista, posicion: int, total: int) -> None:
        """Ver :meth:`ObservadorDescargas.al_iniciar_pista`."""
        with self._candado:
            self._pista = pista
            self._pista_pos = (posicion, total)
            self._progreso = None
            self._dibujar_vivo()

    def al_cambiar_fase(self, fase: FaseProceso, detalle: str | None = None) -> None:
        """Ver :meth:`ObservadorDescargas.al_cambiar_fase`."""
        with self._candado:
            self._fase = fase
            self._detalle_fase = detalle
            self._inicio_fase = time.monotonic()
            self._progreso = None
            self._dibujar_vivo()

    def al_progreso(self, progreso: ProgresoDescarga) -> None:
        """Ver :meth:`ObservadorDescargas.al_progreso`. El refrescador se encarga de dibujar."""
        self._progreso = progreso

    def _linea_pista(self, pista: Pista, icono: str, sufijo: str) -> str:
        """Línea permanente con número, título y artista de una pista."""
        e = self._estilos
        n, total = self._pista_pos
        numero = f"{n:0{len(str(total))}d}" if total else "--"
        disponible = self._ancho() - len(e.sin_estilo(sufijo)) - 12
        titulo = self._recortar(f"{pista.titulo} — {pista.artista_principal}", disponible)
        return f"    {icono} {e.tenue(numero)} {titulo}  {sufijo}"

    def al_completar_pista(self, pista: Pista, tamano_bytes: int) -> None:
        """Ver :meth:`ObservadorDescargas.al_completar_pista`."""
        e = self._estilos
        extension = pista.ruta_archivo.suffix.lstrip(".") if pista.ruta_archivo else "?"
        sufijo = e.tenue(f"{extension} · {BarraProgreso.formatear_bytes(tamano_bytes)}")
        self._permanente(self._linea_pista(pista, e.exito(e.simbolo("✔", "OK")), sufijo))
        if self._detallado and pista.ruta_archivo:
            self._permanente(e.tenue(f"         {pista.ruta_archivo}"))

    def al_omitir_pista(self, pista: Pista, motivo: str) -> None:
        """Ver :meth:`ObservadorDescargas.al_omitir_pista`."""
        e = self._estilos
        with self._candado:
            self._pendiente = None  # El «saltar pista» ya se cumplió.
        self._permanente(self._linea_pista(pista, e.info(e.simbolo("↷", "-")), e.tenue(motivo)))

    def al_fallar_pista(self, pista: Pista | None, mensaje: str) -> None:
        """Ver :meth:`ObservadorDescargas.al_fallar_pista`."""
        e = self._estilos
        if pista is None:
            self._permanente(f"    {e.error(e.simbolo('✖', 'X'))} {e.error(mensaje)}")
            return
        self._permanente(self._linea_pista(pista, e.error(e.simbolo("✖", "X")), e.error("falló")))
        self._permanente(f"         {e.tenue(self._recortar(mensaje, self._ancho() - 10))}")

    def al_terminar_tarea(self, tarea: TareaDescarga, resumen: ResumenEjecucion) -> None:
        """Ver :meth:`ObservadorDescargas.al_terminar_tarea`."""
        e = self._estilos
        with self._candado:
            self._pendiente = None  # Cancelar/salir ya se cumplió.
            if tarea.estado.es_final or tarea.estado is EstadoDescarga.PAUSADA:
                self._tareas_terminadas += 1
            self._pista = None
            self._fase = None
            self._progreso = None
        colores = {
            EstadoDescarga.COMPLETADA: e.exito,
            EstadoDescarga.FALLIDA: e.error,
            EstadoDescarga.PAUSADA: e.aviso,
            EstadoDescarga.CANCELADA: e.aviso,
        }
        estado = colores.get(tarea.estado, e.tenue)(tarea.estado.value.replace("_", " "))
        detalle = e.tenue(
            f"{resumen.completadas} nuevas · {resumen.omitidas} omitidas · {resumen.fallidas} fallidas · "
            f"{BarraProgreso.formatear_bytes(resumen.bytes_totales)}"
        )
        self._permanente(f"    {e.tenue(e.simbolo('└', '`'))} {estado}  {detalle}")

    def al_aviso(self, mensaje: str) -> None:
        """Ver :meth:`ObservadorDescargas.al_aviso`."""
        self._permanente(f"    {self._estilos.aviso(self._estilos.simbolo('▲', '!'))} {self._estilos.aviso(mensaje)}")
