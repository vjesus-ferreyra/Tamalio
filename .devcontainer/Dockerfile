# Imagen de desarrollo de Tamalio.
#
# Python 3.15 no viene en la imagen: uv lo descarga en post-create.sh según
# «requires-python» de pyproject.toml.

FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# FFmpeg para extraer y convertir el audio; el cliente de PostgreSQL para
# psql y pg_isready.
RUN apt-get update \
    && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends ffmpeg postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# uv, copiado desde su imagen oficial.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# QuickJS-ng como motor de JavaScript de yt-dlp (en lugar de Deno).
# yt-dlp busca un ejecutable llamado «qjs» en el PATH.
ARG QUICKJS_VERSION=v0.18.0
RUN case "$(uname -m)" in \
        x86_64) arquitectura=x86_64 ;; \
        aarch64 | arm64) arquitectura=aarch64 ;; \
        *) echo "Arquitectura no soportada: $(uname -m)" >&2; exit 1 ;; \
    esac \
    && curl -fsSL -o /usr/local/bin/qjs \
        "https://github.com/quickjs-ng/quickjs/releases/download/${QUICKJS_VERSION}/qjs-linux-${arquitectura}" \
    && chmod 0755 /usr/local/bin/qjs
