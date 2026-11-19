"""Decide dónde se guarda cada canción dentro de la biblioteca y mueve los ficheros."""

import logging
import re
import shutil
import unicodedata
from pathlib import Path

from tamalio.modelos.pista import Pista
from tamalio.modelos.plataforma import Plataforma

registro = logging.getLogger(__name__)


class OrganizadorBiblioteca:
    """
    Mantiene la estructura de carpetas del catálogo personal::

        ~/Música/<usuario>/
        ├── YouTube/
        │   └── <Artista del álbum>/
        │       ├── <Álbum> (<Año>)/
        │       │   └── 01 - <Título>.opus
        │       └── Sencillos/
        │           └── <Título>.opus
        ├── SoundCloud/
        └── Bandcamp/

    Los nombres se «sanean» para que sean válidos en Windows, macOS y Linux
    (sin ``<>:"/\\|?*``, sin nombres reservados como ``CON`` y con longitud acotada).

    Args:
        raiz: Carpeta raíz de la biblioteca del usuario (``…/Música/<usuario>``).
    """

    #: Longitud máxima de cada componente de la ruta (caracteres).
    LONGITUD_MAXIMA = 120
    #: Nombres prohibidos en Windows (sin importar la extensión).
    RESERVADOS_WINDOWS = frozenset(
        {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    )
    #: Sustituciones de caracteres prohibidos por equivalentes legibles.
    _SUSTITUCIONES = str.maketrans(
        {"/": "-", "\\": "-", ":": " -", "*": "", "?": "", '"': "'", "<": "(", ">": ")", "|": "-"}
    )

    def __init__(self, raiz: Path) -> None:
        self._raiz = raiz

    @property
    def raiz(self) -> Path:
        """Raíz de la biblioteca del usuario."""
        return self._raiz

    def preparar(self) -> None:
        """Crea la carpeta del usuario y las tres carpetas hijas de plataforma."""
        for plataforma in Plataforma:
            (self._raiz / plataforma.nombre_carpeta).mkdir(parents=True, exist_ok=True)

    def ruta_para(self, pista: Pista, extension: str) -> Path:
        """Ruta final (aún no creada) para la pista con la extensión dada."""
        carpeta = self._raiz / pista.plataforma.nombre_carpeta / self.sanear(pista.artista_album_principal)
        if pista.es_sencillo:
            carpeta /= "Sencillos"
            nombre = pista.titulo
        else:
            album = f"{pista.album} ({pista.anio})" if pista.anio else pista.album
            carpeta /= self.sanear(album)
            if pista.numero_pista:
                digitos = 3 if (pista.total_pistas or 0) >= 100 else 2
                nombre = f"{pista.numero_pista:0{digitos}d} - {pista.titulo}"
            else:
                nombre = pista.titulo
        return carpeta / f"{self.sanear(nombre)}.{extension.lstrip('.')}"

    def colocar(self, origen: Path, destino: Path) -> Path:
        """
        Mueve ``origen`` a ``destino`` creando carpetas y evitando sobrescrituras.

        Si ya existe un fichero distinto con ese nombre se agrega « (2)», « (3)»…

        Returns:
            La ruta final real.
        """
        destino.parent.mkdir(parents=True, exist_ok=True)
        final = destino
        contador = 2
        while final.exists():
            final = destino.with_name(f"{destino.stem} ({contador}){destino.suffix}")
            contador += 1
        # shutil.move funciona incluso entre discos distintos (copia + borra).
        shutil.move(origen, final)
        registro.debug("Fichero colocado en %s", final)
        return final

    @classmethod
    def sanear(cls, texto: str) -> str:
        """Convierte ``texto`` en un nombre de fichero válido en cualquier sistema."""
        limpio = unicodedata.normalize("NFC", texto).translate(cls._SUSTITUCIONES)
        limpio = "".join(c for c in limpio if unicodedata.category(c)[0] != "C")  # Sin caracteres de control.
        limpio = re.sub(r"\s+", " ", limpio).strip().rstrip(". ")
        if not limpio:
            limpio = "Sin nombre"
        if limpio.split(".")[0].upper() in cls.RESERVADOS_WINDOWS:
            limpio = f"_{limpio}"
        if len(limpio) > cls.LONGITUD_MAXIMA:
            limpio = limpio[: cls.LONGITUD_MAXIMA].rstrip(". ")
        return limpio
