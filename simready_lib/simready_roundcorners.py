"""Rounded edges at render time, switched on the model.

Every renderer that offers rounded edges does it differently, so the import prepares each material once and a
Python tag "SimRCL Round corners" on the group drives them from the same user data:
    Redshift  a Round Corners node, added on top of the normal map through a Bump Blender (additive)
    Arnold    a round_corners shader, which takes the normal map on its own normal input; it is wired into the
              shader only while on, because at radius 0 it still changes the normal map's shading
    V-Ray     the material's own Options > Round Edges parameters
    Octane    a Round edges shader in the material's Round edges slot, built switched off (mode Off)
    Standard  nothing: there is no such shader, so the model gets no controls
Redshift nodes are built with radius 0 (checked: pixel-identical to a material without the node), Arnold
nodes bypassed; the tag writes the radius and, for Arnold, the wiring.
Radius is in scene units (the user data shows it in the document's unit) for all four (Octane checked by render:
the rounding grows with the radius in scene units); Arnold's node is set to world space so a scaled object does not change it.
"""
import c4d
import maxon

import simready_tagcode as tagcode

# Private container ids on materials: which kind of rounding it carries and the settings last written.
KIND, STATE = 1063910, 1063911
VRAY, REDSHIFT, ARNOLD, OCTANE = 1, 2, 3, 4
VRAY_MATERIAL, OCTANE_MATERIALS = 1053286, (1029501, 1066802)  # Octane Universal and OpenPBR surface
RS_SPACE, AR_SPACE = "com.redshift3d.redshift4c4d.class.nodespace", "com.autodesk.arnold.nodespace"
RS_NODE, AR_NODE = "com.redshift3d.redshift4c4d.nodes.core.roundcorners", "com.autodesk.arnold.shader.round_corners"
# V-Ray Material > Options > Round Edges (ids are hashes of V-Ray's parameter names, checked in V-Ray 7).
VRAY_ON, VRAY_RADIUS, VRAY_SAME, VRAY_CORNERS = 1343838313, 9461143, 574351844, 1459651148
# Octane Material > Round edges link, and its Round edges shader (OctaneRender for Cinema 4D 2027.1).
OCTANE_ROUND, OCTANE_MODE, OCTANE_RADIUS, OCTANE_OTHERS, OCTANE_FAST = 1053013, 2603, 2600, 2605, 1
CORNERS = ("Convex and Concave", "Convex Only", "Concave Only")
DEFAULT_RADIUS_M = 0.001  # 0.1 cm
SLIDER_SPAN = 20  # the slider reaches 20 x the default radius (2 cm); larger values can be typed
TAG_NAME = "SimRCL Round corners"
OLD_TAG_NAMES = ("SimRS Round corners",)  # before the rename to SimRCL
ICON_FILE = "simrs_round_corners.png"
LABELS = {"on": "Round corners", "radius": "Radius", "same": "Same object only", "corners": "Corners (V-Ray)"}


def _has_node(material, space, asset):
    reference = material.GetNodeMaterialReference()
    if reference is None or not reference.HasSpace(maxon.Id(space)):
        return False
    found = []
    reference.GetGraph(maxon.Id(space)).GetViewRoot().GetInnerNodes(
        maxon.NODE_KIND.NODE, False,
        lambda node: (asset in str(node.GetValue("net.maxon.node.attribute.assetid")) and found.append(node)) or True)
    return bool(found)


def octane_round(material):
    """The Round edges shader of an Octane material (Universal links it to a slot, OpenPBR to a pin)."""
    shader = material.GetFirstShader()
    while shader is not None and shader.GetType() != OCTANE_ROUND:
        shader = shader.GetNext()
    return shader


def kind_of(material):
    """VRAY, REDSHIFT, ARNOLD or OCTANE when the material can round its edges, else None."""
    if material.GetType() == VRAY_MATERIAL:
        return VRAY
    if material.GetType() in OCTANE_MATERIALS:
        return OCTANE if octane_round(material) is not None else None
    if _has_node(material, RS_SPACE, RS_NODE):
        return REDSHIFT
    if _has_node(material, AR_SPACE, AR_NODE):
        return ARNOLD
    return None


def mark(materials):
    """Tag every material that can round its edges with its kind; returns the kinds found."""
    kinds = set()
    for material in materials:
        kind = kind_of(material)
        if kind is None:
            continue
        material.GetDataInstance().SetInt32(KIND, kind)
        kinds.add(kind)
    return kinds


