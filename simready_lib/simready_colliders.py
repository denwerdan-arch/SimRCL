"""Hide the collision shapes that some SimReady assets carry next to their visual meshes.

Colliders are simplified convex pieces for the physics engines. They overlap the real geometry, so in the
viewport and in renders they only get in the way; they are kept in the scene (switched off, not deleted)
because a simulation or a later export may still need them.
"""
import re

import c4d

# "Colliders", "Colliders_00", "Collider_3", "collision_mesh_01", ... as written by the USD exporters seen so far
COLLIDER_NAME = re.compile(r"^(colliders?|collisions?|collision_mesh(es)?)([_.\s-]*\d+)*$", re.IGNORECASE)


def is_collider_name(name):
    """True for the names the asset authors give collision shapes and their groups."""
    return bool(COLLIDER_NAME.match((name or "").strip()))


def _hide(obj):
    obj[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR] = c4d.OBJECT_OFF
    obj[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = c4d.OBJECT_OFF


def hide_colliders(root):
    """Switch off viewport and render visibility of every collider below root; returns how many were hidden.

    Only the topmost match of a branch is switched: its children inherit the state, so a user can show the
    whole set again with one click on the group.
    """
    hidden, stack = 0, list(root.GetChildren())
    while stack:
        obj = stack.pop()
        if is_collider_name(obj.GetName()):
            _hide(obj)
            hidden += 1
            continue
        stack.extend(obj.GetChildren())
    return hidden


def hidden_note(count):
    """Status text for the import summary, or '' when the asset had no colliders."""
    if not count:
        return ""
    return "%d collider group%s hidden (viewport and render)" % (count, "" if count == 1 else "s")
