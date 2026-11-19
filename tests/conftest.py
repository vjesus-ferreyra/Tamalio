# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""Fixtures compartidos por todas las pruebas."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tamalio.servicios.detector_plataforma import DetectorPlataforma

#: Carpeta con las respuestas reales de yt-dlp (reducidas y sin URL firmadas).
CARPETA_FIXTURES = Path(__file__).parent / "fixtures"
#: Raíz del repositorio (para leer los ejemplos).
RAIZ_PROYECTO = Path(__file__).parent.parent


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Omite automáticamente las pruebas marcadas ``ffmpeg`` si FFmpeg no está instalado."""
    if shutil.which("ffmpeg"):
        return
    omitir = pytest.mark.skip(reason="FFmpeg no está instalado")
    for item in items:
        if "ffmpeg" in item.keywords:
            item.add_marker(omitir)


@pytest.fixture
def cargar_fixture():
    """Devuelve una función que carga ``tests/fixtures/<nombre>.json``."""

    def cargar(nombre: str) -> dict[str, Any]:
        return json.loads((CARPETA_FIXTURES / f"{nombre}.json").read_text(encoding="utf-8"))

    return cargar


@pytest.fixture
def detector() -> DetectorPlataforma:
    """Detector de plataformas real (no tiene dependencias)."""
    return DetectorPlataforma()


@pytest.fixture
def generar_audio(tmp_path: Path):
    """Genera con FFmpeg un tono corto en el códec/contenedor pedido."""

    def generar(nombre: str, codec: list[str], segundos: float = 1.5) -> Path:
        destino = tmp_path / nombre
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:duration={segundos}",
                *codec,
                str(destino),
            ],
            check=True,
        )
        return destino

    return generar


@pytest.fixture
def imagen_jpeg(tmp_path: Path) -> bytes:
    """JPEG 1280×720 generado con FFmpeg (o un JPEG mínimo si no hay FFmpeg)."""
    if not shutil.which("ffmpeg"):
        return b"\xff\xd8\xff\xe0" + b"\x00" * 4096
    ruta = tmp_path / "imagen.jpg"
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=1280x720:rate=1",
            "-frames:v",
            "1",
            str(ruta),
        ],
        check=True,
    )
    return ruta.read_bytes()
