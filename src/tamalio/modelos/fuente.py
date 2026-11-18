"""Entidad que representa un enlace (fuente) a descargar."""

from dataclasses import dataclass, field
from typing import Any

from tamalio.modelos.formato_audio import FormatoAudio
from tamalio.modelos.plataforma import Plataforma
from tamalio.modelos.tipo_fuente import TipoFuente


@dataclass(frozen=True, slots=True)
class Fuente:
    """
    Un enlace ya clasificado y normalizado, listo para encolarse.

    Attributes:
        url_original: Tal como la escribió el usuario.
        url: URL canónica (p. ej. ``music.youtube.com/watch?v=X`` →
            ``www.youtube.com/watch?v=X``). Sirve para evitar duplicados.
        plataforma: Plataforma detectada.
        tipo: Pista, colección o desconocido.
        identificador: ID dentro de la plataforma (``v``, ``list``, ruta…).
        formato: Formato de salida solicitado para esta fuente (``None`` =
            usar el de la configuración).
        metadatos: Sobrescrituras manuales de metadatos (ver esquema de fuentes).
        comentario: Nota libre del usuario.
    """

    url_original: str
    url: str
    plataforma: Plataforma
    tipo: TipoFuente
    identificador: str
    formato: FormatoAudio | None = None
    metadatos: dict[str, Any] = field(default_factory=dict)
    comentario: str | None = None

    @property
    def solo_pista(self) -> bool:
        """
        ``True`` si debe descargarse únicamente la pista y no la lista asociada.

        Ejemplo: ``watch?v=X&list=Y`` descarga solo ``X``.
        """
        return self.tipo is TipoFuente.PISTA

    def opciones(self) -> dict[str, Any]:
        """Datos opcionales que se guardan como JSONB junto a la tarea."""
        return {
            "url_original": self.url_original,
            "tipo": self.tipo.value,
            "identificador": self.identificador,
            "formato": self.formato.value if self.formato else None,
            "metadatos": dict(self.metadatos),
            "comentario": self.comentario,
        }

    @classmethod
    def desde_opciones(cls, url: str, plataforma: str, opciones: dict[str, Any]) -> Fuente:
        """Reconstruye la fuente a partir de lo guardado en la base de datos."""
        formato = opciones.get("formato")
        return cls(
            url_original=opciones.get("url_original") or url,
            url=url,
            plataforma=Plataforma(plataforma),
            tipo=TipoFuente(opciones.get("tipo") or TipoFuente.DESCONOCIDO.value),
            identificador=opciones.get("identificador") or url,
            formato=FormatoAudio(formato) if formato else None,
            metadatos=dict(opciones.get("metadatos") or {}),
            comentario=opciones.get("comentario"),
        )
