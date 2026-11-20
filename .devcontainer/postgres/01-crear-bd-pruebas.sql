-- Se ejecuta una sola vez, cuando se crea el volumen de PostgreSQL.
-- La base «tamalio» ya la crea la imagen a partir de POSTGRES_DB; aquí se
-- añade la que usan las pruebas de integración (TAMALIO_BD_PRUEBAS).
CREATE DATABASE tamalio_pruebas OWNER tamalio;
