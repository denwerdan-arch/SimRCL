"""Sandbox checks of the Similar strip selection and of collider hiding (c4d is stubbed)."""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))
sys.modules["c4d"] = types.SimpleNamespace(ID_BASEOBJECT_VISIBILITY_EDITOR="ed", ID_BASEOBJECT_VISIBILITY_RENDER="rd", OBJECT_OFF=1)

import simready_catalog as cat  # noqa: E402
import simready_colliders as colliders  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def card(package, kind=None, title=None, filename="x.usd", repo="nvidia/simready-assets"):
    vlm = {"object_type": [kind]} if kind else {}
    return {"key": package, "asset": {"ref": {"repo": repo, "package": package}}, "vlm": vlm, "title": title, "filename": filename}


class Obj:
    """Minimal BaseObject: name, children, visibility parameters."""

    def __init__(self, name, children=()):
        self.name, self.children, self.params = name, list(children), {}

    def GetName(self):
        return self.name

    def GetChildren(self):
        return self.children

    def __setitem__(self, key, value):
        self.params[key] = value


def similar_checks():
    pan = card("pan_a01", "Frying pan")
    candidates = [card("pan_a01", "frying pan"), card("wok_a01", "wok"), card("pan_b01", "frying pan"),
                  card("pan_b01", "frying pan"), card("pan_c01", "frying pan"), card("pan_d01", "frying pan")]
    picks = [c["asset"]["ref"]["package"] for c in cat.pick_similar(pan, candidates)]
    return [
        check("query from object type", cat.similar_query(pan), "frying pan"),
        check("query falls back to title", cat.similar_query(card("p", "unknown", title="Toaster")), "toaster"),
        check("query falls back to file name", cat.similar_query(card("p", filename="sm_kitchenware_pan_a01_01.usd")), "kitchenware pan"),
        check("same kind first, own and duplicate packages dropped", picks, ["pan_b01", "pan_c01", "pan_d01"]),
        check("other kinds fill up", [c["key"] for c in cat.pick_similar(pan, candidates[:3])], ["pan_b01", "wok_a01"]),
        check("search name", (cat.search_name(card("p", title="Dissecting scissors")), cat.search_name(card("p", filename="sm_utensils_scissors_g01_01.usd"))),
              ("Dissecting scissors", "utensils scissors")),
        check("same package name in another repo is kept", len(cat.pick_similar(pan, [card("pan_a01", "frying pan", repo="other/x")])), 1),
    ]


def collider_checks():
    names = ["Colliders", "Colliders_00", "Collider_3", "collision_mesh_01", "CollidersY", "collider_cover", "wheel"]
    matched = [n for n in names if colliders.is_collider_name(n)]
    inner = Obj("Collider_0")
    group = Obj("Colliders_00", [inner])
    root = Obj("group", [Obj("part_00", [Obj("mesh_node"), group]), Obj("Collider_9")])
    hidden = colliders.hide_colliders(root)
    return [
        check("collider names", matched, ["Colliders", "Colliders_00", "Collider_3", "collision_mesh_01"]),
        check("topmost match hidden only", (hidden, group.params, inner.params), (2, {"ed": 1, "rd": 1}, {})),
        check("note", (colliders.hidden_note(0), colliders.hidden_note(1)), ("", "1 collider group hidden (viewport and render)")),
    ]


results = similar_checks() + collider_checks()
print(all(results))
