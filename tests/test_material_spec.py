"""Sandbox checks of simready_material_spec (pure functions, no Cinema 4D)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_material_spec as sp  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def main():
    tex = {"texture": {"file": "a/t.<UDIM>.png", "color_space": "raw", "channel": "g", "uv": {"scale": [2, 3]}}}
    spec = {"diffuseColor": {"value": [0.5, 0.5, 0.5]}, "roughness": tex,
            "emissiveColor": {"value": [0, 0, 0]}, "opacity": {"value": 1.0}, "unknown": {"value": 1}}
    found = sp.slots(spec)
    glow = sp.slots({"emissiveColor": {"value": [40, 20, 0]}})[sp.EMISSION]
    results = [
        check("keeps colour and roughness only", sorted(found), [sp.BASE_COLOR, sp.ROUGHNESS]),
        check("opaque constant dropped", sp.OPACITY in found, False),
        check("glass opacity kept", sp.OPACITY in sp.slots({"opacity": {"value": 0.4}}), True),
        check("emission peak is 1", max(glow["value"]), 1.0),
        check("emission strength capped", glow["strength"], sp.EMISSION_STRENGTH_CAP),
        check("small emission not boosted", sp.emission_strength(sp.slots({"emissiveColor": {"value": [2, 1, 0]}})), 2.0),
        check("strength default", sp.emission_strength({}), 1.0),
        check("udim", sp.has_udim(tex["texture"]), True),
        check("uv scale", sp.uv_scale(tex["texture"]), (2.0, 3.0)),
        check("uv offset default", sp.uv_offset(tex["texture"]), (0.0, 0.0)),
        check("channel g", sp.channel_index(tex["texture"]), 1),
        check("colour has no channel", sp.channel_index({"file": "x"}), None),
        check("grey from scalar", sp.as_rgb(0.5), [0.5, 0.5, 0.5]),
    ]
    print(all(results))


main()
