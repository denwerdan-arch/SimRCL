"""Run simready_inspect.py in an external Python that has `usd-core`.

Cinema 4D ships no `pxr`, and loading a second USD build into its process risks crashing the whole
session, so USD is read out of process and only JSON crosses the boundary.
"""
import json
import os
import subprocess

PACKAGE = "usd-core"
INSPECT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simready_inspect.py")
PYTHON_CANDIDATES = (["py", "-3"], ["python3"], ["python"])
INSTALL_TIMEOUT_SECONDS = 600
INSPECT_TIMEOUT_SECONDS = 120
# A console window flashing per subprocess is noise on Windows.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class RuntimeSetupError(Exception):
    """Raised when the external USD runtime cannot be found, installed or executed."""


def _run(command, timeout):
    """Run command and return the CompletedProcess; never raises on a non-zero exit."""
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                          creationflags=_NO_WINDOW)


def _works(command):
    """True if `command --version` runs and prints a Python 3 version."""
    try:
        result = _run(command + ["--version"], 15)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and "Python 3" in (result.stdout + result.stderr)


def find_python():
    """Return the first working system Python 3 command as a list, or raise RuntimeSetupError."""
    for command in PYTHON_CANDIDATES:
        if _works(command):
            return command
    raise RuntimeSetupError("Python 3 was not found. Install it from python.org and retry.")


def usd_site_dir(base_dir):
    """Folder where usd-core is installed; it stays separate from the user's global site-packages."""
    return os.path.join(base_dir, "usd_core")


PROBE = "import sys; sys.path.insert(0, sys.argv[1]); from pxr import Usd; Usd.Stage.CreateInMemory()"
_WORKING = set()  # (python, base_dir) pairs probed this session, so the probe costs one start-up per session


def usd_works(python, base_dir):
    """True when this Python can import usd-core from the private folder and open a stage.

    A folder check is not enough: a half-deleted install still has its pxr folder, and a wheel built for
    another Python version (py -3 moved from 3.13 to 3.14) has every file but cannot load.
    """
    key = (tuple(python), base_dir)
    if key in _WORKING:
        return True
    try:
        result = _run(python + ["-I", "-c", PROBE, usd_site_dir(base_dir)], 60)
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode == 0:
        _WORKING.add(key)
    return result.returncode == 0


def install_usd_core(python, base_dir):
    """pip-install usd-core into the private site folder, replacing a broken copy; raises RuntimeSetupError."""
    command = python + ["-m", "pip", "install", PACKAGE, "--target", usd_site_dir(base_dir), "--upgrade",
                        "--force-reinstall", "--disable-pip-version-check", "--no-warn-script-location", "-q"]
    result = _run(command, INSTALL_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise RuntimeSetupError("pip failed:\n" + result.stderr[-800:])


def ensure_runtime(base_dir):
    """Make sure usd-core works for the system Python (installing or repairing it) and return that Python."""
    python = find_python()
    if usd_works(python, base_dir):
        return python
    install_usd_core(python, base_dir)
    if not usd_works(python, base_dir):
        raise RuntimeSetupError("usd-core was installed but does not load in %s" % " ".join(python))
    return python


def inspect_asset(usd_path, base_dir):
    """Return the material/mesh description of usd_path as a dict (see simready_inspect.py)."""
    python = ensure_runtime(base_dir)
    command = python + ["-I", INSPECT_SCRIPT, usd_path, usd_site_dir(base_dir)]
    result = _run(command, INSPECT_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise RuntimeSetupError("Inspector failed:\n" + result.stderr[-800:])
    return json.loads(result.stdout)
