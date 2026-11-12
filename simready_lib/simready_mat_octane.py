"""Octane backend: an Octane Material in Universal mode, or Octane's OpenPBR surface material, with Image
Texture shaders (parametric, no node graph).

The Universal material has a slot for each UsdPreviewSurface input (albedo, metallic, roughness, normal,
opacity) and takes emission through a Texture emission shader. The OpenPBR surface material keeps its inputs
as pins: values in one sub-container, linked shaders in another, both keyed by Octane's pin id. A packed map
(ORM: roughness in G, metallic in B) is read through Channel picker shaders, so each float input gets exactly
its channel.

Ids were read from OctaneRender for Cinema 4D 2027.1. Their labels are checked before anything is written,
so a version that moves them fails loudly (the dispatcher then falls back to Universal, then Standard)
instead of writing into the wrong slots. Texture repeat comes from the texture tag (Octane follows its
tiles), and round edges from a Round edges shader the model's tag drives (simready_roundcorners).
"""
import c4d

import simready_material_spec as sp

MATERIAL_ID, IMAGE_ID, PICKER_ID, RGB_ID, EMISSION_ID, ROUND_ID = 1029501, 1029508, 1056190, 1029504, 1029642, 1053013
TYPE, TYPE_UNIVERSAL = 2509, 2516
ALBEDO_COLOR, ALBEDO_TEXTURE = 2515, 2517
METALLIC, METALLIC_TEXTURE = 2613, 2587
ROUGHNESS, ROUGHNESS_TEXTURE = 2532, 2533
NORMAL_TEXTURE = 2542
OPACITY, OPACITY_TEXTURE = 2547, 2545
EMISSION_LINK, ROUND_EDGES = 2557, 2582
IMAGE_FILE, IMAGE_COLOR_SPACE, IMAGE_TYPE = 1100, 1118, 1105
SPACE_DATA, SPACE_SRGB = 0, 1
IMAGE_RGB, IMAGE_ALPHA = 0, 2
PICKER_INPUT, PICKER_CHANNEL = 1200, 1201
RGB_COLOR = 1200
EMISSION_TEXTURE, EMISSION_POWER, EMISSION_SURFACE_BRIGHTNESS = 2170, 2171, 2175
ROUND_MODE, ROUND_RADIUS, ROUND_OTHERS, ROUND_OFF = 2603, 2600, 2605, 0
EXPECTED_LABELS = {TYPE: "Material type", ALBEDO_COLOR: "Color", ALBEDO_TEXTURE: "Texture", METALLIC: "Float",
                   METALLIC_TEXTURE: "Texture", ROUGHNESS: "Float", ROUGHNESS_TEXTURE: "Texture",
                   NORMAL_TEXTURE: "Texture", OPACITY: "Float", OPACITY_TEXTURE: "Texture",
                   EMISSION_LINK: "Texture", ROUND_EDGES: "Round edges"}

OPENPBR_ID = 1066802
PIN_VALUES, PIN_LINKS = 1001, 1002
PBR_BASE_COLOR, PBR_METALNESS, PBR_ROUGHNESS, PBR_NORMAL, PBR_OPACITY = 10763, 10410, 10204, 10119, 10125
PBR_EMISSION_WEIGHT, PBR_EMISSION_COLOR, PBR_EMISSION_LUMINANCE, PBR_ROUND_EDGES = 10751, 10748, 12705, 10467
PBR_LABELS = {PBR_BASE_COLOR: "Base color", PBR_METALNESS: "Metalness", PBR_ROUGHNESS: "Specular roughness",
              PBR_NORMAL: "Normal", PBR_OPACITY: "Opacity", PBR_EMISSION_WEIGHT: "Emission weight",
              PBR_EMISSION_COLOR: "Emission color", PBR_EMISSION_LUMINANCE: "Emission luminance",
              PBR_ROUND_EDGES: "Round edges"}


def verify_ids(material):
    """Raise when a parameter id is missing or carries another label than expected."""
    description = material.GetDescription(c4d.DESCFLAGS_DESC_NONE)
    for param_id, label in EXPECTED_LABELS.items():
        container = description.GetParameter(c4d.DescID(c4d.DescLevel(param_id)))
        found = container[c4d.DESC_NAME] if container else None
        if found != label:
            raise RuntimeError("Octane parameter %d is '%s', expected '%s'" % (param_id, found, label))


