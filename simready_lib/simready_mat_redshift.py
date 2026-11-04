"""Redshift backend: one Redshift Standard or OpenPBR node material per USD material."""
import c4d
import maxon

import simready_material_spec as sp

RS_SPACE = maxon.NodeSpaceIdentifiers.RedshiftMaterial
CORE = "com.redshift3d.redshift4c4d.nodes.core."
OUTPUT = "com.redshift3d.redshift4c4d.node.output"
TEX = CORE + "texturesampler"
BUMP = CORE + "bumpmap"
SPLITTER = CORE + "rscolorsplitter"
ROUND = CORE + "roundcorners"
BLENDER = CORE + "bumpblender"

TANGENT_SPACE_NORMAL = 1
COLOR_SPACES = {"sRGB": "sRGB", "raw": "Raw"}
CHANNEL_PORTS = {"r": "outr", "g": "outg", "b": "outb", "a": "outa"}

# Shader description: node id, slot -> port, the slots whose port is a colour, the normal port and the emission gain port.
STANDARD = {"node": CORE + "standardmaterial",
            "ports": {sp.BASE_COLOR: "base_color", sp.METALLIC: "metalness", sp.ROUGHNESS: "refl_roughness",
                      sp.EMISSION: "emission_color", sp.OPACITY: "opacity_color"},
            "colors": (sp.BASE_COLOR, sp.EMISSION, sp.OPACITY),
            "normal": "bump_input", "emission_gain": ("emission_weight", 1.0)}
OPENPBR = {"node": CORE + "openpbrmaterial",
           "ports": {sp.BASE_COLOR: "base_color", sp.METALLIC: "base_metalness", sp.ROUGHNESS: "specular_roughness",
                     sp.EMISSION: "emission_color", sp.OPACITY: "geometry_opacity"},
           "colors": (sp.BASE_COLOR, sp.EMISSION),
           "normal": "geometry_normal", "emission_gain": ("emission_luminance", 1.0)}


def _port(node, tree_name, prefix, name):
    """Return a port of node by short name; tree_name is 'inputs' or 'outputs'."""
    tree = node.GetInputs() if tree_name == "inputs" else node.GetOutputs()
    return tree.FindChild(prefix + "." + name)


def _add_node(graph, asset_id):
    """Add a node by asset id inside an open transaction."""
    return graph.AddChild(maxon.Id(), maxon.Id(asset_id), maxon.DataDictionary())


def _find_node(graph, id_fragment):
    """Return the first node whose id contains id_fragment, or None."""
    found = []

    def visit(node):
        if id_fragment in str(node.GetId()):
            found.append(node)
        return True

    graph.GetViewRoot().GetInnerNodes(maxon.NODE_KIND.NODE, False, visit)
    return found[0] if found else None


def _standard_graph(material):
    """A Redshift Standard material graph; the default graph already wires the shader to the output."""
    reference = material.GetNodeMaterialReference()
    reference.CreateDefaultGraph(RS_SPACE)
    graph = reference.GetGraph(RS_SPACE)
    return graph, _find_node(graph, "standardmaterial")


def _openpbr_graph(material):
    """An empty Redshift graph with an OpenPBR shader wired to the output node."""
    reference = material.GetNodeMaterialReference()
    reference.CreateEmptyGraph(RS_SPACE)
    graph = reference.GetGraph(RS_SPACE)
    with graph.BeginTransaction() as transaction:
        output = _add_node(graph, OUTPUT)
        shader = _add_node(graph, OPENPBR["node"])
        _port(shader, "outputs", OPENPBR["node"], "outcolor").Connect(_port(output, "inputs", OUTPUT, "surface"))
        transaction.Commit()
    return graph, shader


def _configure_texture(node, tex):
    """Set file and colour space of a texture node.

    UV scale/offset are not applied: vec2 ports cannot be written from Python (no maxon.Vec2 type).
    """
    tex0 = _port(node, "inputs", TEX, "tex0")
    tex0.FindChild("path").SetPortValue(maxon.Url(tex["file"]))
    tex0.FindChild("colorspace").SetPortValue(COLOR_SPACES.get(tex["color_space"], "sRGB"))


def _texture_node(graph, tex):
    node = _add_node(graph, TEX)
    _configure_texture(node, tex)
    return node


def _colour_output(graph, tex):
    """The output port that carries a texture as colour."""
    return _port(_texture_node(graph, tex), "outputs", TEX, "outcolor")


