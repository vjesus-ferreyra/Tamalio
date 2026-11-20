#!/usr/bin/env bash
# Prepara el proyecto la primera vez que se crea el contenedor.
set -euo pipefail

proyecto="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$proyecto"

echo "» Instalando Python y las dependencias con uv…"
uv sync

# Las sesiones SSH (Zed conectado a Codespaces) no heredan el entorno de
# Docker. Este script lo recrea a partir de entorno.env para los shells de
# inicio de sesión, y /etc/bash.bashrc lo carga en los interactivos.
echo "» Configurando el entorno para las sesiones SSH…"
sudo tee /etc/profile.d/tamalio.sh > /dev/null <<EOF
# Generado por .devcontainer/post-create.sh. No lo edites a mano.
set -a
. "$proyecto/.devcontainer/entorno.env"
set +a
case ":\$PATH:" in
    *":$proyecto/.venv/bin:"*) ;;
    *) export PATH="$proyecto/.venv/bin:\$PATH" ;;
esac
EOF
if ! grep -q "/etc/profile.d/tamalio.sh" /etc/bash.bashrc; then
    echo '[ -r /etc/profile.d/tamalio.sh ] && . /etc/profile.d/tamalio.sh' \
        | sudo tee -a /etc/bash.bashrc > /dev/null
fi

echo "» Esperando a PostgreSQL…"
pg_isready --timeout=60

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
