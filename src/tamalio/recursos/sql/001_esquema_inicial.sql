-- =====================================================================
-- Tamalio · Esquema inicial de PostgreSQL
-- ---------------------------------------------------------------------
-- Lo aplica «tamalio bd iniciar» (es idempotente: puede ejecutarse
-- varias veces sin efectos secundarios). El diagrama entidad-relación
-- está en docs/arquitectura.md.
-- =====================================================================

-- Función de disparador que mantiene «actualizado_en» al día.
CREATE OR REPLACE FUNCTION tamalio_marcar_actualizado()
RETURNS TRIGGER AS $$
BEGIN
    NEW.actualizado_en := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- Catálogo: una fila por canción descargada (o importada de otro equipo).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pistas (
    id                 BIGSERIAL PRIMARY KEY,
    plataforma         TEXT        NOT NULL CHECK (plataforma IN ('youtube', 'soundcloud', 'bandcamp')),
    id_externo         TEXT        NOT NULL,
    url                TEXT        NOT NULL,
    titulo             TEXT        NOT NULL,
    album              TEXT        NOT NULL,
    artistas           TEXT[]      NOT NULL DEFAULT '{}',
    artistas_album     TEXT[]      NOT NULL DEFAULT '{}',
    numero_pista       INTEGER     CHECK (numero_pista > 0),
    total_pistas       INTEGER     CHECK (total_pistas > 0),
    generos            TEXT[]      NOT NULL DEFAULT '{}',
    anio               INTEGER     CHECK (anio BETWEEN 1877 AND 3000),
    duracion           NUMERIC(10, 3),
    url_caratula       TEXT,
    es_sencillo        BOOLEAN     NOT NULL DEFAULT FALSE,
    codec_origen       TEXT,
    bitrate_origen     NUMERIC(8, 3),
    formato            TEXT,
    ruta_archivo       TEXT,
    creado_en          TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pistas_unicas UNIQUE (plataforma, id_externo)
);

CREATE INDEX IF NOT EXISTS pistas_por_album ON pistas (plataforma, album);
CREATE INDEX IF NOT EXISTS pistas_por_ruta ON pistas (ruta_archivo);

DROP TRIGGER IF EXISTS pistas_actualizado ON pistas;
CREATE TRIGGER pistas_actualizado BEFORE UPDATE ON pistas
    FOR EACH ROW EXECUTE FUNCTION tamalio_marcar_actualizado();

-- ---------------------------------------------------------------------
-- Cola de descargas: hace posible pausar, reanudar, reintentar y cancelar.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tareas_descarga (
    id                 BIGSERIAL PRIMARY KEY,
    url                TEXT        NOT NULL,
    plataforma         TEXT        NOT NULL CHECK (plataforma IN ('youtube', 'soundcloud', 'bandcamp')),
    estado             TEXT        NOT NULL DEFAULT 'pendiente'
                       CHECK (estado IN ('pendiente', 'en_proceso', 'pausada', 'completada', 'fallida', 'cancelada')),
    intentos           INTEGER     NOT NULL DEFAULT 0,
    ultimo_error       TEXT,
    opciones           JSONB       NOT NULL DEFAULT '{}'::jsonb,
    creado_en          TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Una misma URL no puede estar dos veces «activa» en la cola.
CREATE UNIQUE INDEX IF NOT EXISTS tareas_activas_unicas ON tareas_descarga (url)
    WHERE estado IN ('pendiente', 'en_proceso', 'pausada');
CREATE INDEX IF NOT EXISTS tareas_por_estado ON tareas_descarga (estado, creado_en);

DROP TRIGGER IF EXISTS tareas_actualizado ON tareas_descarga;
CREATE TRIGGER tareas_actualizado BEFORE UPDATE ON tareas_descarga
    FOR EACH ROW EXECUTE FUNCTION tamalio_marcar_actualizado();

-- ---------------------------------------------------------------------
-- Sesiones: ruta (no contenido) del fichero de cookies de cada plataforma.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sesiones_plataforma (
    plataforma         TEXT        PRIMARY KEY CHECK (plataforma IN ('youtube', 'soundcloud', 'bandcamp')),
    ruta_cookies       TEXT        NOT NULL,
    actualizado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS sesiones_actualizado ON sesiones_plataforma;
CREATE TRIGGER sesiones_actualizado BEFORE UPDATE ON sesiones_plataforma
    FOR EACH ROW EXECUTE FUNCTION tamalio_marcar_actualizado();
