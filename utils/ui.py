# /utils/ui.py
import os
import sys

# ── Versión central ───────────────────────────────────────────────────────────
# Cambia SOLO este valor para actualizar la versión en toda la interfaz.
__version__ = "2.0.1"


def _c(code: str, text: str) -> str:
    """Aplica color ANSI si el terminal lo soporta."""
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def _stdout_supports_unicode() -> bool:
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "█╚═─".encode(enc)
        return True
    except Exception:
        return False


def _detect_platform_label() -> str:
    """Retorna una etiqueta corta de plataforma para el banner."""
    if sys.platform == "win32":
        return "Windows"
    home = os.environ.get("HOME", "")
    if "com.termux" in home or os.path.exists("/data/data/com.termux"):
        return "Termux"
    return "Linux"


def _cls():
    os.system("clear" if os.name != "nt" else "cls")


def _pause(msg="  Pulsa Enter para continuar..."):
    try:
        input(_c("90", msg))
    except (EOFError, KeyboardInterrupt):
        pass


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def ui_banner():
    unicode_ok = _stdout_supports_unicode()
    platform   = _detect_platform_label()
    version    = __version__

    print()
    if unicode_ok:
        # Las primeras 4 filas del ASCII art son iguales
        print(_c("96;1", "  ████████╗███╗   ███╗██████╗ "))
        print(_c("96;1", "  ╚══██╔══╝████╗ ████║██╔══██╗"))
        print(_c("97;1", "     ██║   ██╔████╔██║██║  ██║"))
        print(_c("97;1", "     ██║   ██║╚██╔╝██║██║  ██║"))
        # Última fila: las letras TMD en dorado + versión en gris sutil pegada
        print(
            _c("93;1", "     ██║   ██║ ╚═╝ ██║██████╔╝") +
            _c("90",   f"  v{version}")
        )
        print(_c("93;1", "     ╚═╝   ╚═╝     ╚═╝╚═════╝ "))
    else:
        # Fallback sin Unicode: cabecera simple con versión inline
        print(_c("96;1", "  ========================================"))
        print(
            _c("96;1", "        TMD  Manga Downloader  ") +
            _c("90",   f"v{version}    ")
        )
        print(_c("96;1", "  ========================================"))

    print()
    print(
        _c("90", "  ") +
        _c("96", "Manga Downloader") +
        _c("90", f"  —  {platform}")
    )
    print(_c("90", "  " + ("─" * 43 if unicode_ok else "-" * 43)))
