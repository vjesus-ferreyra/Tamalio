# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Víctor Jesús Torres Ferreyra (Quetzal Nocturno)
# Tamalio es software libre: consulta el fichero LICENSE en la raíz del proyecto.

"""
Tamalio — Extractor de música Hi-Fi.

Paquete raíz de la aplicación. Aquí solo viven las constantes de identidad del
proyecto; toda la lógica se encuentra en los subpaquetes organizados bajo el
patrón **MVC**:

- ``modelos``       → entidades del dominio (Pista, Fuente, TareaDescarga…).
- ``vistas``        → todo lo que ve y escribe el usuario en la terminal.
- ``controladores`` → coordinan los casos de uso (descargar, exportar…).
- ``servicios``, ``extractores`` y ``repositorios`` → lógica de negocio y
  persistencia que el modelo usa para hacer su trabajo.
"""

#: Nombre comercial de la aplicación.
NOMBRE = "Tamalio"

#: Versión semántica del proyecto (MAYOR.MENOR.PARCHE).
__version__ = "0.1.0"

#: Autor del proyecto.
AUTOR = "Víctor Jesús Torres Ferreyra"

#: Alias del autor.
ALIAS_AUTOR = "Quetzal Nocturno"

#: Repositorio en GitHub (``usuario/proyecto``). Se usa para construir las URL
#: públicas de los esquemas JSON (``$schema``). Cámbialo si tu usuario es otro.
REPOSITORIO = "vjesus-ferreyra/tamalio"

#: URL base donde GitHub sirve los esquemas en crudo desde la rama principal.
URL_ESQUEMAS = f"https://raw.githubusercontent.com/{REPOSITORIO}/main/src/tamalio/recursos/esquemas"