def default_radius(meters_per_unit):
    """0.1 cm in the document's units (a document may use 1 unit = 10 cm)."""
    return DEFAULT_RADIUS_M / meters_per_unit


FEATURE_CODE = '''"""SimRCL: rounds the edges of the model's materials at render time.

Redshift and Arnold through their round corners nodes, V-Ray through the material's Round Edges options,
Octane through the Round edges shader in the material. The
materials are edited from message() on the main thread only, and only when the settings differ from those last
written (kept in each material's container), because node graphs must not change inside scene evaluation.
"""
import c4d
import maxon

KIND, STATE = __KIND__, __STATE__
VRAY, REDSHIFT, ARNOLD, OCTANE = __VRAY__, __REDSHIFT__, __ARNOLD__, __OCTANE__
ON, RADIUS, SAME, CORNERS = __ON__, __RADIUS__, __SAME__, __CORNERS__
VRAY_ON, VRAY_RADIUS, VRAY_SAME, VRAY_CORNERS = __VRAY_ON__, __VRAY_RADIUS__, __VRAY_SAME__, __VRAY_CORNERS__
OCTANE_ROUND, OCTANE_MODE, OCTANE_RADIUS, OCTANE_OTHERS, OCTANE_FAST = (
    __OCTANE_ROUND__, __OCTANE_MODE__, __OCTANE_RADIUS__, __OCTANE_OTHERS__, __OCTANE_FAST__)
NODES = {REDSHIFT: ("__RS_SPACE__", "__RS_NODE__", "radius", "sameobjectonly"),
         ARNOLD: ("__AR_SPACE__", "__AR_NODE__", "radius", "self_only")}
# Arnold shader node -> its normal input; the round node is wired into it only while rounding is on
ARNOLD_SHADERS = {"shader.standard_surface": "normal", "shader.openpbr_surface": "geometry_normal"}


def settings(root):
    """(on, radius, same object only, corners); corners is 0 for models without V-Ray materials."""
    corners = root[c4d.ID_USERDATA, CORNERS] if CORNERS else 0
    return root[c4d.ID_USERDATA, ON], root[c4d.ID_USERDATA, RADIUS], root[c4d.ID_USERDATA, SAME], corners


def layout(values):
    hidden = not values[0]
    fields = {RADIUS: (hidden, "Radius"), SAME: (hidden, "Same object only")}
    if CORNERS:
        fields[CORNERS] = (hidden, "Corners (V-Ray)")
    return fields


def state_text(values):
    """What the materials should hold; an off model writes radius 0 whatever the slider says."""
    on, radius, same, corners = values
    return "%d %.6g %d %d" % (bool(on), radius if on else 0.0, bool(same), corners)


def materials(root):
    found, stack = [], [root]
    while stack:
        obj = stack.pop()
        stack.extend(obj.GetChildren())
        for tag in obj.GetTags():
            material = tag[c4d.TEXTURETAG_MATERIAL] if tag.GetType() == c4d.Ttexture else None
            if material is not None and material.GetDataInstance().GetInt32(KIND) and material not in found:
                found.append(material)
    return found


def stale_materials(root):
    text = state_text(settings(root))
    return [material for material in materials(root) if material.GetDataInstance().GetString(STATE) != text]


def port(node, name, outputs=False):
    for child in (node.GetOutputs() if outputs else node.GetInputs()).GetChildren():
        if str(child.GetId()).split("|")[-1].split(".")[-1] == name:
            return child
    return None


def nodes_of(graph, fragment):
    found = []
    graph.GetViewRoot().GetInnerNodes(maxon.NODE_KIND.NODE, False, lambda node: (
        fragment in str(node.GetValue("net.maxon.node.attribute.assetid")) and found.append(node)) or True)
    return found


def route_arnold(graph, round_node, on):
    """Feed the shader's normal from the round node while on, else straight from the normal map (or nothing)."""
    normal_in = port(round_node, "normal").GetConnections(maxon.PORT_DIR.INPUT)
    source = port(round_node, "output", True) if on else (normal_in[0][0] if normal_in else None)
    for shader_id, port_name in ARNOLD_SHADERS.items():
        for shader in nodes_of(graph, shader_id):
            target = port(shader, port_name)
            target.RemoveConnections(maxon.PORT_DIR.INPUT, maxon.Wires.All())
            if source is not None:
                source.Connect(target)


def write_nodes(material, kind, values):
    space, asset, radius_port, same_port = NODES[kind]
    graph = material.GetNodeMaterialReference().GetGraph(maxon.Id(space))
    with graph.BeginTransaction() as transaction:
        for node in nodes_of(graph, asset):
            port(node, radius_port).SetPortValue(float(values[1]) if values[0] else 0.0)
            port(node, same_port).SetPortValue(bool(values[2]))
            if kind == ARNOLD:
                route_arnold(graph, node, bool(values[0]))
        transaction.Commit()


def write_vray(material, values):
    on, radius, same, corners = values
    material[VRAY_ON], material[VRAY_RADIUS], material[VRAY_SAME] = bool(on), float(radius), bool(same)
    material[VRAY_CORNERS] = corners


def write_octane(material, values):
    on, radius, same, _ = values
    # found among the material's shaders: Universal links it to a slot, OpenPBR to a pin
    shader = material.GetFirstShader()
    while shader is not None and shader.GetType() != OCTANE_ROUND:
        shader = shader.GetNext()
    if shader is None:
        return
    shader[OCTANE_MODE] = OCTANE_FAST if on else 0  # 0 is Off
    shader[OCTANE_RADIUS], shader[OCTANE_OTHERS] = float(radius), not same


WRITERS = {VRAY: write_vray, OCTANE: write_octane}


def evaluate(root):
    pass


def on_main_thread(root):
    values = settings(root)
    for material in stale_materials(root):
        kind = material.GetDataInstance().GetInt32(KIND)
        try:
            if kind in WRITERS:
                WRITERS[kind](material, values)
            else:
                write_nodes(material, kind, values)
        except Exception as error:  # a renamed node or port must not stop the other materials
            print("SimRCL Round corners: %s: %s" % (material.GetName(), error))
        # recorded even after a failure, so a broken material is not retried on every message
        material.GetDataInstance().SetString(STATE, state_text(values))
        material.Message(c4d.MSG_UPDATE)


def pending(root):
    return bool(stale_fields(root)) or bool(stale_materials(root))
'''


