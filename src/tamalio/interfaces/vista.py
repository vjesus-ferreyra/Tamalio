"""Contrato de la capa de presentación (la «V» de MVC)."""

from abc import abstractmethod
from collections.abc import Sequence

from tamalio.interfaces.observador_descargas import ObservadorDescargas
from tamalio.modelos.resumen_ejecucion import ResumenEjecucion


class Vista(ObservadorDescargas):
    """
    Todo lo que el usuario ve o responde.

    Hereda de :class:`ObservadorDescargas` para poder recibir los eventos del
    proceso de descarga. Hoy existe una implementación de consola; mañana
    podría existir una gráfica sin tocar controladores ni modelos.
    """

    @abstractmethod
    def mostrar_encabezado(self) -> None:
        """Muestra el nombre y la versión de la aplicación."""

    @abstractmethod
    def mostrar_info(self, mensaje: str) -> None:
        """Mensaje neutro."""

    @abstractmethod
    def mostrar_exito(self, mensaje: str) -> None:
        """Mensaje de operación exitosa."""

    @abstractmethod
    def mostrar_advertencia(self, mensaje: str) -> None:
        """Mensaje de advertencia."""

    @abstractmethod
    def mostrar_error(self, mensaje: str, sugerencia: str | None = None) -> None:
        """Mensaje de error con una sugerencia opcional."""

    @abstractmethod
    def mostrar_tabla(self, encabezados: Sequence[str], filas: Sequence[Sequence[object]]) -> None:
        """Muestra datos tabulares."""

    @abstractmethod
    def mostrar_resumen(self, resumen: ResumenEjecucion, segundos: float) -> None:
        """Resumen final de un lote de descargas."""

    @abstractmethod
    def preguntar(self, pregunta: str, predeterminado: str | None = None) -> str | None:
        """
        Hace una pregunta abierta.

        Returns:
            La respuesta, el valor predeterminado si se deja vacía o ``None`` si
            no hay una terminal interactiva para preguntar.
        """

    @abstractmethod
    def confirmar(self, pregunta: str, predeterminado: bool = False) -> bool:
        """Pregunta de sí/no."""

    @abstractmethod
    def iniciar_lote(self, total_tareas: int) -> None:
        """Prepara la presentación del progreso de un lote de ``total_tareas`` tareas."""

    @abstractmethod
    def terminar_lote(self) -> None:
        """Retira la presentación del progreso al terminar el lote."""

    @abstractmethod
    def establecer_ayuda_teclas(self, activa: bool) -> None:
        """Muestra u oculta la línea con los atajos de teclado (pausa, saltar…)."""

    @abstractmethod
    def establecer_pausa(self, pausada: bool) -> None:
        """Refleja visualmente que la descarga está en pausa."""

    @abstractmethod
    def mostrar_accion_pendiente(self, mensaje: str | None) -> None:
        """
        Muestra que una orden del usuario (saltar, cancelar, salir) está en curso.

        Detener una petición de red no es instantáneo; este aviso permanece en
        pantalla, con el tiempo transcurrido, hasta que la orden se cumple.
        ``None`` lo retira.
        """
