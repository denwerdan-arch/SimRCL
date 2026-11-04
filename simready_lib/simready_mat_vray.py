"""V-Ray backend: a V-Ray Material (parametric, not a node graph) with V-Ray Bitmap textures.

The parameter ids are hashes of V-Ray's parameter names. They are looked up by their expected label before
anything is written, so a V-Ray version that renames them fails loudly (the dispatcher then falls back to a
Standard material) instead of silently writing into the wrong slots.

V-Ray Bitmap has no per-channel output, so a channel of a packed map is read by multiplying the colour with
(0, 3, 0)-style weights: a colour plugged into a float slot is averaged, which leaves exactly that channel.
"""
import c4d

import simready_material_spec as sp

MATERIAL_ID = 1053286
BITMAP_ID = 1055619
BITMAP_FILE, BITMAP_TILING, BITMAP_TRANSFER, BITMAP_COLOR_MULT = 824467988, 296999407, 1023120141, 723411671
TILING_UDIM, TRANSFER_LINEAR, TRANSFER_SRGB = 3, 0, 2
BUMP_NORMAL_TANGENT = 1
MODE, MODE_VRAY, MODE_OPENPBR = 1211305978, 0, 1  # the V-Ray Material switches its shading model with this cycle
CHANNEL_WEIGHTS = ((3, 0, 0), (0, 3, 0), (0, 0, 3))

# slot -> (parameter id, expected label), with the id of the matching texture link where there is one.
DIFFUSE_COLOR, DIFFUSE_TEXTURE = 2131196938, 605015197
GLOSSINESS, GLOSSINESS_TEXTURE, USE_ROUGHNESS = 451657623, 1991442305, 1975159604
METALNESS, METALNESS_TEXTURE = 960290471, 1250581027
BUMP_MAP, BUMP_TYPE, BUMP_AMOUNT = 1668198367, 1323892867, 959928724
OPACITY_COLOR, OPACITY_TEXTURE = 1751720365, 1547479758
SELF_COLOR, SELF_BRIGHTNESS, SELF_TEXTURE = 786462466, 893457058, 1761564596
EXPECTED_LABELS = {DIFFUSE_COLOR: "Color", DIFFUSE_TEXTURE: "Texture", GLOSSINESS: "Glossiness",
                   GLOSSINESS_TEXTURE: "Texture", USE_ROUGHNESS: "Use Roughness", METALNESS: "Metalness",
                   METALNESS_TEXTURE: "Texture", BUMP_MAP: "Bump Map", BUMP_TYPE: "Bump Type",
                   BUMP_AMOUNT: "Bump Amount", OPACITY_COLOR: "Color", OPACITY_TEXTURE: "Texture",
                   SELF_COLOR: "Color", SELF_BRIGHTNESS: "Brightness", SELF_TEXTURE: "Texture", MODE: "Mode"}


def has_openpbr():
    """True when this V-Ray build offers the Open PBR mode of the V-Ray Material (V-Ray 7 and newer)."""
    material = c4d.BaseMaterial(MATERIAL_ID)
    if material is None:
        return False
    container = material.GetDescription(c4d.DESCFLAGS_DESC_NONE).GetParameter(c4d.DescID(c4d.DescLevel(MODE)))
    cycle = container.GetContainer(c4d.DESC_CYCLE) if container else None
    return bool(cycle) and cycle[MODE_OPENPBR] == "Open PBR"


def verify_ids(material):
    """Raise when a parameter id is missing or carries another label than expected."""
    description = material.GetDescription(c4d.DESCFLAGS_DESC_NONE)
    for param_id, label in EXPECTED_LABELS.items():
        container = description.GetParameter(c4d.DescID(c4d.DescLevel(param_id)))
        found = container[c4d.DESC_NAME] if container else None
        if found != label:
            raise RuntimeError("V-Ray parameter %d is '%s', expected '%s'" % (param_id, found, label))


def _bitmap(material, tex, weights=None):
    """A V-Ray Bitmap for the texture file; weights multiply the colour (see the module docstring)."""
    shader = c4d.BaseShader(BITMAP_ID)
    shader[BITMAP_FILE] = tex["file"]
    shader[BITMAP_TRANSFER] = TRANSFER_SRGB if tex["color_space"] == "sRGB" else TRANSFER_LINEAR
    if sp.has_udim(tex):
        shader[BITMAP_TILING] = TILING_UDIM
    if weights:
        shader[BITMAP_COLOR_MULT] = c4d.Vector(*weights)
    material.InsertShader(shader)
    return shader


def _scalar_shader(material, tex):
    """A bitmap that yields one channel of the texture when read as a float."""
    index = sp.channel_index(tex)
    return _bitmap(material, tex, None if index is None else CHANNEL_WEIGHTS[index])


def _set_color(material, entry, color_id, texture_id):
    """Set a colour parameter from a constant or link a bitmap texture to its texture slot."""
    if "texture" in entry:
        material[texture_id] = _bitmap(material, entry["texture"])
        return
    material[color_id] = c4d.Vector(*sp.as_rgb(entry["value"]))


def _set_scalar(material, entry, value_id, texture_id):
    """Set a float parameter from a constant or link a channel bitmap to its texture slot."""
    if "texture" in entry:
        material[texture_id] = _scalar_shader(material, entry["texture"])
        return
    material[value_id] = float(entry["value"])


def _apply_base_color(material, entry):
    _set_color(material, entry, DIFFUSE_COLOR, DIFFUSE_TEXTURE)


def _apply_metallic(material, entry):
    _set_scalar(material, entry, METALNESS, METALNESS_TEXTURE)


def _apply_roughness(material, entry):
    material[USE_ROUGHNESS] = True  # the glossiness parameter then holds roughness
    _set_scalar(material, entry, GLOSSINESS, GLOSSINESS_TEXTURE)


def _apply_normal(material, entry):
    if "texture" not in entry:
        return
    material[BUMP_MAP] = _bitmap(material, entry["texture"])
    material[BUMP_TYPE] = BUMP_NORMAL_TANGENT
    material[BUMP_AMOUNT] = 1.0


def _apply_emission(material, entry):
    material[SELF_BRIGHTNESS] = entry["strength"]
    _set_color(material, entry, SELF_COLOR, SELF_TEXTURE)


def _apply_opacity(material, entry):
    value = entry.get("value")
    if value is not None:
        material[OPACITY_COLOR] = c4d.Vector(*sp.as_rgb(value))
        return
    material[OPACITY_TEXTURE] = _scalar_shader(material, entry["texture"])


APPLIERS = {sp.BASE_COLOR: _apply_base_color, sp.METALLIC: _apply_metallic, sp.ROUGHNESS: _apply_roughness,
            sp.NORMAL: _apply_normal, sp.EMISSION: _apply_emission, sp.OPACITY: _apply_opacity}


def build_material(name, slots, openpbr=False, round_corners=False):
    """Create a V-Ray material named name from slots (simready_material_spec.slots); openpbr selects the Open PBR mode.

    The Open PBR mode reads the same parameters (colour, metalness, roughness, self-illumination), so only the
    mode switch differs. round_corners needs nothing here: the material has Round Edges options of its own,
    which the model's tag drives (simready_roundcorners).
    """
    material = c4d.BaseMaterial(MATERIAL_ID)
    material.SetName(name)
    verify_ids(material)
    material[MODE] = MODE_OPENPBR if openpbr else MODE_VRAY
    for slot, entry in slots.items():
        APPLIERS[slot](material, entry)
    return material
