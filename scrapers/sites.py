# /scrapers/sites.py
"""
Registro central de todos los dominios y URLs base que usa TMD.
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
