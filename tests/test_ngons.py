"""Sandbox checks of the USD face -> Cinema 4D polygon mapping for meshes whose n-gons were split."""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_ngons as ngons  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def fake_mesh(translation, ngon_count):
    return types.SimpleNamespace(GetPolygonCount=lambda: len(translation), GetNgonCount=lambda: ngon_count,
                                 GetPolygonTranslationMap=lambda: (len(set(translation)), list(translation)))


def main():
    # USD faces 0..4; face 2 is a hexagon that Cinema 4D split into polygons 2 and 3 (n-gons come first in
    # the translation space, as in Cinema 4D: n-gon 0, then the ordinary polygons from 1)
    translation = [1, 2, 0, 0, 3, 4]
    runs = ngons.face_runs(translation)
    spec = {"path": "/m", "faces": 5, "default_material": "a",
            "subsets": [{"material": "a", "ranges": [[0, 1]]}, {"material": "b", "ranges": [[2, 4]]}]}
    adapted = ngons.adapt_spec(spec, runs)
    results = [
        check("runs per USD face", runs, [[0], [1], [2, 3], [4], [5]]),
        check("ranges before the n-gon stay", ngons.remap_ranges([[0, 1]], runs), [[0, 1]]),
        check("the n-gon and what follows shift", ngons.remap_ranges([[2, 4]], runs), [[2, 5]]),
        check("adapted spec counts polygons", adapted["faces"], 6),
        check("adapted subsets", [s["ranges"] for s in adapted["subsets"]], [[[0, 1]], [[2, 5]]]),
        check("original spec untouched", spec["subsets"][1]["ranges"], [[2, 4]]),
        check("wrong mesh is refused", ngons.adapt_spec(dict(spec, faces=7), runs), None),
        check("equal counts pass through", ngons.matched_spec(fake_mesh([0, 1, 2, 3, 4], 0), spec) is spec, True),
        check("split n-gons are remapped", ngons.matched_spec(fake_mesh(translation, 1), spec)["faces"], 6),
        check("more polygons without n-gons is refused", ngons.matched_spec(fake_mesh([0, 1, 2, 3, 4, 5], 0), spec), None),
        check("fewer polygons is refused", ngons.matched_spec(fake_mesh([0, 1, 2], 0), spec), None),
        check("ranges compress", ngons.to_ranges([5, 1, 2, 3, 7]), [[1, 3], [5, 5], [7, 7]]),
    ]
    print(all(results))
    return all(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
