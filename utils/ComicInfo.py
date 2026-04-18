# /utils/ComicInfo.py
"""
Genera el archivo ComicInfo.xml según el estándar Anansi/ComicRack.
Todos los campos son opcionales; si llegan vacíos/None se usan valores genéricos.
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path


# Campos que se escriben y sus fallbacks genéricos
_DEFAULTS = {
    "Title":       "Desconocido",
    "Series":      "Desconocido",
    "Number":      "1",
    "Year":        None,          # None = omitir si no hay valor
    "Writer":      "Desconocido",
    "Publisher":   "Desconocido",
    "Genre":       "",
    "Tags":        "",
    "LanguageISO": "es",
    "Source":      "",
    "Web":         "",
    "Summary":     "",
    "BlackAndWhite": "Unknown",
    "Manga":       "Yes",
}


def build_comicinfo(meta: dict | None, image_count: int = 0) -> str:
    """
    Construye el contenido XML de ComicInfo.xml.

    meta puede contener cualquier subconjunto de las claves de _DEFAULTS
    más 'PageCount' (se calcula automáticamente si no viene).
    Si meta es None o vacío, todo queda con valores genéricos.
    """
    meta = meta or {}

    root = ET.Element("ComicInfo")
    root.set("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")

    for field, default in _DEFAULTS.items():
        value = meta.get(field, default)
        if value is None:           # campo opcional sin valor → omitir
            continue
        ET.SubElement(root, field).text = str(value)

    # PageCount: viene en meta o se usa el conteo real de imágenes
    page_count = meta.get("PageCount", image_count)
    if page_count:
        ET.SubElement(root, "PageCount").text = str(page_count)

    # Pretty-print
    raw = ET.tostring(root, encoding="unicode")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ")
    # minidom agrega <?xml ...?> — lo conservamos
    return pretty


def write_comicinfo(folder_path: Path, meta: dict | None, image_count: int = 0) -> Path:
    """
    Escribe ComicInfo.xml dentro de folder_path.
    Retorna la ruta del archivo generado.
    """
    xml_content = build_comicinfo(meta, image_count)
    out = folder_path / "ComicInfo.xml"
    out.write_text(xml_content, encoding="utf-8")
    return out
