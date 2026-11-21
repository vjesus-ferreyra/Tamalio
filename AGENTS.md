# AGENTS.md — Guía para agentes de código en Tamalio

Instrucciones para cualquier asistente o agente de IA (Claude Code, Codex,
Cursor, Zed AI, Copilot…) que trabaje en este repositorio. Las personas que
contribuyen también pueden usarla como referencia rápida.

> **Idioma:** todo el proyecto está en **español**: código (clases, métodos,
> variables), documentación, *docstrings*, mensajes al usuario, commits y
> respuestas. Mantén ese idioma.

---

## 1. Qué es Tamalio

Aplicación de **línea de comandos** que extrae música en la mayor calidad
disponible (Hi-Fi) desde **YouTube, YouTube Music, SoundCloud y Bandcamp**, la
etiqueta (título, álbum, artistas, artistas del álbum, número de pista,
géneros, año y carátula en alta resolución) y la organiza en un **catálogo
personal** guardado en PostgreSQL.

- Autor: Víctor Jesús Torres Ferreyra (*Quetzal Nocturno*).
- Licencia: **GPL-3.0-or-later** (ver `LICENSE`).
- Uso: personal y no comercial.
- Documentación de usuario: `README.md`. Arquitectura y diagramas Mermaid:
  `docs/arquitectura.md`. Formatos de ficheros y reglas de metadatos:
  `docs/formatos.md`.

## 2. Pila tecnológica

| Pieza | Uso |
|-------|-----|
| Python **≥ 3.15** | Se permiten las novedades del lenguaje (`type X = …`, genéricos `def f[T]()`, etc.). |
| `uv` | Entornos, dependencias, construcción (`uv_build`). |
| `yt-dlp[default,curl-cffi]` | Extracción y descarga; `curl_cffi` para suplantación de navegador. |
| QuickJS (`qjs`) | Intérprete JS de yt-dlp (en lugar de Deno). |
| FFmpeg + ffprobe | Conversión de audio y procesamiento de carátulas. |
| PostgreSQL + `psycopg` 3 | Catálogo, cola de descargas, sesiones. |
| `mutagen` | Etiquetas y carátulas en los ficheros. |
| `requests` | Descarga de carátulas. |
| `pytest` | Pruebas. |
| **Ruff** | Linter y formateador (única herramienta de calidad del proyecto). |

## 3. Comandos esenciales

```bash
uv sync                               # Instala todo (incluye pytest y ruff)
uv run tamalio --ayuda                # Ayuda de la CLI
uv run tamalio doctor                 # Verifica FFmpeg, QuickJS, PostgreSQL…
uv run tamalio bd iniciar             # Crea/actualiza las tablas
uv run tamalio --debug descargar URL  # Ejecuta mostrando la salida de cada parte

uv run ruff check .                   # Linter
uv run ruff check --fix .             # Correcciones automáticas
uv run ruff format .                  # Formato
uv run pytest -q                      # Pruebas (las de PostgreSQL se omiten sin TAMALIO_BD_PRUEBAS)
TAMALIO_BD_PRUEBAS=postgresql://tamalio:CLAVE@localhost:5432/tamalio_pruebas uv run pytest -q
```

**Antes de dar por terminado un cambio**, los tres deben pasar limpios:
`ruff check .`, `ruff format --check .` y `pytest -q`.

La verificación de tipos la hace el editor (Zed usa basedpyright en modo
`standard`). El código actual tiene **0 errores de tipos**; no introduzcas
nuevos (ver §8). No agregues basedpyright ni mypy como dependencia.

## 4. Arquitectura (MVC)

```text
src/tamalio/
├── __main__.py / aplicacion.py  Punto de entrada y *composition root* (único lugar que crea clases concretas)
├── configuracion/               Configuracion (tamalio.toml + TAMALIO_*) y RutasSistema (carpetas por SO)
├── modelos/                     MODELO: entidades y enumeraciones (Pista, Fuente, TareaDescarga, FormatoAudio…)
├── interfaces/                  Contratos abstractos (Extractor, Vista, ClienteMedios, Repositorio*…)
├── extractores/                 Normalización de metadatos por plataforma (Template Method + Factory)
├── servicios/                   Lógica de negocio: GestorDescargas, ClienteYtDlp, ConversorAudio, EtiquetadorAudio…
├── repositorios/                Persistencia PostgreSQL (ConexionPostgres + repositorios)
├── controladores/               CONTROLADOR: un controlador por grupo de comandos
├── vistas/                      VISTA: VistaConsola, BarraProgreso, AnalizadorArgumentos, ParserEspanol…
└── recursos/                    esquemas/*.schema.json (fuentes, catálogo) y sql/NNN_*.sql (migraciones)
```

