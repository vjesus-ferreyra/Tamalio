"""Lector del formato de fuentes estructurado (JSONC con ``$schema``)."""

from pathlib import Path
from typing import Any

from tamalio.excepciones.error_formato_fuentes import ErrorFormatoFuentes
from tamalio.excepciones.error_tamalio import ErrorTamalio
from tamalio.interfaces.lector_fuentes import LectorFuentes
from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.fuente import Fuente
from tamalio.modelos.plataforma import Plataforma
from tamalio.servicios.analizador_jsonc import AnalizadorJsonc
from tamalio.servicios.detector_plataforma import DetectorPlataforma
from tamalio.servicios.recursos_empaquetados import RecursosEmpaquetados
from tamalio.servicios.validador_esquema import ValidadorEsquema


class LectorFuentesJsonc(LectorFuentes):
    """
    Lee ficheros ``.jsonc`` / ``.json`` que cumplen ``fuentes.schema.json``.

    Ejemplo mínimo::

        {
          "$schema": "…/fuentes.schema.json",
          "version": 1,
          "predeterminados": { "formato": "flac" },
          "fuentes": [
            // Una cadena es la forma corta…
            "https://ghostdata.bandcamp.com/track/fluorite-fault",
            // …y un objeto permite opciones por fuente.
            { "url": "https://youtu.be/FB9u24ZpDek", "formato": "opus",
              "metadatos": { "generos": ["Electronic"] } }
          ]
        }

    Los valores de ``predeterminados`` se aplican a cada fuente que no los
    defina; los ``metadatos`` se combinan (los de la fuente ganan).

    Args:
        detector: Clasificador de URL.
        analizador: Analizador JSONC.
    """

    EXTENSIONES = frozenset({".jsonc", ".json", ".tamalio"})

    def __init__(self, detector: DetectorPlataforma, analizador: AnalizadorJsonc | None = None) -> None:
        self._detector = detector
        self._analizador = analizador or AnalizadorJsonc()

    def admite(self, ruta: Path, contenido: str) -> bool:
        """Por extensión o si el contenido (sin comentarios) empieza con ``{``."""
        if ruta.suffix.lower() in self.EXTENSIONES:
            return True
        return AnalizadorJsonc.quitar_comentarios(contenido).lstrip().startswith("{")

    def leer(self, ruta: Path, contenido: str) -> list[Fuente]:
        """Ver :meth:`LectorFuentes.leer`."""
        try:
            documento = self._analizador.cargar(contenido)
        except ValueError as error:
            raise ErrorFormatoFuentes(ruta, [str(error)]) from error

        errores = ValidadorEsquema(RecursosEmpaquetados.esquema("fuentes")).validar(documento)
        if errores:
            raise ErrorFormatoFuentes(ruta, errores)

        predeterminados: dict[str, Any] = documento.get("predeterminados", {})
        fuentes: list[Fuente] = []
        vistas: set[str] = set()
        for indice, entrada in enumerate(documento["fuentes"]):
            datos = {"url": entrada} if isinstance(entrada, str) else dict(entrada)
            if datos.get("omitir"):
                continue
            try:
                fuente = self._crear_fuente(datos, predeterminados)
            except (ErrorTamalio, ValueError) as error:
                mensaje = error.mensaje if isinstance(error, ErrorTamalio) else str(error)
                errores.append(f"$.fuentes[{indice}]: {mensaje}")
                continue
            if fuente.url not in vistas:
                vistas.add(fuente.url)
                fuentes.append(fuente)
        if errores:
            raise ErrorFormatoFuentes(ruta, errores)
        return fuentes

    def _crear_fuente(self, datos: dict[str, Any], predeterminados: dict[str, Any]) -> Fuente:
        """Combina la entrada con los predeterminados y la clasifica."""
        formato = datos.get("formato") or predeterminados.get("formato")
        plataforma = datos.get("plataforma")
        metadatos = {**predeterminados.get("metadatos", {}), **datos.get("metadatos", {})}
        return self._detector.detectar(
            datos["url"],
            plataforma=Plataforma.desde_texto(plataforma) if plataforma else None,
            formato=FormatoAudio(formato) if formato else None,
            metadatos=metadatos,
            comentario=datos.get("comentario"),
        )
