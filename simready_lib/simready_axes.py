"""Give imported meshes a usable axis.

Many SimReady assets (Palatial ones, for example) store every part with an identity transform and the points
already placed in the model's space, so after import every axis sits at the model origin. Rotating or scaling
such a part then swings it around a far-away point. Those parts get their axis moved to the centre of their
bounding box, the way Cinema 4D's "Axis Center" does it; the geometry does not move in the scene.

A part whose transform the author did set (a wheel placed by its Xform, a door positioned at its hinge) keeps
its axis: that pivot is intentional and often the rotation point the physics joints use.
"""
import c4d

import simready_cleanup

RELATIVE_TOLERANCE = 1e-4  # of the part's size; below it an offset counts as "at the origin"


def _tolerance(obj):
    return RELATIVE_TOLERANCE * max(obj.GetRad().GetLength(), 1e-9)


def has_authored_axis(obj):
    """True when the part sits away from its parent's origin, i.e. its author placed it by a transform."""
    return obj.GetMl().off.GetLength() > _tolerance(obj)


def needs_centering(obj):
    """A polygon object with points, an identity placement and a bounding box away from its axis."""
    if not obj.IsInstanceOf(c4d.Opolygon) or not obj.GetPointCount() or has_authored_axis(obj):
        return False
    return obj.GetMp().GetLength() > _tolerance(obj)


def move_axis(obj, local_point):
    """Put the axis of obj at local_point (in its own coordinates) without moving its points or children in the scene."""
    if obj.IsInstanceOf(c4d.Opoint):
        obj.SetAllPoints([point - local_point for point in obj.GetAllPoints()])
        obj.Message(c4d.MSG_UPDATE)
    matrix = obj.GetMl()
    matrix.off = matrix * local_point  # the old local position of the point becomes the new origin
    obj.SetMl(matrix)
    # children are stored relative to this axis, so they shift back by the same amount in its frame
    for child in obj.GetChildren():
        local = child.GetMl()
        local.off = local.off - local_point
        child.SetMl(local)


def center_axis(obj):
    """Move the axis of obj to its bounding box centre."""
    move_axis(obj, obj.GetMp())


def center_unset_axes(root):
    """Center the axis of every part below root that has none of its own; returns how many were moved."""
    parts = [obj for obj in simready_cleanup.iter_objects(root) if needs_centering(obj)]
    for obj in parts:
        center_axis(obj)
    return len(parts)



FIXED_JOINTS = ("PhysicsFixedJoint",)  # welded parts: their anchor is no rotation point


def usd_to_group(point, up_axis):
    """Stage coordinates of a point -> coordinates of the imported group before the unit bake.

    Cinema 4D is Y-up and left-handed; its USD importer swaps Y and Z for Z-up stages and mirrors Z for
    Y-up ones (checked against the imported meshes of a Z-up Palatial asset).
    """
    x, y, z = point
    return c4d.Vector(x, z, y) if up_axis == "Z" else c4d.Vector(x, y, -z)


def model_bounds(root):
    """(min, max) corners of a box around every mesh below root, from their cached centres and radii (cheap)."""
    boxes = [(obj.GetMg() * obj.GetMp(), obj.GetRad().GetLength()) for obj in simready_cleanup.iter_objects(root)
             if obj.IsInstanceOf(c4d.Opolygon) and obj.GetPointCount()]
    if not boxes:
        return None
    low = c4d.Vector(*(min(c[i] - r for c, r in boxes) for i in range(3)))
    high = c4d.Vector(*(max(c[i] + r for c, r in boxes) for i in range(3)))
    return low, high


def inside(point, bounds):
    """True when point lies in the box (a missing box accepts nothing)."""
    return bounds is not None and all(bounds[0][i] <= point[i] <= bounds[1][i] for i in range(3))


def set_joint_pivots(group, joints, resolve, up_axis):
    """Put the axis of every moving joint's child body on the joint, so rotating it turns the part like the
    real hinge or wheel does; returns [(part, joint)] of the parts that got their pivot.

    An anchor outside the model is ignored: it would mean a stage in other units or a broken joint, and a
    pivot far away is worse than the centred one the part already has.
    """
    bounds, moved = model_bounds(group), []
    for joint in joints:
        child = resolve(joint["child"])
        if child is None or joint.get("anchor") is None or joint.get("kind") in FIXED_JOINTS:
            continue
        world = group.GetMg() * usd_to_group(joint["anchor"], up_axis)
        if inside(world, bounds):
            move_axis(child, ~child.GetMg() * world)
            moved.append((child, joint))
    return moved
