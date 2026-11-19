# Formatos de ficheros y metadatos

Tamalio trabaja con tres tipos de ficheros escritos por personas (o por la
propia aplicación) y legibles por máquinas. Todos admiten **comentarios**.

| Fichero | Para qué | Formato | Esquema |
|---------|----------|---------|---------|
| Fuentes (estructurado) | Descarga en masa con opciones por fuente | JSONC (`.jsonc`) | [`fuentes.schema.json`](../src/tamalio/recursos/esquemas/fuentes.schema.json) |
| Fuentes (simple) | Descarga en masa rápida | Texto (`.txt`) | — (una URL por línea) |
| Catálogo | Exportar / importar entre equipos | JSONC (`.jsonc`) | [`catalogo.schema.json`](../src/tamalio/recursos/esquemas/catalogo.schema.json) |
| Configuración | Ajustes de la aplicación | TOML (`tamalio.toml`) | — (ver [`config/tamalio.ejemplo.toml`](../config/tamalio.ejemplo.toml)) |

## ¿Por qué JSONC?

- Es JSON (cualquier lenguaje lo lee) con **comentarios** `//` y `/* */` y
  **comas finales** opcionales: cómodo de escribir a mano.
- Admite la propiedad **`$schema`**: editores como VS Code, JetBrains o Zed
  validan y autocompletan el fichero mientras se escribe.
- Tamalio lo lee solo con la biblioteca estándar (`AnalizadorJsonc`) y lo valida
  contra su esquema (`ValidadorEsquema`) antes de usarlo, mostrando la ruta JSON
  exacta de cada error (por ejemplo `$.fuentes[3].formato`).

---

## 1. Fichero de fuentes (`.jsonc`)

Ejemplo completo: [`ejemplos/fuentes.jsonc`](../ejemplos/fuentes.jsonc).

```jsonc
{
  "$schema": "https://raw.githubusercontent.com/QuetzalNocturno/tamalio/main/src/tamalio/recursos/esquemas/fuentes.schema.json",
  "version": 1,                      // Obligatorio.
  "nombre": "Mi lote",               // Opcional, informativo.
  "predeterminados": {               // Se aplican a quien no los defina.
    "formato": "flac",
    "metadatos": { "generos": ["Electronic"] }
  },
  "fuentes": [
    "https://music.youtube.com/watch?v=FB9u24ZpDek",   // Forma corta.
    {                                                  // Forma con opciones.
      "url": "https://ghostdata.bandcamp.com/album/symphony-of-the-shepherdess",
      "formato": "opus",
      "comentario": "Se ve en «tamalio cola»",
      "metadatos": { "generos": ["Aether Pop"], "anio": 2022 }
    },
    { "url": "https://artista.com/album/x", "plataforma": "bandcamp" }, // Dominio propio.
    { "url": "https://soundcloud.com/x/y", "omitir": true },           // Desactivada.
  ],
}
```

### Propiedades de cada fuente

| Propiedad | Tipo | Descripción |
|-----------|------|-------------|
| `url` | texto | **Obligatoria.** Pista, álbum, lista o *set*. |
| `plataforma` | `youtube` · `youtube_music` · `soundcloud` · `bandcamp` | Fuerza la plataforma (dominios propios de Bandcamp). |
| `formato` | `original` · `flac` · `alac` · `wav` · `mp3` · `opus` · `aac` · `vorbis` | Formato de salida de esta fuente. |
| `metadatos` | objeto | Sobrescribe lo extraído (ver abajo). Se aplica a todas las pistas de la fuente. |
| `comentario` | texto | Nota libre. |
| `omitir` | booleano | `true` para ignorar la fuente sin borrarla. |

### Metadatos que se pueden sobrescribir

`titulo`, `album`, `artistas`, `artistas_album`, `generos` (texto o lista),
`anio`, `numero_pista`, `total_pistas`, `es_sencillo` y `caratula` (URL).

**Prioridad del formato:** el de la fuente → el de `predeterminados` → la opción
`-f` de la línea de comandos → `formato_salida` de `tamalio.toml`.

---

## 2. Fichero de fuentes (`.txt`)

Ejemplo: [`ejemplos/fuentes.txt`](../ejemplos/fuentes.txt).

```text
# Comentario de línea completa
https://music.youtube.com/watch?v=FB9u24ZpDek
https://soundcloud.com/klaypex/sets/loosedirt   # comentario al final
```

- Una URL por línea; las líneas vacías se ignoran.
- `#` al inicio o después de un espacio inicia un comentario.
- Las URL repetidas (incluso escritas distinto, como `youtu.be/X` y
  `music.youtube.com/watch?v=X`) se cargan una sola vez.

---

## 3. Catálogo exportable (`.jsonc`)

Lo genera `tamalio catalogo exportar mi-catalogo.jsonc` y lo lee
`tamalio catalogo importar mi-catalogo.jsonc [--descargar]`. Ejemplo:
[`ejemplos/catalogo.jsonc`](../ejemplos/catalogo.jsonc).

