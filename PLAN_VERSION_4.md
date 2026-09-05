# Plan de la versión 4

## Objetivo

Mejorar el informe generado por LRC Checker para que:

- Cada resultado tenga un enlace al archivo `.lrc`.
- Cada resultado tenga un enlace al archivo de audio asociado.
- Los resultados continúen organizados por categoría de estado.
- Dentro de cada categoría, las canciones se agrupen por álbum.
- Los datos del álbum, artista y canción se obtengan de varias fuentes y conserven su procedencia.
- Las inconsistencias y ambigüedades sean visibles, en lugar de corregirse silenciosamente.

Esta versión se probará con la biblioteca real del usuario, que contiene más de 400 álbumes.

## Fuentes de metadatos

### Archivo `.lrc`

Extraer los valores de las etiquetas:

- `[ar:]`: artista.
- `[al:]`: álbum.
- `[ti:]`: título.
- `[length:]`, `[offset:]` y otras etiquetas: conservarlas cuando sean relevantes para el análisis.

Actualmente el proyecto detecta si existen metadatos, pero no conserva sus valores. La versión 4 debe almacenarlos de forma estructurada.

### Directorio del álbum

La biblioteca utiliza directorios con el formato:

```text
AÑO-ARTISTA-ÁLBUM
```

Ejemplo:

```text
1997-Pink Floyd-The Division Bell
```

El parser debe:

1. Detectar el primer bloque como año cuando tenga un formato válido.
2. Separar artista y álbum sin asumir que nunca contienen guiones.
3. Conservar siempre el nombre original del directorio.
4. Marcar como ambiguos los nombres que no puedan dividirse de forma confiable.
5. Soportar directorios sin año o que no respeten el formato esperado.

No se debe perder información cuando el nombre contenga guiones, paréntesis, tildes u otros caracteres.

### Nombre del archivo

Usar el nombre del archivo como fuente alternativa para:

- Título.
- Número de pista.
- Número de disco, si puede identificarse sin ambigüedad.

Ejemplos posibles:

```text
01 - Song Title.flac
01 Song Title.lrc
01. Song Title.mp3
```

El parser debe evitar interpretar como número de pista cualquier prefijo ambiguo.

## Prioridad de las fuentes

La prioridad inicial será:

```text
Título:
  [ti:] del LRC
  nombre del archivo

Álbum:
  [al:] del LRC
  directorio del álbum

Artista:
  [ar:] del LRC
  directorio del álbum

Año:
  directorio del álbum
  metadatos del audio, si se incorporan posteriormente

Número de pista/disco:
  nombre del archivo
  metadatos del audio, si se incorporan posteriormente
```

Cuando una fuente de mayor prioridad esté vacía, se utilizará la siguiente. Cuando dos fuentes tengan valores distintos, se conservará el valor elegido y se registrará una advertencia.

## Modelo de datos propuesto

Cada resultado del escaneo debe conservar, además del estado actual:

```text
audio_file
lrc_file
relative_path
album_directory
artist
album
title
year
track_number
disc_number
metadata_sources
warnings
```

También se deben conservar los valores originales necesarios para investigar conflictos:

```text
raw_lrc_artist
raw_lrc_album
raw_lrc_title
raw_directory_name
raw_filename
```

Ejemplo conceptual:

```json
{
  "artist": "Pink Floyd",
  "album": "The Division Bell",
  "title": "High Hopes",
  "year": 1997,
  "metadata_sources": {
    "artist": "album_directory",
    "album": "album_directory",
    "title": "lrc",
    "year": "album_directory"
  },
  "warnings": []
}
```

## Identidad del álbum

El agrupamiento no debe utilizar solamente el nombre del álbum. La identidad debe considerar como mínimo:

```text
directorio relativo + año + artista + álbum
```

El directorio relativo evita mezclar álbumes con el mismo nombre pertenecientes a artistas o ubicaciones diferentes.

Debe existir un grupo visible para:

```text
Álbum desconocido
```

También se deben mostrar advertencias para álbumes cuyos datos del LRC y del directorio sean contradictorios.

## Estructura del informe HTML

Se mantendrán las categorías existentes:

- Todos.
- OK.
- Missing.
- Empty.
- Unsynced.
- INSTRUMENTAL.
- Revisar.
- Desync.
- Corrupt.
- Huérfanos.
- Firmados.

Dentro de cada categoría, los resultados se agruparán por álbum:

```text
Categoría: OK

  Álbum: The Division Bell (1997) - Pink Floyd
    01 - Cluster One       [LRC] [Audio]
    02 - What Do You Want  [LRC] [Audio]

  Álbum desconocido
    archivo_sin_metadatos  [LRC] [Audio]
```

Los enlaces deben mostrar claramente si abren el `.lrc` o el audio.

## Enlaces a archivos

La versión 4 enlazará ambos archivos:

