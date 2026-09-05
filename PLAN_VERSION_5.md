# Plan de la versión 5

## Objetivo

Incorporar al informe una sección de edición controlada de archivos `.lrc`, comenzando con dos acciones:

1. Crear o marcar una canción como instrumental.
2. Firmar un archivo `.lrc` existente como verificado o arreglado.

Las acciones deben utilizar enlaces de archivos, aplicar las mismas restricciones de seguridad del servidor y dejar el estado reflejado en el siguiente informe.

## Acción: marcar como instrumental

### Flujo de usuario

1. El usuario pulsa el botón **Instrumental**.
2. El informe solicita el archivo de audio que se desea marcar.
3. El usuario pega el enlace del archivo de audio.
4. El servidor valida y resuelve ese enlace.
5. Se crea un archivo `.lrc` con el mismo nombre base y en el mismo directorio que el audio.
6. El contenido creado es exactamente:

```text
This song is an instrumental.
```

7. El resultado se informa al usuario y el reporte se actualiza.

### Reglas

- Solo se aceptan enlaces generados por el propio informe o rutas relativas válidas dentro de `MUSIC_DIR`.
- El archivo de destino debe ser un formato de audio soportado.
- El `.lrc` se crea sustituyendo únicamente la extensión del audio.
- Si ya existe un `.lrc`, no se debe sobrescribir silenciosamente.
- Antes de reemplazar un archivo existente, el sistema debe solicitar confirmación explícita o rechazar la operación en la primera versión.
- La operación debe ser segura para nombres con espacios, tildes y caracteres especiales.
- El texto debe conservar la detección actual de `INSTRUMENTAL`.
- Tras la operación, el archivo debe aparecer asociado al audio y clasificado como `instrumental` en el siguiente escaneo.

### Casos a informar

- Enlace ausente o inválido.
- Archivo fuera de `MUSIC_DIR`.
- Archivo que no existe.
- Archivo que no es audio.
- `.lrc` ya existente.
- Error de permisos o de escritura.

## Acción: firmar un archivo `.lrc`

### Flujo de usuario

1. El usuario pulsa el botón **Firmar**.
2. El informe solicita el archivo `.lrc` existente.
3. El usuario pega el enlace del `.lrc`.
4. El servidor valida y resuelve el enlace.
5. Se crea un backup antes de modificar el archivo.
6. Se agrega el valor configurado en `SIGNED_MARKER`.
7. Se agrega junto con un timestamp que no interfiera con la letra.
8. El resultado se informa al usuario y el reporte se actualiza.

El valor de `SIGNED_MARKER` debe ser el configurado en `docker-compose.yml` mediante la variable de entorno correspondiente. Si no se configura, se mantiene el valor predeterminado actual del proyecto.

### Forma de la marca

La marca debe conservar el formato que ya reconoce el analizador:

```text
[timestamp]SIGNED_MARKER
```

El timestamp debe elegirse de forma que no altere el análisis de sincronización. La estrategia preferida es:

- Insertarlo al final del archivo, después de la letra existente; o
- Insertarlo en una posición explícitamente elegida que no cambie el último timestamp real.

La implementación debe excluir la línea firmada al calcular el último timestamp, como ya hace la lógica actual para archivos firmados.

### Reglas de firma

- Solo se aceptan archivos `.lrc` dentro de `MUSIC_DIR`.
- Si el archivo ya contiene `SIGNED_MARKER`, no se debe añadir una segunda firma.
- Se debe crear un backup antes de modificar el archivo.
- El backup debe conservarse con una extensión claramente identificable, por ejemplo `.lrc.bak`.
- La escritura debe conservar UTF-8 y el contenido existente.
- El servidor debe rechazar rutas arbitrarias y traversal.
- Si el marcador configurado está vacío, la operación debe fallar con un mensaje explícito.
- El sistema debe evitar alterar los timestamps existentes de la letra.

## Interfaz inicial

El reporte tendrá un apartado de edición con:

```text
[Instrumental]
[Firmar]
```

Cada botón abrirá un diálogo o formulario para pegar el enlace del archivo correspondiente. La interfaz debe mostrar:

- Qué tipo de archivo se espera.
- Una confirmación antes de escribir.
- El resultado de la operación.
- El error concreto si la operación no se puede realizar.

Los botones no deben permitir editar directamente una ruta escrita arbitrariamente sin pasar por la validación del servidor.

## Endpoints previstos

Se pueden incorporar endpoints específicos al servidor HTTP integrado:

```text
POST /instrumental?audio=...
POST /firmar?archivo=...
```

Ambos endpoints deben:

- Validar la petición.
- Resolver únicamente archivos dentro de `MUSIC_DIR`.
- Rechazar extensiones incorrectas.
- Evitar escritura durante un escaneo activo.
- Ejecutar la operación de manera atómica cuando sea posible.
- Devolver un mensaje de éxito o error adecuado.
- Regenerar el HTML y el JSON después de una operación exitosa.

La lectura de archivos y la edición deben compartir helpers de normalización y validación de rutas para no duplicar controles de seguridad.

## Backups y recuperación

Antes de cualquier modificación:

- Crear una copia del `.lrc` original.
- No sobrescribir un backup anterior sin una regla explícita.
- Informar dónde quedó el backup.
- Cancelar la operación si el backup no pudo crearse.

La versión inicial no debe incorporar restauración automática, pero debe dejar el backup disponible para recuperación manual. Una funcionalidad posterior podría agregar un botón de restaurar.

## Relación con las categorías

Después de crear un instrumental:

- El resultado debe clasificarse como `INSTRUMENTAL`.
- Debe incluir enlaces al audio y al nuevo `.lrc`.

