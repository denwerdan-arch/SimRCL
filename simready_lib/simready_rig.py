"""Animation controls for the moving parts of an imported asset.

Every revolute, prismatic or spherical physics joint gets a two-level control at its anchor:

    <name>_offset   Null, no display: carries the joint frame (its Y axis is the joint axis), never animated
      <controller>  Null, coloured shape: identity at rest, so the one channel that moves it starts at 0
        part        the moving part (the joint's body1), unchanged in the scene

At rest every controller value is 0. A revolute part turns with H (degrees match the USD joint angle), a
prismatic part slides with P.Y. A Protection tag locks the channels the joint cannot move and limits the free
one to the joint's range when the asset defines it. Rigid parts need no bones: a controller carries its part
as a child, and an IK tag works on a chain of Nulls as well.
"""
import math

import c4d

import simready_cleanup

REVOLUTE, PRISMATIC, SPHERICAL = "PhysicsRevoluteJoint", "PhysicsPrismaticJoint", "PhysicsSphericalJoint"
CONTROLLED = (REVOLUTE, PRISMATIC, SPHERICAL)
SHAPES = {REVOLUTE: c4d.NULLOBJECT_DISPLAY_CIRCLE, PRISMATIC: c4d.NULLOBJECT_DISPLAY_RECTANGLE,
          SPHERICAL: c4d.NULLOBJECT_DISPLAY_SPHERE}
CONTROL_COLOR = c4d.Vector(1.0, 0.64, 0.0)  # the plugin's accent orange
RING_MARGIN = 1.15  # a ring a little wider than the part's cross-section stays visible around it
MODEL_SHARE = 0.25  # but never wider than this share of the whole model (long parts such as scissor blades)
MIN_SHARE = 0.02


def to_c4d_direction(direction, up_axis):
    """Stage direction -> Cinema 4D direction (same swap as the anchors; a reflection, see set_joint_pivots)."""
    x, y, z = direction
    return c4d.Vector(x, z, y) if up_axis == "Z" else c4d.Vector(x, y, -z)


def frame_along(origin, axis):
    """World matrix at origin whose Y axis is axis; X is the world X (or Z) made perpendicular, so frames are stable."""
    y = axis.GetNormalized()
    reference = c4d.Vector(1, 0, 0) if abs(y.x) < 0.9 else c4d.Vector(0, 0, 1)
    x = (reference - y * reference.Dot(y)).GetNormalized()
    return c4d.Matrix(origin, x, y, x.Cross(y))


def set_frame_keep_children(obj, world):
    """Give obj a new world matrix while its children stay where they are in the scene."""
    children = [(child, child.GetMg()) for child in obj.GetChildren()]
    obj.SetMg(world)
    for child, child_world in children:
        child.SetMg(child_world)


def make_null(name):
    null = c4d.BaseObject(c4d.Onull)
    null.SetName(name)
    return null


def insert_above(obj, new_parent, world):
    """Put new_parent at obj's place in the hierarchy with the given world matrix, then obj under it (world kept)."""
    obj_world = obj.GetMg()
    new_parent.InsertBefore(obj)
    new_parent.SetMg(world)
    obj.Remove()
    obj.InsertUnder(new_parent)
    obj.SetMg(obj_world)


def controller_for(part, world):
    """The Null that will move part: part itself when it is a Null (it keeps its name), else a new '<name>_ctrl'."""
    if part.GetType() == c4d.Onull:
        set_frame_keep_children(part, world)
        return part
    controller = make_null(part.GetName() + "_ctrl")
    insert_above(part, controller, world)
    return controller


def own_meshes(controller, controller_ids):
    """Polygon objects moved by controller and by no controller below it (controllers given by GUID)."""
    found, stack = [], list(controller.GetChildren())
    while stack:
        obj = stack.pop()
        if obj.GetGUID() in controller_ids:
            continue
        if obj.IsInstanceOf(c4d.Opolygon) and obj.GetPointCount():
            found.append(obj)
        stack.extend(obj.GetChildren())
    return found