def _scalar_output(graph, tex):
    """The output port that carries one channel of a texture, through a colour splitter."""
    split = _add_node(graph, SPLITTER)
    _colour_output(graph, tex).Connect(_port(split, "inputs", SPLITTER, "input"))
    return _port(split, "outputs", SPLITTER, CHANNEL_PORTS.get(tex["channel"], "outr"))


def _normal_output(graph, tex):
    """The output of a bump node that reads the texture as a tangent-space normal map."""
    bump = _add_node(graph, BUMP)
    _port(bump, "inputs", BUMP, "inputtype").SetPortValue(TANGENT_SPACE_NORMAL)
    _colour_output(graph, tex).Connect(_port(bump, "inputs", BUMP, "input"))
    return _port(bump, "outputs", BUMP, "out")


def _constant(value):
    """A shader value: colours arrive as lists, scalars as floats."""
    return maxon.ColorA(*sp.as_rgb(value), 1.0) if isinstance(value, list) else value


def _source(graph, slot, tex):
    """The output port of the texture network for a slot: one channel or the colour."""
    return _colour_output(graph, tex) if sp.channel_index(tex) is None else _scalar_output(graph, tex)


def _value_for(model, slot, value):
    """A constant in the type of the port: a colour for colour slots, a float otherwise."""
    if slot in model["colors"]:
        return maxon.ColorA(*sp.as_rgb(value), 1.0)
    return float(value)


def _round_corners_output(graph, normal_source):
    """Round Corners at radius 0 (the model's tag sets it), added on top of the normal map when there is one.

    The node has no input for an existing normal, so a Bump Blender in additive mode stacks the two.
    """
    round_node = _add_node(graph, ROUND)
    _port(round_node, "inputs", ROUND, "radius").SetPortValue(0.0)
    rounded = _port(round_node, "outputs", ROUND, "out")
    if normal_source is None:
        return rounded
    blender = _add_node(graph, BLENDER)
    _port(blender, "inputs", BLENDER, "additive").SetPortValue(True)
    _port(blender, "inputs", BLENDER, "bumpweight0").SetPortValue(1.0)
    normal_source.Connect(_port(blender, "inputs", BLENDER, "baseinput"))
    rounded.Connect(_port(blender, "inputs", BLENDER, "bumpinput0"))
    return _port(blender, "outputs", BLENDER, "outdisplacementvector")


def _wire_normal(graph, shader, model, entry, round_corners):
    """Connect the normal map and/or the round corners to the shader's normal input."""
    texture = (entry or {}).get("texture")
    source = _normal_output(graph, texture) if texture else None
    if round_corners:
        source = _round_corners_output(graph, source)
    if source is not None:
        source.Connect(_port(shader, "inputs", model["node"], model["normal"]))


def _apply_slot(graph, shader, model, slot, entry):
    """Wire or set one slot of the shader; slots the shader has no port for are skipped (normal: _wire_normal)."""
    port_name = model["ports"].get(slot)
    if port_name is None:
        return
    target = _port(shader, "inputs", model["node"], port_name)
    if "texture" in entry:
        _source(graph, slot, entry["texture"]).Connect(target)
        return
    target.SetPortValue(_value_for(model, slot, entry["value"]))


def _switch_on_emission(shader, model, slots):
    """Emission colours do nothing until the shader's emission gain is raised."""
    if sp.EMISSION not in slots:
        return
    name, scale = model["emission_gain"]
    _port(shader, "inputs", model["node"], name).SetPortValue(scale * sp.emission_strength(slots))


def build_material(name, slots, openpbr=False, round_corners=False):
    """Create a Redshift material named name from slots (simready_material_spec.slots).

    round_corners adds a Round Corners node at radius 0 for the model's controls (simready_roundcorners).
    """
    material = c4d.BaseMaterial(c4d.Mmaterial)
    material.SetName(name)
    model = OPENPBR if openpbr else STANDARD
    graph, shader = (_openpbr_graph if openpbr else _standard_graph)(material)
    with graph.BeginTransaction() as transaction:
        for slot, entry in slots.items():
            _apply_slot(graph, shader, model, slot, entry)
        _wire_normal(graph, shader, model, slots.get(sp.NORMAL), round_corners)
        _switch_on_emission(shader, model, slots)
        transaction.Commit()
    return material