Reglas que **no** se rompen:

1. **Una clase, entidad, interfaz, clase abstracta, vista o controlador por
   fichero.** Si necesitas un `dataclass` o `Enum` auxiliar, va en su propio
   fichero (normalmente en `modelos/`).
2. **El modelo nunca importa de `vistas/` ni de `controladores/`.** El modelo
   avisa a la vista a través de `ObservadorDescargas` (patrón *Observer*).
3. **Inyección de dependencias por constructor.** Los servicios reciben sus
   colaboradores; solo `aplicacion.py` conoce las clases concretas.
4. **Dependencias hacia interfaces**, no hacia implementaciones (p. ej.
   `GestorDescargas` depende de `ClienteMedios`, no de `ClienteYtDlp`).
5. Nombres de ficheros en `snake_case` español; clases en `PascalCase`
   español (`extractor_bandcamp.py` → `ExtractorBandcamp`).

## 5. Estilo de código y documentación

- Cada fichero `.py` empieza con el encabezado de licencia y luego el
  *docstring* del módulo:

  ```python
  # SPDX-License-Identifier: GPL-3.0-or-later
  # Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
  # Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

  """Descripción breve del módulo."""
  ```

- *Docstrings* en español (estilo Google: `Args:`, `Returns:`, `Raises:`,
  `Attributes:`) en clases y métodos públicos; comentarios que expliquen el
  **porqué**, no el qué.
- Anotaciones de tipo en todo el código. Línea máxima: 120 (la controla Ruff).
- Errores para el usuario: excepciones que heredan de `ErrorTamalio`
  (`excepciones/`), con `mensaje` y `sugerencia` en español.
- Registro con `logging.getLogger(__name__)`. Lo útil para diagnosticar va en
  `registro.debug(...)`: aparece con `--debug`. No uses `print` fuera de la vista.
- Configuración de Ruff: `[tool.ruff]` en `pyproject.toml`. Zed la usa vía
  `.zed/settings.json` (formatea y ordena importaciones al guardar).

## 6. Pruebas

- `tests/` es un **paquete**: importa con ruta absoluta
  (`from tests.dobles.repositorio_tareas_memoria import RepositorioTareasMemoria`,
  `from tests.conftest import RAIZ_PROYECTO`).
- `tests/dobles/`: implementaciones en memoria de las interfaces. Úsalas en
  lugar de PostgreSQL o de la red.
- `tests/fixtures/*.json`: respuestas **reales** de yt-dlp (reducidas, sin URL
  firmadas). Para casos nuevos, genera el JSON con `tamalio --debug …` (se
  guarda en `~/.local/state/tamalio/depuracion/`) y quita `formats`, cabeceras
  y URL con tokens antes de agregarlo.
- Marcadores: `@pytest.mark.ffmpeg` (se omite sin FFmpeg) y
  `@pytest.mark.postgres` (requiere `TAMALIO_BD_PRUEBAS`, base **desechable**:
  las pruebas vacían sus tablas; nunca apuntes a la base real).
- Las pruebas **no** acceden a internet. Esperas: inyecta `reloj`/`dormir`
  simulados en `TemporizadorHumano`.
- Todo error corregido lleva una prueba que lo reproduce.

## 7. Cómo extender

- **Nueva plataforma:** agrega el valor en `modelos/plataforma.py`, la
  detección de URL en `servicios/detector_plataforma.py`, un
  `extractores/extractor_<plataforma>.py` que herede de `ExtractorBase`
  (sobrescribe solo los «ganchos»), regístralo en `fabrica_extractores.py`,
  actualiza los `CHECK` de `recursos/sql/` con una **nueva** migración y los
  `enum` de los esquemas JSON. Agrega fixtures y pruebas.
- **Nuevo comando:** argumentos en `vistas/analizador_argumentos.py`, despacho
  en `aplicacion.py`, lógica en un controlador; documenta en `README.md`.
- **Cambios de base de datos:** nunca edites una migración publicada; crea
  `recursos/sql/00N_descripcion.sql` (idempotente). `tamalio bd iniciar` las aplica en orden.
- **Formatos de ficheros (`.jsonc`):** si cambias el esquema, actualiza
  `recursos/esquemas/*.schema.json`, `ejemplos/` y `docs/formatos.md`; las
  pruebas validan los ejemplos contra su esquema.

## 8. Lecciones aprendidas (no repetir errores)

- **Suplantación de navegador:** `[red] suplantar_navegador = "auto"` (no
  forzar `impersonate` globalmente). Forzarlo rompe la estrategia del
  extractor de Bandcamp y provoca «Client Challenge».
