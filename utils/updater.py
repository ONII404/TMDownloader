# /utils/updater.py
"""
Módulo de actualización de TMD vía git pull.

Estrategia elegida: git pull sobre el repositorio clonado.
Razones frente a la GitHub Releases API:
  - TMD se instala con git clone → el repo ya existe localmente, git es la
    herramienta natural para sincronizar.
  - No requiere dependencias extra (no GitPython): subprocess + git es
    suficiente y funciona en Termux, Linux y Windows sin instalar nada.
  - Las Releases de GitHub son opcionales para proyectos en desarrollo activo;
    mantener etiquetas sincronizadas con commits añade fricción innecesaria.
  - git pull es atómico y reversible (git reset --hard HEAD@{1}).

Flujo completo de --update:
  1. Detectar si estamos dentro de un repositorio git.
  2. Obtener la versión actual (__version__ en ui.py).
  3. Obtener la versión remota (git fetch + leer ui.py del origin).
  4. Comparar. Si ya estamos al día, informar y salir.
  5. Avisar al usuario de cambios locales o rama no estándar.
  6. Pedir confirmación (o aceptar --yes).
  7. Hacer git pull --rebase=false --ff-only para mayor seguridad.
  8. Informar resultado y cómo reiniciar.
"""
import os
import re
import sys
import subprocess
from pathlib import Path

from utils.ui import _c, __version__ as _LOCAL_VERSION

# Raíz del proyecto (un nivel arriba de /utils/)
_ROOT = Path(__file__).parent.parent


# ══════════════════════════════════════════════════════════════════════════════
# Punto de entrada principal
# ══════════════════════════════════════════════════════════════════════════════

def run_update(yes: bool = False) -> int:
    """
    Ejecuta el flujo completo de actualización.
    Retorna 0 si todo fue bien, 1 si hubo un error o el usuario canceló.
    """
    sep  = "═" * 52
    sep2 = "─" * 52

    print()
    print(_c("96;1", f"  {sep}"))
    print(_c("97;1",  "  🔄  ACTUALIZADOR DE TMD"))
    print(_c("96;1", f"  {sep}"))
    print()

    # ── 1. ¿Hay repositorio git? ──────────────────────────────────────────────
    if not _is_git_repo():
        print(_c("91;1", "  [✗] No se detectó un repositorio git en:"))
        print(_c("90",   f"      {_ROOT}"))
        print()
        print(_c("97",   "  TMD debe haberse instalado con git clone para poder"))
        print(_c("97",   "  actualizarse automáticamente. Instalación manual:"))
        print(_c("90",   "    git clone https://github.com/ONII404/TMDownloader.git"))
        return 1

    # ── 2. Versión local ──────────────────────────────────────────────────────
    local_ver = _LOCAL_VERSION
    print(_c("97",   f"  Versión actual  : ") + _c("93;1", f"v{local_ver}"))

    # ── 3. Fetch y versión remota ─────────────────────────────────────────────
    print(_c("90",    "  Consultando repositorio remoto..."), end="", flush=True)
    fetch_ok, fetch_err = _git_fetch()
    if not fetch_ok:
        print(_c("91;1", " ✗"))
        print(_c("91",   f"  [!] git fetch falló: {fetch_err}"))
        print(_c("90",    "      Comprueba tu conexión a internet."))
        return 1
    print(_c("92", " ✓"))

    remote_ver = _get_remote_version()
    if remote_ver:
        print(_c("97",  f"  Última versión  : ") + _c("92;1", f"v{remote_ver}"))
    else:
        print(_c("90",   "  Última versión  : (no se pudo determinar)"))

    # ── 4. ¿Ya está al día? ───────────────────────────────────────────────────
    commits_behind = _commits_behind()

    if commits_behind == 0:
        # Confirmado con el remoto: estamos al día
        print()
        print(_c("92;1", "  ✓  TMD ya está en la última versión. No hay nada que actualizar."))
        return 0
    elif commits_behind == -1:
        # No se pudo comparar — no asumimos nada, dejamos decidir al usuario
        print(_c("93", "  (no se pudo determinar el número de commits pendientes)"))
    else:
        print(_c("93",  f"  {commits_behind} commit(s) por detrás del remoto."))

    # ── 5. Advertencias de estado local ──────────────────────────────────────
    print()
    warnings = _check_local_state()
    if warnings:
        print(_c("93;1", f"  {sep2}"))
        print(_c("93;1",  "  ⚠  ADVERTENCIAS"))
        for w in warnings:
            print(_c("93",  f"  • {w}"))
        print(_c("93;1", f"  {sep2}"))
        print()

    # ── 6. Confirmación ───────────────────────────────────────────────────────
    if not yes:
        print(_c("97",  "  Se aplicará: git pull --ff-only"))
        print(_c("90",  "  (solo avance rápido — nunca sobreescribe tus cambios locales)"))
        print()
        confirm = _ask_confirm("  ¿Actualizar ahora? [S/n] > ")
        if not confirm:
            print(_c("90", "\n  Actualización cancelada."))
            return 1

    # ── 7. git pull ───────────────────────────────────────────────────────────
    print()
    print(_c("90", "  Aplicando actualización..."))
    success, output = _git_pull()

    print()
    if success:
        print(_c("92;1", f"  {sep}"))
        print(_c("92;1",  "  ✓  TMD actualizado correctamente"))
        if remote_ver:
            print(_c("97",  f"  Nueva versión: v{remote_ver}"))
        print(_c("92;1", f"  {sep}"))
        print()
        print(_c("97",    "  Reinicia el programa para aplicar los cambios:"))
        _print_restart_hint()
    else:
        print(_c("91;1", f"  {sep}"))
        print(_c("91;1",  "  ✗  La actualización falló"))
        print(_c("91;1", f"  {sep}"))
        print()
        print(_c("91",    f"  Detalle: {output}"))
        print()
        _print_manual_fix_hint(warnings)

    return 0 if success else 1


