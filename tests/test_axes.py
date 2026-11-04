"""Sandbox checks of the pure parts of simready_axes (c4d is stubbed: vectors are tuples)."""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))
sys.modules["c4d"] = types.SimpleNamespace(Vector=lambda *v: tuple(v), Tuserdata=1, Tprotection=2)

import simready_axes as axes  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


# expected values measured on imported assets: D00715 (Palatial) and S18-17 (Comau), both Z-up
results = [
    check("z-up swaps y and z", axes.usd_to_group((0.150, -0.143, 0.464), "Z"), (0.150, 0.464, -0.143)),
    check("y-up mirrors z", axes.usd_to_group((1.0, 2.0, 3.0), "Y"), (1.0, 2.0, -3.0)),
    check("inside", axes.inside((0, 1, 0), ((-1, 0, -1), (1, 2, 1))), True),
    check("outside", axes.inside((0, 3, 0), ((-1, 0, -1), (1, 2, 1))), False),
    check("no bounds", axes.inside((0, 0, 0), None), False),
]
print(all(results))
