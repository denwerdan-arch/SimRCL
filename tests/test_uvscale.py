"""Sandbox checks of the material repeat helpers and the UV tag's pure logic (c4d stubbed)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_material_spec as sp  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


class _Constants:
    """Stand-in for the c4d module: any attribute is a unique integer."""

    def __init__(self):
        self._ids = {}

    def __getattr__(self, name):
        return self._ids.setdefault(name, len(self._ids) + 1)


sys.modules.setdefault("c4d", _Constants())


def tag_checks():
    """The generated tag source: ids filled in, tiling per mode, which fields show."""
    import simready_uvscale as uv
    code = uv.tag_code({"mode": 1, "uniform": 2, "u": 3, "v": 4})
    space = {}
    exec(compile(code, "tag", "exec"), space)  # noqa: S102 - our own template
    wanted, factors, layout = space["wanted"], space["factors"], space["layout"]
    auto = (8.0, 9.0)
    return [
        check("ids filled in", "__" in code, False),
        check("auto keeps USD", wanted(0, auto, (2.0, 3.0)), auto),
        check("custom multiplies", wanted(1, auto, (0.5, 2.0)), (4.0, 18.0)),
        check("off is 1:1", wanted(2, auto, (2.0, 3.0)), (1.0, 1.0)),
        check("uniform drives both", factors(1, True, 0.5, 7.0), (0.5, 0.5)),
        check("separate U and V", factors(1, False, 0.5, 7.0), (0.5, 7.0)),
        check("auto hides the factors", layout((0, True)), {2: (True, "Uniform UV"), 3: (True, "UV x"), 4: (True, "V x")}),
        check("custom uniform shows one field", layout((1, True)), {2: (False, "Uniform UV"), 3: (False, "UV x"), 4: (True, "V x")}),
        check("custom free shows U and V", layout((1, False)), {2: (False, "Uniform UV"), 3: (False, "U x"), 4: (False, "V x")}),
        check("off hides the factors", layout((2, False))[3][0] and layout((2, False))[4][0], True),
    ]


def tex(scale):
    return {"texture": {"file": "x.png", "uv": {"scale": scale, "rotation": 0.0, "translation": [0, 0]}}}


chair_plastic = {"diffuseColor": tex([9.0, 9.0]), "metallic": tex([9.0, 9.0]), "normal": tex([9.0, 9.0]), "opacity": {"value": 1.0}}
mixed = {"diffuseColor": tex([2.0, 2.0]), "normal": tex([4.0, 4.0])}
results = [
    check("chair plastic repeats 9x", sp.material_uv_scale(chair_plastic), (9.0, 9.0)),
    check("tie goes to the base colour", sp.material_uv_scale(mixed), (2.0, 2.0)),
    check("no textures, no scale", sp.material_uv_scale({"diffuseColor": {"value": [1, 0, 0]}}), None),
    check("no transform means 1:1", sp.material_uv_scale({"diffuseColor": {"texture": {"file": "x.png", "uv": None}}}), (1.0, 1.0)),
]
results += tag_checks()
print(all(results))
