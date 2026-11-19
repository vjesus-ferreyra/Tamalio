# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""
Pruebas automatizadas de Tamalio.

La carpeta es un paquete para que los dobles de prueba se importen con una
ruta absoluta desde la raíz del proyecto (``from tests.dobles… import …``).
Así los resuelven igual pytest, Ruff y el servidor de lenguaje del editor
(Zed / basedpyright), sin configurar rutas extra.
"""