Después de firmar:

- El resultado debe incluir la marca `Firmado`.
- La firma no debe modificar indebidamente la clasificación de sincronización.
- El archivo debe seguir siendo editable manualmente fuera de la herramienta.
- La lógica actual debe continuar excluyendo la línea firmada del cálculo de sincronización.

## Validación

Probar como mínimo:

- Audio sin `.lrc`.
- Audio con `.lrc` ya existente.
- Audio cuyo nombre contiene espacios y tildes.
- Enlace copiado desde otra categoría del informe.
- Enlace manipulado para salir de `MUSIC_DIR`.
- `.lrc` inexistente.
- `.lrc` ya firmado.
- Archivo firmado con `SIGNED_MARKER` personalizado.
- Archivo con timestamps al principio y al final.
- Error de permisos.
- Escaneo simultáneo.
- Regeneración correcta del JSON y HTML.

## Criterios de aceptación

La versión 5 estará lista cuando:

1. El botón Instrumental cree el `.lrc` correcto a partir de un enlace de audio válido.
2. No se sobrescriban `.lrc` existentes sin confirmación.
3. El botón Firmar modifique únicamente `.lrc` válidos.
4. La marca utilice el `SIGNED_MARKER` configurado.
5. La marca incluya un timestamp no intrusivo.
6. Se cree un backup antes de modificar.
7. Las rutas fuera de `MUSIC_DIR` sean rechazadas.
8. Los archivos ya firmados no reciban firmas duplicadas.
9. El reporte y el JSON se regeneren después de una operación exitosa.
10. Las categorías `INSTRUMENTAL` y `Firmados` reflejen el cambio.
11. Las reparaciones existentes continúen funcionando.
12. Los errores se informen explícitamente y no se oculten.

## Dependencias con la versión 4

La versión 5 debería implementarse después de la versión 4, porque reutiliza:

- Enlaces seguros a archivos.
- Resolución de rutas relativas.
- Identificación de audio y `.lrc`.
- Regeneración del informe.
- Metadatos y categorías agrupadas.
- Validación común del servidor.

## Componente principal de la v5: reproductor y verificación in situ

La versión 5 incorporará como componente principal un reproductor sincronizado
asociado al informe HTML. Puede abrirse en una ventana o pestaña nueva del
navegador para disponer de espacio suficiente para los controles y la letra.
La molestia será mínima porque se abrirá directamente desde el resultado que se
está revisando y utilizará los mismos archivos y datos del informe. El objetivo
es verificar rápidamente que el audio corresponde a la canción y que la letra
está correctamente sincronizada.

### Flujo propuesto

Cada resultado que tenga audio y `.lrc` incluirá una acción:

```text
▶ Verificar sincronización
```

Al activarla, se abrirá una ventana o pestaña de verificación que:

1. Carga el audio mediante el endpoint seguro `/archivo`.
2. Carga el `.lrc` asociado.
3. Reproduce el audio con un reproductor HTML5.
4. Muestra la línea de letra activa según el tiempo de reproducción.
5. Resalta la línea siguiente y su timestamp.
6. Muestra el tiempo actual y la diferencia respecto del timestamp esperado.
7. Permite ajustar temporalmente un offset, por ejemplo:
   `-500 ms`, `0 ms`, `+500 ms`.
8. Permite volver a reproducir, pausar, retroceder y avanzar unos segundos.
9. Permite marcar el archivo como revisado o firmarlo desde la misma vista.
10. Permite marcar el audio como instrumental desde la misma vista.

Controles iniciales sugeridos:

```text
[Reproducir] [Pausa] [Retroceder 5 s] [Avanzar 5 s]
Offset: [-] 0.000 s [+]
```

### Motivo para integrarlo en el informe

El LRC Checker ya conoce:

- El audio asociado.
- El `.lrc` asociado.
- La duración del audio.
- Los timestamps.
- La categoría actual.
- El marcador `SIGNED_MARKER`.

Una implementación integrada evita depender de permisos adicionales para
extensiones del navegador y reduce los problemas de acceso a archivos locales,
SMB y recursos `file://`. También permitiría que la verificación use exactamente
los mismos archivos y datos que el escaneo.

### Alcance de la primera implementación

La primera implementación debe priorizar:

- Reproducción del audio asociado.
- Carga del `.lrc` asociado.
- Resaltado de la línea activa.
- Navegación haciendo clic sobre una línea de la letra.
- Ajuste temporal del offset sin modificar todavía el archivo.
- Acción **Firmar** reutilizando `SIGNED_MARKER`.
- Acción **Instrumental** reutilizando la creación del `.lrc`.

El ajuste permanente de timestamps solo debe incorporarse después de confirmar
que la reproducción y el cálculo visual de sincronización son correctos.

La acción de firmado debe crear el backup y respetar las validaciones definidas
en este documento. La acción de instrumental debe confirmar antes de crear o
reemplazar un `.lrc`.

### Herramientas externas opcionales

Como alternativas para revisar la biblioteca fuera del informe se pueden
documentar:

- **VLC**, por su compatibilidad con formatos de audio.
- **foobar2000**, por sus componentes y flexibilidad.
- **MusicBee**, por sus paneles de letras.
- **LRCGET**, para descargar y administrar archivos `.lrc`, no como herramienta
  principal de validación manual.

Estas aplicaciones serán únicamente complementarias. No forman parte del flujo
principal de validación: VLC y foobar2000 son demasiado generales o pesados
para este objetivo puntual, y LRCGET está orientado a descargar y administrar
letras, no a verificar in situ su sincronización y correspondencia.

La solución oficial de la v5 será el reproductor integrado.
