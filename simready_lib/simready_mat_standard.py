"""Standard backend: a classic Cinema 4D material (Color, Reflectance, Normal, Luminance, Transparency).

It is rendered by the Standard and Physical renderers and shown in the viewport. The classic material has no
metalness input, so metal is a second GGX reflection layer in the colour of the surface, masked by the metallic
map or its constant; a packed map is read through a Colorizer shader that picks one channel.
"""
import c4d

import simready_material_spec as sp

COLORIZER_ID = 1011112
COLORIZER_INPUT, COLORIZER_TEXTURE = 1001, 1002
COLORIZER_CHANNELS = (2005, 2006, 2007)  # Red, Green, Blue
DIELECTRIC_IOR = 1.5
LUMINANCE_SCALE = 0.2


def _bitmap_shader(tex):
    """A Bitmap shader for the texture file, linear for data maps and sRGB for colour; not inserted anywhere yet."""
    shader = c4d.BaseShader(c4d.Xbitmap)
    shader[c4d.BITMAPSHADER_FILENAME] = tex["file"]
    srgb = tex["color_space"] == "sRGB"
    shader[c4d.BITMAPSHADER_COLORPROFILE] = c4d.BITMAPSHADER_COLORPROFILE_SRGB if srgb else c4d.BITMAPSHADER_COLORPROFILE_LINEAR
    return shader


def _bitmap(material, tex):
    """A Bitmap shader owned by the material."""
    shader = _bitmap_shader(tex)
    material.InsertShader(shader)
    return shader


def _channel(material, tex):
    """A Colorizer that outputs one channel of the texture as a grey value."""
    bitmap = _bitmap_shader(tex)
    colorizer = c4d.BaseShader(COLORIZER_ID)
    colorizer[COLORIZER_INPUT] = COLORIZER_CHANNELS[sp.channel_index(tex)]
    colorizer[COLORIZER_TEXTURE] = bitmap
    colorizer.InsertShader(bitmap)
    material.InsertShader(colorizer)
    return colorizer


def _shader_for(material, tex):
    """The shader that carries a texture: the bitmap itself, or a channel picker for a packed map."""
    return _bitmap(material, tex) if sp.channel_index(tex) is None else _channel(material, tex)


def _color(material, entry):
    """Colour channel from the base colour (constant or texture)."""
    material[c4d.MATERIAL_USE_COLOR] = True
    if "texture" in entry:
        material[c4d.MATERIAL_COLOR_SHADER] = _shader_for(material, entry["texture"])
        return
    material[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(*sp.as_rgb(entry["value"]))


def _luminance(material, entry):
    """Luminance channel for emission; the strength is scaled because classic brightness is a percentage."""
    material[c4d.MATERIAL_USE_LUMINANCE] = True
    material[c4d.MATERIAL_LUMINANCE_BRIGHTNESS] = entry["strength"] * LUMINANCE_SCALE
    if "texture" in entry:
        material[c4d.MATERIAL_LUMINANCE_SHADER] = _shader_for(material, entry["texture"])
        return
    material[c4d.MATERIAL_LUMINANCE_COLOR] = c4d.Vector(*sp.as_rgb(entry["value"]))


def _normal(material, entry):
    """Normal channel from a tangent-space normal map."""
    if "texture" not in entry:
        return
    material[c4d.MATERIAL_USE_NORMAL] = True
    material[c4d.MATERIAL_NORMAL_SHADER] = _bitmap(material, entry["texture"])
    material[c4d.MATERIAL_NORMAL_SPACE] = c4d.MATERIAL_NORMAL_SPACE_TANGENT


def _opacity(material, entry):
    """Transparency channel: a constant opacity becomes the matching transparency brightness."""
    if "texture" in entry:
        return
    material[c4d.MATERIAL_USE_TRANSPARENCY] = True
    material[c4d.MATERIAL_TRANSPARENCY_BRIGHTNESS] = 1.0 - float(entry["value"])


def _new_layer(material, name):
    """Append a GGX reflection layer named name and return its parameter id prefix."""
    layer = material.AddReflectionLayer()
    layer.SetName(name)
    prefix = layer.GetDataID()
    material[prefix + c4d.REFLECTION_LAYER_MAIN_DISTRIBUTION] = c4d.REFLECTION_DISTRIBUTION_GGX
    return prefix


def _set_roughness(material, prefix, entry):
    """Roughness of a layer from a constant or a texture channel."""
    if entry is None:
        return
    if "texture" in entry:
        material[prefix + c4d.REFLECTION_LAYER_MAIN_SHADER_ROUGHNESS] = _shader_for(material, entry["texture"])
        return
    material[prefix + c4d.REFLECTION_LAYER_MAIN_VALUE_ROUGHNESS] = float(entry["value"])


def _dielectric_layer(material, slots):
    """The plastic-like layer: Fresnel dielectric with the roughness of the surface."""
    prefix = _new_layer(material, "Dielectric")
    material[prefix + c4d.REFLECTION_LAYER_FRESNEL_MODE] = c4d.REFLECTION_FRESNEL_DIELECTRIC
    material[prefix + c4d.REFLECTION_LAYER_FRESNEL_VALUE_IOR] = DIELECTRIC_IOR
    _set_roughness(material, prefix, slots.get(sp.ROUGHNESS))


def _metal_mask(material, prefix, entry):
    """Restrict the metal layer by the metallic map, or scale it by the constant."""
    if "texture" in entry:
        material[prefix + c4d.REFLECTION_LAYER_TRANS_TEXTURE] = _shader_for(material, entry["texture"])
        return
    material[prefix + c4d.REFLECTION_LAYER_TRANS_BRIGHTNESS] = float(entry["value"])


def _has_metal(entry):
    return entry is not None and ("texture" in entry or float(entry["value"]) > 0)


def _metal_layer(material, slots):
    """The metal layer: no Fresnel falloff, tinted by the base colour, masked by the metallic slot."""
    prefix = _new_layer(material, "Metal")
    material[prefix + c4d.REFLECTION_LAYER_FRESNEL_MODE] = c4d.REFLECTION_FRESNEL_NONE
    color = slots.get(sp.BASE_COLOR)
    if color and "texture" in color:
        material[prefix + c4d.REFLECTION_LAYER_COLOR_TEXTURE] = _shader_for(material, color["texture"])
    elif color:
        material[prefix + c4d.REFLECTION_LAYER_COLOR_COLOR] = c4d.Vector(*sp.as_rgb(color["value"]))
    _set_roughness(material, prefix, slots.get(sp.ROUGHNESS))
    _metal_mask(material, prefix, slots[sp.METALLIC])


def _reflectance(material, slots):
    """Replace the default specular layer by a dielectric layer and, for metals, a masked metal layer."""
    material[c4d.MATERIAL_USE_REFLECTION] = True
    material.RemoveReflectionAllLayers()
    _dielectric_layer(material, slots)
    if _has_metal(slots.get(sp.METALLIC)):
        _metal_layer(material, slots)


def build_material(name, slots, openpbr=False, round_corners=False):
    """Create a classic material named name from slots (simready_material_spec.slots).

    openpbr and round_corners are ignored: the classic material has neither.
    """
    material = c4d.BaseMaterial(c4d.Mmaterial)
    material.SetName(name)
    if sp.BASE_COLOR in slots:
        _color(material, slots[sp.BASE_COLOR])
    _reflectance(material, slots)
    for slot, apply in ((sp.NORMAL, _normal), (sp.EMISSION, _luminance), (sp.OPACITY, _opacity)):
        if slot in slots:
            apply(material, slots[slot])
    return material
