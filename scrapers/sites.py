# /scrapers/sites.py
"""
Registro central de todos los dominios y URLs base que usa TMD.

Por qué existe este archivo:
  - Las URLs de los sitios soportados no son credenciales ni secretos,
    pero centralizarlas aquí tiene dos ventajas:
    1. Un único lugar donde actualizar si un sitio cambia de dominio.
    2. El README y los docstrings de los scrapers pueden referirse al
       nombre del scraper sin exponer URLs explícitas en la documentación.

Por qué NO se usa base64 u ofuscación:
  - Las URLs de los scrapers no son secretos. Cualquiera puede abrirlas
    en un navegador. Ofuscarlas daría una falsa sensación de seguridad
    sin proteger nada real.
  - Si GitHub Secret Scanning marcó alguna línea, es casi seguro por una
    cookie, token o clave de API embebida en ella — no por la URL en sí.
    La solución a eso es variables de entorno o un archivo .env, no base64.

Qué sí se puede mantener privado:
  - Cookies de sesión, tokens de autenticación, claves de API.
    → Usar --cookies archivo.txt o variables de entorno (ver config.py).
  - El archivo lista.txt con URLs de contenido específico.
    → Ya está en .gitignore (ver .gitignore en la raíz).
"""
from __future__ import annotations

# ── Dominios base ─────────────────────────────────────────────────────────────

TMO_BASE     = "https://tmohentai.com"
LECTOR_BASE  = "https://lectorhentai.com"
ONF_BASE     = "https://onfmangas.com"

# ── CDN hosts de TMOHentai ────────────────────────────────────────────────────

TMO_CDN_HOSTS: list[str] = [
    "cache1.tmohentai.com",
    "cache2.tmohentai.com",
    "cache3.tmohentai.com",
    "cache4.tmohentai.com",
]

# ── Nombres de fuente para ComicInfo.xml ──────────────────────────────────────

TMO_SOURCE_NAME    = "TMOHentai"
LECTOR_SOURCE_NAME = "LectorHentai"
ONF_SOURCE_NAME    = "ONFMangas"

# ── CDN de imágenes de LectorHentai ──────────────────────────────────────────

LECTOR_CDN_DOMAIN = "giolandscaping.com"
