# TMD — Manga Downloader

Descargador modular de manga con soporte para múltiples sitios, empaquetado en `.cbz` con metadatos `ComicInfo.xml`. Diseñado para funcionar en **Android (Termux)**, **Linux** y **Windows**.

---

## Características

- Descarga individual o en lote desde un archivo `lista.txt`
- Empaqueta las imágenes en `.cbz` compatible con lectores como Mihon, Komga o Kavita
- Genera `ComicInfo.xml` automáticamente con metadata del manga
- Conversión opcional de imágenes a **JPG** o **AVIF**
- Detecta la plataforma y sugiere la ruta de salida correcta
- Historial de descargas
- Arquitectura modular: añadir soporte para nuevos sitios es sencillo

---

## Instalación

### Termux (Android)

```bash
pkg install python git
git clone https://github.com/tu-usuario/tmd-downloader
cd tmd-downloader
python main.py   # instala dependencias automáticamente en el primer arranque
```

### Linux / Windows

```bash
git clone https://github.com/tu-usuario/tmd-downloader
cd tmd-downloader
python main.py   # instala dependencias automáticamente en el primer arranque
```

> Las dependencias (`requests`, `cloudscraper`, `Pillow`) se instalan solas la primera vez que ejecutas el script. No necesitas correr `pip install` manualmente.

---

## Uso

### Menú interactivo

```bash
python main.py
```

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
python main.py https://tmohentai.com/contents/69b6fd0b4a6fa

# Con ruta de salida y conversión a JPG
python main.py https://tmohentai.com/contents/69b6fd0b4a6fa -o ~/Manga -f jpg

# Descarga en lote desde lista.txt
python main.py --batch

# Lote con ruta de salida
python main.py --batch -o /storage/emulated/0/Manga
```

| Argumento | Corto | Descripción |
|---|---|---|
| `url` | — | URL o ID del manga |
| `--batch` | `-b` | Activa el modo lote (lee `lista.txt`) |
| `--output` | `-o` | Ruta de salida |
| `--format` | `-f` | Convierte imágenes: `jpg` o `avif` |
| `--cookies` | `-c` | Archivo de cookies en formato Netscape |

---

## Descarga en lote

Crea o edita el archivo `lista.txt` en la raíz del proyecto. Si no existe, se genera automáticamente con instrucciones la primera vez que usas la opción de lote.

```
# Una URL por línea. Las líneas con # son comentarios.
https://tmohentai.com/contents/69b6fd0b4a6fa
https://tmohentai.com/contents/otro_id_aqui
69b6fd0b4a6fa
```

---

## Estructura del proyecto

```
tmd-downloader/
│   main.py              # Punto de entrada
│   lista.txt            # Lista de URLs para descarga en lote
│   requirements.txt     # Dependencias
│
├───core/
│       Session.py       # Gestión de sesión HTTP (cloudscraper / requests)
│       DownloadEngine.py# Descarga paralela de imágenes
│       ScraperFactory.py# Selección automática de scraper por URL
│
├───scrapers/
│       BaseScraper.py   # Clase base abstracta para nuevos scrapers
│       TMOHentaiScraper.py
│
└───utils/
        FileManager.py   # Empaquetado .cbz y gestión de carpetas
        ComicInfo.py     # Generación de ComicInfo.xml
        ImageConverter.py# Conversión a JPG / AVIF
        BatchManager.py  # Lógica de descarga en lote
        HistoryManager.py# Historial de descargas
        config.py        # Detección de plataforma y persistencia de config
        ui.py            # Colores ANSI, banner, helpers de input
```

---

## Añadir soporte para un nuevo sitio

1. Crea `scrapers/NuevoSitioScraper.py` heredando de `BaseScraper`:

```python
from scrapers.BaseScraper import BaseScraper

class NuevoSitioScraper(BaseScraper):
    _source_name = "NuevoSitio"

    def matches(self, url: str) -> bool:
        return "nuevositio.com" in url

    def extract_id(self, url: str) -> str:
        # extrae el ID único del manga desde la URL
        ...

    def get_image_tasks(self, session, cid: str, dest_dir) -> list:
        # retorna lista de tuplas (url_imagen, ruta_destino, referer)
        ...

    def get_metadata(self, session, cid: str) -> dict:
        # opcional: retorna dict con Title, Series, Writer, Tags, etc.
        # si no se implementa, se usan valores genéricos automáticamente
        ...
```

2. Regístralo en `core/ScraperFactory.py`:

```python
from scrapers.NuevoSitioScraper import NuevoSitioScraper

class ScraperFactory:
    _scrapers = [
        TMOHentaiScraper(),
        NuevoSitioScraper(),  # <- añadir aquí
    ]
```

---

## Dependencias

| Paquete | Uso | Obligatorio |
|---|---|---|
| `requests` | Peticiones HTTP base | ✓ |
| `cloudscraper` | Bypass de protecciones anti-bot | ✓ |
| `Pillow` | Conversión de imágenes a JPG/AVIF | Solo si usas `--format` |
| `pillow-avif-plugin` | Soporte AVIF en Pillow antiguo | Opcional |

---

## Sitios soportados

| Sitio | Scraper | Metadata |
|---|---|---|
| tmohentai.com | `TMOHentaiScraper` | Título, tags, idioma |

---

## Notas

- El archivo `.cbz` generado es compatible con cualquier lector que soporte el estándar ComicRack (`ComicInfo.xml`): **Mihon**, **Tachiyomi**, **Komga**, **Kavita**, **YACReader**, etc.
- En Termux, AVIF puede no estar disponible si `libavif` no está compilado. El script cae automáticamente a JPG en ese caso.
- Las cookies en formato Netscape (exportadas con extensiones como _Get cookies.txt_) se pueden pasar con `--cookies archivo.txt` para sitios que requieren sesión.
