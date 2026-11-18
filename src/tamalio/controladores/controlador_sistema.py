"""Controlador de comandos de mantenimiento: doctor, base de datos y sesiones."""

from pathlib import Path

from tamalio.interfaces.repositorio_sesiones import RepositorioSesiones
from tamalio.interfaces.vista import Vista
from tamalio.modelos.plataforma import Plataforma
from tamalio.repositorios.conexion_postgres import ConexionPostgres
from tamalio.servicios.gestor_sesiones import GestorSesiones
from tamalio.servicios.verificador_dependencias import VerificadorDependencias


class ControladorSistema:
    """
    Casos de uso de mantenimiento.

    Args:
        vista: Vista activa.
    """

    def __init__(self, vista: Vista) -> None:
        self._vista = vista

    def doctor(self, verificador: VerificadorDependencias) -> int:
        """``tamalio doctor``: tabla de comprobaciones; devuelve 1 si alguna falla."""
        resultados = verificador.verificar()
        filas = [
            (
                "✔" if resultado.correcto else "✖",
                resultado.nombre,
                resultado.detalle if resultado.correcto else f"{resultado.detalle} → {resultado.sugerencia}",
            )
            for resultado in resultados
        ]
        self._vista.mostrar_tabla(("", "Componente", "Detalle"), filas)
        fallidos = [resultado for resultado in resultados if not resultado.correcto]
        if fallidos:
            self._vista.mostrar_advertencia(f"{len(fallidos)} comprobación(es) requieren atención.")
            return 1
        self._vista.mostrar_exito("Todo listo para extraer música.")
        return 0

    def iniciar_bd(self, conexion: ConexionPostgres) -> int:
        """``tamalio bd iniciar``: aplica las migraciones pendientes."""
        aplicados = conexion.migrar()
        if aplicados:
            self._vista.mostrar_exito(f"Esquema actualizado: {', '.join(aplicados)}.")
        else:
            self._vista.mostrar_info("La base de datos ya estaba al día.")
        self._vista.mostrar_info(conexion.version_servidor())
        return 0

    def establecer_sesion(self, sesiones: GestorSesiones, plataforma: Plataforma, ruta: Path) -> int:
        """``tamalio sesion establecer``."""
        validada = sesiones.registrar(plataforma, ruta)
        self._vista.mostrar_exito(f"Cookies de {plataforma.nombre_visible} registradas: {validada}")
        return 0

    def listar_sesiones(self, repositorio: RepositorioSesiones, configuradas: dict[Plataforma, Path]) -> int:
        """``tamalio sesion listar``: muestra rutas de la BD y de la configuración."""
        registradas = repositorio.listar()
        filas = []
        for plataforma in Plataforma:
            ruta = registradas.get(plataforma) or configuradas.get(plataforma)
            origen = "base de datos" if plataforma in registradas else ("configuración" if ruta else "—")
            existe = "sí" if ruta and ruta.is_file() else "no"
            filas.append((plataforma.nombre_visible, origen, existe, ruta))
        self._vista.mostrar_tabla(("Plataforma", "Origen", "Existe", "Fichero"), filas)
        return 0

    def quitar_sesion(self, repositorio: RepositorioSesiones, plataforma: Plataforma) -> int:
        """``tamalio sesion quitar``."""
        if repositorio.eliminar(plataforma):
            self._vista.mostrar_exito(f"Se olvidó el fichero de cookies de {plataforma.nombre_visible}.")
        else:
            self._vista.mostrar_info(f"No había cookies registradas para {plataforma.nombre_visible}.")
        return 0
