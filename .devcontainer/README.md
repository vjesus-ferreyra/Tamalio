# Entorno de desarrollo de Tamalio

Este directorio define un entorno de desarrollo completo para Tamalio. Sirve
para **Zed**, **GitHub Codespaces** y **VS Code**, y siempre levanta los mismos
servicios: el contenedor de trabajo y PostgreSQL.

## Zed

Necesitas Zed con soporte de Dev Containers (versión 0.218 o posterior).

### En tu equipo, con Docker

1. Instala Docker o Podman. Si usas Podman, añade `"use_podman": true` a tu
   `settings.json` de Zed.
2. Abre la carpeta del proyecto en Zed.
3. Cuando aparezca el aviso, pulsa **Open in Container**. Si no aparece, abre
   la paleta de comandos, ejecuta **Project: Open Remote** y elige **Connect
   Dev Container**.

Zed construye la imagen, levanta PostgreSQL, ejecuta `post-create.sh` y
reabre el proyecto dentro del contenedor. La terminal, las tareas y los
servidores de lenguaje (Ruff y basedpyright) corren dentro de él y usan
`.zed/settings.json` del proyecto.

Zed no reconstruye el contenedor cuando cambias algo en `.devcontainer/`.
Para aplicar los cambios, detén los contenedores (`docker compose -p <nombre>
down` o desde Docker Desktop) y vuelve a abrir el proyecto.

### Con GitHub Codespaces, por SSH

Zed no abre Codespaces directamente, pero sí se conecta a un codespace como a
cualquier servidor remoto. El contenedor ya incluye el servidor SSH que hace
falta.

1. Crea el codespace desde GitHub (**Code → Codespaces → Create codespace on
   main**) o con `gh codespace create`.
2. En tu equipo, genera la configuración de SSH una vez:

   ```bash
   gh codespace ssh --config > ~/.ssh/codespaces
   printf 'Match all\nInclude ~/.ssh/codespaces\n' >> ~/.ssh/config
   ```

   Vuelve a ejecutar la primera línea cada vez que crees un codespace nuevo.
3. Busca el nombre del host con `grep ^Host ~/.ssh/codespaces`.
4. En Zed, abre **Project: Open Remote → Connect New Server**, escribe
   `ssh <host>` y abre la carpeta `/workspaces/tamalio`.

En las sesiones SSH las variables de `entorno.env` y el `PATH` del entorno
`.venv` se cargan desde `/etc/profile.d/tamalio.sh`, que genera
`post-create.sh`.

## VS Code

- **Codespaces:** crea el codespace y ábrelo en el navegador o en VS Code.
- **En local:** con la extensión Dev Containers, elige **Dev Containers:
  Reopen in Container**.

Se instalan las extensiones de Python, Ruff, TOML y Mermaid. Ruff formatea y
ordena las importaciones al guardar, y Pylance revisa los tipos en modo
`standard`, igual que Zed.

## Qué incluye

| Pieza | Detalle |
| --- | --- |
| Sistema | Ubuntu 24.04 (`mcr.microsoft.com/devcontainers/base`) |
| Python | 3.15, instalado por uv según `pyproject.toml` |
| Herramientas | uv, FFmpeg, QuickJS-ng (`qjs`), `psql`, GitHub CLI, servidor SSH |
| Base de datos | PostgreSQL 18 en `localhost:5432` |
| Extensiones de Zed | TOML, SQL, Dockerfile, Docker Compose y Mermaid |

La primera vez tarda unos minutos: `post-create.sh` instala Python 3.15 y las
dependencias con `uv sync`. Después, `tamalio`, `ruff` y `pytest` funcionan
directamente en la terminal.

## PostgreSQL

| Dato | Valor |
| --- | --- |
| Servidor | `localhost:5432` |
| Usuario y contraseña | `tamalio` / `tamalio` |
| Base del catálogo | `tamalio` |
| Base de pruebas | `tamalio_pruebas` |

Las variables `PGHOST`, `PGUSER`, `PGPASSWORD` y `PGDATABASE` ya están
definidas en `entorno.env`, así que `psql` se conecta sin argumentos. Si tu
configuración de Tamalio pide una cadena de conexión, usa
`postgresql://tamalio:tamalio@localhost:5432/tamalio`.

`TAMALIO_BD_PRUEBAS` también está definida, así que `pytest` ejecuta las
pruebas de PostgreSQL en lugar de omitirlas.

Los datos viven en el volumen `datos-postgres` y sobreviven a reinicios del
contenedor. Para empezar de cero, borra el volumen o reconstruye el
contenedor.

## Avisos

- **Bloqueos de YouTube:** las IP de los centros de datos de GitHub suelen
  recibir el aviso de «inicia sesión para confirmar que no eres un bot».
  Si ocurre, usa el flujo de cookies de Tamalio. No subas el fichero de
  cookies al repositorio. En tu equipo, con Zed y Docker, este problema no
  se presenta.
- **Dónde queda la música:** se guarda en `~/Música/` dentro del contenedor,
  fuera de la carpeta del proyecto. Para pasarla a tu equipo desde un
  codespace, usa `gh codespace cp -r remote:Música .` (las rutas `remote:`
  parten de la carpeta personal).
- **Extensiones de Zed:** las que declara `devcontainer.json` también quedan
  instaladas en tu Zed local.
- **Horas de Codespaces:** el plan gratuito tiene un límite mensual. Detén el
  codespace cuando no lo uses.
