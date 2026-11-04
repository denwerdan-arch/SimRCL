"""Build the release zip: python tools/build_release.py [out_dir] (default dist/).

The version comes from simready_lib/simready_ui.py (VERSION), the one place to change it. The archive holds
INSTALL.bat (the one step for users), the SimRCL plugin folder, the docs and the agent files. Tests and tools
stay out. Prints the path of the zip.
"""
import os
import re
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "simready_lib")
DOCS = ("README.md", "CHANGELOG.md", "LICENSE")


def version():
    """VERSION from simready_ui.py, read as text so the build needs no Cinema 4D."""
    text = open(os.path.join(LIB, "simready_ui.py"), encoding="utf-8").read()
    return re.search(r'^VERSION = "([^"]+)"', text, re.M).group(1)


def copy_plugin(target):
    """The folder that goes into Cinema 4D's plugins: the .pyp, its icon, the modules and the docs."""
    os.makedirs(target)
    shutil.copy2(os.path.join(ROOT, "SimRCL.pyp"), target)
    shutil.copytree(os.path.join(ROOT, "res"), os.path.join(target, "res"))
    shutil.copytree(LIB, os.path.join(target, "simready_lib"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in DOCS + ("AGENTS.md",):
        shutil.copy2(os.path.join(ROOT, name), target)


def assemble(out_dir, ver):
    """out_dir/SimRCL_v<ver>/ with the installer at the top; returns its path."""
    base = os.path.join(out_dir, "SimRCL_v" + ver)
    if os.path.exists(base):
        shutil.rmtree(base)
    copy_plugin(os.path.join(base, "SimRCL"))
    for name in ("INSTALL.bat", "install.ps1"):
        shutil.copy2(os.path.join(ROOT, "installer", name), base)
    for name in DOCS:
        shutil.copy2(os.path.join(ROOT, name), base)
    shutil.copytree(os.path.join(ROOT, "for_agents"), os.path.join(base, "for_agents"))
    shutil.copy2(os.path.join(ROOT, "AGENTS.md"), os.path.join(base, "for_agents"))
    return base


def zip_folder(base, ver):
    """SimRCL_by_Dead_wall_v<ver>.zip with the version folder as its only top entry."""
    archive = os.path.join(os.path.dirname(base), "SimRCL_by_Dead_wall_v%s.zip" % ver)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as out:
        for folder, _, files in sorted(os.walk(base)):
            for name in sorted(files):
                path = os.path.join(folder, name)
                out.write(path, os.path.relpath(path, os.path.dirname(base)))
    return archive


if __name__ == "__main__":
    ver = version()
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist")
    print(zip_folder(assemble(out, ver), ver))