def has_openpbr():
    """True when this Octane build registers the OpenPBR surface material."""
    return c4d.plugins.FindPlugin(OPENPBR_ID, c4d.PLUGINTYPE_MATERIAL) is not None


def pin_labels(material):
    """{pin id: label} of the material's linkable pins (OpenPBR keeps its inputs under PIN_LINKS)."""
    labels = {}
    for container, desc_id, _ in material.GetDescription(c4d.DESCFLAGS_DESC_NONE):
        if desc_id.GetDepth() >= 2 and desc_id[0].id == PIN_LINKS:
            labels[desc_id[1].id] = container[c4d.DESC_NAME]
    return labels


def verify_pins(material):
    """Raise when an OpenPBR pin is missing or carries another label than expected."""
    labels = pin_labels(material)
    for pin, label in PBR_LABELS.items():
        if labels.get(pin) != label:
            raise RuntimeError("Octane OpenPBR pin %d is '%s', expected '%s'" % (pin, labels.get(pin), label))


def _color(value):
    return c4d.Vector(*sp.as_rgb(value))


def _shader(material, kind):
    shader = c4d.BaseShader(kind)
    if shader is None:
        raise RuntimeError("Octane shader %d is not available" % kind)
    material.InsertShader(shader)
    return shader


def _image(material, tex, alpha=False):
    """An Image Texture for the file; colour textures in sRGB, data (normal, ORM) left linear."""
    shader = _shader(material, IMAGE_ID)
    shader[IMAGE_FILE] = tex["file"]
    shader[IMAGE_COLOR_SPACE] = SPACE_SRGB if tex.get("color_space") == "sRGB" else SPACE_DATA
    shader[IMAGE_TYPE] = IMAGE_ALPHA if alpha else IMAGE_RGB
    return shader


def _scalar(material, tex):
    """A float input for one channel of a texture: the alpha itself, or a Channel picker on R, G or B."""
    if tex.get("channel") == "a":
        return _image(material, tex, alpha=True)
    index = sp.channel_index(tex)
    image = _image(material, tex)
    if index is None:
        return image
    picker = _shader(material, PICKER_ID)
    picker[PICKER_INPUT], picker[PICKER_CHANNEL] = image, index
    return picker


def _apply_base_color(material, entry):
    if "texture" in entry:
        material[ALBEDO_TEXTURE] = _image(material, entry["texture"])
        return
    material[ALBEDO_COLOR] = _color(entry["value"])


def _set_scalar(material, entry, value_id, texture_id):
    if "texture" in entry:
        material[texture_id] = _scalar(material, entry["texture"])
        return
    material[value_id] = float(entry["value"])


def _apply_metallic(material, entry):
    _set_scalar(material, entry, METALLIC, METALLIC_TEXTURE)


def _apply_roughness(material, entry):
    _set_scalar(material, entry, ROUGHNESS, ROUGHNESS_TEXTURE)


def _apply_normal(material, entry):
    if "texture" in entry:
        material[NORMAL_TEXTURE] = _image(material, entry["texture"])


def _apply_opacity(material, entry):
    _set_scalar(material, entry, OPACITY, OPACITY_TEXTURE)


def _apply_emission(material, entry):
    """Texture emission with surface brightness: power then scales the texture's own brightness."""
    emission = _shader(material, EMISSION_ID)
    if "texture" in entry:
        emission[EMISSION_TEXTURE] = _image(material, entry["texture"])
    else:
        color = _shader(material, RGB_ID)
        color[RGB_COLOR] = _color(entry["value"])
        emission[EMISSION_TEXTURE] = color
    emission[EMISSION_SURFACE_BRIGHTNESS] = True
    emission[EMISSION_POWER] = float(entry["strength"])
    material[EMISSION_LINK] = emission


APPLIERS = {sp.BASE_COLOR: _apply_base_color, sp.METALLIC: _apply_metallic, sp.ROUGHNESS: _apply_roughness,
            sp.NORMAL: _apply_normal, sp.EMISSION: _apply_emission, sp.OPACITY: _apply_opacity}


