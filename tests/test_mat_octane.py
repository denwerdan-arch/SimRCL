"""Sandbox checks of the Octane OpenPBR pin writes (c4d is stubbed; rendering is checked in Cinema 4D)."""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))


class Shader(dict):
    """Stand-in for a BaseShader: parameters by id, plus its type."""

    def __init__(self, kind):
        super().__init__()
        self.kind = kind


c4d = types.SimpleNamespace(Vector=lambda *rgb: tuple(rgb), BaseShader=Shader)
sys.modules["c4d"] = c4d

import simready_mat_octane as octane  # noqa: E402

MATERIAL = types.SimpleNamespace(InsertShader=lambda shader: None)


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def writes(slot, entry):
    return octane.PBR_APPLIERS[slot](MATERIAL, entry)


def main():
    orm = {"file": "orm.png", "channel": "g", "color_space": "raw"}
    rough = writes("roughness", {"texture": orm})
    picker = rough[0][2]
    albedo = writes("base_color", {"texture": {"file": "alb.png", "color_space": "sRGB"}})[0]
    emission = writes("emission", {"value": [1, 0.5, 0], "strength": 2.0})
    results = [
        check("roughness is a link", rough[0][:2], (octane.PIN_LINKS, octane.PBR_ROUGHNESS)),
        check("ORM G through a channel picker", (picker.kind, picker[octane.PICKER_CHANNEL]), (octane.PICKER_ID, 1)),
        check("picked image stays linear", picker[octane.PICKER_INPUT][octane.IMAGE_COLOR_SPACE], octane.SPACE_DATA),
        check("albedo image in sRGB", (albedo[1], albedo[2][octane.IMAGE_COLOR_SPACE]), (octane.PBR_BASE_COLOR, octane.SPACE_SRGB)),
        check("constant metalness is a value", writes("metallic", {"value": 1}), [(octane.PIN_VALUES, octane.PBR_METALNESS, 1.0)]),
        check("constant colour", writes("base_color", {"value": 0.5}), [(octane.PIN_VALUES, octane.PBR_BASE_COLOR, (0.5, 0.5, 0.5))]),
        check("emission colour, weight and luminance", emission,
              [(octane.PIN_VALUES, octane.PBR_EMISSION_COLOR, (1.0, 0.5, 0.0)),
               (octane.PIN_VALUES, octane.PBR_EMISSION_WEIGHT, 1.0),
               (octane.PIN_VALUES, octane.PBR_EMISSION_LUMINANCE, 2.0)]),
        check("normal without texture writes nothing", writes("normal", {"value": [0, 0, 1]}), []),
        check("alpha opacity reads the alpha", writes("opacity", {"texture": {"file": "a.png", "channel": "a"}})[0][2][octane.IMAGE_TYPE],
              octane.IMAGE_ALPHA),
    ]
    print(all(results))
    return all(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