- `.lrc`: para revisar o editar la letra.
- Audio: para comprobar la canción, duración y correspondencia.

Los enlaces no deben depender de rutas internas como `/music/...`, porque el HTML puede abrirse desde `file://`, SMB o desde otra computadora.

La solución preferida es exponer rutas controladas mediante el servidor HTTP integrado, por ejemplo:

```text
GET /archivo?path=Artista/Album/Cancion.lrc
GET /archivo?path=Artista/Album/Cancion.flac
```

El servidor debe:

- Resolver rutas relativas dentro de `MUSIC_DIR`.
- Rechazar rutas con `..` o cualquier ruta fuera de `MUSIC_DIR`.
- Validar que el archivo exista.
- Permitir únicamente extensiones esperadas.
- Servir el tipo MIME apropiado.
- Codificar correctamente espacios, tildes y caracteres especiales.
- Mantener el control de acceso existente para la reparación de `.lrc`.

La reproducción en el navegador dependerá del formato de audio y del navegador, por lo que el enlace debe seguir siendo útil aunque el navegador no pueda reproducir directamente ese formato.

## JSON y persistencia

La primera implementación no necesita una base de datos. El JSON enriquecido puede actuar como catálogo de la ejecución actual y conservar todos los metadatos, fuentes y advertencias.

SQLite queda como una fase posterior si se necesitan:

- Historial de escaneos.
- Comparación entre escaneos.
- Búsquedas rápidas.
- Estadísticas por artista, álbum o año.
- Persistencia del catálogo entre reinicios.
- Detección de archivos nuevos, modificados o eliminados.

No se debe introducir SQLite hasta comprobar que el modelo de datos y las reglas de normalización funcionan con la biblioteca real.

## Fases de implementación

### Fase 1: extracción y normalización

- Extraer valores reales de `[ar:]`, `[al:]` y `[ti:]`.
- Analizar el directorio `AÑO-ARTISTA-ÁLBUM`.
- Analizar título, pista y disco desde el nombre del archivo.
- Definir fallbacks.
- Registrar fuentes y advertencias.
- Incorporar los datos al JSON.

### Fase 2: agrupamiento del informe

- Definir una identidad estable de álbum.
- Agrupar resultados dentro de cada categoría.
- Mostrar álbumes desconocidos y conflictos.
- Mantener el filtrado actual por categorías.

### Fase 3: enlaces seguros

- Añadir endpoint de lectura controlada de archivos.
- Generar enlaces al `.lrc` y al audio.
- Proteger contra traversal y rutas fuera de `MUSIC_DIR`.
- Probar nombres con espacios, tildes y caracteres especiales.

### Fase 4: validación con la biblioteca real

Generar un resumen de calidad de datos que incluya:

- Álbumes detectados.
- Directorios que no cumplen el formato.
- Archivos sin `.lrc`.
- Archivos sin metadatos.
- Conflictos entre LRC, directorio y nombre de archivo.
- Pistas o discos ambiguos.
- Archivos `.lrc` huérfanos.
- Álbumes agrupados como desconocidos.
- Nombres de álbum repetidos.

Las reglas se ajustarán a partir de estos casos reales antes de considerar terminado el modelo.

### Fase 5: documentación

- Actualizar README.
- Documentar el endpoint de archivos.
- Documentar la importancia de `SERVER_URL`.
- Explicar la prioridad de metadatos y el significado de las advertencias.
- Documentar las limitaciones de reproducción según el formato de audio.

## Criterios de aceptación

La versión 4 estará lista cuando:

1. Cada fila con archivo asociado tenga enlace al `.lrc`.
2. Cada fila con audio asociado tenga enlace al audio.
3. Ningún enlace permita acceder fuera de `MUSIC_DIR`.
4. Los caracteres especiales funcionen correctamente.
5. Las categorías actuales sigan funcionando.
6. Los temas se agrupen correctamente por álbum.
7. Los datos faltantes se completen desde el directorio o el archivo cuando sea seguro.
8. Los conflictos se informen sin sobrescribir silenciosamente información.
9. Los archivos huérfanos y sin metadatos sigan apareciendo.
10. El JSON contenga los datos normalizados, sus fuentes y advertencias.
11. El escaneo de la biblioteca de más de 400 álbumes pueda revisarse mediante un resumen de calidad.
12. Las reparaciones existentes continúen funcionando sin regresiones.

## Decisiones actuales

- La versión será la **v4**.
- Se enlazarán tanto los archivos `.lrc` como los audios.
- Se utilizarán varias fuentes de metadatos.
- Se conservarán las fuentes y los valores originales.
- Los conflictos se advertirán y no se corregirán automáticamente.
- El JSON enriquecido será la persistencia inicial.
- SQLite queda fuera del primer alcance.
- La biblioteca real del usuario será el conjunto principal de validación.
