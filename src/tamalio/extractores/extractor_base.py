"""Clase abstracta con la lógica de normalización común a todas las plataformas."""

import re
from abc import abstractmethod
from collections import Counter
from datetime import UTC, date, datetime
from typing import Any

from tamalio.extractores.contexto_coleccion import ContextoColeccion
from tamalio.interfaces.extractor import Extractor
from tamalio.modelos.caratula import Caratula
from tamalio.modelos.fuente import Fuente
from tamalio.modelos.pista import Pista


class ExtractorBase(Extractor):
    """
    Implementa el patrón *Template Method* para construir :class:`Pista`.

    El algoritmo general vive en :meth:`normalizar` y :meth:`_crear_pista`;
    cada plataforma solo sobrescribe los «ganchos» (``_titulo_crudo``,
    ``_artistas_crudos``, ``_generos``, ``_caratula``, ``_es_album``…) donde sus
    datos se comportan distinto.

    Pasos del algoritmo para cada entrada:

    1. Obtener artistas y título «crudos» de la plataforma.
    2. Separar «Artista - Título» si el título trae el artista como prefijo.
    3. Limpiar sufijos de video: «(Official Music Video)», «[Lyric Video]»…
    4. Normalizar invitados «ft./feat.» → «(feat. X)» y agregarlos a artistas.
    5. Resolver álbum, artistas del álbum, número de pista, géneros, año y carátula,
       usando el :class:`ContextoColeccion` cuando la pista viene de un álbum.

    Args:
        agregar_invitados: Si ``True``, los artistas invitados se agregan a la
            lista de artistas de la pista.
        recortar_caratulas_video: Si ``True``, las miniaturas 16:9 se recortan a 1:1.
    """

    # «Artista - Título» (acepta guion, en-dash y em-dash).
    _PATRON_ARTISTA_TITULO = re.compile(r"^(?P<artista>.+?)\s+[-–—]\s+(?P<titulo>.+)$")
    # Sufijos típicos de videos: (Official Music Video), [Audio], (Video Oficial)…
    _PATRON_SUFIJO_VIDEO = re.compile(
        r"\s*[\(\[]\s*(?:(?:official|oficial|music|musical|lyrics?|letra|con|audio|v[ií]deo|"
        r"visuali[sz]er|mv|hd|hq|4k)\s*)+[\)\]]",
        re.IGNORECASE,
    )
    # Invitados entre paréntesis: (feat. X), [ft. X], (featuring X).
    _PATRON_INVITADOS_PARENTESIS = re.compile(
        r"\s*[\(\[]\s*(?:feat\.?|ft\.?|featuring)\s+(?P<invitados>[^\)\]]+)[\)\]]", re.IGNORECASE
    )
    # Invitados sin paréntesis al final: «Canción ft. X, Y».
    _PATRON_INVITADOS_LIBRE = re.compile(r"\s+(?:feat\.?|ft\.?|featuring)\s+(?P<invitados>.+)$", re.IGNORECASE)
    # Separadores entre varios invitados («X, Y & Z»).
    _SEPARADOR_INVITADOS = re.compile(r"\s*,\s*|\s+&\s+")

    def __init__(self, agregar_invitados: bool = True, recortar_caratulas_video: bool = True) -> None:
        self._agregar_invitados = agregar_invitados
        self._recortar_caratulas_video = recortar_caratulas_video

    # ================================================================== #
    # Algoritmo plantilla
    # ================================================================== #
    def normalizar(self, info: dict[str, Any], fuente: Fuente) -> list[Pista]:
        """Ver :meth:`Extractor.normalizar`."""
        if info.get("_type") == "playlist" or "entries" in info:
            entradas = [entrada for entrada in (info.get("entries") or []) if entrada]
            contexto = self._crear_contexto(info, entradas)
            pistas = [
                self._crear_pista(entrada, contexto, posicion) for posicion, entrada in enumerate(entradas, start=1)
            ]
        else:
            pistas = [self._crear_pista(info, None, 1)]

        # Las sobrescrituras del usuario siempre ganan sobre lo extraído.
        for pista in pistas:
            pista.aplicar_metadatos(fuente.metadatos)
        return pistas

    def _crear_contexto(self, info: dict[str, Any], entradas: list[dict[str, Any]]) -> ContextoColeccion:
        """Calcula los datos compartidos de la colección (artista y año más frecuentes)."""
        artistas = Counter()
        anios = Counter()
        for entrada in entradas:
            lista, _ = self._artistas_y_titulo(entrada)
            if lista:
                artistas[lista[0]] += 1
            anio = self._anio_propio(entrada)
            if anio:
                anios[anio] += 1
        return ContextoColeccion(
            titulo=str(info.get("title") or info.get("album") or "Colección sin nombre"),
            identificador=str(info.get("id") or ""),
            es_album=self._es_album(info, entradas),
            total=len(entradas) or int(info.get("playlist_count") or 0),
            artista=self._artista_album_coleccion(info) or (artistas.most_common(1)[0][0] if artistas else None),
            anio=anios.most_common(1)[0][0] if anios else self._anio_plausible(info.get("release_year")),
            caratula=self._caratula_coleccion(info, entradas),
        )

    def _crear_pista(self, entrada: dict[str, Any], contexto: ContextoColeccion | None, posicion: int) -> Pista:
        """Construye una :class:`Pista` aplicando los pasos descritos en la clase."""
        artistas, titulo = self._artistas_y_titulo(entrada)
        titulo, invitados = self._extraer_invitados(self._limpiar_titulo(titulo))
        if self._agregar_invitados:
            artistas = self._sin_duplicados([*artistas, *invitados])
        if not artistas:
            artistas = [self._artista_respaldo(entrada)]

        album, es_sencillo = self._album(entrada, contexto, titulo)
        artistas_album = self._artistas_album(entrada, contexto) or artistas[:1]
        en_album = contexto is not None and contexto.es_album

        if en_album:
            numero = self._numero_pista(entrada) or posicion
            total = contexto.total
        elif es_sencillo:
            numero, total = 1, 1
        else:
            numero, total = self._numero_pista(entrada), None
            # Sencillo «de facto»: pista suelta cuyo álbum se llama igual que ella.
            if contexto is None and numero is None and album.casefold() == titulo.casefold():
                numero, total = 1, 1

        caratula = contexto.caratula if en_album and contexto.caratula else self._caratula(entrada)
        return Pista(
            plataforma=self.plataforma,
            id_externo=str(entrada.get("id") or entrada.get("track_id")),
            url=self._url_pista(entrada),
            titulo=titulo,
            album=album,
            artistas=artistas,
            artistas_album=artistas_album,
            numero_pista=numero,
            total_pistas=total,
            generos=self._generos(entrada),
            anio=self._anio_propio(entrada) or (contexto.anio if contexto else None) or self._anio_subida(entrada),
            duracion=entrada.get("duration"),
            caratula=caratula,
            es_sencillo=es_sencillo,
            codec_origen=entrada.get("acodec"),
            bitrate_origen=entrada.get("abr"),
            info_extraccion=entrada,
        )

    # ================================================================== #
    # Ganchos que las subclases pueden sobrescribir
    # ================================================================== #
    def _titulo_crudo(self, entrada: dict[str, Any]) -> str:
        """Título tal como lo da la plataforma (antes de limpiarlo)."""
        return str(entrada.get("track") or entrada.get("title") or "Sin título")

    def _artistas_crudos(self, entrada: dict[str, Any]) -> list[str]:
        """Artistas declarados explícitamente por la plataforma."""
        artistas = entrada.get("artists")
        if artistas:
            return self._sin_duplicados(str(a) for a in artistas)
        if entrada.get("artist"):
            return self._sin_duplicados(a.strip() for a in str(entrada["artist"]).split(","))
        return []

    def _artista_respaldo(self, entrada: dict[str, Any]) -> str:
        """Último recurso: el nombre de quien subió la pista."""
        return str(entrada.get("uploader") or entrada.get("channel") or "Artista desconocido")

    def _album(self, entrada: dict[str, Any], contexto: ContextoColeccion | None, titulo: str) -> tuple[str, bool]:
        """
        Devuelve ``(album, es_sencillo)``.

        Si la pista no tiene álbum, se usa su propio título y se marca como
        sencillo (convención de las tiendas digitales para *singles*).
        """
        if entrada.get("album"):
            return str(entrada["album"]), False
        if contexto is not None and contexto.es_album:
            return contexto.titulo, False
        return titulo, True

    def _artistas_album(self, entrada: dict[str, Any], contexto: ContextoColeccion | None) -> list[str]:
        """Artistas del álbum declarados por la plataforma o heredados del contexto."""
        if entrada.get("album_artists"):
            return self._sin_duplicados(str(a) for a in entrada["album_artists"])
        if entrada.get("album_artist"):
            return [str(entrada["album_artist"])]
        if contexto is not None and contexto.es_album and contexto.artista:
            return [contexto.artista]
        return []

    def _artista_album_coleccion(self, info: dict[str, Any]) -> str | None:
        """Artista del álbum declarado en la raíz de la colección, si existe."""
        if info.get("album_artist"):
            return str(info["album_artist"])
        artistas = info.get("album_artists")
        return str(artistas[0]) if artistas else None

    def _numero_pista(self, entrada: dict[str, Any]) -> int | None:
        """Número declarado por la plataforma (``track_number``) o la posición en la lista."""
        valor = entrada.get("track_number") or entrada.get("playlist_index")
        return int(valor) if valor else None

    def _generos(self, entrada: dict[str, Any]) -> list[str]:
        """Géneros declarados (``genres`` o ``genre``)."""
        if entrada.get("genres"):
            return self._sin_duplicados(str(g) for g in entrada["genres"])
        if entrada.get("genre"):
            return [str(entrada["genre"])]
        return []

    @abstractmethod
    def _es_album(self, info: dict[str, Any], entradas: list[dict[str, Any]]) -> bool:
        """Decide si la colección es un álbum real o una lista cualquiera."""

    @abstractmethod
    def _caratula(self, entrada: dict[str, Any]) -> Caratula | None:
        """Carátula de una pista individual."""

    @abstractmethod
    def _caratula_coleccion(self, info: dict[str, Any], entradas: list[dict[str, Any]]) -> Caratula | None:
        """Carátula del álbum completo."""

    def _url_pista(self, entrada: dict[str, Any]) -> str:
        """URL canónica de la pista."""
        return str(entrada.get("webpage_url") or entrada.get("original_url") or entrada.get("url"))

    # ================================================================== #
    # Utilidades compartidas
    # ================================================================== #
    def _artistas_y_titulo(self, entrada: dict[str, Any]) -> tuple[list[str], str]:
        """
        Obtiene artistas y título separando el prefijo «Artista - » cuando aplica.

        - Si la plataforma declara artistas y el título empieza con uno de ellos,
          se quita el prefijo («Klaypex - Lights» → «Lights»).
        - Si no declara artistas, el prefijo se toma como artista
          («K/DA - FIRESTARTER…» → artista «K/DA»).
        """
        artistas = self._artistas_crudos(entrada)
        titulo = self._titulo_crudo(entrada).strip()
        coincidencia = self._PATRON_ARTISTA_TITULO.match(titulo)
        if coincidencia:
            prefijo = coincidencia["artista"].strip()
            if not artistas:
                return [prefijo], coincidencia["titulo"].strip()
            if prefijo.casefold() in {a.casefold() for a in artistas}:
                return artistas, coincidencia["titulo"].strip()
        return artistas, titulo

    def _limpiar_titulo(self, titulo: str) -> str:
        """Quita sufijos de video («(Official Music Video)», «[Audio]»…) y espacios dobles."""
        limpio = self._PATRON_SUFIJO_VIDEO.sub("", titulo)
        return re.sub(r"\s{2,}", " ", limpio).strip() or titulo

    def _extraer_invitados(self, titulo: str) -> tuple[str, list[str]]:
        """
        Detecta artistas invitados y normaliza el título a «Canción (feat. X, Y)».

        Returns:
            ``(titulo_normalizado, invitados)``.
        """
        coincidencia = self._PATRON_INVITADOS_PARENTESIS.search(titulo) or self._PATRON_INVITADOS_LIBRE.search(titulo)
        if not coincidencia:
            return titulo, []
        texto_invitados = coincidencia["invitados"].strip()
        invitados = [i.strip() for i in self._SEPARADOR_INVITADOS.split(texto_invitados) if i.strip()]
        base = (titulo[: coincidencia.start()] + titulo[coincidencia.end() :]).strip()
        return f"{base} (feat. {texto_invitados})", invitados

    def _anio_propio(self, entrada: dict[str, Any]) -> int | None:
        """Año de lanzamiento declarado por la pista (``release_date`` o ``release_year``)."""
        return self._anio_plausible(entrada.get("release_date")) or self._anio_plausible(entrada.get("release_year"))

    def _anio_subida(self, entrada: dict[str, Any]) -> int | None:
        """Respaldo: año en que se subió la pista a la plataforma."""
        anio = self._anio_plausible(entrada.get("upload_date"))
        if anio is None and entrada.get("timestamp"):
            anio = datetime.fromtimestamp(float(entrada["timestamp"]), tz=UTC).year
        return anio

    @staticmethod
    def _anio_plausible(valor: Any) -> int | None:
        """
        Convierte ``"20220429"``, ``2022`` o ``"2022"`` en un año **verosímil**.

        Se descartan años absurdos: YouTube a veces calcula ``release_year``
        a partir del texto «℗ 2839655 Records», lo que produce ``2839``.
        """
        if valor in (None, ""):
            return None
        try:
            anio = int(str(valor)[:4])
        except ValueError:
            return None
        return anio if 1877 <= anio <= date.today().year + 1 else None

    @staticmethod
    def _sin_duplicados(valores) -> list[str]:
        """Elimina duplicados (sin distinguir mayúsculas) conservando el orden."""
        vistos: set[str] = set()
        resultado: list[str] = []
        for valor in valores:
            texto = str(valor).strip()
            if texto and texto.casefold() not in vistos:
                vistos.add(texto.casefold())
                resultado.append(texto)
        return resultado
