"""Sandbox checks of simready_settings (temporary folders only)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_settings as settings  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def main():
    root = tempfile.mkdtemp()
    path = os.path.join(root, "sub", "settings.json")
    results = [check("missing file", settings.load(path), {})]
    chosen = os.path.join(root, "big drive", "Assets")
    saved = settings.with_download_dir({}, chosen)
    results.append(check("save ok", settings.save(saved, path), ""))
    results.append(check("round trip", settings.download_dir(settings.load(path)), os.path.normpath(chosen)))
    results.append(check("not default", settings.is_default(saved), False))
    reset = settings.with_download_dir(saved, settings.DEFAULT_DOWNLOAD_DIR)
    results.append(check("reset", (settings.is_default(reset), settings.download_dir(reset)), (True, settings.DEFAULT_DOWNLOAD_DIR)))
    with open(path, "w") as handle:
        handle.write("{broken")
    results.append(check("damaged file", settings.load(path), {}))
    results.append(check("folder created and writable", (settings.check_folder(chosen), os.path.isdir(chosen), os.listdir(chosen)), ("", True, [])))
    results.append(check("relative rejected", bool(settings.check_folder("assets")), True))
    blocker = os.path.join(root, "file.txt")
    open(blocker, "w").close()
    results.append(check("file instead of folder", bool(settings.check_folder(os.path.join(blocker, "x"))), True))
    results.append(check("free space", settings.free_bytes(os.path.join(root, "not", "yet")) > 0, True))
    off = settings.with_tidy(saved, False)
    results.append(check("tidy on by default", settings.tidy_enabled({}), True))
    results.append(check("tidy off keeps folder", (settings.tidy_enabled(off), settings.download_dir(off)), (False, os.path.normpath(chosen))))
    results.append(check("tidy back on", settings.tidy_enabled(settings.with_tidy(off, True)), True))
    results.append(check("phong, split, layers on by default", (settings.phong_enabled({}), settings.split_enabled({}), settings.layers_enabled({})), (True, True, True)))
    results.append(check("flag switch", settings.layers_enabled(settings.with_flag({}, settings.LAYERS_KEY, False)), False))
    results.append(check("rig on by default, switchable", (settings.rig_enabled({}), settings.rig_enabled(settings.with_rig({}, False))), (True, False)))
    targets = ("redshift", "standard", "arnold", "vray")
    picked = settings.with_material_target({}, "arnold")
    results.append(check("target default auto", settings.material_target({}, targets), "auto"))
    results.append(check("target stored", settings.material_target(picked, targets), "arnold"))
    results.append(check("target unknown", settings.material_target({"material_target": "maya"}, targets), "auto"))
    results.append(check("target auto clears", settings.material_target(settings.with_material_target(picked, "auto"), targets), "auto"))
    results.append(check("openpbr on by default", settings.prefer_openpbr({}), True))
    results.append(check("openpbr off", settings.prefer_openpbr(settings.with_openpbr({}, False)), False))
    print(all(results))


main()
