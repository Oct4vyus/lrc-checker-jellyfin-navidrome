
# 🎵 LRC Checker para Jellyfin y Navidrome

Contenedor Docker que permite verificar y corregir archivos `.lrc` (letras sincronizadas) en bibliotecas musicales usadas con 
**Jellyfin** y **Navidrome**. Genera un informe visual (`lrc_report.html`) con categorías de clasificación y herramientas 
básicas de reparación.

## Plan de la versión 4

La planificación para enriquecer el reporte con metadatos, agrupamiento por álbum y enlaces seguros al `.lrc` y al audio está documentada en [PLAN_VERSION_4.md](PLAN_VERSION_4.md). La propuesta de edición controlada de archivos `.lrc` está documentada en [PLAN_VERSION_5.md](PLAN_VERSION_5.md).

---
## 🔌 Requisitos previos

Este contenedor está pensado para quienes ya tienen corriendo alguno de los siguientes plugins:

- **jellyfin-plugin-lyrics**
- **navidrome-lyrics-plugin**

Estos plugins son los encargados de descargar y buscar los archivos `.lrc` en tu biblioteca musical.  
El contenedor **LRC Checker** se encarga únicamente de verificar que estén sincronizados y corregirlos si es necesario.

## ✨ Qué hace

- Compara el **último timestamp** del archivo `.lrc` con la **duración real del audio**, aplicando una **tolerancia configurable**.
- Clasifica los resultados en 10 categorías dentro de `lrc_report.html`.
- La revisión es **on demand**: se inicia manualmente desde el navegador.
- Además de verificar, puede **editar y corregir** archivos en ciertas categorías.

---

## 📊 Informe generado (`lrc_report.html`)

El informe organiza los archivos en las siguientes categorías:
- Todos
- ✅ OK  
- ❌ Missing  
- ⚠️ Empty  
- ⚠️ Unsynced
- 🎼 INSTRUMENTAL
- 🟡 Revisar  
- 🔴 Desync  
- ❌ Corrupt  
- ℹ️ Huérfanos  
- ✍️ Firmados  

## INSTRUMENTAL 🎼️

A los archivos de la biblioteca  musical que no tienen letra, se les editará un archivo `.lrc`sin timestamps, pero con una línea descriptiva
"This song is an instrumental", sin comillas.
Si un .lrc no tiene timestamps y su contenido coincide con esa línea descripta, se marca como:
- INSTRUMENTAL

## 🟡 Revisar  y ## 🔴 Desync

Ambas categorías tienen en cada uno de los archivos .lrc listados, un boton "reparar". Si se ha verificado que el archivo es correcto y está 
sincronizado, este boton le agrega un timestamps al final con la duracion real del tema, por lo cual pasa a categoria OK. Antes de esta edición
automática, se guarda un backup del archivo .lrc.

## Firmados 🎼️

A los archivos `.lrc` generados  manualmente se les pueden incluir un **marcador configurable** con formato[00:00.000] (`SIGNED_MARKER`) para 
identificar que fueron sincronizados a mano.  
Este marcador se inserta en un tramo sin letra cantada (intro, final o pasaje instrumental), de modo que no interfiera con la visualizacion de 
la letra de la canción.
Aclaración: Si el timestamps [00:00.000](`SIGNED_MARKER`) se pone al final, no influye sobre las clasificacion en otras categorias. 
Ya que muchas dependen de la diferencias de tiempo entre el  último timestamps y el tiempo esperado total de la canción.

Ejemplo de configuración en `docker-compose.yml`:
```bash
environment:
  - SIGNED_MARKER=Oct4vyus Kandle
```

Sino se establece otra, Oct4vyus Kandle es la firma por defecto.

### Funcionalidades del informe
- **Barra de progreso**: muestra el porcentaje de archivos en estado ✅ OK respecto al total.  
- **Botón “Escanear ahora”**: relanza la verificación completa de la biblioteca muestra una barra de progreso.  
- **Botón “Reparar”** en la categoría 🟡 Revisar y 🔴 Desync: si la sincronización es correcta, mueve el archivo a ✅ OK.  