def tag_code(ids):
    """The Python tag source for the user data ids {'on', 'radius', 'same', 'corners'} (corners may be 0)."""
    values = dict(KIND=KIND, STATE=STATE, VRAY=VRAY, REDSHIFT=REDSHIFT, ARNOLD=ARNOLD, OCTANE=OCTANE,
                  OCTANE_ROUND=OCTANE_ROUND, OCTANE_MODE=OCTANE_MODE, OCTANE_RADIUS=OCTANE_RADIUS,
                  OCTANE_OTHERS=OCTANE_OTHERS, OCTANE_FAST=OCTANE_FAST, VRAY_ON=VRAY_ON,
                  VRAY_RADIUS=VRAY_RADIUS, VRAY_SAME=VRAY_SAME, VRAY_CORNERS=VRAY_CORNERS, RS_SPACE=RS_SPACE,
                  RS_NODE=RS_NODE, AR_SPACE=AR_SPACE, AR_NODE=AR_NODE)
    values.update({key.upper(): number for key, number in ids.items()})
    return tagcode.compose(FEATURE_CODE, values)


def _add_fields(root, radius, with_corners):
    # created as the tag shows them while off, so they do not flash before its first message
    ids = {"on": root.AddUserData(tagcode.check(LABELS["on"])),
           "radius": root.AddUserData(tagcode.length(LABELS["radius"], radius * SLIDER_SPAN, True)),
           "same": root.AddUserData(tagcode.check(LABELS["same"], True))}
    if with_corners:
        ids["corners"] = root.AddUserData(tagcode.cycle(LABELS["corners"], CORNERS, True))
        root[ids["corners"]] = 0
    root[ids["on"]], root[ids["radius"]], root[ids["same"]] = False, radius, False
    return ids


def add_controls(root, kinds, radius):
    """User data (Round corners, Radius, Same object only, Corners for V-Ray) and the tag; returns the tag.

    kinds: the kinds mark() found under root; radius: the default radius in scene units.
    """
    tagcode.remove(root, set(LABELS.values()), (TAG_NAME,) + OLD_TAG_NAMES)
    ids = {key: did[1].id for key, did in _add_fields(root, radius, VRAY in kinds).items()}
    ids.setdefault("corners", 0)
    return tagcode.make_tag(root, TAG_NAME, ICON_FILE, tag_code(ids))


def note(requested, kinds, has_materials):
    """Status text when rounding was asked for but no material of this renderer supports it."""
    return "no round corners for this renderer" if requested and has_materials and not kinds else ""