- **psycopg 3.3 y tipos:** conecta con `psycopg.Connection[DictRow].connect(...)`.
  Las consultas deben ser `LiteralString` o `psycopg.sql.SQL/Composed`: compón
  SQL dinámico con `sql.SQL(...).format(sql.Identifier(...))`, nunca con
  f-strings sobre texto variable. Todo pasa por `ConexionPostgres.ejecutar/una/todas`
  (que además registra el SQL en `--debug`).
- **Contraseña de la BD:** no hay conexión ni contraseña predeterminada
  (`Configuracion.bd_url` es `None`). La aplicación abre PostgreSQL con
  `Configuracion.url_base_datos()`, que exige una contraseña propia (en la URL o
  en `PGPASSWORD`) y rechaza las de `CONTRASENAS_BD_PROHIBIDAS`. No vuelvas a
  escribir credenciales reales ni de ejemplo como `tamalio:tamalio` en el código
  o la documentación; usa `TU_CONTRASEÑA`.
- **Búsquedas `LIKE`/`ILIKE`:** el texto del usuario se escapa con
  `RepositorioCatalogoPostgres._patron_contiene` y la consulta lleva
  `ESCAPE '\'`. Sin eso, `%` y `_` funcionan como comodines (buscar «%»
  devolvía todo el catálogo).
- **Títulos de Bandcamp:** `track` a veces trae el número de pista pegado
  («01 - Opening Credits», «06 -X-CaliBR8»). `ExtractorBandcamp._titulo_crudo`
  lo quita solo si coincide con `track_number` o tiene ceros a la izquierda,
  para no estropear títulos como «100 - Gecs».
- **Carátula de álbumes de Bandcamp:** todas las pistas reciben la misma, la
  que más se repite (se compara el identificador `a123…` de la imagen, no la
  URL); en un empate, la de enlace exacto más repetido entre las empatadas.
  Si todas son distintas o los enlaces también empatan,
  `LectorCaratulaBandcamp` (Playwright) la lee de
  `#tralbumArt` en la página del álbum. Ese lector nunca lanza excepciones y en
  las pruebas se sustituye por `tests/dobles/lector_caratula_fijo.py`.
- **yt-dlp y tipos:** sus `TypedDict` (`_Params`, `_InfoDict`) son parciales;
  adapta con `cast(Any, ...)` en el límite, no en todo el código.
- **Cancelación:** yt-dlp no llama *hooks* mientras espera la red. Por eso
  `ClienteYtDlp._en_segundo_plano` ejecuta yt-dlp en un hilo y el principal
  vigila `ControlEjecucion` cada 0.1 s. Cualquier operación nueva que pueda
  bloquear debe aceptar `punto_control` y llamarlo con frecuencia.
- **Artistas:** separa con `ExtractorBase._dividir_artistas` (comas, `&`, `x`,
  `×`; un «&» seguido de artículo —«& the»— **no** separa). Nunca guardes
  artistas como valores múltiples en `ARTIST`/`TPE1`/`©ART`: se escriben como
  **un texto separado por comas** («A, B, C»), porque los reproductores
  muestran los valores múltiples con «/».
- **Bandcamp `tags`:** solo minúsculas son géneros; se descartan ubicaciones y
  sellos («… records»).
- **YouTube:** la carátula de un álbum es el **penúltimo** elemento de
  `thumbnails` en la raíz; descarta años imposibles (p. ej. `release_year` 2839).
- **Fichero ya descargado:** el catálogo omite pistas cuyo fichero existe; para
  regenerar metadatos de una pista hay que borrar el fichero y descargar de nuevo.

## 9. Flujo de trabajo y entrega de cambios

- El mantenedor recibe los cambios como **parches** (`.patch`) que aplica con
  `git apply`. Cada parche es **incremental** respecto al anterior y se
  comprueba con `git apply --check` sobre una copia limpia antes de entregarlo.
- **Evita tocar `pyproject.toml` y `uv.lock`** salvo que el cambio lo exija: la
  copia local del mantenedor puede diferir y el parche no encajaría. Si es
  necesario, dilo explícitamente y mantén el cambio mínimo.
- Un commit por parche, mensaje en español en imperativo
  (`Separa artistas de Bandcamp unidos con «&»`).
- Actualiza `README.md` y `docs/` cuando cambie el comportamiento visible.

## 10. Seguridad y datos personales

- Nunca leas, imprimas ni subas ficheros de **cookies** (`*cookies*.txt`),
  `.env` ni `tamalio.toml` personales; ya están en `.gitignore`. Tamalio solo
  guarda la **ruta** de las cookies, nunca su contenido.
- No subas audio, carátulas descargadas ni catálogos exportados del usuario.
- `tamalio bd borrar` es irreversible y exige escribir `BORRAR`; no lo
  ejecutes sin que el usuario lo pida.
