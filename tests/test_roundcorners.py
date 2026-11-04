"""Sandbox checks of the round corners tag source and helpers (c4d and maxon stubbed)."""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))


class _Constants:
    """Stand-in for the c4d module: any attribute is a unique integer."""

    def __init__(self):
        self._ids = {}

    def __getattr__(self, name):
        return self._ids.setdefault(name, len(self._ids) + 1)


sys.modules.setdefault("c4d", _Constants())
sys.modules.setdefault("maxon", types.ModuleType("maxon"))

import simready_roundcorners as rc  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def tag_space(corners):
    code = rc.tag_code({"on": 1, "radius": 2, "same": 3, "corners": corners})
    space = {}
    exec(compile(code, "tag", "exec"), space)  # noqa: S102 - our own template
    return code, space


def main():
    code, space = tag_space(4)
    _, plain = tag_space(0)
    layout, state = space["layout"], space["state_text"]
    results = [
        check("ids and constants filled in", "__" in code.replace("__name__", ""), False),
        check("off hides radius, same and corners", layout((False, 0.01, False, 0)), {2: (True, "Radius"), 3: (True, "Same object only"), 4: (True, "Corners (V-Ray)")}),
        check("on shows them", layout((True, 0.01, False, 0))[2][0], False),
        check("no V-Ray, no corners field", 4 in plain["layout"]((True, 0.01, False, 0)), False),
        check("off writes radius 0", state((False, 0.5, True, 1)), "0 0 1 1"),
        check("on writes the radius", state((True, 0.01, False, 0)), "1 0.01 0 0"),
        check("0.1 cm in a 10 cm unit document", round(rc.default_radius(0.1), 9), 0.01),
        check("0.1 cm in a cm document", round(rc.default_radius(0.01), 9), 0.1),
        check("note when Standard cannot round", rc.note(True, set(), True), "no round corners for this renderer"),
        check("no note when switched off", rc.note(False, set(), True), ""),
        check("no note when rounding works", rc.note(True, {rc.REDSHIFT}, True), ""),
    ]
    print(all(results))


main()