### Metadatos, grupos y enlaces (v4)

Cada resultado conserva en `lrc_report.json` el artista, álbum, título, año,
pista y disco normalizados. Se indica la fuente elegida (`lrc`,
`album_directory` o `filename`), los valores `raw_*` y las advertencias de
conflictos o nombres ambiguos. El reporte HTML agrupa dentro de cada filtro
por una identidad estable del álbum (directorio relativo, año, artista y
álbum); los elementos sin datos aparecen como **Álbum desconocido**.

Los botones **LRC** y **Audio** usan el endpoint controlado:

```text
GET /archivo?path=Artista/Álbum/Canción.lrc
GET /archivo?path=Artista/Álbum/Canción.flac
```

El servidor solo acepta rutas relativas existentes dentro de `MUSIC_DIR`,
rechaza traversal (`..`) y extensiones no soportadas, y devuelve el MIME del
archivo. Configurá `SERVER_URL` con la URL que verá el navegador (no
`localhost` si abrís el HTML desde otra computadora). La reproducción de
audio depende del formato y del navegador; el enlace sigue permitiendo
descargar o inspeccionar el archivo.

---
## 📂 Estructura del proyecto

El contenedor espera la siguiente organización de archivos:

- `Dockerfile`
- `docker-compose.yml`
- `entrypoint.sh`
- `.gitignore`
- `README.md`
- `version_servidor/lrc_checker_server.py`  ← Script principal del servidor web

## Archivos excluidos por .gitignore

- **Archivos temporales / reportes generados**
  - `reports/`
  - `*.lrc.tmp`

- **Directorios de trabajo internos**
  - `__pycache__/`
  - `*.pyc`

- **Entornos locales**
  - `.env`
  - `.env.local`

- **Directorios montados (no subir los volúmenes reales)**
  - `/music/`
  - `/reports/`


## 🔧 Mecanismo de funcionamiento

1. Preparar la carpeta con los archivos necesarios para construir la imagen del contenedor.  
2. Construir la imagen con Docker.  
3. Configurar en `docker-compose.yml`:  
   - Ruta de tu biblioteca de música.  
   - Carpeta donde se generan los informes.  
   - Puerto e IP del servidor.  
4. Levantar el contenedor.  
5. Verificar conexión:  

http://IP-SERVIDOR:PUERTO/status
Debe responder **OK**. 
 
6. Generar primer informe:  

http://IP-SERVIDOR:PUERTO/escanear

En bibliotecas grandes puede tardar. Al finalizar muestra:  
*Escaneo completo: XX archivo(s) en estado REVISAR, XX OK de XX total.*  
7. Abrir el archivo `lrc_report.html` en la carpeta de informes para revisar y reparar.  

---

## 🎯 Compatibilidad

- **Jellyfin**: muestra las letras sincronizadas directamente en la interfaz web y apps compatibles.  
- **Navidrome**: no las muestra en su interfaz, pero sí si se usa con apps como **Symfonium** vía Subsonic.  

---

## ⚡ Quick Start

```bash
# Clonar repositorio
git clone https://github.com/Oct4vyus/lrc-checker-jellyfin-navidrome.git
cd lrc-checker-jellyfin-navidrome

# Construir imagen
docker-compose build

# Levantar contenedor
docker-compose up -d


```

Luego abrir en el navegador:

http://IP-SERVIDOR:PUERTO/status → verificar conexión.

http://IP-SERVIDOR:PUERTO/escanear → generar primer informe.

📌 Notas
No genera letras nuevas, solo valida y corrige las existentes.

Ideal para colecciones grandes donde la sincronización es importante.

🤝 Contribuciones
¡Las contribuciones son bienvenidas! Abre un issue o un pull request para sugerir mejoras.

📜 Licencia
MIT License

## Captura de pantalla del informe

El siguiente ejemplo muestra un reporte generado por **LRC Checker v2.0.0**, donde se resumen los resultados del escaneo de la biblioteca:

![Captura de pantalla del informe](https://github.com/Oct4vyus/lrc-checker-jellyfin-navidrome/raw/main/docs/imagenes/lrc-checker-report.png)
