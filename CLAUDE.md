# CLAUDE.md

Instrucciones para Claude Code en este repositorio. Las reglas generales del
proyecto (arquitectura, estilo, pruebas, lecciones aprendidas y forma de
entregar cambios) están en `AGENTS.md`, que se importa a continuación para no
duplicarlas:

@AGENTS.md

## Notas específicas para Claude

- Responde y escribe todo en **español**.
- Antes de editar, lee el fichero completo y su prueba; respeta el patrón MVC y
  la regla de **una clase por fichero**.
- Después de cada cambio ejecuta, en este orden:
  1. `uv run ruff check --fix .`
  2. `uv run ruff format .`
  3. `uv run pytest -q`

  No termines con alguno en rojo; si una prueba falla por algo ajeno al cambio,
  dilo.
- Para diagnosticar un problema real del usuario, pídele la salida de
  `uv run tamalio --debug …` (muestra yt-dlp, FFmpeg, SQL, carátulas y
  etiquetas) y, si hace falta, el JSON de `~/.local/state/tamalio/depuracion/`.
  Conviértelo en un fixture de prueba antes de corregir.
- Si el usuario pide la entrega como `.patch`, genéralo con `git diff` respecto
  al último estado que él tiene, verifica que aplique con `git apply --check`
  sobre una copia limpia y no incluyas `pyproject.toml`/`uv.lock` salvo que sea
  imprescindible (ver `AGENTS.md` §9).
- No ejecutes descargas reales ni `tamalio bd borrar` sin que el usuario lo pida.
