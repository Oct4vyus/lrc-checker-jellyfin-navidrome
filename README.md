# 🎵 LRC Checker para Jellyfin y Navidrome

Contenedor Docker que permite verificar y corregir archivos `.lrc` (letras sincronizadas) en bibliotecas musicales usadas con **Jellyfin** y **Navidrome**. Genera un informe visual (`lrc_report.html`) con categorías de clasificación y herramientas básicas de reparación.

---

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

### Funcionalidades del informe
- **Barra de progreso**: muestra el porcentaje de archivos en estado ✅ OK respecto al total.  
- **Botón “Escanear ahora”**: relanza la verificación completa de la biblioteca.  
- **Botón “Reparar”** en la categoría 🟡 Revisar: si la sincronización es correcta, mueve el archivo a ✅ OK.  

---

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