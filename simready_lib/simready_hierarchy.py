"""Rebuild the parent/child structure that a SimReady model carries in its physics joints.

The USD Xform tree of these assets is flat (every part sits directly under Geometry); what belongs to what
is written in the joints: body0 carries body1 (trolley > wheel engine > wheel). Importing that as real
parenting lets the user move or rotate a part together with everything attached to it.
"""
import c4d

import simready_cleanup


def mesh_index(meshes, spec):
    """{USD mesh path: polygon object} for the meshes whose face count matches the inspected USD mesh.

    meshes must be in the traversal order of spec["meshes"]; call it before the hierarchy is tidied.
    """
    return {mesh_spec["path"]: mesh for mesh, mesh_spec in zip(meshes, spec["meshes"])
            if mesh.GetPolygonCount() == mesh_spec["faces"]}


def is_ancestor(candidate, obj):
    """True when candidate is obj or one of its parents."""
    while obj is not None:
        if obj == candidate:
            return True
        obj = obj.GetUp()
    return False


def reparent(child, parent):
    """Make child a child of parent without moving it in the scene."""
    world = child.GetMg()
    child.Remove()
    child.InsertUnder(parent)
    child.SetMg(world)


def can_attach(child, parent, group):
    """Only a part that still hangs directly under the group moves, and never into its own subtree."""
    return child is not None and parent is not None and child.GetUp() == group and not is_ancestor(child, parent)


def _name_chain(obj, group):
    """Names from the group's child down to obj."""
    names = []
    while obj is not None and obj != group:
        names.append(obj.GetName())
        obj = obj.GetUp()
    return names[::-1]


def find_by_path(group, path):
    """The object of a USD prim path, matched by names; the tidy-up may have dropped top wrappers, so the
    object's name chain only has to be the end of the path. None when no object or several match."""
    parts = [part for part in (path or "").split("/") if part]
    if not parts:
        return None
    found = [obj for obj in simready_cleanup.iter_objects(group)
             if obj.GetName() == parts[-1] and parts[-len(_name_chain(obj, group)):] == _name_chain(obj, group)]
    return found[0] if len(found) == 1 else None


def resolve_body(group, index, path):
    """Object of one joint body: the mesh index (exact, by traversal order), the name path (Xform bodies), else
    the body's parent Xform.

    The parent is needed for instanced parts: an office chair's five casters are instances of one wheel, so the
    mesh inside wheel 2 is really called sm_wheel1_a01_mesh_00 while its joint names sm_wheel2_a01_mesh_00.
    The tidy-up has merged that mesh into its Xform (sm_wheel2_a01_obj_00), which the parent path finds.
    Only one level up: higher would hand the joint a whole assembly.
    """
    found = index.get(path) or find_by_path(group, path)
    parent = path.rsplit("/", 1)[0] if path and path.count("/") > 1 else None
    return found or (parent and (index.get(parent) or find_by_path(group, parent)))


def resolver(group, index, joints):
    """path -> object for every body of joints (see resolve_body). Resolved up front, because reparenting
    changes the name paths it matches on."""
    paths = {path for joint in joints for path in (joint["parent"], joint["child"]) if path}
    found = {path: resolve_body(group, index, path) for path in paths}
    return found.get


def build_from_joints(group, joints, resolve):
    """Parent each joint's body1 under its body0; returns how many parts were attached."""
    attached = 0
    for joint in joints:
        child, parent = resolve(joint["child"]), resolve(joint["parent"])
        if can_attach(child, parent, group):
            reparent(child, parent)
            attached += 1
    return attached
