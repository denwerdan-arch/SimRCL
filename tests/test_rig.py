"""Sandbox checks of the pure rules of simready_rig (c4d is stubbed: every constant is a distinct int)."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))


class _Constants:
    """Stand-in for the c4d module: any attribute is a unique integer, Vector builds a tuple."""

    def __init__(self):
        self._ids = {}

    def __getattr__(self, name):
        if name == "Vector":
            return lambda *v: tuple(v)
        return self._ids.setdefault(name, len(self._ids) + 1)


sys.modules["c4d"] = _Constants()

import simready_rig as rig  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def rounded(values):
    return tuple(round(v, 4) for v in values)


results = [
    check("degrees", rounded(rig.angle_limits([-60.0, 0.0])), rounded((math.radians(-60), 0.0))),
    check("radians written into the degree field", rounded(rig.angle_limits([0.0, 0.942477822])), (0.0, 0.9425)),
    check("mixed range read as degrees", rounded(rig.angle_limits([-50.0, 2.7])), rounded((math.radians(-50), math.radians(2.7)))),
    check("limits measured from the saved pose", rounded(rig.angle_limits([20.0, 150.0], 115.0)), rounded((math.radians(-95), math.radians(35)))),
    check("lamp upper arm keeps its pose", rig.joint_rules(rig.REVOLUTE, [20.0, 150.0], 1.0, 115.0)["R"][0] != rig.FREE, True),
    check("pose outside the range frees the channel", rig.joint_rules(rig.REVOLUTE, [20.0, 150.0], 1.0, 0.0)["R"][0], rig.FREE),
    check("prismatic from the saved pose", rig.slide_limits([0.0, 0.003], 0.001, 100.0), (-0.1, 0.2)),
    check("revolute without limits turns freely", rig.joint_rules(rig.REVOLUTE, None, 1.0)["R"], (rig.FREE, rig.LOCKED, rig.LOCKED)),
    check("revolute keeps its place", rig.joint_rules(rig.REVOLUTE, None, 1.0)["P"], (rig.LOCKED,) * 3),
    check("prismatic slides on Y in scene units", rig.joint_rules(rig.PRISMATIC, [0.0, 0.5], 100.0)["P"], (rig.LOCKED, (0.0, 50.0), rig.LOCKED)),
    check("spherical turns freely", rig.joint_rules(rig.SPHERICAL, None, 1.0)["R"], (rig.FREE,) * 3),
    check("ring follows the cross-section", round(rig.control_radius(10.0, 200.0), 3), 11.5),
    check("ring capped by model size", rig.control_radius(100.0, 200.0), 50.0),
    check("ring never vanishes", rig.control_radius(0.1, 200.0), 4.0),
    check("notes", (rig.controls_note(0), rig.controls_note(1), rig.controls_note(6)), ("", "1 moving part with controls", "6 moving parts with controls")),
]
print(all(results))
