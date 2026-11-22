#!/usr/bin/env bash
# Prepara el proyecto la primera vez que se crea el contenedor.
set -euo pipefail

proyecto="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$proyecto"

echo "» Instalando Python y las dependencias con uv…"
uv sync

echo "» Esperando a PostgreSQL…"
pg_isready --timeout=60

# Contraseña aleatoria que generó el servicio «db» (ver compose.yaml).
fichero_contrasena=/run/secretos-tamalio/contrasena-bd
if [ ! -s "$fichero_contrasena" ]; then
    echo "No se encontró la contraseña de PostgreSQL en $fichero_contrasena." >&2
    exit 1
fi
contrasena="$(cat "$fichero_contrasena")"

# Entorno de todas las terminales: lo cargan los shells de inicio de sesión
# (incluidas las sesiones SSH de Zed con Codespaces, que no heredan el entorno
# de Docker) y, gracias a /etc/bash.bashrc, también los interactivos.
# Contiene la contraseña, así que solo lo leen root y el usuario del contenedor.
echo "» Configurando el entorno de las terminales…"
sudo tee /etc/profile.d/tamalio.sh > /dev/null <<EOF
# Generado por .devcontainer/post-create.sh. No lo edites a mano.
set -a
. "$proyecto/.devcontainer/entorno.env"
PGPASSWORD=$contrasena
TAMALIO_BD_URL=postgresql://tamalio:$contrasena@localhost:5432/tamalio
# Base de las pruebas de integración; sin ella se omiten.
TAMALIO_BD_PRUEBAS=postgresql://tamalio:$contrasena@localhost:5432/tamalio_pruebas
set +a
case ":\$PATH:" in
    *":$proyecto/.venv/bin:"*) ;;
    *) export PATH="$proyecto/.venv/bin:\$PATH" ;;
esac
EOF
sudo chown "root:$(id -gn)" /etc/profile.d/tamalio.sh
sudo chmod 0640 /etc/profile.d/tamalio.sh
if ! grep -q "/etc/profile.d/tamalio.sh" /etc/bash.bashrc; then
    echo '[ -r /etc/profile.d/tamalio.sh ] && . /etc/profile.d/tamalio.sh' \
        | sudo tee -a /etc/bash.bashrc > /dev/null
fi

echo "» Creando las tablas…"
# shellcheck disable=SC1091
. /etc/profile.d/tamalio.sh
uv run tamalio bd iniciar

echo
echo "» Herramientas disponibles:"
uv run python --version
uv run ruff --version
uv run yt-dlp --version | sed 's/^/yt-dlp /'
ffmpeg -version | head -n 1
qjs -h 2>&1 | head -n 1 || true
psql --version

echo
echo "Listo. Prueba con:"
echo "  ruff check && ruff format --check"
echo "  pytest"
echo "  tamalio --help"
