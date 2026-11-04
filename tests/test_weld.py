"""Sandbox checks of the loose-triangle weld rules (c4d is stubbed; the Optimize call itself runs in Cinema 4D)."""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))


class _Constants:
    """Stand-in for the c4d module: any attribute is a unique integer."""

    def __init__(self):
        self._ids = {}

    def __getattr__(self, name):
        if name in ("utils", "gui"):
            return types.SimpleNamespace()
        return self._ids.setdefault(name, len(self._ids) + 1)


c4d = _Constants()
sys.modules["c4d"] = c4d
sys.modules["c4d.utils"] = c4d.utils

import simready_weld as weld  # noqa: E402

P = lambda x, y, z: types.SimpleNamespace(x=x, y=y, z=z)  # noqa: E731


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def main():
    # two triangles of a quad, stored STL-style: 6 corners, 4 distinct positions
    soup = [P(0, 0, 0), P(1, 0, 0), P(1, 1, 0), P(0, 0, 0), P(1, 1, 0), P(0, 1, 0)]
    near = [P(0, 0, 0), P(0.0000004, 0, 0), P(1, 0, 0)]
    results = [
        check("STL soup positions", weld.unique_count(soup, 1e-6), 4),
        check("STL soup is welded", weld.needs_weld(6, 4), True),
        check("Asimov hip: 66 618 points on 11 003 positions", weld.needs_weld(66618, 11003), True),
        check("a mesh with a few seams is left alone", weld.needs_weld(1000, 950), False),
        check("empty mesh", weld.needs_weld(0, 0), False),
        check("float noise counts as one point", weld.unique_count(near, weld.tolerance(1.0)), 2),
        check("tolerance follows the size", (round(weld.tolerance(100.0), 12), weld.tolerance(0.0)), (1e-4, weld.MIN_TOLERANCE)),
        check("note", weld.note((26, 2877108, 473914)), "welded 26 loose-triangle meshes (2 877 108 -> 473 914 points)"),
        check("one mesh", weld.note((1, 6, 4)), "welded 1 loose-triangle mesh (6 -> 4 points)"),
        check("nothing welded, no note", weld.note((0, 0, 0)), ""),
    ]
    print(all(results))
    return all(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
