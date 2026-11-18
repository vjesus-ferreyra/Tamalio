# Arquitectura de Tamalio

Este documento describe cómo está construido Tamalio. Todos los diagramas
están en [Mermaid](https://mermaid.js.org/) y GitHub los dibuja directamente.

## Contenido

1. [Capas MVC](#1-capas-mvc)
2. [Diagrama de clases](#2-diagrama-de-clases)
3. [Secuencia de una descarga](#3-secuencia-de-una-descarga)
4. [Estados de una tarea](#4-estados-de-una-tarea)
5. [Modelo de datos (PostgreSQL)](#5-modelo-de-datos-postgresql)
6. [Estrategia anti-bloqueo](#6-estrategia-anti-bloqueo)
7. [Pausa, salto y cancelación](#7-pausa-salto-y-cancelación)
8. [Exportar e importar el catálogo](#8-exportar-e-importar-el-catálogo)
9. [Organización de ficheros del código](#9-organización-de-ficheros-del-código)

---

## 1. Capas MVC

Tamalio sigue el patrón **Modelo-Vista-Controlador**. La regla de oro: el
modelo nunca importa nada de la vista. Cuando necesita informar algo (avance,
errores), lo hace mediante la interfaz `ObservadorDescargas`, que la vista
implementa.

```mermaid
flowchart TB
    usuario([Usuario en la terminal])

    subgraph V["Vista"]
        AA[AnalizadorArgumentos<br/>comandos y opciones]
        VC[VistaConsola<br/>barras de progreso en vivo]
        LT[LectorTeclado<br/>p · s · c · q]
    end

    subgraph C["Controladores"]
        CD[ControladorDescargas]
        CC[ControladorCatalogo]
        CV[ControladorConversion]
        CS[ControladorSistema]
    end

    subgraph M["Modelo"]
        direction TB
        ENT[Entidades<br/>Pista · Fuente · TareaDescarga · Caratula]
        GD[GestorDescargas]
        EXT[Extractores<br/>YouTube · SoundCloud · Bandcamp]
        SRV[Servicios<br/>ClienteYtDlp · ConversorAudio · EtiquetadorAudio<br/>DescargadorCaratulas · OrganizadorBiblioteca]
        REP[Repositorios<br/>PostgreSQL]
    end

    subgraph EXTERNO["Herramientas externas"]
        YTDLP[(yt-dlp + curl_cffi)]
        QJS[(QuickJS)]
        FF[(FFmpeg)]
        PG[(PostgreSQL)]
        MUT[(mutagen)]
    end

    usuario --> AA --> CD & CC & CV & CS
    LT --> CD
    CD --> GD
    CC --> REP
    CV --> SRV
    GD --> EXT & SRV & REP
    GD -. ObservadorDescargas .-> VC
    VC --> usuario
    SRV --> YTDLP --> QJS
    SRV --> FF
    SRV --> MUT
    REP --> PG
```

| Capa | Paquete | Responsabilidad |
|------|---------|-----------------|
| Vista | `tamalio.vistas` | Analizar argumentos, dibujar progreso, preguntar al usuario. |
| Controlador | `tamalio.controladores` | Un controlador por grupo de comandos; une vista y modelo. |
| Modelo | `tamalio.modelos`, `servicios`, `extractores`, `repositorios` | Entidades, reglas de negocio y persistencia. |
| Contratos | `tamalio.interfaces` | Clases abstractas que permiten cambiar implementaciones (p. ej. pruebas en memoria). |
| Composición | `tamalio.aplicacion` | Único lugar que crea las clases concretas y las conecta (inyección de dependencias). |

---

## 2. Diagrama de clases

Clases principales y sus relaciones (se omiten atributos menores).

```mermaid
classDiagram
    direction LR

    class Extractor {
        <<abstract>>
        +plataforma Plataforma
        +normalizar(info, fuente) list~Pista~
    }
    class ExtractorBase {
        <<abstract>>
        #_crear_pista(entrada, contexto, posicion) Pista
        #_es_album(info, entradas) bool
        #_caratula(entrada) Caratula
        #_caratula_coleccion(info, entradas) Caratula
    }
    class ExtractorYoutube
    class ExtractorSoundcloud
    class ExtractorBandcamp
    class FabricaExtractores {
        +obtener(plataforma) Extractor
    }
    Extractor <|-- ExtractorBase
    ExtractorBase <|-- ExtractorYoutube
    ExtractorBase <|-- ExtractorSoundcloud
    ExtractorBase <|-- ExtractorBandcamp
    FabricaExtractores o-- Extractor

    class Pista {
        +plataforma Plataforma
        +id_externo str
        +titulo str
        +album str
        +artistas list~str~
        +artistas_album list~str~
        +numero_pista int
        +generos list~str~
        +anio int
        +caratula Caratula
        +aplicar_metadatos(dict)
        +a_diccionario() dict
    }
    class Fuente {
        +url str
        +plataforma Plataforma
        +tipo TipoFuente
        +formato FormatoAudio
        +metadatos dict
    }
    class TareaDescarga {
        +id int
        +estado EstadoDescarga
        +intentos int
        +iniciar()
        +pausar()
        +reanudar()
        +completar()
        +fallar(mensaje)
        +cancelar()
        +reintentar()
    }
    class Caratula {
        +url str
        +alternativas tuple
        +recortar_cuadrada bool
    }
    TareaDescarga *-- Fuente
    Pista *-- Caratula

    class ObservadorDescargas {
        <<interface>>
        +al_iniciar_pista()
        +al_progreso()
        +al_completar_pista()
        +al_fallar_pista()
    }
    class Vista {
        <<interface>>
        +mostrar_tabla()
        +preguntar() str
    }
    class VistaConsola
    ObservadorDescargas <|-- Vista
    Vista <|.. VistaConsola

    class RepositorioCatalogo {
        <<interface>>
    }
    class RepositorioTareas {
        <<interface>>
    }
    class RepositorioSesiones {
        <<interface>>
    }
    RepositorioCatalogo <|.. RepositorioCatalogoPostgres
    RepositorioTareas <|.. RepositorioTareasPostgres
    RepositorioSesiones <|.. RepositorioSesionesPostgres

    class GestorDescargas {
        +procesar(tarea, control, observador) ResumenEjecucion
    }
    GestorDescargas --> FabricaExtractores
    GestorDescargas --> ClienteYtDlp
    GestorDescargas --> ConversorAudio
    GestorDescargas --> EtiquetadorAudio
    GestorDescargas --> DescargadorCaratulas
    GestorDescargas --> OrganizadorBiblioteca
    GestorDescargas --> GestorSesiones
    GestorDescargas --> TemporizadorHumano
    GestorDescargas --> RepositorioCatalogo
    GestorDescargas --> RepositorioTareas
    GestorDescargas ..> ObservadorDescargas : notifica
    GestorDescargas ..> ControlEjecucion : punto_control()

    class ControladorDescargas
    ControladorDescargas --> GestorDescargas
    ControladorDescargas --> Vista
    ControladorDescargas --> LectorTeclado
```

**Patrones de diseño usados**

| Patrón | Dónde | Para qué |
|--------|-------|----------|
| *Template Method* | `ExtractorBase` | El algoritmo de normalización es común; cada plataforma redefine «ganchos». |
| *Factory* | `FabricaExtractores`, `FabricaLectoresFuentes` | Elegir la implementación correcta sin `if` repartidos por el código. |
| *Chain of Responsibility* | `FabricaLectoresFuentes` | Cada lector decide si «admite» el fichero. |
| *Observer* | `ObservadorDescargas` | El modelo informa el avance sin conocer a la vista. |
| *Repository* | `repositorios/` | Aislar SQL del resto de la aplicación. |
| *State* (tabla de transiciones) | `EstadoDescarga`, `TareaDescarga` | Impedir cambios de estado inválidos. |
| *Composition Root* | `Aplicacion` | Un único lugar crea y conecta los objetos. |

---

## 3. Secuencia de una descarga

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario
    participant CD as ControladorDescargas
    participant RT as RepositorioTareas
    participant GD as GestorDescargas
    participant YT as ClienteYtDlp
    participant EX as Extractor
    participant FF as Conversor/FFmpeg
    participant ET as EtiquetadorAudio
    participant OB as OrganizadorBiblioteca
    participant RC as RepositorioCatalogo
    participant V as VistaConsola

    U->>CD: tamalio descargar URL / -a fuentes.jsonc
    CD->>RT: agregar(fuente) (sin duplicar activas)
    loop por cada tarea
        CD->>GD: procesar(tarea, control, vista)
        GD->>RT: estado = en_proceso
        GD->>YT: extraer(fuente)
        YT-->>GD: info (JSON de yt-dlp)
        GD->>EX: normalizar(info)
        EX-->>GD: [Pista, …]
        loop por cada pista
            GD->>RC: ¿ya está descargada?
            alt ya existe
                GD-->>V: al_omitir_pista
            else nueva
                GD->>GD: pausa humana aleatoria
                GD->>YT: descargar(pista, hook)
                YT-->>V: al_progreso (bytes, velocidad, ETA)
                GD->>GD: carátula (caché → requests → FFmpeg)
                GD->>FF: convertir / re-empaquetar
                GD->>ET: etiquetar (metadatos + carátula)
                GD->>OB: colocar en ~/Música/usuario/Plataforma/…
                GD->>RC: guardar(pista)
                GD-->>V: al_completar_pista
            end
        end
        GD->>RT: estado final (completada/fallida/pausada/cancelada)
    end
    CD-->>V: mostrar_resumen
```

---

## 4. Estados de una tarea

```mermaid
stateDiagram-v2
    [*] --> pendiente: tamalio descargar
    pendiente --> en_proceso: el gestor la toma
    pendiente --> pausada: tamalio pausar
    pendiente --> cancelada: tamalio cancelar
    en_proceso --> completada: todas las pistas OK u omitidas
    en_proceso --> fallida: alguna pista falló
    en_proceso --> pausada: tecla [q], Ctrl+C o tamalio pausar
    en_proceso --> cancelada: tecla [c] o tamalio cancelar
    en_proceso --> pendiente: recuperación tras un cierre inesperado
    pausada --> pendiente: tamalio reanudar
    pausada --> en_proceso: tamalio reanudar
    pausada --> cancelada: tamalio cancelar
    fallida --> pendiente: tamalio reintentar
    fallida --> cancelada: tamalio cancelar
    cancelada --> pendiente: tamalio reintentar --incluir-canceladas
    completada --> pendiente: re-descarga forzada
    completada --> [*]
```

> Al **pausar** se conservan los ficheros `.part` de `yt-dlp` para continuar
> donde se quedó; al **cancelar** o **saltar** se borran.

---

## 5. Modelo de datos (PostgreSQL)

```mermaid
erDiagram
    PISTAS {
        bigserial id PK
        text plataforma "youtube · soundcloud · bandcamp"
        text id_externo "único junto con plataforma"
        text url
        text titulo
        text album
        text_array artistas
        text_array artistas_album
        int numero_pista
        int total_pistas
        text_array generos
        int anio
        numeric duracion
        text url_caratula
        bool es_sencillo
        text codec_origen
        numeric bitrate_origen
        text formato
        text ruta_archivo
        timestamptz creado_en
        timestamptz actualizado_en
    }
    TAREAS_DESCARGA {
        bigserial id PK
        text url "única mientras esté activa"
        text plataforma
        text estado
        int intentos
        text ultimo_error
        jsonb opciones "formato, metadatos, comentario"
        timestamptz creado_en
        timestamptz actualizado_en
    }
    SESIONES_PLATAFORMA {
        text plataforma PK
        text ruta_cookies "solo la ruta, nunca el contenido"
        timestamptz actualizado_en
    }
    ESQUEMA_MIGRACIONES {
        text nombre PK
        timestamptz aplicado_en
    }
    TAREAS_DESCARGA ||--o{ PISTAS : "produce"
    SESIONES_PLATAFORMA ||--o{ TAREAS_DESCARGA : "autentica (por plataforma)"
```

La relación tarea → pistas es lógica (una tarea de álbum genera varias pistas)
y no se modela con clave foránea: una pista puede llegar desde distintas tareas
o desde la importación de un catálogo.

---

## 6. Estrategia anti-bloqueo

```mermaid
flowchart TD
    A[Operación: extraer o descargar] --> B{¿Respuesta OK?}
    B -- sí --> Z[Continuar]
    B -- no --> C{¿Bloqueo?<br/>«not a bot», captcha,<br/>login, HTTP 429}
    C -- no --> E[Error normal:<br/>la pista falla y se registra]
    C -- sí --> D{¿Hay cookies<br/>registradas?}
    D -- no, primera vez --> P[Pedir al usuario la ruta<br/>del fichero de cookies]
    P --> V{¿Fichero Netscape<br/>válido?}
    V -- sí --> G[Guardar ruta en PostgreSQL] --> A
    V -- no, 3 intentos --> R
    D -- sí --> R{¿Reintentos de bloqueo<br/>agotados?}
    R -- no --> W[Esperar con backoff exponencial<br/>+ jitter aleatorio] --> A
    R -- sí --> F[La tarea queda fallida<br/>tamalio reintentar más tarde]
```

Medidas preventivas activas siempre:

- **Suplantación de navegador** con `curl_cffi` (`impersonate`), recomendada por
  la documentación de `yt-dlp` para sitios con *TLS fingerprinting*.
- **Esperas aleatorias** entre pistas (distribución triangular + ruido gaussiano
  con `random.SystemRandom`) y **pausas largas** cada 8–15 pistas.
- **Espera aleatoria entre peticiones internas** (`sleep_interval_requests`).
- **QuickJS** para resolver los retos JavaScript de YouTube sin Deno.
- Una sola conexión de fragmentos a la vez y reanudación de `.part`.

---

## 7. Pausa, salto y cancelación

```mermaid
sequenceDiagram
    participant T as Hilo del teclado
    participant CE as ControlEjecucion
    participant H as Hook de yt-dlp / FFmpeg / esperas
    participant BD as PostgreSQL
    participant O as Otra terminal

    T->>CE: [p] alternar_pausa()
    H->>CE: punto_control()
    Note over H,CE: bloqueado mientras esté en pausa
    T->>CE: [p] alternar_pausa()
    CE-->>H: continúa
    O->>BD: tamalio pausar 7
    H->>CE: punto_control()
    CE->>BD: estado_actual(7) (cada 2 s)
    BD-->>CE: pausada
    CE-->>H: ErrorDescargaCancelada(TAREA, pausar=True)
    Note over H: yt-dlp aborta con DownloadCancelled<br/>y el .part se conserva
```

| Tecla | Acción | Resultado |
|-------|--------|-----------|
| `p` | Pausar / reanudar | La descarga se congela sin cerrar el fichero parcial. |
| `s` | Saltar pista | Se borra el parcial y se sigue con la siguiente pista. |
| `c` | Cancelar tarea | La tarea queda *cancelada*; se sigue con la siguiente tarea. |
| `q` / `Ctrl+C` | Salir | La tarea actual queda *pausada*; `tamalio reanudar` continúa. |

---

## 8. Exportar e importar el catálogo

```mermaid
flowchart LR
    subgraph A["Equipo A"]
        BA[(PostgreSQL A)] --> EXP[tamalio catalogo exportar<br/>mi-catalogo.jsonc]
    end
    EXP -- "USB, nube, Git…" --> IMP
    subgraph B["Equipo B"]
        IMP[tamalio catalogo importar<br/>mi-catalogo.jsonc --descargar] --> Q{¿Existe el fichero en<br/>ruta_relativa?}
        Q -- sí --> VIN[Se vincula al catálogo<br/>sin descargar]
        Q -- no --> DES[Se encola la URL con sus<br/>metadatos originales fijos]
        VIN & DES --> BB[(PostgreSQL B)]
    end
```

El fichero exportado cumple `catalogo.schema.json`, guarda rutas **relativas**
a la biblioteca (con `/` también en Windows) y nunca contiene audio ni cookies.

---

## 9. Organización de ficheros del código

Cada clase, entidad, interfaz, clase abstracta, vista y controlador vive en su
propio fichero, con documentación en español y *docstrings*.

```mermaid
flowchart LR
    raiz[src/tamalio] --> app[aplicacion.py · __main__.py]
    raiz --> cfg[configuracion/<br/>configuracion · rutas_sistema]
    raiz --> exc[excepciones/<br/>6 excepciones]
    raiz --> mod[modelos/<br/>14 entidades y enumeraciones]
    raiz --> itf[interfaces/<br/>7 contratos abstractos]
    raiz --> ext[extractores/<br/>base · youtube · soundcloud · bandcamp · fábrica · contexto]
    raiz --> srv[servicios/<br/>22 servicios]
    raiz --> rep[repositorios/<br/>conexión + 3 repositorios]
    raiz --> ctl[controladores/<br/>4 controladores]
    raiz --> vis[vistas/<br/>consola · barra · estilos · argumentos · parser · registro]
    raiz --> rec[recursos/<br/>esquemas JSON · SQL]
```
