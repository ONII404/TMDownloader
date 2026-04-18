# /utils/FileManager.py
"""
Gestión de carpetas y empaquetado .cbz.

Estructura de salida:
  - Oneshot  (series_name == None o igual a chapter_name):
      output_path / Series / Series.cbz

  - Multi-capítulo (series_name distinto al nombre del capítulo):
      output_path / Series / Capitulo.cbz

La diferencia la decide el scraper a través del campo "Series" en meta
y el parámetro series_name que se pasa desde main.py.
"""
import zipfile
import shutil
from pathlib import Path

from utils.ComicInfo import write_comicinfo


class FileManager:

    @staticmethod
    def prepare_dir(base_path: str, folder_name: str) -> Path:
        """Crea y retorna una carpeta temporal de trabajo."""
        path = Path(base_path) / folder_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def compress_and_clean(
        folder_path: Path,
        meta: dict | None = None,
        conv_format: str | None = None,
        series_name: str | None = None,
    ) -> Path:
        """
        1. (Opcional) Convierte imágenes a conv_format ('jpg' o 'avif').
        2. Escribe ComicInfo.xml en folder_path con la metadata dada.
        3. Empaqueta todo en un .cbz (ZIP renombrado).
        4. Mueve el .cbz a la carpeta de serie correcta.
        5. Elimina la carpeta temporal.

        Estructura resultante
        ─────────────────────
        Oneshot  →  output / SeriesName / SeriesName.cbz
        Capítulo →  output / SeriesName / ChapterName.cbz

        Retorna la ruta del .cbz generado.

        Parámetros
        ──────────
        series_name : nombre de la serie (para subcarpeta).
                      Si es None se usa el nombre de folder_path como serie.
        """
        meta = meta or {}

        # 1 ── Conversión de imágenes
        if conv_format:
            from utils.ImageConverter import convert_images
            n = convert_images(folder_path, conv_format)
            print(f"  Imágenes convertidas a {conv_format.upper()}: {n}")

        # 2 ── Contar imágenes y escribir ComicInfo.xml
        image_exts = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
        image_files = [
            f for f in folder_path.iterdir()
            if f.is_file() and f.suffix.lower() in image_exts
        ]
        write_comicinfo(folder_path, meta, image_count=len(image_files))

        # 3 ── Nombre del .cbz = nombre de la carpeta temporal (= cid / chapter id)
        cbz_name     = f"{folder_path.name}.cbz"
        temp_cbz     = folder_path.parent / f"_tmp_{cbz_name}"

        with zipfile.ZipFile(temp_cbz, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in sorted(folder_path.iterdir()):
                if file.is_file():
                    zf.write(file, arcname=file.name)

        # 4 ── Limpiar carpeta temporal de imágenes
        shutil.rmtree(folder_path)

        # 5 ── Determinar carpeta de destino (serie)
        #
        # series_name puede venir de:
        #   a) meta["Series"]  – lo rellenó el scraper
        #   b) el parámetro explícito series_name
        #   c) fallback: el propio nombre del capítulo (oneshot)
        #
        effective_series = (
            series_name
            or meta.get("Series")
            or folder_path.name
        )

        # Sanitizar el nombre de carpeta (quitar caracteres problemáticos)
        safe_series = _safe_dirname(effective_series)

        final_dir = folder_path.parent / safe_series
        final_dir.mkdir(parents=True, exist_ok=True)

        final_cbz = final_dir / cbz_name
        shutil.move(str(temp_cbz), str(final_cbz))

        return final_cbz


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_dirname(name: str) -> str:
    """
    Elimina o reemplaza caracteres que no son válidos en nombres de carpeta
    en Windows, Linux y Android/Termux.
    """
    # Caracteres prohibidos en Windows: \ / : * ? " < > |
    # En Linux/Android son más permisivos, pero los evitamos igualmente.
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    # Eliminar puntos/espacios al inicio o final
    name = name.strip(". ")
    return name or "Sin_titulo"