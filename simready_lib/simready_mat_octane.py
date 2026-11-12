"""Octane backend: an Octane Material in Universal mode with Image Texture shaders (parametric, no node graph).

The Universal material has a slot for each UsdPreviewSurface input (albedo, metallic, roughness, normal,
opacity) and takes emission through a Texture emission shader. A packed map (ORM: roughness in G, metallic
in B) is read through Channel picker shaders, so each float slot gets exactly its channel.

Ids were read from OctaneRender for Cinema 4D 2027.1. Their labels are checked before anything is written,
so a version that moves them fails loudly (the dispatcher then falls back to a Standard material) instead of
writing into the wrong slots. Texture repeat comes from the texture tag (Octane follows its tiles), and
round edges from a Round edges shader the model's tag drives (simready_roundcorners).
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


def verify_ids(material):
    """Raise when a parameter id is missing or carries another label than expected."""
    description = material.GetDescription(c4d.DESCFLAGS_DESC_NONE)
    for param_id, label in EXPECTED_LABELS.items():
        container = description.GetParameter(c4d.DescID(c4d.DescLevel(param_id)))
        found = container[c4d.DESC_NAME] if container else None
        if found != label:
            raise RuntimeError("Octane parameter %d is '%s', expected '%s'" % (param_id, found, label))


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
    material[ALBEDO_COLOR] = c4d.Vector(*sp.as_rgb(entry["value"]))


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
        color[RGB_COLOR] = c4d.Vector(*sp.as_rgb(entry["value"]))
        emission[EMISSION_TEXTURE] = color
    emission[EMISSION_SURFACE_BRIGHTNESS] = True
    emission[EMISSION_POWER] = float(entry["strength"])
    material[EMISSION_LINK] = emission


def add_round_edges(material):
    """A Round edges shader switched off; the model's Round corners tag sets mode and radius."""
    shader = _shader(material, ROUND_ID)
    shader[ROUND_MODE], shader[ROUND_RADIUS] = ROUND_OFF, 0.0
    material[ROUND_EDGES] = shader


APPLIERS = {sp.BASE_COLOR: _apply_base_color, sp.METALLIC: _apply_metallic, sp.ROUGHNESS: _apply_roughness,
            sp.NORMAL: _apply_normal, sp.EMISSION: _apply_emission, sp.OPACITY: _apply_opacity}


def build_material(name, slots, openpbr=False, round_corners=False):
    """Create an Octane Universal material named name from slots (simready_material_spec.slots).

    openpbr is ignored: this Octane build's material has no Standard Surface type. round_corners adds the
    Round edges shader, off until the model's tag turns it on.
    """
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