```jsonc
// Catálogo musical exportado por Tamalio 0.1.0.
{
  "$schema": "https://raw.githubusercontent.com/QuetzalNocturno/tamalio/main/src/tamalio/recursos/esquemas/catalogo.schema.json",
  "version": 1,
  "aplicacion": { "nombre": "Tamalio", "version": "0.1.0" },
  "exportado_en": "2026-11-17T22:28:00-06:00",
  "usuario": "quetzal",
  "equipo": "escritorio",
  "total": 1,
  "pistas": [
    {
      "plataforma": "bandcamp",
      "id_externo": "4125386728",
      "url": "https://ghostdata.bandcamp.com/track/beyond-eternity-feat-skye-light-2",
      "titulo": "Beyond Eternity (feat. Skye Light)",
      "album": "Symphony of the Shepherdess",
      "artistas": ["GHOST DATA", "Skye Light"],
      "artistas_album": ["GHOST DATA"],
      "numero_pista": 1, "total_pistas": 15,
      "generos": ["Aether Pop", "Electronic", "Dreamsynth"],
      "anio": 2022, "duracion": 265.333, "es_sencillo": false,
      "caratula": "https://f4.bcbits.com/img/a3054183310_0.jpg",
      "formato": "original",
      "ruta_relativa": "Bandcamp/GHOST DATA/Symphony of the Shepherdess (2022)/01 - Beyond Eternity (feat. Skye Light).mp3"
    }
  ]
}
```

- **No contiene audio ni cookies**, solo metadatos y enlaces.
- `ruta_relativa` es relativa a `<carpeta de música>/<usuario>` y usa `/`
  como separador en todos los sistemas, para que el catálogo sea portable.
- Al importar, las pistas cuyo fichero ya existe se **vinculan**; las demás se
  pueden descargar con `--descargar`, forzando sus metadatos originales para que
  queden idénticas a las del otro equipo.

---

## 4. Metadatos escritos en cada fichero de audio

| Dato | FLAC / Opus / Vorbis | MP3 / WAV (ID3v2.4) | M4A (AAC/ALAC) |
|------|----------------------|---------------------|----------------|
| Nombre de la canción | `TITLE` | `TIT2` | `©nam` |
| Álbum | `ALBUM` | `TALB` | `©alb` |
| Artista(s) de la canción | `ARTIST` («A, B, C») y `ARTISTS` (lista) | `TPE1` («A, B, C») | `©ART` («A, B, C») |
| Artista(s) del álbum | `ALBUMARTIST` («A, B») | `TPE2` («A, B») | `aART` («A, B») |
| Número de pista / total | `TRACKNUMBER`, `TRACKTOTAL`, `TOTALTRACKS` | `TRCK` («n/total») | `trkn` |
| Género(s) | `GENRE` (multivalor) | `TCON` | `©gen` |
| Año | `DATE` | `TDRC` | `©day` |
| Carátula | `PICTURE` (FLAC) / `METADATA_BLOCK_PICTURE` (Ogg) | `APIC` (portada frontal) | `covr` |
| Origen | `TAMALIO_PLATAFORMA`, `TAMALIO_ID`, `TAMALIO_URL` | `TXXX:TAMALIO_*` | `----:com.apple.iTunes:TAMALIO_*` |

Varios artistas se escriben en un solo texto separado por **comas**
(«GHOST DATA, Skye Light»). Si se guardaran como valores múltiples, muchos
reproductores los mostrarían unidos con «/». En FLAC/Opus/Vorbis la etiqueta
`ARTISTS` conserva además la lista por separado.

## 5. Reglas de extracción por plataforma

Derivadas de las respuestas reales de `yt-dlp` incluidas en `tests/fixtures/`.

| Situación | Regla |
|-----------|-------|
| YouTube «Topic» (`Provided to YouTube by…`) | Usa `track`, `artists` y `album`. Los artistas repetidos se eliminan. |
| YouTube video oficial sin metadatos | El artista sale del prefijo «Artista - »; se quitan «(Official Music Video)», «[Lyric Video]», «(Visualizer)»… |
| `release_year` absurdo (p. ej. 2839 por «℗ 2839655 Records») | Se descarta; se usa `release_date`, el año más común del álbum o la fecha de subida. |
| Álbum de YouTube Music (`OLAK5uy_…`) | Carátula = objeto **penúltimo** de `thumbnails` en la raíz (al nivel de `entries`); el último queda de respaldo. |
| Pista suelta de YouTube | Miniatura de mayor preferencia, recortada al centro en 1:1. |
| SoundCloud «Artista - Título» | Se quita el prefijo si coincide con `artists`. El `uploader` no se usa como artista si hay `artists`. |
| SoundCloud *set* | Todas las pistas comparten la carátula `original` del *set*; número = posición. |
| Bandcamp `tags` | Solo las etiquetas en minúsculas son géneros; la ubicación («Houston») y los sellos («Ed Banger Records») se descartan. |
| Bandcamp con varios artistas en un texto | «A, B, C & D & the E» → «A», «B», «C», «D & the E» (un «&» seguido de artículo no separa). |
| Bandcamp carátula `…_5.jpg` | Se pide `…_0.jpg` (original), con `…_10.jpg` (1200 px) de respaldo. |
| Invitados «feat./ft.» | El título se normaliza a «Canción (feat. X, Y)» y X, Y se agregan a los artistas. |
| Pista sin álbum | Álbum = título (convención de *singles*) y se guarda en la carpeta «Sencillos». |
