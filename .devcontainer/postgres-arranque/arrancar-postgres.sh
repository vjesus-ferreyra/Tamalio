#!/bin/sh
# Arranque del servicio «db» del contenedor de desarrollo.
#
# Genera, la primera vez, una contraseña aleatoria para el usuario «tamalio» y
# la guarda en el volumen «secretos-bd», que comparte con el servicio «app».
# Así el repositorio no contiene ninguna contraseña y cada entorno tiene la suya.
# Después cede el control al arranque normal de la imagen oficial de PostgreSQL,
# que solo usa POSTGRES_PASSWORD al crear la base por primera vez.
set -eu

fichero=/run/secretos-tamalio/contrasena-bd

if [ ! -s "$fichero" ]; then
    # 24 bytes aleatorios en hexadecimal: 48 caracteres seguros dentro de una URL.
    od -An -N24 -tx1 /dev/urandom | tr -d ' \n' > "$fichero.tmp"
    # Legible por el usuario del contenedor «app» (otro UID); el volumen solo lo
    # montan estos dos servicios.
    chmod 0644 "$fichero.tmp"
    mv "$fichero.tmp" "$fichero"
fi

POSTGRES_PASSWORD="$(cat "$fichero")"
export POSTGRES_PASSWORD
exec docker-entrypoint.sh postgres
