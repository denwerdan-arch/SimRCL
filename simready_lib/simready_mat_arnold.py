"""Arnold backend: an Arnold node material with a Standard Surface or OpenPBR shader per USD material.

Arnold keeps its own node space; textures are `image` nodes, which expose r/g/b outputs (so a packed
ORM map needs no splitter) and offset, and expand <UDIM> tiles themselves; the repeat is on the texture tag.
"""
import c4d
import maxon

import simready_material_spec as sp

AR_SPACE = maxon.Id("com.autodesk.arnold.nodespace")
NODE = "com.autodesk.arnold."
MATERIAL = NODE + "material"
IMAGE = NODE + "shader.image"
NORMAL_MAP = NODE + "shader.normal_map"
ROUND = NODE + "shader.round_corners"
COLOR_SPACES = {"sRGB": "sRGB", "raw": "Raw"}
CHANNEL_PORTS = {"r": "r", "g": "g", "b": "b"}

# Shader description: node id, slot -> port, the slots whose port is a colour, and the emission gain port.
STANDARD = {"node": NODE + "shader.standard_surface",
            "ports": {sp.BASE_COLOR: "base_color", sp.METALLIC: "metalness", sp.ROUGHNESS: "specular_roughness",
                      sp.NORMAL: "normal", sp.EMISSION: "emission_color", sp.OPACITY: "opacity"},
            "colors": (sp.BASE_COLOR, sp.EMISSION, sp.OPACITY), "emission_gain": ("emission", 1.0)}
OPENPBR = {"node": NODE + "shader.openpbr_surface",
           "ports": {sp.BASE_COLOR: "base_color", sp.METALLIC: "base_metalness", sp.ROUGHNESS: "specular_roughness",
                     sp.NORMAL: "geometry_normal", sp.EMISSION: "emission_color", sp.OPACITY: "geometry_opacity"},
           "colors": (sp.BASE_COLOR, sp.EMISSION), "emission_gain": ("emission_luminance", 1.0)}


def _port(node, tree_name, name):
    """Return a port of node by its short name (Arnold ports are not prefixed with the node id)."""
    tree = node.GetInputs() if tree_name == "inputs" else node.GetOutputs()
    for child in tree.GetChildren():
        if str(child.GetId()).split("|")[-1].split(".")[-1] == name:
            return child
    raise KeyError("%s has no port %s" % (node.GetId(), name))


def _add_node(graph, asset_id):
    return graph.AddChild(maxon.Id(), maxon.Id(asset_id), maxon.DataDictionary())


def _image_node(graph, tex):
    """An image node that reads the texture file with the right colour space and tiling."""
    node = _add_node(graph, IMAGE)
    _port(node, "inputs", "filename").SetPortValue(maxon.Url(tex["file"]))
    _port(node, "inputs", "color_space").SetPortValue(COLOR_SPACES.get(tex["color_space"], "sRGB"))
    # the repeat goes on the texture tag like for every renderer (simready_uvscale); the offset stays here,
    # applied after the tag's tiling, which is the order of USD's st * scale + translation
    offset_s, offset_t = sp.uv_offset(tex)
    for name, value in (("soffset", offset_s), ("toffset", offset_t)):
        _port(node, "inputs", name).SetPortValue(value)
    return node


def _normal_output(graph, tex):
    """A normal map node fed by the image."""
    normal_map = _add_node(graph, NORMAL_MAP)
    _port(_image_node(graph, tex), "outputs", "output").Connect(_port(normal_map, "inputs", "input"))
    return _port(normal_map, "outputs", "output")


def _source(graph, slot, tex):
    """The output port of the texture network for a slot: one channel or the colour."""
    image = _image_node(graph, tex)
    channel = CHANNEL_PORTS.get(tex.get("channel"))
    return _port(image, "outputs", channel or "output")


def _value_for(model, slot, value):
    """A constant in the type of the port: a colour for colour slots, a float otherwise."""
    if slot in model["colors"]:
        return maxon.Color(*sp.as_rgb(value))
    return float(value)


def _add_round_corners(graph, normal_source):
    """round_corners at radius 0, fed by the normal map, its output left unconnected.

    The model's tag connects it to the shader only while rounding is on: unlike Redshift's node, Arnold's
    round_corners at radius 0 still changes how the normal map shades (checked on a normal-mapped sphere), so
    "off" must bypass it. World space, so the radius means the same as in Redshift and V-Ray.
    """
    node = _add_node(graph, ROUND)
    _port(node, "inputs", "radius").SetPortValue(0.0)
    _port(node, "inputs", "object_space").SetPortValue(False)
    if normal_source is not None:
        normal_source.Connect(_port(node, "inputs", "normal"))


def _wire_normal(graph, shader, model, entry, round_corners):
    """Connect the normal map to the shader's normal input; with round_corners also prepare the bypassed node."""
    texture = (entry or {}).get("texture")
    source = _normal_output(graph, texture) if texture else None
    if source is not None:
        source.Connect(_port(shader, "inputs", model["ports"][sp.NORMAL]))
    if round_corners:
        _add_round_corners(graph, source)


def _apply_slot(graph, shader, model, slot, entry):
    """Wire or set one slot; the normal is wired by _wire_normal."""
    if slot == sp.NORMAL:
        return
    target = _port(shader, "inputs", model["ports"][slot])
    if "texture" in entry:
        _source(graph, slot, entry["texture"]).Connect(target)
        return
    target.SetPortValue(_value_for(model, slot, entry["value"]))


def _switch_on_emission(shader, model, slots):
    if sp.EMISSION not in slots:
        return
    name, scale = model["emission_gain"]
    _port(shader, "inputs", name).SetPortValue(scale * sp.emission_strength(slots))


def build_material(name, slots, openpbr=False, round_corners=False):
    """Create an Arnold material named name from slots (simready_material_spec.slots).

    round_corners adds a round_corners shader at radius 0 for the model's controls (simready_roundcorners).
    """
    material = c4d.BaseMaterial(c4d.Mmaterial)
    material.SetName(name)
    reference = material.GetNodeMaterialReference()
    reference.CreateEmptyGraph(AR_SPACE)
    graph = reference.GetGraph(AR_SPACE)
    model = OPENPBR if openpbr else STANDARD
    with graph.BeginTransaction() as transaction:
        output = _add_node(graph, MATERIAL)
        shader = _add_node(graph, model["node"])
        _port(shader, "outputs", "output").Connect(_port(output, "inputs", "shader"))
        for slot, entry in slots.items():
            _apply_slot(graph, shader, model, slot, entry)
        _wire_normal(graph, shader, model, slots.get(sp.NORMAL), round_corners)
        _switch_on_emission(shader, model, slots)
        transaction.Commit()
    return material
