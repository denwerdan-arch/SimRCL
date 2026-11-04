"""Sandbox checks of the multi-material split rules with a stand-in mesh (c4d is stubbed)."""
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

import simready_split as split  # noqa: E402

Poly = types.SimpleNamespace


class Select:
    def __init__(self, indices):
        self.indices = set(indices)

    def GetAll(self, count):
        return [i in self.indices for i in range(count)]


class Tag:
    def __init__(self, kind, values=None, name="", select=None):
        self.kind, self.values, self.name = kind, dict(values or {}, select=select), name

    def GetType(self):
        return self.kind

    def GetName(self):
        return self.name

    def __getitem__(self, key):
        return self.values.get(key)

    def GetBaseSelect(self):
        return self.values["select"]


class Mesh:
    def __init__(self, polys, tags):
        self.polys, self.tags = polys, tags

    def GetPolygonCount(self):
        return len(self.polys)

    def GetPolygon(self, i):
        return self.polys[i]

    def GetTags(self):
        return self.tags


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def texture(material, restriction=""):
    return Tag(c4d.Ttexture, {c4d.TEXTURETAG_MATERIAL: material, c4d.TEXTURETAG_RESTRICTION: restriction})


def main():
    quads = [Poly(a=0, b=1, c=2, d=3), Poly(a=4, b=5, c=6, d=7), Poly(a=3, b=2, c=8, d=9)]
    tags = [texture("top"), Tag(c4d.Tpolygonselection, name="legs", select=Select([1])), texture("steel", "legs"),
            texture("importer_grey")]
    mesh = Mesh(quads, tags)
    owner = split.material_of_polygons(mesh, ["top", "steel"])
    parts = split.regions(mesh, owner)
    touching = split.regions(mesh, ["top", "steel", "steel"])
    results = [
        check("later tag wins on its selection, unknown materials ignored", owner, ["top", "steel", "top"]),
        check("regions", parts, {"top": [0, 2], "steel": [1]}),
        check("separate parts split", split.separable(mesh, parts), True),
        check("parts sharing points stay whole", split.separable(mesh, touching), False),
    ]
    print(all(results))


main()
