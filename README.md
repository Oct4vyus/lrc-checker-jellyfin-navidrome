
# 🎵 LRC Checker para Jellyfin y Navidrome

Contenedor Docker que permite verificar y corregir archivos `.lrc` (letras sincronizadas) en bibliotecas musicales usadas con **Jellyfin** y **Navidrome**. Genera un informe visual (`lrc_report.html`) con categorías de clasificación y herramientas básicas de reparación.

---
## 🔌 Requisitos previos

Este contenedor está pensado para quienes ya tienen corriendo alguno de los siguientes plugins:

- **jellyfin-plugin-lyrics**
- **navidrome-lyrics-plugin**

Estos plugins son los encargados de descargar y buscar los archivos `.lrc` en tu biblioteca musical.  
El contenedor **LRC Checker** se encarga únicamente de verificar que estén sincronizados y corregirlos si es necesario.

## ✨ Qué hace

- Compara el **último timestamp** del archivo `.lrc` con la **duración real del audio**, aplicando una **tolerancia configurable**.
- Clasifica los resultados en 9 categorías dentro de `lrc_report.html`.
- La revisión es **on demand**: se inicia manualmente desde el navegador.
- Además de verificar, puede **editar y corregir** archivos en ciertas categorías.

---

## 📊 Informe generado (`lrc_report.html`)

El informe organiza los archivos en las siguientes categorías:

- ✅ OK  
- ❌ Missing  
- ⚠️ Empty  
- ⚠️ Unsynced  
- 🟡 Revisar  
- 🔴 Desync  
- ❌ Corrupt  
- ℹ️ Huérfanos  
- ✍️ Firmados  

## Archivos firmados ✍️

A los archivos `.lrc` generados  manualmente se les pueden incluir un **marcador configurable** con formato[00:00.000] (`SIGNED_MARKER`) para identificar que fueron sincronizados a mano.  
Este marcador se inserta en un tramo sin letra cantada (intro, final o pasaje instrumental), de modo que no interfiera con la visualizacion de la letra de la canción.
Aclaración: Si el timestamps [00:00.000](`SIGNED_MARKER`) se pone al final, no influye sobre las clasificacion en otras categorias. Ya que muchas dependen de la diferencias de tiempo 
de tiempo entre el  último timestamps y el tiempo esperado total de la canción.
Ejemplo de configuración en `docker-compose.yml`:

```yaml
environment:
  - SIGNED_MARKER=Oct4vyus Kandle

### Funcionalidades del informe
- **Barra de progreso**: muestra el porcentaje de archivos en estado ✅ OK respecto al total.  
- **Botón “Escanear ahora”**: relanza la verificación completa de la biblioteca.  
- **Botón “Reparar”** en la categoría 🟡 Revisar: si la sincronización es correcta, mueve el archivo a ✅ OK.  

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


=======
# 🎵 LRC Checker para Jellyfin y Navidrome

Contenedor Docker que permite verificar y corregir archivos `.lrc` (letras sincronizadas) en bibliotecas musicales usadas con **Jellyfin** y **Navidrome**. Genera un informe visual (`lrc_report.htm[...]

---
## 🔌 Requisitos previos

Este contenedor está pensado para quienes ya tienen corriendo alguno de los siguientes plugins:

- **jellyfin-plugin-lyrics**
- **navidrome-lyrics-plugin**

Estos plugins son los encargados de descargar y buscar los archivos `.lrc` en tu biblioteca musical.  
El contenedor **LRC Checker** se encarga únicamente de verificar que estén sincronizados y corregirlos si es necesario.

## ✨ Qué hace

- Compara el **último timestamp** del archivo `.lrc` con la **duración real del audio**, aplicando una **tolerancia configurable**.
- Clasifica los resultados en 9 categorías dentro de `lrc_report.html`.
- La revisión es **on demand**: se inicia manualmente desde el navegador.
- Además de verificar, puede **editar y corregir** archivos en ciertas categorías.

---

## 📊 Informe generado (`lrc_report.html`)

El informe organiza los archivos en las siguientes categorías:

- ✅ OK  
- ❌ Missing  
- ⚠️ Empty  
- ⚠️ Unsynced  
- 🟡 Revisar  
- 🔴 Desync  
- ❌ Corrupt  
- ℹ️ Huérfanos  
- ✍️ Firmados  

## Archivos firmados

A los archivos `.lrc` generados  manualmente se les pueden incluir un **marcador configurable** con formato[00:00.000] (`SIGNED_MARKER`) para identificar que fueron sincronizados a mano.  
Este marcador se inserta en un tramo sin letra cantada (intro, final o pasaje instrumental), de modo que no interfiera con la visualizacion de la letra de la canción.
Aclaración: Si el timestamps [00:00.000](`SIGNED_MARKER`) se pone al final, no influye sobre las clasificacion en otras categorias. Ya que muchas dependen de la diferencias de tiempo 
de tiempo entre el  último timestamps y el tiempo esperado total de la canción.
Ejemplo de configuración en `docker-compose.yml`:

```yaml
environment:
  - SIGNED_MARKER=Oct4vyus Kandle
```

### Funcionalidades del informe
- **Barra de progreso**: muestra el porcentaje de archivos en estado ✅ OK respecto al total.  
- **Botón “Escanear ahora”**: relanza la verificación completa de la biblioteca.  
- **Botón “Reparar”** en la categoría 🟡 Revisar: si la sincronización es correcta, mueve el archivo a ✅ OK.  

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

El siguiente ejemplo muestra un reporte generado por **LRC Checker v2.0.0**, donde se resumen los resultados del escaneo de la colección:

![Captura de pantalla del informe](https://github.com/Oct4vyus/lrc-checker-jellyfin-navidrome/raw/main/docs/imagenes/lrc-checker-report.png)