# ══════════════════════════════════════════════════════════════════════════════
# Operaciones git (vía subprocess)
# ══════════════════════════════════════════════════════════════════════════════

def _run_git(*args, capture: bool = True) -> tuple[bool, str]:
    """
    Ejecuta un comando git en _ROOT.
    Retorna (éxito: bool, salida/error: str).

    IMPORTANTE: siempre forzamos encoding='utf-8' + errors='replace'.
    Sin esto, Windows usa el codec del sistema (CP1252 / CP850) y explota
    al decodificar la salida de 'git show' si el archivo contiene bytes
    fuera del rango CP1252 (por ejemplo los bloques █ del banner ASCII).
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(_ROOT),
            capture_output=capture,
            text=True,
            encoding="utf-8",   # ← forzar UTF-8 en todas las plataformas
            errors="replace",   # ← sustituir bytes inválidos en vez de explotar
            timeout=30,
        )
        out = (result.stdout + result.stderr).strip()
        return result.returncode == 0, out
    except FileNotFoundError:
        return False, "git no está instalado o no está en el PATH."
    except subprocess.TimeoutExpired:
        return False, "Tiempo de espera agotado (30s)."
    except Exception as e:
        return False, str(e)


def _is_git_repo() -> bool:
    ok, _ = _run_git("rev-parse", "--git-dir")
    return ok


def _git_fetch() -> tuple[bool, str]:
    return _run_git("fetch", "--quiet", "origin")


def _git_pull() -> tuple[bool, str]:
    """
    Usa --ff-only: solo actualiza si es un avance rápido (fast-forward).
    Nunca hace merge automático que pueda crear conflictos.
    """
    return _run_git("pull", "--ff-only", "origin")


def _commits_behind() -> int:
    """Cuántos commits lleva el remoto por delante. -1 si no se puede saber."""
    ok, out = _run_git("rev-list", "--count", "HEAD..origin/HEAD")
    if ok and out.strip().isdigit():
        return int(out.strip())
    # Intentar con la rama main / master explícita
    for branch in ("origin/main", "origin/master"):
        ok, out = _run_git("rev-list", "--count", f"HEAD..{branch}")
        if ok and out.strip().isdigit():
            return int(out.strip())
    return -1


def _get_remote_version() -> str:
    """
    Lee __version__ del ui.py del origin sin hacer checkout.
    Funciona incluso si la rama local está desactualizada.
    """
    for branch in ("origin/HEAD", "origin/main", "origin/master"):
        ok, content = _run_git("show", f"{branch}:utils/ui.py")
        if ok and content:
            m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if m:
                return m.group(1)
    return ""


def _check_local_state() -> list[str]:
    """
    Comprueba el estado del repo local.
    Retorna lista de advertencias (vacía = todo limpio).
    """
    warnings = []

    # ¿Cambios sin commitear?
    ok, out = _run_git("status", "--porcelain")
    if ok and out.strip():
        warnings.append(
            "Tienes cambios locales no commiteados. "
            "--ff-only NO los sobreescribirá, pero si hay conflicto el pull fallará."
        )

    # ¿Rama distinta a main/master?
    ok, branch = _run_git("rev-parse", "--abbrev-ref", "HEAD")
    if ok:
        branch = branch.strip()
        if branch not in ("main", "master", "HEAD"):
            warnings.append(
                f"Estás en la rama '{branch}' en vez de 'main'/'master'. "
                "El pull actualizará esta rama, no main."
            )

    # ¿Stash pendiente?
    ok, stash = _run_git("stash", "list")
    if ok and stash.strip():
        count = len(stash.strip().splitlines())
        warnings.append(f"Tienes {count} entrada(s) en el stash (git stash list).")

    return warnings


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de UI
# ══════════════════════════════════════════════════════════════════════════════

def _ask_confirm(prompt: str) -> bool:
    try:
        ans = input(_c("93;1", prompt)).strip().lower()
        return ans in ("", "s", "si", "sí", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _print_restart_hint():
    """Muestra el comando exacto para reiniciar según la plataforma."""
    platform = sys.platform
    print()
    if "com.termux" in os.environ.get("HOME", "") or os.path.exists("/data/data/com.termux"):
        print(_c("90", "    tmd"))
    elif platform == "win32":
        print(_c("90", "    tmd"))
    else:
        print(_c("90", "    tmd   ó   python3 main.py"))


def _print_manual_fix_hint(warnings: list):
    """Sugiere cómo resolver el fallo según las advertencias detectadas."""
    print(_c("97", "  Posibles soluciones:"))
    if any("cambios locales" in w for w in warnings):
        print(_c("90", "    1. Guarda tus cambios:  git stash"))
        print(_c("90", "    2. Actualiza:            tmd --update"))
        print(_c("90", "    3. Recupera cambios:     git stash pop"))
    else:
        print(_c("90", "    git pull origin main"))
    print()
    print(_c("90", "  Para deshacer una actualización problemática:"))
    print(_c("90", '    git reset --hard "HEAD@{1}"'))
