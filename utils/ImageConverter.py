# /utils/ImageConverter.py
"""
Conversión de imágenes descargadas a JPG o AVIF usando Pillow.
Si Pillow no está instalado, informa al usuario y omite la conversión.
AVIF requiere además el plugin pillow-avif-plugin o Pillow >= 9.1 con libavif.
"""
from pathlib import Path

# Formatos de imagen que reconocemos como descargados
_IMAGE_EXTS = {".webp", ".jpg", ".jpeg", ".png", ".gif"}


def _pillow_available() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def _avif_available() -> bool:
    try:
        from PIL import Image
        # Intentamos registrar el plugin si existe
        try:
            import pillow_avif  # noqa: F401
        except ImportError:
            pass
        return "avif" in Image.registered_extensions().values() or \
               "AVIF" in Image.SAVE
    except Exception:
        return False


def convert_images(folder_path: Path, target_fmt: str) -> int:
    """
    Convierte todas las imágenes en folder_path al formato target_fmt ('jpg' o 'avif').
    Las originales se eliminan si la conversión es exitosa.
    Retorna el número de imágenes convertidas.

    Si Pillow no está disponible, imprime advertencia y retorna 0.
    """
    if not _pillow_available():
        print("  [!] Pillow no está instalado. Omitiendo conversión.")
        print("      Instala con: pip install Pillow")
        return 0

    from PIL import Image

    fmt = target_fmt.lower().strip()
    if fmt not in ("jpg", "avif"):
        raise ValueError(f"Formato no soportado: {fmt}. Usa 'jpg' o 'avif'.")

    if fmt == "avif" and not _avif_available():
        print("  [!] AVIF no está disponible en tu instalación de Pillow.")
        print("      Instala con: pip install pillow-avif-plugin")
        print("  [~] Convirtiendo a JPG como alternativa...")
        fmt = "jpg"

    pil_fmt   = "JPEG" if fmt == "jpg" else "AVIF"
    out_ext   = f".{fmt}"
    save_opts = {"quality": 90} if fmt == "jpg" else {"quality": 80}

    converted = 0
    files = sorted(p for p in folder_path.iterdir()
                   if p.is_file() and p.suffix.lower() in _IMAGE_EXTS)

    for src in files:
        if src.suffix.lower() == out_ext:
            converted += 1  # ya está en el formato deseado
            continue
        dest = src.with_suffix(out_ext)
        try:
            with Image.open(src) as img:
                # JPEG no soporta transparencia — convertir a RGB
                if pil_fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")
                img.save(dest, pil_fmt, **save_opts)
            src.unlink()   # eliminar original
            converted += 1
        except Exception as e:
            print(f"  [!] No se pudo convertir {src.name}: {e}")

    return converted
