"""Controlador del comando ``tamalio convertir``."""

from pathlib import Path

from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.interfaces.repositorio_catalogo import RepositorioCatalogo
from tamalio.interfaces.vista import Vista
from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma
from tamalio.servicios.conversor_audio import ConversorAudio
from tamalio.servicios.descargador_caratulas import DescargadorCaratulas
from tamalio.servicios.ejecutor_ffmpeg import EjecutorFfmpeg
from tamalio.servicios.etiquetador_audio import EtiquetadorAudio


class ControladorConversion:
    """
    Convierte música ya descargada a otro formato.

    - Si el fichero está en el catálogo, se vuelve a etiquetar con los datos
      del catálogo (incluida la carátula) y se actualiza su ruta y formato.
    - Si no lo está, FFmpeg copia las etiquetas existentes (``-map_metadata 0``).

    Args:
        vista: Vista activa.
        catalogo: Repositorio del catálogo.
        conversor: Conversor de audio.
        etiquetador: Etiquetador.
        caratulas: Descargador de carátulas (con caché).
        ffmpeg: Ejecutor de FFmpeg (para leer duración y códec).
    """

    EXTENSIONES_AUDIO = frozenset({".flac", ".opus", ".ogg", ".mp3", ".m4a", ".wav", ".mka", ".webm", ".aac"})

    def __init__(
        self,
        vista: Vista,
        catalogo: RepositorioCatalogo,
        conversor: ConversorAudio,
        etiquetador: EtiquetadorAudio,
        caratulas: DescargadorCaratulas,
        ffmpeg: EjecutorFfmpeg,
    ) -> None:
        self._vista = vista
        self._catalogo = catalogo
        self._conversor = conversor
        self._etiquetador = etiquetador
        self._caratulas = caratulas
        self._ffmpeg = ffmpeg

    def convertir(
        self,
        rutas: list[Path],
        formato: FormatoAudio,
        plataforma: Plataforma | None = None,
        todo: bool = False,
        conservar_original: bool = False,
    ) -> int:
        """Convierte los ficheros indicados (o el catálogo completo/por plataforma)."""
        objetivos: list[tuple[Path, Pista | None]] = []
        if todo or plataforma:
            objetivos += [
                (p.ruta_archivo, p)
                for p in self._catalogo.listar(plataforma)
                if p.ruta_archivo is not None and p.descargada
            ]
        for ruta in rutas:
            ruta = ruta.expanduser()
            ficheros = (
                sorted(f for f in ruta.rglob("*") if f.suffix.lower() in self.EXTENSIONES_AUDIO)
                if ruta.is_dir()
                else [ruta]
            )
            objetivos += [(f, self._catalogo.buscar_por_ruta(f.resolve())) for f in ficheros]
        if not objetivos:
            raise ErrorTamalio("No hay nada que convertir.", sugerencia="Indica rutas, --plataforma o --todo.")

        errores = 0
        for indice, (ruta, pista) in enumerate(objetivos, start=1):
            prefijo = f"[{indice}/{len(objetivos)}]"
            codec = self._ffmpeg.codec_audio(ruta) if ruta.is_file() else None
            if codec is not None and codec == formato.codec:
                self._vista.mostrar_info(f"{prefijo} {ruta.name} ya está en {formato.value}; se omite.")
                continue
            try:
                nuevo = self._convertir_uno(ruta, pista, formato, codec)
            except ErrorTamalio as error:
                errores += 1
                self._vista.mostrar_error(f"{prefijo} {ruta.name}: {error.mensaje}")
                continue
            if not conservar_original and nuevo.resolve() != ruta.resolve():
                ruta.unlink(missing_ok=True)
            self._vista.mostrar_exito(f"{prefijo} {ruta.name} → {nuevo.name}")
        return 1 if errores else 0

    def _convertir_uno(self, ruta: Path, pista: Pista | None, formato: FormatoAudio, codec: str | None) -> Path:
        """Convierte un fichero y lo vuelve a etiquetar si está en el catálogo."""
        if not ruta.is_file():
            raise ErrorTamalio("el fichero no existe.")
        if ConversorAudio.pierde_calidad(formato, codec):
            self._vista.mostrar_advertencia(f"{ruta.name}: {codec} → {formato.value} recodifica con pérdida.")
        duracion = pista.duracion if pista else None
        nuevo = self._conversor.convertir(
            ruta,
            formato,
            ruta.parent / ruta.stem,
            codec_origen=codec,
            duracion=duracion,
            conservar_metadatos=pista is None,
        )
        if pista is not None:
            imagen = self._caratulas.obtener(pista.caratula) if pista.caratula else None
            self._etiquetador.etiquetar(nuevo, pista, imagen)
            pista.ruta_archivo = nuevo.resolve()
            pista.formato = formato.value
            self._catalogo.guardar(pista)
        return nuevo
