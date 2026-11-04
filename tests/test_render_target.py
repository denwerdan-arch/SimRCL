"""Sandbox checks of simready_render_target with a stub of the c4d module."""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

INSTALLED = {1036219, 1029988}  # Redshift and Arnold, not V-Ray
stub = types.SimpleNamespace(
    RDATA_RENDERENGINE=1, PLUGINTYPE_VIDEOPOST=2,
    plugins=types.SimpleNamespace(FindPlugin=lambda plugin_id, kind=None: object() if plugin_id in INSTALLED else None))
sys.modules["c4d"] = stub

import simready_render_target as rt  # noqa: E402


class Doc:
    def __init__(self, engine):
        self.engine = engine

    def GetActiveRenderData(self):
        return {stub.RDATA_RENDERENGINE: self.engine}


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def main():
    results = [
        check("auto follows redshift", rt.resolve(rt.AUTO, True, Doc(1036219)), rt.Choice(rt.REDSHIFT, True, "")),
        check("auto follows physical", rt.resolve(rt.AUTO, True, Doc(1023342)), rt.Choice(rt.STANDARD, False, "")),
        check("explicit beats document", rt.resolve(rt.ARNOLD, False, Doc(1036219)), rt.Choice(rt.ARNOLD, False, "")),
        check("openpbr needs support", rt.resolve(rt.STANDARD, True, Doc(0)).openpbr, False),
        check("missing renderer falls back", rt.resolve(rt.VRAY, True, Doc(0)).target, rt.STANDARD),
        check("fallback explains", bool(rt.resolve(rt.VRAY, True, Doc(0)).note), True),
        check("unknown setting uses document", rt.resolve("maya", False, Doc(1029988)).target, rt.ARNOLD),
        check("label", rt.label(rt.Choice(rt.REDSHIFT, True, "")), "Redshift OpenPBR"),
    ]
    print(all(results))


main()
