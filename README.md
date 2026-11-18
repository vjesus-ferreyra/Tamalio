# 🫔 Tamalio — Extractor de Música Hi-Fi

**Tamalio** es una aplicación de línea de comandos para extraer música en la
mayor calidad y fidelidad disponibles (**Hi-Fi**) desde YouTube, YouTube Music,
SoundCloud y Bandcamp, y organizarla en un **catálogo personal** con metadatos
completos y carátulas en alta resolución.

Acepta enlaces (**fuentes**) de forma individual o agrupados en un fichero para
descargarlos en masa, y permite **pausar, reanudar, reintentar y cancelar** las
descargas cuando quieras, incluso desde otra terminal.

| | |
|---|---|
| **Autor** | Víctor Jesús Torres Ferreyra — *Quetzal Nocturno* |
| **Versión** | 0.1.0 |
| **Python** | 3.15 o superior |
| **Paradigma** | Programación orientada a objetos, patrón MVC |
| **Uso** | Personal y no comercial |

---

## Contenido

- [Objetivos](#objetivos)
- [Características](#características)
- [Tecnologías](#tecnologías)
- [Instalación](#instalación)
- [Uso](#uso)
- [Construcción para la máquina anfitrión](#construcción-para-la-máquina-anfitrión)
- [Desarrollo](#desarrollo)
- [Calidad de audio: qué significa «Hi-Fi» aquí](#calidad-de-audio-qué-significa-hi-fi-aquí)
- [Riesgos y cómo se mitigan](#riesgos-y-cómo-se-mitigan)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Documentación adicional](#documentación-adicional)

---

## Objetivos

- Descargar y extraer música y audio desde las **plataformas fuente** soportadas.
- Tener un **catálogo personal** propio, ahorrar en servicios de *streaming* y
  controlar por completo lo que se escucha.
- **Exportar e importar** el catálogo entre equipos con un solo fichero.
- **Reanudar, reintentar, pausar y cancelar** descargas a voluntad.
- **Convertir** la música a varios formatos de audio.

## Características

- 🎧 **Mejor audio disponible** de cada plataforma; por defecto se guarda **sin
  recodificar** (formato `original`), y se puede convertir a FLAC, ALAC, WAV,
  MP3, Opus, AAC u Ogg Vorbis.
- 🏷️ **Metadatos completos** en el fichero: nombre de la canción, álbum,
  artista(s) de la canción, artista(s) del álbum, número de pista, género(s),
  año y **carátula en alta resolución** incrustada.
- 🧠 **Limpieza inteligente** de metadatos por plataforma: quita «Artista - » y
  «(Official Music Video)» de los títulos, detecta invitados «feat.», descarta
  años absurdos, separa géneros de ubicaciones en Bandcamp, etc.
- 📂 **Biblioteca ordenada**: `~/Música/<usuario>/<Plataforma>/<Artista>/<Álbum (Año)>/01 - Canción.ext`.
- 📋 **Descarga en masa** desde ficheros **JSONC** (con `$schema` y comentarios)
  o **texto plano**.
- ⏯️ **Control total**: teclas `p` (pausa), `s` (saltar), `c` (cancelar), `q`
  (salir); `tamalio pausar/cancelar` desde otra terminal; cola persistente en
  PostgreSQL.
- 🛡️ **Anti-bloqueo**: suplantación de navegador con `curl_cffi`, esperas
  aleatorias «humanas», *backoff* exponencial y solicitud de cookies de sesión
  cuando la plataforma detecta un bot.
- 📊 **Barras de progreso en vivo** con velocidad, tamaño, ETA y estado del lote.
- 🔁 **Catálogo portable**: exporta en un equipo, importa en otro y descarga solo
  lo que falte.

### Plataformas soportadas

| Plataforma | Pistas | Álbumes / listas | Notas |
|------------|:------:|:----------------:|-------|
| YouTube | ✅ | ✅ | Incluye canales y listas. |
| YouTube Music | ✅ | ✅ | Misma plataforma que YouTube: el ID de `watch?v=` es idéntico; solo cambia el dominio. |
| SoundCloud | ✅ | ✅ (*sets*) | Enlaces cortos `on.soundcloud.com` incluidos. |
| Bandcamp | ✅ | ✅ | Dominios propios con `--plataforma bandcamp`. |

---

## Tecnologías

### Necesarias para el funcionamiento

| Tecnología | Uso en Tamalio |
|------------|----------------|
| **Python ≥ 3.15** | Lenguaje de la aplicación. |
| **FFmpeg** (con `ffprobe`) | Conversión de audio y procesamiento de carátulas. |
| **QuickJS** (o QuickJS-ng) | Intérprete de JavaScript para los retos de YouTube, en lugar de Deno. |
| **PostgreSQL** | Catálogo, cola de descargas y registro de sesiones. |
| **Git** | Obtener y actualizar el código. |

### Módulos de Python

| Módulo | Uso |
|--------|-----|
| `yt_dlp` (con extras `default` y `curl-cffi`) | Extracción y descarga. Incluye `yt-dlp-ejs` y `curl_cffi`. |
| `psycopg` 3 | Acceso a PostgreSQL. |
| `requests` | Descarga de carátulas. |
| `mutagen` | Escritura de metadatos y carátulas. |
| `pytest` | Pruebas automatizadas. |

### Herramientas de desarrollo

| Herramienta | Uso |
|-------------|-----|
| **Git** | Control de versiones. |
| **uv** | Gestor de paquetes, entornos y versiones de Python; construcción del paquete. |
| **Ruff** | Linter y formateador de código. |

---

## Instalación

### 1. Instalar las herramientas del sistema

<details open>
<summary><b>Linux (Debian/Ubuntu)</b></summary>

```bash
sudo apt update
sudo apt install git ffmpeg postgresql
curl -LsSf https://astral.sh/uv/install.sh | sh
```

QuickJS: los repositorios de algunas distribuciones traen versiones antiguas
(yt-dlp requiere QuickJS ≥ 2023-12-09). Lo más simple es usar el binario de
**QuickJS-ng** de su página de *releases* en GitHub
(<https://github.com/quickjs-ng/quickjs/releases>):

```bash
# Descarga el binario de Linux para tu arquitectura desde la página de releases,
# luego (ajusta el nombre del fichero descargado):
chmod +x ./qjs-linux-*
sudo mv ./qjs-linux-* /usr/local/bin/qjs
qjs --help | head -1        # Debe decir «QuickJS-ng version …»
```

En Arch Linux: `sudo pacman -S git ffmpeg postgresql quickjs uv`.
</details>

<details>
<summary><b>macOS (Homebrew)</b></summary>

```bash
brew install git ffmpeg uv quickjs-ng postgresql@18
brew services start postgresql@18
```
</details>

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
winget install Git.Git
winget install Gyan.FFmpeg
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

- **PostgreSQL**: instala la versión actual con el instalador oficial de
  <https://www.postgresql.org/download/windows/>.
- **QuickJS-ng**: descarga el ejecutable de Windows desde
  <https://github.com/quickjs-ng/quickjs/releases>, renómbralo a `qjs.exe` y
  colócalo en una carpeta del `PATH` (o indica su ruta en `[javascript] ruta`
  de la configuración).
</details>

> Python 3.15 **no** necesita instalarse a mano: `uv` lo descarga automáticamente
> gracias al fichero `.python-version` (o con `uv python install 3.15`).

### 2. Obtener el código e instalar dependencias

```bash
git clone https://github.com/QuetzalNocturno/tamalio.git
cd tamalio
uv sync            # Crea .venv con Python 3.15 e instala todo (incluye pytest y ruff)
```

### 3. Preparar PostgreSQL

Crea un usuario y una base de datos (ajusta la contraseña a tu gusto):

```bash
# Linux
sudo -u postgres psql -c "CREATE USER tamalio WITH PASSWORD 'tamalio';"
sudo -u postgres createdb -O tamalio tamalio

# macOS (Homebrew: tu usuario ya es superusuario)
createuser -P tamalio && createdb -O tamalio tamalio

# Windows (desde la carpeta bin de PostgreSQL)
psql -U postgres -c "CREATE USER tamalio WITH PASSWORD 'tamalio';"
createdb -U postgres -O tamalio tamalio
```

Crea las tablas (el comando es idempotente):

```bash
uv run tamalio bd iniciar
```

### 4. Configurar (opcional)

Copia [`config/tamalio.ejemplo.toml`](config/tamalio.ejemplo.toml) a tu carpeta
de configuración y ajústalo:

| Sistema | Ruta |
|---------|------|
| Linux | `~/.config/tamalio/tamalio.toml` |
| macOS | `~/Library/Application Support/tamalio/tamalio.toml` |
| Windows | `%APPDATA%\tamalio\tamalio.toml` |

También puedes usar variables de entorno (ver [`.env.ejemplo`](.env.ejemplo)):
`TAMALIO_BD_URL`, `TAMALIO_DESTINO`, `TAMALIO_USUARIO`, `TAMALIO_CONFIG`.

### 5. Verificar

```bash
uv run tamalio doctor
```

Revisa Python, FFmpeg, QuickJS, `yt-dlp`, `yt-dlp-ejs`, `curl_cffi`, `mutagen`,
`requests`, `psycopg`, la conexión a PostgreSQL y la carpeta de destino.

---

## Uso

> Dentro del repositorio usa `uv run tamalio …`. Si lo instalaste como
> herramienta (ver [Construcción](#construcción-para-la-máquina-anfitrión)),
> basta con `tamalio …`.

### Descargar

```bash
# Una pista (YouTube Music y YouTube son equivalentes)
tamalio descargar https://music.youtube.com/watch?v=FB9u24ZpDek

# Un álbum completo en FLAC
tamalio descargar -f flac https://ghostdata.bandcamp.com/album/symphony-of-the-shepherdess

# Varias fuentes a la vez
tamalio descargar https://soundcloud.com/klaypex/sets/loosedirt https://youtu.be/FB9u24ZpDek

# En masa desde un fichero (JSONC o texto)
tamalio descargar -a ejemplos/fuentes.jsonc
tamalio descargar -a ejemplos/fuentes.txt -f opus

# Solo encolar (procesar después con «tamalio reanudar»)
tamalio descargar -a mis-fuentes.jsonc --solo-encolar

# Otra carpeta de música y un dominio propio de Bandcamp
tamalio descargar -d /mnt/musica --plataforma bandcamp https://musica.artista.com/album/x
```

Así se ve una descarga:

```text
  🫔 Tamalio 0.1.0  · Extractor de música Hi-Fi
  • 2 fuente(s) leídas de «fuentes.jsonc».

  ▶ [1/2] Bandcamp · https://ghostdata.bandcamp.com/album/symphony-of-the-shepherdess
    Symphony of the Shepherdess · 15 pista(s)
    ✔ 01 Beyond Eternity (feat. Skye Light) — GHOST DATA        mp3 · 8.4 MB
    ✔ 02 Adagio For Souls (feat. COR!S & dreamiecloud) — GHOST… mp3 · 8.3 MB
  ↓ 03/15  Healing Light (feat. Azuria Sky) — GHOST DATA
    Descargando    ━━━━━━━━━━━━━━━━━━━━╸━━━━━━━━━━━   62.0% · 4.3 MB / 6.9 MB · 1.2 MB/s · 0:02
  Lote ━━━━━━━━━━━━━━━━━━━━  0/2 · [p] pausa  [s] saltar  [c] cancelar  [q] salir
```

### Controles durante la descarga

| Tecla | Acción |
|-------|--------|
| `p` | Pausa / reanuda (el fichero parcial se conserva). |
| `s` | Salta la pista actual. |
| `c` | Cancela la tarea actual y sigue con la siguiente. |
| `q` o `Ctrl+C` | Sale; la tarea actual queda **pausada**. Un segundo `Ctrl+C` fuerza la salida. |

### Cola de descargas

```bash
tamalio cola                          # Todas las tareas
tamalio cola --estado fallida pausada # Filtrar por estado
tamalio reanudar                      # Pendientes y pausadas
tamalio reanudar 12 15                # Tareas concretas
tamalio reintentar                    # Fallidas (las pistas ya bajadas se omiten)
tamalio reintentar --incluir-canceladas
tamalio pausar 12                     # También funciona si se descarga en otra terminal
tamalio cancelar --todas
```

### Catálogo personal

```bash
tamalio catalogo listar
tamalio catalogo listar --plataforma bandcamp --buscar "ghost data"
tamalio catalogo exportar ~/mi-catalogo.jsonc
tamalio catalogo importar ~/mi-catalogo.jsonc              # Vincula lo que ya exista
tamalio catalogo importar ~/mi-catalogo.jsonc --descargar  # …y descarga lo que falte
```

### Convertir

```bash
tamalio convertir --todo -f flac                          # Todo el catálogo
tamalio convertir --plataforma youtube -f mp3 --conservar-original
tamalio convertir "~/Música/quetzal/Bandcamp/GHOST DATA" -f alac
```

### Sesiones (cookies)

Si una plataforma detecta un bot o exige iniciar sesión, Tamalio **te pedirá la
ruta del fichero de cookies** de esa plataforma, la recordará y reintentará.
También puedes registrarla antes:

```bash
tamalio sesion establecer youtube ~/cookies/youtube.txt
tamalio sesion listar
tamalio sesion quitar youtube
```

El fichero debe estar en **formato Netscape** (`cookies.txt`), por ejemplo
exportado con una extensión de navegador tipo «Get cookies.txt LOCALLY». Solo se
guarda su **ruta**, nunca su contenido.

### Carpeta de destino

Por defecto: `~/Música` en Linux y macOS, `~/Music` en Windows. Dentro se crea
una carpeta con tu nombre de usuario y tres carpetas hijas, una por plataforma:

```text
~/Música/quetzal/
├── YouTube/
│   └── K-DA/
│       └── FIRESTARTER (2026)/
│           ├── 01 - FIRESTARTER (feat. MIYEON and SOYEON of i-dle, Sophie Powers, Mimi Webb).opus
│           └── 04 - GIRLS.opus
├── SoundCloud/
│   ├── John Kenza/Sencillos/Nightmare.m4a
│   └── Klaypex/Loose Dirt (2011)/01 - Lights.m4a
└── Bandcamp/
    └── GHOST DATA/
        ├── Sencillos/Fluorite Fault.mp3
        └── Symphony of the Shepherdess (2022)/01 - Beyond Eternity (feat. Skye Light).mp3
```

> En macOS el sistema ya trae `~/Music` (Finder lo muestra como «Música»).
> Si prefieres usar esa carpeta, pon `carpeta_destino = "~/Music"` en la configuración.

### Formatos de ficheros de entrada

Los ficheros de fuentes y de catálogo son **JSONC** (JSON con comentarios) y
tienen su propio **`$schema`**, así tu editor los valida y autocompleta:

- [`fuentes.schema.json`](src/tamalio/recursos/esquemas/fuentes.schema.json) — ejemplo en [`ejemplos/fuentes.jsonc`](ejemplos/fuentes.jsonc)
- [`catalogo.schema.json`](src/tamalio/recursos/esquemas/catalogo.schema.json) — ejemplo en [`ejemplos/catalogo.jsonc`](ejemplos/catalogo.jsonc)
- Texto plano, una URL por línea con comentarios `#` — ejemplo en [`ejemplos/fuentes.txt`](ejemplos/fuentes.txt)

Detalles en [`docs/formatos.md`](docs/formatos.md).

---

## Construcción para la máquina anfitrión

Tamalio se empaqueta con el *backend* de construcción de **uv**. Construir en la
propia máquina garantiza que las dependencias con código nativo (`curl_cffi`,
`psycopg-binary`) correspondan a tu sistema operativo y arquitectura.

```bash
# 1) Construir el paquete (wheel + código fuente) en dist/
uv build

# 2) Instalar el comando «tamalio» de forma global para tu usuario
uv tool install dist/tamalio-0.1.0-py3-none-any.whl
#    (o directamente desde el repositorio:  uv tool install .)

# 3) Asegurar que la carpeta de herramientas de uv esté en el PATH (una sola vez)
uv tool update-shell

# 4) Usarlo desde cualquier carpeta
tamalio doctor
```

Actualizar y desinstalar:

```bash
git pull && uv tool install --reinstall .
uv tool uninstall tamalio
```

---

## Desarrollo

```bash
uv sync                         # Entorno de desarrollo (pytest y ruff incluidos)
uv run ruff check .             # Linter
uv run ruff check --fix .       # Corregir lo automático
uv run ruff format .            # Formatear
uv run pytest                   # Pruebas
```

Las pruebas usan las **respuestas reales de yt-dlp** de cada plataforma
(`tests/fixtures/`), FFmpeg real para conversión/etiquetado (se omiten si no está
instalado) y, opcionalmente, una base PostgreSQL **desechable**:

```bash
TAMALIO_BD_PRUEBAS=postgresql://tamalio:tamalio@localhost:5432/tamalio_pruebas uv run pytest
```

La integración continua (`.github/workflows/ci.yml`) ejecuta Ruff y todas las
pruebas con FFmpeg y PostgreSQL en cada *push*.

### Convenciones

- **POO bajo MVC**: cada clase, entidad, interfaz, clase abstracta, vista y
  controlador vive en **su propio fichero**.
- Documentación en **español** dentro de cada fichero, con *docstrings* en clases
  y métodos públicos.
- Dependencias inyectadas por constructor; `aplicacion.py` es el único lugar que
  crea las clases concretas.

---

## Calidad de audio: qué significa «Hi-Fi» aquí

Tamalio siempre pide **el mejor flujo de audio** que la plataforma entrega y, con
el formato `original`, lo guarda **bit a bit, sin recodificar**: no hay pérdida
adicional. Conviene saber qué entrega cada plataforma de forma pública:

| Plataforma | Audio típico | Notas |
|------------|--------------|-------|
| YouTube / YouTube Music | Opus ~130 kbps (o AAC ~128 kbps) | Con cookies de YouTube Premium suele estar disponible Opus de mayor tasa. |
| SoundCloud | AAC 160 kbps (HLS) | Depende de la pista. |
| Bandcamp | MP3 128 kbps (vista previa) | Las descargas FLAC de compras se obtienen desde tu cuenta de Bandcamp, no con yt-dlp. |

Convertir algo con pérdida a FLAC/ALAC/WAV **no recupera calidad**, pero evita
perder más si luego vas a editar o recodificar. Tamalio avisa cuando una
conversión recodifica con pérdida (por ejemplo Opus → MP3).

---

## Riesgos y cómo se mitigan

| Riesgo | Mitigación |
|--------|------------|
| **Detección de bots / *TLS fingerprinting*** | Suplantación de navegador con `curl_cffi` (`impersonate`), recomendada por la documentación de `yt-dlp`. Si `curl_cffi` no está disponible, se continúa sin ella y se avisa. |
| **HTTP 403 / límite de N peticiones por minuto** | Esperas **aleatorias** (azar del sistema operativo) entre pistas y entre peticiones, pausas largas periódicas y *backoff* exponencial con *jitter* ante un HTTP 429. |
| **Registro obligatorio o captcha** | Se pide al usuario la ubicación del fichero de **tokens de sesión** (cookies) de esa plataforma, se valida y se reintenta. |
| **Retos de JavaScript de YouTube** | Se usa el intérprete **QuickJS** (`js_runtimes = {"quickjs": …}`) en lugar de Deno. |
| **URLs de descarga caducadas** (tras una pausa larga) | Se vuelve a extraer la pista automáticamente una vez. |
| **Cortes de red o cierre inesperado** | Ficheros `.part` reanudables, cola persistente en PostgreSQL y `tamalio reanudar`. |
| **Legalidad** | Uso **personal y no comercial**. Respeta los términos de cada plataforma y los derechos de los artistas; si te gusta su música, apóyalos comprándola. |

---

## Estructura del proyecto

```text
tamalio/
├── .github/workflows/ci.yml        Integración continua (Ruff + pytest)
├── config/tamalio.ejemplo.toml     Configuración documentada
├── docs/
│   ├── arquitectura.md             Diagramas Mermaid (MVC, clases, secuencia, estados, ER…)
│   └── formatos.md                 Ficheros de fuentes, catálogo y metadatos
├── ejemplos/                       fuentes.jsonc · fuentes.txt · catalogo.jsonc
├── src/tamalio/
│   ├── __main__.py · aplicacion.py Punto de entrada y composición
│   ├── configuracion/              Configuración y rutas por sistema operativo
│   ├── controladores/              Controlador (MVC)
│   ├── excepciones/                Errores propios
│   ├── extractores/                Normalización de metadatos por plataforma
│   ├── interfaces/                 Clases abstractas (contratos)
│   ├── modelos/                    Entidades y enumeraciones (Modelo)
│   ├── recursos/esquemas/          $schema de fuentes y catálogo
│   ├── recursos/sql/               Migraciones de PostgreSQL
│   ├── repositorios/               Persistencia con psycopg 3
│   ├── servicios/                  yt-dlp, FFmpeg, mutagen, cola, anti-bloqueo…
│   └── vistas/                     Consola, barras de progreso, argumentos (Vista)
├── tests/                          pytest + fixtures reales de yt-dlp
├── .editorconfig · .gitattributes · .gitignore · .env.ejemplo · .python-version
├── pyproject.toml                  Proyecto, dependencias, Ruff y pytest
└── uv.lock                         Versiones exactas (instalación reproducible)
```

## Documentación adicional

- [`docs/arquitectura.md`](docs/arquitectura.md) — capas MVC, diagrama de clases,
  secuencia de descarga, estados de una tarea, modelo de datos, anti-bloqueo,
  pausa/cancelación e importación/exportación (todo en **Mermaid**).
- [`docs/formatos.md`](docs/formatos.md) — formatos de ficheros y reglas de metadatos.
- `tamalio --ayuda` y `tamalio COMANDO --ayuda` — ayuda en la terminal.

---

Hecho con 🌽 por **Quetzal Nocturno** · Uso personal y no comercial.