def _corners(mesh):
    center, rad, world = mesh.GetMp(), mesh.GetRad(), mesh.GetMg()
    return [world * (center + c4d.Vector(sx * rad.x, sy * rad.y, sz * rad.z))
            for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def cross_section(controller, meshes):
    """Largest distance of the meshes' box corners from the controller's Y axis (0 without meshes)."""
    inverse = ~controller.GetMg()
    points = [inverse * corner for mesh in meshes for corner in _corners(mesh)]
    return max((math.hypot(p.x, p.z) for p in points), default=0.0)


def model_size(group):
    """Largest box dimension of all meshes of the group (scene units)."""
    corners = [corner for mesh in simready_cleanup.iter_objects(group)
               if mesh.IsInstanceOf(c4d.Opolygon) and mesh.GetPointCount() for corner in _corners(mesh)]
    if not corners:
        return 0.0
    return max(max(c[i] for c in corners) - min(c[i] for c in corners) for i in range(3))


def control_radius(section, size):
    """Ring size: just around the part's cross-section, capped by the model size, never vanishingly small."""
    if size <= 0:
        return 10.0
    wanted = RING_MARGIN * section if section > 0 else MODEL_SHARE * size
    return max(min(wanted, MODEL_SHARE * size), MIN_SHARE * size)


def style(controller, kind, radius):
    """Shape, orientation, size and colour of the controller."""
    # the USD importer gives its Nulls a ZYX order, where the first rotation field turns about X, not the axis
    controller[c4d.ID_BASEOBJECT_ROTATION_ORDER] = c4d.ROTATIONORDER_HPB
    controller[c4d.NULLOBJECT_DISPLAY] = SHAPES[kind]
    controller[c4d.NULLOBJECT_ORIENTATION] = c4d.NULLOBJECT_ORIENTATION_XZ  # perpendicular to the joint axis (Y)
    controller[c4d.NULLOBJECT_RADIUS] = radius
    controller[c4d.ID_BASEOBJECT_USECOLOR] = c4d.ID_BASEOBJECT_USECOLOR_ALWAYS
    controller[c4d.ID_BASEOBJECT_COLOR] = CONTROL_COLOR


# Protection tag: one mode per vector (None / Lock / Limit), a check box per component saying whether the mode
# applies to it, and per-component Min/Max used by Limit (rotations in radians).
VECTOR_MODES = {"P": c4d.PROTECTION_P, "R": c4d.PROTECTION_R, "S": c4d.PROTECTION_S}
COMPONENTS = {
    "P": ((c4d.PROTECTION_P_X, c4d.PROTECTION_P_MIN_X, c4d.PROTECTION_P_MAX_X),
          (c4d.PROTECTION_P_Y, c4d.PROTECTION_P_MIN_Y, c4d.PROTECTION_P_MAX_Y),
          (c4d.PROTECTION_P_Z, c4d.PROTECTION_P_MIN_Z, c4d.PROTECTION_P_MAX_Z)),
    "R": ((c4d.PROTECTION_R_X, c4d.PROTECTION_R_MIN_X, c4d.PROTECTION_R_MAX_X),  # H
          (c4d.PROTECTION_R_Y, c4d.PROTECTION_R_MIN_Y, c4d.PROTECTION_R_MAX_Y),  # P
          (c4d.PROTECTION_R_Z, c4d.PROTECTION_R_MIN_Z, c4d.PROTECTION_R_MAX_Z)),  # B
    "S": ((c4d.PROTECTION_S_X, c4d.PROTECTION_S_MIN_X, c4d.PROTECTION_S_MAX_X),
          (c4d.PROTECTION_S_Y, c4d.PROTECTION_S_MIN_Y, c4d.PROTECTION_S_MAX_Y),
          (c4d.PROTECTION_S_Z, c4d.PROTECTION_S_MIN_Z, c4d.PROTECTION_S_MAX_Z)),
}
LOCKED, FREE = "locked", "free"


RADIAN_LIKE = 2 * math.pi + 1e-3


def angle_limits(limits, rest=0.0):
    """Revolute limits in radians for the Protection tag, measured from the saved pose (rest, in degrees).

    USD stores them in degrees, but some exporters write radians into the same attribute (the NVIDIA trash
    trolley: clamps 0..0.9425 = 0..54 deg, swivels 0..1.5708 = 0..90 deg). A range that never leaves +-2*pi is
    therefore read as radians: as degrees it would weld those parts in place, while a real joint that moves
    less than 6 degrees is rare and only becomes freer than intended.
    """
    lower, upper = limits
    if max(abs(lower), abs(upper)) > RADIAN_LIKE:
        lower, upper = math.radians(lower), math.radians(upper)
    offset = math.radians(rest or 0.0)
    return lower - offset, upper - offset


def slide_limits(limits, rest, unit_scale):
    """Prismatic limits in scene units, measured from the saved pose (rest, in stage units)."""
    return tuple((value - (rest or 0.0)) * unit_scale for value in limits)


REST_TOLERANCE = 1e-4


def holds_rest(limits):
    """True when the saved pose (0 on the controller) lies within limits.

    If it does not, the data contradict each other; a limit would snap the part away from where the model
    shows it as soon as the scene evaluates, so the channel is left free instead.
    """
    lower, upper = limits
    return lower - REST_TOLERANCE <= 0.0 <= upper + REST_TOLERANCE


def free_or_limited(limits):
    return limits if limits and holds_rest(limits) else FREE


def joint_rules(kind, limits, unit_scale, rest=None):
    """{vector: (rule for X/H, rule for Y/P, rule for Z/B)}; a rule is LOCKED, FREE or a (min, max) range.

    Revolute: turns with H only. Prismatic: slides along its Y only. Spherical: turns freely, stays in place.
    Ranges are relative to the saved pose, which is the controllers' zero.
    """
    lock3 = (LOCKED, LOCKED, LOCKED)
    if kind == REVOLUTE:
        turn = free_or_limited(angle_limits(limits, rest) if limits else None)
        return {"P": lock3, "R": (turn, LOCKED, LOCKED), "S": lock3}
    if kind == PRISMATIC:
        slide = free_or_limited(slide_limits(limits, rest, unit_scale) if limits else None)
        return {"P": (LOCKED, slide, LOCKED), "R": lock3, "S": lock3}
    return {"P": lock3, "R": (FREE, FREE, FREE), "S": lock3}


def apply_vector(tag, vector, rules, rest):
    """Set one vector of the tag: Lock when everything is locked, else Limit with locks as a zero-width range."""
    tag[VECTOR_MODES[vector]] = c4d.PROTECTION_LOCK if all(rule == LOCKED for rule in rules) else c4d.PROTECTION_LIMIT
    for (enabled_id, min_id, max_id), rule in zip(COMPONENTS[vector], rules):
        tag[enabled_id] = rule != FREE
        if rule not in (LOCKED, FREE):
            tag[min_id], tag[max_id] = rule
        elif rule == LOCKED:
            tag[min_id] = tag[max_id] = rest


def protect(controller, joint, unit_scale):
    """Protection tag: lock what the joint cannot do, limit (or free) what it can."""
    tag = controller.MakeTag(c4d.Tprotection)
    for vector, rules in joint_rules(joint["kind"], joint.get("limits"), unit_scale, joint.get("rest")).items():
        apply_vector(tag, vector, rules, 1.0 if vector == "S" else 0.0)
    return tag


def add_control(part, joint, up_axis):
    """Build offset + controller for one joint; returns the controller, or None when the joint has no axis."""
    direction = joint.get("direction")
    if not direction:
        return None
    world = frame_along(part.GetMg().off, to_c4d_direction(direction, up_axis))  # the part's axis is the anchor
    offset = make_null(part.GetName() + "_offset")
    offset[c4d.NULLOBJECT_DISPLAY] = c4d.NULLOBJECT_DISPLAY_NONE
    insert_above(part, offset, world)
    controller = controller_for(part, world)
    # SetMg may decompose the identity as H = 360 deg; a controller must read exactly 0 at rest
    controller.SetRelRot(c4d.Vector())
    return controller


def unique_parts(moving):
    """First joint per part: a body driven by two joints (rare, usually a closed loop) gets one control."""
    seen, unique = set(), []
    for part, joint in moving:
        if part.GetGUID() not in seen:
            seen.add(part.GetGUID())
            unique.append((part, joint))
    return unique


def build_controls(group, moving, up_axis, unit_scale):
    """Add controls for [(part, joint)] of moving joints; returns how many were built.

    Run after the unit bake: radii and prismatic limits are then in scene units (unit_scale converts the
    stage units of the limits). World positions of all geometry are unchanged.
    """
    built = [(add_control(part, joint, up_axis), joint) for part, joint in unique_parts(moving)
             if joint.get("kind") in CONTROLLED]
    built = [(controller, joint) for controller, joint in built if controller is not None]
    controller_ids, size = {controller.GetGUID() for controller, _ in built}, model_size(group)
    for controller, joint in built:
        section = cross_section(controller, own_meshes(controller, controller_ids))
        style(controller, joint["kind"], control_radius(section, size))
        protect(controller, joint, unit_scale)
    return len(built)


def controls_note(count):
    """Status text for the import summary, or '' when nothing moves."""
    if not count:
        return ""
    return "%d moving part%s with controls" % (count, "" if count == 1 else "s")