def _round_edges_shader(material):
    """A Round edges shader switched off; the model's Round corners tag sets mode and radius."""
    shader = _shader(material, ROUND_ID)
    shader[ROUND_MODE], shader[ROUND_RADIUS] = ROUND_OFF, 0.0
    return shader


def add_round_edges(material):
    material[ROUND_EDGES] = _round_edges_shader(material)


def build_universal(name, slots, round_corners=False):
    """An Octane Material in Universal mode named name, from slots (simready_material_spec.slots)."""
    material = c4d.BaseMaterial(MATERIAL_ID)
    if material is None:
        raise RuntimeError("Octane Material is not available")
    material.SetName(name)
    verify_ids(material)
    material[TYPE] = TYPE_UNIVERSAL
    for slot, entry in slots.items():
        APPLIERS[slot](material, entry)
    if round_corners:
        add_round_edges(material)
    return material


# ---------------------------------------------------------------- OpenPBR surface material (pins)
# Each applier returns (container, pin, value) triples; _write_pins stores them in one pass per container.

def _pbr_input(material, entry, pin, colour=False):
    """A colour (sRGB image or RGB value) or float (one channel or value) input, as pin writes."""
    if "texture" in entry:
        texture = entry["texture"]
        return [(PIN_LINKS, pin, _image(material, texture) if colour else _scalar(material, texture))]
    return [(PIN_VALUES, pin, _color(entry["value"]) if colour else float(entry["value"]))]


def _pbr_normal(material, entry):
    return [(PIN_LINKS, PBR_NORMAL, _image(material, entry["texture"]))] if "texture" in entry else []


def _pbr_emission(material, entry):
    """Weight 1 switches the layer on; luminance carries the strength, as on Redshift's and Arnold's OpenPBR."""
    gain = [(PIN_VALUES, PBR_EMISSION_WEIGHT, 1.0), (PIN_VALUES, PBR_EMISSION_LUMINANCE, float(entry["strength"]))]
    return _pbr_input(material, entry, PBR_EMISSION_COLOR, colour=True) + gain


PBR_APPLIERS = {
    sp.BASE_COLOR: lambda material, entry: _pbr_input(material, entry, PBR_BASE_COLOR, colour=True),
    sp.METALLIC: lambda material, entry: _pbr_input(material, entry, PBR_METALNESS),
    sp.ROUGHNESS: lambda material, entry: _pbr_input(material, entry, PBR_ROUGHNESS),
    sp.OPACITY: lambda material, entry: _pbr_input(material, entry, PBR_OPACITY),
    sp.NORMAL: _pbr_normal, sp.EMISSION: _pbr_emission}


def _write_pins(material, writes):
    """Store values and shader links; the sub-containers are copies, so each is written back once."""
    data = material.GetDataInstance()
    for container_id in (PIN_VALUES, PIN_LINKS):
        container = data.GetContainer(container_id)
        for _, pin, value in (w for w in writes if w[0] == container_id):
            if container_id == PIN_LINKS:
                container.SetLink(pin, value)
            else:
                container[pin] = value
        data.SetContainer(container_id, container)


def build_openpbr(name, slots, round_corners=False):
    """An Octane OpenPBR surface material named name, from slots (simready_material_spec.slots)."""
    material = c4d.BaseMaterial(OPENPBR_ID)
    if material is None:
        raise RuntimeError("Octane OpenPBR surface material is not available")
    material.SetName(name)
    verify_pins(material)
    writes = [write for slot, entry in slots.items() for write in PBR_APPLIERS[slot](material, entry)]
    if round_corners:
        writes.append((PIN_LINKS, PBR_ROUND_EDGES, _round_edges_shader(material)))
    _write_pins(material, writes)
    return material


def build_material(name, slots, openpbr=False, round_corners=False):
    """Create an Octane material named name from slots: OpenPBR surface when openpbr, else Universal.

    round_corners adds the Round edges shader, off until the model's tag turns it on.
    """
    builder = build_openpbr if openpbr else build_universal
    return builder(name, slots, round_corners)
