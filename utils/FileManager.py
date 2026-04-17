# /utils/FileManager.py
import zipfile
import shutil
from pathlib import Path

from utils.ComicInfo import write_comicinfo


class FileManager:

    @staticmethod
    def prepare_dir(base_path: str, folder_name: str) -> Path:
        path = Path(base_path) / folder_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def compress_and_clean(
        folder_path: Path,
        meta: dict | None = None,
        conv_format: str | None = None,
    ) -> Path:
        """
        1. (Opcional) Convierte imágenes a conv_format ('jpg' o 'avif').
        2. Escribe ComicInfo.xml en folder_path con la metadata dada.
        3. Empaqueta todo en un .cbz (ZIP renombrado).
        4. Elimina la carpeta temporal.
        Retorna la ruta del .cbz generado.
        """
        # 1 ── Conversión de imágenes
        if conv_format:
            from utils.ImageConverter import convert_images
            n = convert_images(folder_path, conv_format)
            print(f"  Imágenes convertidas a {conv_format.upper()}: {n}")

        # 2 ── Contar imágenes y escribir ComicInfo.xml
        image_files = [
            f for f in folder_path.iterdir()
            if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".avif"}
        ]
        write_comicinfo(folder_path, meta, image_count=len(image_files))

        # 3 ── Empaquetar como .cbz
        cbz_path = folder_path.parent / f"{folder_path.name}.cbz"
        with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in sorted(folder_path.iterdir()):
                if file.is_file():
                    zf.write(file, arcname=file.name)

        # 4 ── Limpiar carpeta temporal
        shutil.rmtree(folder_path)
        return cbz_path