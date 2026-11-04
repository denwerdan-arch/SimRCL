"""Tidy the hierarchy that the native USD importer leaves in a freshly imported group.

A SimReady asset arrives as RootNode > Geometry > <part>_obj_00 (Null) > <part>_mesh_00 (Polygon), next
to empty stand-ins for materials, physics scopes, joints and reference points, and every prim carries a
"USD Prim" User Data tag. None of that is needed to render or edit the model, so it is removed here.

The steps never change what the scene looks like: geometry, UVs, material tags and world transforms stay.
Grouping that the model itself defines (Nulls that hold several parts, nested assemblies) is kept as authored.
"""
import c4d

CLUTTER_TAGS = (c4d.Tuserdata, c4d.Tprotection)
IDENTITY_TOLERANCE = 1e-6


def iter_objects(root):
    """Every descendant of root (not root itself), depth first."""
    stack = list(reversed(root.GetChildren()))
    while stack:
        obj = stack.pop()
        yield obj
        stack.extend(reversed(obj.GetChildren()))


def count_objects(root):
    """Number of objects under root, root excluded."""
    return sum(1 for _ in iter_objects(root))


def is_null(obj):
    return obj.GetType() == c4d.Onull


def has_content(obj):
    """True when obj or anything below it is not a Null (a mesh, light, camera ...)."""
    return not is_null(obj) or any(not is_null(child) for child in iter_objects(obj))


def strip_clutter_tags(root):
    """Remove User Data and Protection tags below root; they only mirror USD prim paths and flags."""
    for obj in iter_objects(root):
        for tag in obj.GetTags():
            if tag.GetType() in CLUTTER_TAGS:
                tag.Remove()


def prune_empty_nulls(root):
    """Delete every Null subtree that holds no real object: material scopes, joints, reference points, duplicates."""
    stack = list(root.GetChildren())
    while stack:
        obj = stack.pop()
        if not has_content(obj):
            obj.Remove()
            continue
        stack.extend(obj.GetChildren())


def is_mesh_wrapper(obj):
    """A tag-free Null whose only child is a polygon object: the USD Xform that merely positions the mesh."""
    child = obj.GetDown()
    return (is_null(obj) and not obj.GetTags() and child is not None
            and child.GetNext() is None and child.IsInstanceOf(c4d.Opolygon))


def merge_into_child(wrapper):
    """Replace wrapper by its mesh, keeping the world transform and the wrapper's name (the meaningful one)."""
    mesh = wrapper.GetDown()
    mesh.SetMl(wrapper.GetMl() * mesh.GetMl())
    mesh.SetName(wrapper.GetName())
    mesh.Remove()
    mesh.InsertBefore(wrapper)
    wrapper.Remove()


def collapse_mesh_wrappers(root):
    """Merge each positioning Null into the mesh it holds."""
    for wrapper in [obj for obj in iter_objects(root) if is_mesh_wrapper(obj)]:
        merge_into_child(wrapper)


def is_identity(matrix):
    reference = c4d.Matrix()
    pairs = ((matrix.off, reference.off), (matrix.v1, reference.v1), (matrix.v2, reference.v2), (matrix.v3, reference.v3))
    return all((a - b).GetLength() < IDENTITY_TOLERANCE for a, b in pairs)


def is_redundant_wrapper(obj):
    """A tag-free, untransformed Null that is the only child of its parent adds a level and nothing else."""
    only_child = obj.GetPred() is None and obj.GetNext() is None
    return is_null(obj) and only_child and not obj.GetTags() and is_identity(obj.GetMl())


def lift_children(wrapper):
    """Move the children of wrapper next to it, in order, and delete it."""
    for child in wrapper.GetChildren():
        child.Remove()
        child.InsertBefore(wrapper)
    wrapper.Remove()


def unwrap_top_levels(root):
    """Remove the redundant wrapper levels directly under root (RootNode, Geometry ...).

    Only the top of the tree is flattened: deeper Nulls are the model's own grouping (a door with its handle,
    a wheel assembly) and are kept even when they have a single child or no transform.
    """
    while True:
        wrapper = root.GetDown()
        if wrapper is None or not is_redundant_wrapper(wrapper):
            return
        lift_children(wrapper)


def tidy_hierarchy(group):
    """Clean the imported group in place and return (objects_before, objects_after)."""
    before = count_objects(group)
    for step in (strip_clutter_tags, prune_empty_nulls, collapse_mesh_wrappers, unwrap_top_levels):
        step(group)
    return before, count_objects(group)
