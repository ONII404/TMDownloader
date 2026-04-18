# /utils/ui.py
import os
import sys


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
    print()
    if unicode_ok:
        # TMD en ASCII art
        print(_c("96;1", "  ████████╗███╗   ███╗██████╗ "))
        print(_c("96;1", "  ╚══██╔══╝████╗ ████║██╔══██╗"))
        print(_c("97;1", "     ██║   ██╔████╔██║██║  ██║"))
        print(_c("97;1", "     ██║   ██║╚██╔╝██║██║  ██║"))
        print(_c("93;1", "     ██║   ██║ ╚═╝ ██║██████╔╝"))
        print(_c("93;1", "     ╚═╝   ╚═╝     ╚═╝╚═════╝ "))
    else:
        print(_c("96;1", "  ========================================"))
        print(_c("96;1", "           TMD  Manga Downloader          "))
        print(_c("96;1", "  ========================================"))
    print()
    print(_c("90", "  ") + _c("96", "Manga Downloader") +
          _c("90", "  -  Arquitectura Modular  -  Termux"))
    print(_c("90", "  " + ("─" * 43 if unicode_ok else "-" * 43)))