# TMD — Manga Downloader

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Android%20|%20Windows-green.svg)

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
  - [Estructura de salida](#estructura-de-salida)
  - [Estructura del proyecto](#estructura-del-proyecto)
  - [Sitios soportados](#sitios-soportados)
  - [Añadir soporte para un nuevo sitio](#añadir-soporte-para-un-nuevo-sitio)
    - [1. Crear el scraper](#1-crear-el-scraper)
    - [2. Registrar el scraper](#2-registrar-el-scraper)
    - [Referencia rápida de la interfaz](#referencia-rápida-de-la-interfaz)
  - [Dependencias](#dependencias)
  - [Notas](#notas)

---

## Características

- Descarga individual o en lote desde un archivo `lista.txt`
- Empaqueta las imágenes en `.cbz` compatible con lectores como Mihon, Komga o Kavita
- Genera `ComicInfo.xml` automáticamente con metadata del manga (título, autor, géneros, tags, idioma, año, etc.)
- Organiza la salida en carpetas por serie.
- Conversión opcional de imágenes a **JPG** o **AVIF**
- Historial de descargas

---

## Instalación

### Termux (Android)
1.- Preparamos el entorno

```bash
pkg update && pkg upgrade -y && pkg install python git -y
```
2.- Permitimos de Termux acceda al almacenamiento

```Bash
termux-setup-storage
```

3.- Instalamos TMDownloader

```bash
git clone https://github.com/ONII404/TMDownloader.git /storage/emulated/0/TMDownloader
```
4.- Configurar alias

```Bash
echo "alias tmd='cd /storage/emulated/0/TMDownloader && python3 main.py'" >> ~/.bashrc && source ~/.bashrc && echo -e "\n✅ Instalado. Ahora puedes usar: tmd"
```

### Windows
1.- Requisitos previos

- **Python 3**: Descárgalo de [python.org](https://www.python.org/). **_Importante_**: _Marca la casilla "Add Python to PATH" durante la instalación_.
- **Git**: Descárgalo de [git-scm.com](https://git-scm.com/).

2.- Instalación

```powershell
git clone https://github.com/ONII404/TMDownloader.git $HOME\TMDownloader && cd TMDownloader
```

3.- Configurar alias (Recomendado)
>    De lo contrario tendras que usar `python3 main.py` en la ubicacion donde este TMDownloader.
> - *Ejecuta PowerShell como administrador si es la primera vez que configuras scripts*.


```powershell
# 1. Habilitar ejecución de scripts locales (necesario para que el perfil cargue)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

# 2. Crear perfil si no existe
if (!(Test-Path $PROFILE)) { New-Item -Type File -Path $PROFILE -Force }

# 3. Añadir la función solo si no existe ya en el archivo
$functionCode = "`nfunction tmd { python `$HOME\TMDownloader\main.py `$args }"
if (!(Select-String -Path $PROFILE -Pattern "function tmd")) {
    Add-Content $PROFILE $functionCode
    Write-Host "✅ Alias 'tmd' configurado correctamente." -ForegroundColor Green
} else {
    Write-Host "ℹ️ El alias 'tmd' ya estaba configurado." -ForegroundColor Yellow
}
```

4.- Reinicia la terminal para poder empezar a usar el comando

> Las dependencias (`requests`, `cloudscraper`) se instalan solas la primera vez. `Pillow` solo es necesario si usas `--format`.

---

## Uso

### Menú interactivo

Usar `tmd` ejecutara el Menú
```
  MENU PRINCIPAL
  [1] Descargar manga
  [2] Descarga en lote  (.txt)
  [3] Ver historial
  [4] Salir
```

### Línea de comandos

```bash
# Descarga individual
tmd https://tmohentai.com/contents/69b6fd0b4a6fa

# Con ruta de salida y conversión a JPG
tmd https://tmohentai.com/contents/69b6fd0b4a6fa -o ~/Manga -f jpg

# Descarga en lote desde lista.txt
tmd --batch

# Lote con ruta de salida
tmd --batch -o /storage/emulated/0/Manga
```

| Argumento   | Corto | Descripción                                   |
|-------------|-------|-----------------------------------------------|
| `url`       | —     | URL del manga a descargar                     |
| `--batch`   | `-b`  | Activa el modo lote (lee `lista.txt`)         |
| `--output`  | `-o`  | Ruta de salida                                |
| `--format`  | `-f`  | Convierte imágenes: `jpg` o `avif`            |
| `--cookies` | `-c`  | Archivo de cookies en formato Netscape        |

---

## Descarga en lote

Crea o edita el archivo `lista.txt` en la raíz del proyecto. Si no existe, se genera automáticamente con instrucciones la primera vez que usas la opción de lote.

```
# Una URL por línea. Las líneas con # son comentarios.
https://tmohentai.com/contents/69b6fd0b4a6fa
https://lectorhentai.com/manga/24514/loca-por-ti
https://tmohentai.com/contents/otro_id_aqui
```

Entre cada descarga se aplica una pausa automática de **5 segundos** para evitar rate-limiting. Este valor es configurable en `utils/BatchManager.py` (constante `DELAY_BETWEEN_DOWNLOADS`).

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

Para **oneshots** (un manga completo en una sola URL), el `.cbz` queda dentro de una carpeta con el mismo nombre:

```
Manga/
└── Loca por Ti/
    └── 24514-loca-por-ti.cbz
```

La carpeta de serie se toma del campo `Series` que retorna el scraper en su metadata. Si el scraper no lo define, se usa el ID del capítulo como nombre de carpeta.

---

## Estructura del proyecto

```
tmd-downloader/
│   main.py               # Punto de entrada
│   lista.txt             # Lista de URLs para descarga en lote
│
├── core/
│       Session.py        # Gestión de sesión HTTP (cloudscraper / requests)
│       DownloadEngine.py # Descarga paralela de imágenes con barra de progreso
│       ScraperFactory.py # Selección automática de scraper por URL
│
├── scrapers/
│       BaseScraper.py    # Clase base abstracta para nuevos scrapers
│       TMOHentaiScraper.py
│       LectorHentaiScraper.py
│
└── utils/
        FileManager.py    # Empaquetado .cbz y organización de carpetas
        ComicInfo.py      # Generación de ComicInfo.xml
        ImageConverter.py # Conversión a JPG / AVIF
        BatchManager.py   # Lógica de descarga en lote con pausas
        history.py        # Historial de descargas
        config.py         # Detección de plataforma y persistencia de config
        ui.py             # Colores ANSI, banner, helpers de input
```

---

## Sitios soportados

| Sitio               | Scraper                 |
|---------------------|-------------------------|
| `tmohentai.com`     | `TMOHentaiScraper`      |
| `lectorhentai.com`  | `LectorHentaiScraper`   |
| ~~`onfmangas.com`~~ | ~~`ONFMangasScraper`~~  | # Roto


---

## Añadir soporte para un nuevo sitio

### 1. Crear el scraper

Crea el archivo `scrapers/NuevoSitioScraper.py` heredando de `BaseScraper`.
Los tres métodos marcados como `@abstractmethod` son **obligatorios**. `get_metadata` es opcional pero recomendado.

```python
# scrapers/NuevoSitioScraper.py
from scrapers.BaseScraper import BaseScraper
import re
from pathlib import Path


class NuevoSitioScraper(BaseScraper):

    _source_name = "NuevoSitio"
    _BASE        = "https://nuevositio.com"

    def matches(self, url: str) -> bool:
        """Retorna True si esta clase es la indicada para manejar la URL."""
        return "nuevositio.com" in url

    def extract_id(self, url: str) -> str:
        """
        Extrae un identificador único del manga/capítulo desde la URL.
        Se usa como nombre de la carpeta temporal y del .cbz resultante.

        Ejemplo: 'https://nuevositio.com/manga/mi-manga-123'
                 → 'mi-manga-123'
        """
        m = re.search(r"/manga/([^/?#]+)", url)
        return m.group(1) if m else url.rstrip("/").split("/")[-1]

    def get_image_tasks(self, session, cid: str, dest_dir) -> list:
        """
        Retorna la lista de imágenes a descargar como tuplas:
            (url_imagen, ruta_destino, referer)

        - url_imagen  : URL directa de la imagen
        - ruta_destino: Path donde se guardará el archivo
        - referer     : URL que se envía como Referer en el header HTTP

        El DownloadEngine descarga todas estas tuplas en paralelo.
        """
        manga_url = f"{self._BASE}/manga/{cid}"
        referer   = manga_url

        # --- tu lógica para obtener las URLs de imagen ---
        image_urls = self._scrape_image_urls(session, manga_url)

        tasks = []
        for i, img_url in enumerate(image_urls):
            ext  = self._guess_ext(img_url)
            dest = Path(dest_dir) / f"{i:03d}{ext}"
            tasks.append((img_url, dest, referer))

        return tasks

    def get_metadata(self, session, cid: str) -> dict:
        """
        Opcional. Retorna un dict con los campos de ComicInfo.xml.
        Si no se implementa, BaseScraper provee valores genéricos.

        Claves reconocidas:
            Title, Series, Number, Year, Writer, Publisher,
            Genre, Tags, LanguageISO, Source, Web, Summary,
            BlackAndWhite, Manga, PageCount

        'Series' es especialmente importante: determina el nombre
        de la carpeta donde se guardará el .cbz.
        Para oneshots, Series == Title.
        Para series multi-capítulo, Series es el nombre de la serie
        y Title puede incluir el nombre del capítulo.
        """
        meta = super().get_metadata(session, cid)   # fallbacks genéricos

        try:
            resp = session.get(f"{self._BASE}/manga/{cid}", timeout=15)
            html = resp.text

            # --- extrae los campos que puedas ---
            m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            if m:
                title = m.group(1).strip()
                meta["Title"]  = title
                meta["Series"] = title   # oneshot: Series == Title

            meta["Web"] = f"{self._BASE}/manga/{cid}"

        except Exception:
            pass

        return meta

    # ── Helpers internos (privados, no forman parte de la interfaz) ──────────

    def _scrape_image_urls(self, session, manga_url: str) -> list[str]:
        """Lógica específica del sitio para obtener las URLs de imagen."""
        # implementar según la estructura del sitio
        return []

    def _guess_ext(self, url: str) -> str:
        m = re.search(r'\.(webp|jpg|jpeg|png|gif)(?:[?#]|$)', url, re.IGNORECASE)
        return f".{m.group(1).lower()}" if m else ".jpg"
```

### 2. Registrar el scraper

Añade tu scraper en `core/ScraperFactory.py`. El orden importa: el primer scraper cuyo `matches()` retorne `True` es el que se usa.

```python
# core/ScraperFactory.py
from scrapers.TMOHentaiScraper    import TMOHentaiScraper
from scrapers.LectorHentaiScraper import LectorHentaiScraper
from scrapers.NuevoSitioScraper   import NuevoSitioScraper   # ← añadir import

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

| Método           | Obligatorio | Descripción                                                        |
|------------------|-------------|--------------------------------------------------------------------|
| `matches(url)`   | ✓           | Decide si este scraper maneja la URL                               |
| `extract_id(url)`| ✓           | ID único del manga/capítulo (nombre del .cbz y carpeta temporal)   |
| `get_image_tasks`| ✓           | Lista de `(url, dest_path, referer)` para descargar               |
| `get_metadata`   | —           | Dict con campos de ComicInfo.xml; `Series` define la carpeta final |

---

## Dependencias

| Paquete              | Uso                                  | Obligatorio              |
|----------------------|--------------------------------------|--------------------------|
| `requests`           | Peticiones HTTP base                 | ✓                        |
| `cloudscraper`       | Bypass de protecciones anti-bot      | ✓                        |
| `Pillow`             | Conversión de imágenes a JPG/AVIF    | Solo si usas `--format`  |
| `pillow-avif-plugin` | Soporte AVIF en Pillow antiguo       | Opcional                 |

---

## Notas

- El `.cbz` generado es compatible con cualquier lector que soporte el estándar ComicRack (`ComicInfo.xml`): **Mihon**, **Tachiyomi**, **Komga**, **Kavita**, **YACReader**, etc.
- En Termux, AVIF puede no estar disponible si `libavif` no está compilado. El script cae automáticamente a JPG en ese caso.
- Las cookies en formato Netscape (exportadas con extensiones como _Get cookies.txt_) se pueden pasar con `--cookies archivo.txt` para sitios que requieren sesión.
- Si una descarga falla parcialmente, los archivos temporales se conservan en la carpeta de trabajo para revisión manual.
