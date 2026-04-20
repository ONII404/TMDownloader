# TMD — Manga Downloader

![Version](https://img.shields.io/badge/version-2.0-blue.svg)
![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Android%20|%20Linux%20|%20Windows-green.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

Descargador de manga con soporte para múltiples sitios, empaquetado en `.cbz` con metadatos `ComicInfo.xml`. Diseñado para funcionar en **Android (Termux)**, **Linux** y **Windows**.

---

## 📋 Tabla de Contenidos

- [TMD — Manga Downloader](#tmd--manga-downloader)
  - [📋 Tabla de Contenidos](#-tabla-de-contenidos)
  - [Características](#características)
  - [Instalación](#instalación)
    - [Termux (Android)](#termux-android)
    - [Windows](#windows)
  - [Uso](#uso)
    - [Menú interactivo](#menú-interactivo)
    - [Línea de comandos](#línea-de-comandos)
  - [Descarga en lote](#descarga-en-lote)
    - [Modo Normal](#modo-normal)
    - [Modo Descarga Profunda](#modo-descarga-profunda)
  - [Configuración personalizada](#configuración-personalizada)
    - [Archivo .tmo\_config.json](#archivo-tmo_configjson)
    - [Referencia de parámetros](#referencia-de-parámetros)
  - [Metadatos externos (TMOH.json)](#metadatos-externos-tmohjson)
  - [Actualizaciones](#actualizaciones)
  - [Estructura de salida](#estructura-de-salida)
  - [Estructura del proyecto](#estructura-del-proyecto)
  - [Sitios soportados](#sitios-soportados)
  - [Añadir soporte para un nuevo sitio](#añadir-soporte-para-un-nuevo-sitio)
    - [1. Crear el scraper](#1-crear-el-scraper)
    - [2. Registrar el scraper](#2-registrar-el-scraper)
    - [Referencia rápida de la interfaz](#referencia-rápida-de-la-interfaz)
  - [Dependencias](#dependencias)
  - [Notas](#notas)
  - [Licencia](#licencia)

---

## Características

- Descarga individual o en lote desde un archivo `lista.txt`
- **Modo Descarga Profunda** automático para listas grandes (+10 URLs): lotes de 25, delays aleatorios, pausas entre lotes y reanudación segura si se interrumpe
- Detección y manejo automático de bloqueos Cloudflare (403 / 429 / 1015)
- Rotación de User-Agent configurable para reducir el riesgo de ban
- Avisos periódicos de cambio de IP / VPN durante descargas masivas
- Empaquetado en `.cbz` compatible con Mihon, Komga, Kavita, YACReader
- Genera `ComicInfo.xml` automáticamente con título, autor, géneros, tags, idioma, año, etc.
- Soporte de metadatos externos mediante `TMOH.json`
- Organiza la salida en carpetas por serie
- Conversión opcional de imágenes a **JPG** o **AVIF**
- Historial de descargas en `downloads_history.txt`
- Configuración persistente en `.tmo_config.json`
- Actualización automática vía `tmd --update`

---

## Instalación

### Termux (Android)

**1. Preparar el entorno**

```bash
pkg update && pkg upgrade -y && pkg install python git -y
```

**2. Permitir acceso al almacenamiento**

```bash
termux-setup-storage
```

**3. Clonar TMD**

```bash
git clone https://github.com/ONII404/TMDownloader.git /storage/emulated/0/TMDownloader
```

**4. Configurar alias**

```bash
echo "alias tmd='cd /storage/emulated/0/TMDownloader && python3 main.py'" >> ~/.bashrc && source ~/.bashrc && echo -e "\n✅ Instalado. Ahora puedes usar: tmd"
```

### Windows

**1. Requisitos previos**

- **Python 3.10+**: Descárgalo de [python.org](https://www.python.org/). **_Importante_**: marca la casilla "Add Python to PATH".
- **Git**: Descárgalo de [git-scm.com](https://git-scm.com/).

**2. Clonar TMD**

```powershell
git clone https://github.com/ONII404/TMDownloader.git $HOME\TMDownloader
```

**3. Configurar alias** *(recomendado — ejecuta PowerShell como administrador la primera vez)*

```powershell
# Habilitar ejecución de scripts locales
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

# Crear perfil si no existe
if (!(Test-Path $PROFILE)) { New-Item -Type File -Path $PROFILE -Force }

# Añadir función tmd
$functionCode = "`nfunction tmd { python `$HOME\TMDownloader\main.py `$args }"
if (!(Select-String -Path $PROFILE -Pattern "function tmd")) {
    Add-Content $PROFILE $functionCode
    Write-Host "✅ Alias 'tmd' configurado correctamente." -ForegroundColor Green
} else {
    Write-Host "ℹ️ El alias 'tmd' ya estaba configurado." -ForegroundColor Yellow
}
```

**4. Reinicia la terminal**

> Las dependencias (`requests`, `cloudscraper`) se instalan automáticamente la primera vez. `Pillow` solo es necesario si usas `--format`.

---

## Uso

### Menú interactivo

Ejecutar `tmd` sin argumentos abre el menú:

```
  MENU PRINCIPAL
  [1] Descargar manga
  [2] Descarga en lote  (.txt)
  [3] Ver historial
  [4] Configuración
  [5] Buscar actualizaciones
  [6] Salir
```

### Línea de comandos

```bash
# Descarga individual
tmd https://un-sitio/contents/69b6fd0b4a6fa

# Con ruta de salida y conversión a JPG
tmd https://un-sitio/contents/69b6fd0b4a6fa -o ~/Manga -f jpg

# Descarga en lote desde lista.txt
tmd --batch

# Lote con ruta de salida personalizada
tmd --batch -o /storage/emulated/0/Manga

# Comprobar y aplicar actualizaciones
tmd --update

# Actualizar sin confirmación (para scripts / automatización)
tmd --update --yes

# Ver la versión instalada
tmd --version
```

| Argumento   | Corto | Descripción                                          |
|-------------|-------|------------------------------------------------------|
| `url`       | —     | URL del manga a descargar                            |
| `--batch`   | `-b`  | Activa el modo lote (lee `lista.txt`)                |
| `--output`  | `-o`  | Ruta de salida                                       |
| `--format`  | `-f`  | Convierte imágenes: `jpg` o `avif`                   |
| `--cookies` | `-c`  | Archivo de cookies en formato Netscape               |
| `--update`  | `-u`  | Actualiza TMD desde el repositorio git               |
| `--yes`     | `-y`  | Confirma la actualización sin preguntar              |
| `--version` | `-V`  | Muestra la versión instalada y sale                  |

---

## Descarga en lote

Crea o edita `lista.txt` en la raíz del proyecto. Si no existe, se genera automáticamente con instrucciones la primera vez que usas la opción de lote.

```
# Una URL por línea. Las líneas con # son comentarios.
https://un-sitio/contents/69b6fd0b4a6fa
https://lectorhentai.com/manga/24514/loca-por-ti
https://un-sitio/contents/otro_id_aqui
```

### Modo Normal

Se activa automáticamente cuando la lista tiene **10 URLs o menos** (umbral configurable). Las descargas son secuenciales con una pausa fija de 5 segundos entre ellas.

### Modo Descarga Profunda

Se activa automáticamente cuando la lista supera el umbral. Está diseñado para descargas masivas (+5000 URLs) con protección activa contra baneos.

**Comportamiento:**

- Procesa las URLs en **lotes de 25** (configurable)
- Aplica un **delay aleatorio de 5 a 9 segundos** entre descargas individuales
- Aplica una **pausa aleatoria de 8 a 15 minutos** entre lotes
- Muestra el progreso global: `Lote 12/218 — 300/5448 URLs`
- Recuerda la posición exacta: si se interrumpe (cierre, error, apagado), al volver a ejecutar `tmd --batch` preguntará si reanudar desde donde se quedó
- Muestra un **aviso de cambio de IP/VPN** cada 4–7 lotes (aleatorio)
- Detecta bloqueos Cloudflare (403 / 429 / 1015) y espera automáticamente 2–4 horas antes de continuar

> Todos estos valores son configurables desde el menú **[4] Configuración** o editando directamente `.tmo_config.json`.

---

## Configuración personalizada

TMD guarda toda su configuración en `.tmo_config.json` en la raíz del proyecto. Puedes editarlo a mano o usar el menú **[4] Configuración** del modo interactivo.

### Archivo .tmo_config.json

```json
{
  "last_output": "/storage/emulated/0/Download/Manga",
  "deep_mode_threshold": 10,
  "batch_size": 25,
  "delay_between_downloads": [5, 9],
  "delay_between_batches": [480, 900],
  "vpn_remind_every": [4, 7],
  "cf_wait_seconds": [7200, 14400],
  "user_agent": null,
  "ua_rotate_every_batches": 3
}
```

### Referencia de parámetros

| Parámetro                  | Tipo          | Por defecto  | Descripción                                                                 |
|----------------------------|---------------|--------------|-----------------------------------------------------------------------------|
| `last_output`              | string        | Auto         | Ruta de salida usada por defecto                                            |
| `deep_mode_threshold`      | int           | `10`         | A partir de cuántas URLs se activa el Modo Profundo                         |
| `batch_size`               | int           | `25`         | Número de URLs por lote en Modo Profundo                                    |
| `delay_between_downloads`  | [min, max]    | `[5, 9]`     | Segundos de pausa entre descargas individuales (se elige aleatoriamente)    |
| `delay_between_batches`    | [min, max]    | `[480, 900]` | Segundos de pausa entre lotes (8–15 min por defecto)                        |
| `vpn_remind_every`         | [min, max]    | `[4, 7]`     | Cada cuántos lotes aparece el aviso de cambio de IP/VPN                     |
| `cf_wait_seconds`          | [min, max]    | `[7200, 14400]` | Segundos de espera al detectar bloqueo Cloudflare (2–4 horas)            |
| `user_agent`               | string / null | `null`       | User-Agent fijo. Si es `null`, rota automáticamente entre los predefinidos  |
| `ua_rotate_every_batches`  | int           | `3`          | Cambia el User-Agent cada N lotes. `0` desactiva la rotación                |

> **Nota sobre `user_agent`:** cuando es `null`, TMD elige aleatoriamente entre 7 User-Agents predefinidos (Chrome Android, Chrome Desktop, Firefox). Puedes fijar uno concreto o escribir uno personalizado desde el menú de Configuración.

---

## Metadatos externos (TMOH.json)

El scraper de `tmoRojo` puede enriquecer el `ComicInfo.xml` con datos de un archivo JSON externo llamado `TMOH.json`, colocado en la raíz del proyecto.

**Formato esperado:**

```json
[
  {
    "url":         "/contents/69b6fd0b4a6fa",
    "title":       "Título del manga",
    "artist":      "Nombre del artista",
    "author":      "Nombre del autor",
    "description": "Sinopsis del manga...",
    "genre":       "Hentai",
    "chapters":    [
      { "chapterNumber": "1" }
    ]
  }
]
```

**Cómo funciona el emparejamiento:**

TMD extrae el ID del final de la URL en ambos lados y los compara:

```
URL descargada : https://un-sitio.com/contents/69b6fd0b4a6fa
Campo en JSON  : "url": "/contents/69b6fd0b4a6fa"
ID extraído    : 69b6fd0b4a6fa  ← coincidencia
```

Los datos del JSON tienen **prioridad** sobre el scraping web. Si no existe `TMOH.json` o no hay entrada para un ID concreto, TMD usa la metadata scrapeada de la página normalmente.

Los campos reconocidos son: `title` → `Title`/`Series`, `artist` + `author` → `Writer`, `description` → `Summary`, `genre` → `Genre`/`Tags`, `chapters[0].chapterNumber` → `Number`.

---

## Actualizaciones

TMD incluye un actualizador automático basado en `git pull`. Requiere que hayas instalado TMD con `git clone` (es el método de instalación estándar).

```bash
# Comprobar si hay versión nueva y actualizar
tmd --update

# Actualizar sin confirmación (útil en scripts)
tmd --update --yes
```

**Qué hace el actualizador:**

1. Comprueba que la instalación es un repositorio git válido
2. Muestra la versión local instalada (`v2.0`) y la última disponible en el remoto
3. Informa de cuántos commits lleva el remoto por delante
4. Avisa si tienes cambios locales sin commitear o si estás en una rama no estándar
5. Pide confirmación antes de actualizar (salvo con `--yes`)
6. Ejecuta `git pull --ff-only` — solo avance rápido, nunca sobreescribe cambios locales
7. Indica cómo reiniciar el programa tras la actualización

**Si la actualización falla** (por ejemplo, tienes cambios locales en conflicto):

```bash
# Guarda tus cambios temporalmente
git stash

# Actualiza
tmd --update

# Recupera tus cambios
git stash pop
```

**Para deshacer una actualización:**

```bash
git reset --hard "HEAD@{1}"
```

---

## Estructura de salida

Los archivos se organizan automáticamente por serie:

```
Manga/
└── Nombre de la Serie/
    ├── nombre-capitulo-1.cbz
    ├── nombre-capitulo-2.cbz
    └── ...
```

Para **oneshots** (manga completo en una sola URL):

```
Manga/
└── Loca por Ti/
    └── 24514-loca-por-ti.cbz
```

La carpeta de serie se toma del campo `Series` que retorna el scraper en su metadata. Si el scraper no lo define, se usa el ID del capítulo como nombre de carpeta.

---

## Estructura del proyecto

```
TMDownloader/
│   main.py                  # Punto de entrada y menú interactivo
│   lista.txt                # Lista de URLs para descarga en lote
│   TMOH.json                # (opcional) Metadatos externos para tmoh.com
│   .tmo_config.json         # Configuración persistente (generado automáticamente)
│   .tmd_progress.json       # Estado del lote actual para reanudación (generado automáticamente)
│   downloads_history.txt    # Historial de descargas (generado automáticamente)
│
├── core/
│       Session.py           # Gestión de sesión HTTP (cloudscraper / requests)
│       DownloadEngine.py    # Descarga paralela con barra de progreso
│       ScraperFactory.py    # Selección automática de scraper por URL
│
├── scrapers/
│       BaseScraper.py       # Clase base abstracta para nuevos scrapers
│       TMOHentaiScraper.py  # Scraper tmoh.com (con soporte TMOH.json)
│       LectorHentaiScraper.py
│
└── utils/
        FileManager.py       # Empaquetado .cbz y organización de carpetas
        ComicInfo.py         # Generación de ComicInfo.xml
        ImageConverter.py    # Conversión a JPG / AVIF
        BatchManager.py      # Lote normal y Modo Profundo con reanudación
        history.py           # Historial de descargas y estado de progreso
        config.py            # Configuración, plataforma y User-Agents
        updater.py           # Actualización automática vía git pull
        ui.py                # Banner con versión, colores ANSI, helpers de input
```

---

## Sitios soportados

| Sitio               | Scraper                  | Estado   |
|---------------------|--------------------------|----------|
| `tmoRojo`           | `TMOHentaiScraper`       | ✓ Activo |
| `lectorhentai.com`  | `LectorHentaiScraper`    | ✓ Activo |
| ~~`onfmangas.com`~~ | ~~`ONFMangasScraper`~~   | ✗ Roto   |

---

## Añadir soporte para un nuevo sitio

### 1. Crear el scraper

Crea `scrapers/NuevoSitioScraper.py` heredando de `BaseScraper`. Los tres métodos `@abstractmethod` son obligatorios; `get_metadata` es opcional pero muy recomendado.

```python
# scrapers/NuevoSitioScraper.py
from scrapers.BaseScraper import BaseScraper
import re
from pathlib import Path


class NuevoSitioScraper(BaseScraper):

    _source_name = "NuevoSitio"
    _BASE        = "https://nuevositio.com"

    def matches(self, url: str) -> bool:
        return "nuevositio.com" in url

    def extract_id(self, url: str) -> str:
        m = re.search(r"/manga/([^/?#]+)", url)
        return m.group(1) if m else url.rstrip("/").split("/")[-1]

    def get_image_tasks(self, session, cid: str, dest_dir) -> list:
        manga_url  = f"{self._BASE}/manga/{cid}"
        image_urls = self._scrape_image_urls(session, manga_url)
        tasks = []
        for i, img_url in enumerate(image_urls):
            ext  = self._guess_ext(img_url)
            dest = Path(dest_dir) / f"{i:03d}{ext}"
            tasks.append((img_url, dest, manga_url))
        return tasks

    def get_metadata(self, session, cid: str) -> dict:
        meta = super().get_metadata(session, cid)
        try:
            resp = session.get(f"{self._BASE}/manga/{cid}", timeout=15)
            m = re.search(r'<h1[^>]*>([^<]+)</h1>', resp.text)
            if m:
                title = m.group(1).strip()
                meta["Title"]  = title
                meta["Series"] = title
            meta["Web"] = f"{self._BASE}/manga/{cid}"
        except Exception:
            pass
        return meta

    def _scrape_image_urls(self, session, manga_url: str) -> list[str]:
        return []  # implementar según el sitio

    def _guess_ext(self, url: str) -> str:
        m = re.search(r'\.(webp|jpg|jpeg|png|gif)(?:[?#]|$)', url, re.IGNORECASE)
        return f".{m.group(1).lower()}" if m else ".jpg"
```

### 2. Registrar el scraper

```python
# core/ScraperFactory.py
from scrapers.TMOHentaiScraper    import TMOHentaiScraper
from scrapers.LectorHentaiScraper import LectorHentaiScraper
from scrapers.NuevoSitioScraper   import NuevoSitioScraper   # ← añadir

class ScraperFactory:
    _scrapers = [
        TMOHentaiScraper(),
        LectorHentaiScraper(),
        NuevoSitioScraper(),   # ← añadir aquí
    ]

    @classmethod
    def get_scraper(cls, url: str):
        for s in cls._scrapers:
            if s.matches(url):
                return s
        return None
```

### Referencia rápida de la interfaz

| Método                    | Obligatorio | Descripción                                                        |
|---------------------------|-------------|--------------------------------------------------------------------|
| `matches(url)`            | ✓           | Decide si este scraper maneja la URL                               |
| `extract_id(url)`         | ✓           | ID único del manga/capítulo (nombre del .cbz y carpeta temporal)   |
| `get_image_tasks(...)`    | ✓           | Lista de `(url, dest_path, referer)` para descargar               |
| `get_metadata(...)`       | —           | Dict con campos de ComicInfo.xml; `Series` define la carpeta final |
| `is_multi_chapter(url)`   | —           | Retorna `True` si la URL es una página de serie con varios caps    |
| `get_chapters(...)`       | —           | Lista de capítulos para series multi-capítulo                      |
| `get_series_metadata(...)`| —           | Metadata de la serie completa (para series multi-capítulo)         |

---

## Dependencias

| Paquete              | Uso                                  | Obligatorio              |
|----------------------|--------------------------------------|--------------------------|
| `requests`           | Peticiones HTTP base                 | ✓                        |
| `cloudscraper`       | Bypass de protecciones anti-bot      | ✓                        |
| `Pillow`             | Conversión de imágenes a JPG/AVIF    | Solo si usas `--format`  |
| `pillow-avif-plugin` | Soporte AVIF en Pillow antiguo       | Opcional                 |

Las dependencias obligatorias se instalan automáticamente al ejecutar TMD por primera vez.

---

## Notas

- El `.cbz` es compatible con cualquier lector que soporte el estándar ComicRack (`ComicInfo.xml`): **Mihon**, **Tachiyomi**, **Komga**, **Kavita**, **YACReader**, etc.
- En Termux, AVIF puede no estar disponible si `libavif` no está compilado. El script cae automáticamente a JPG en ese caso.
- Las cookies en formato Netscape (exportadas con extensiones como _Get cookies.txt_) se pueden pasar con `--cookies archivo.txt` para sitios que requieren sesión.
- Si una descarga falla parcialmente, los archivos temporales se conservan en la carpeta de trabajo para revisión manual.
- El historial se guarda en `downloads_history.txt`. Si tenías el archivo antiguo `.tmohentai_history.txt`, se migra automáticamente en la primera ejecución.
- El estado de reanudación (`.tmd_progress.json`) se basa en un hash del archivo `lista.txt`. Si modificas la lista entre sesiones, TMD detectará el cambio y preguntará si empezar de cero.

## Licencia

Distribuido bajo la [Licencia MIT](LICENSE).
