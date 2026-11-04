"""One layer per imported asset, under a common "SimRCL" layer.

Assets bring many materials (an office chair five, a toolbox over ten); with a layer per asset the Material
and Object Managers can be filtered to one asset, and an asset can be hidden, locked or soloed as a whole.
Importing the same asset again reuses its layer.
"""
import zlib

import c4d
from c4d import documents

import simready_cleanup

PARENT_NAME = "SimRCL"
# a scene that already has the common layer under the old brand keeps using it, unrenamed
OLD_PARENT_NAMES = ("SimRS",)
PARENT_COLOR = c4d.Vector(1.0, 0.64, 0.0)  # the plugin's accent orange
# Distinct, readable layer colours; an asset always gets the same one (picked by a hash of its name).
PALETTE = [c4d.Vector(*rgb) for rgb in ((0.35, 0.65, 1.0), (0.45, 0.85, 0.45), (1.0, 0.45, 0.45), (0.85, 0.55, 1.0),
                                         (1.0, 0.8, 0.3), (0.3, 0.85, 0.85), (1.0, 0.55, 0.75), (0.7, 0.7, 0.4))]


def color_for(name):
    """Stable palette colour of a layer name (crc32 instead of hash(), which changes between sessions)."""
    return PALETTE[zlib.crc32(name.encode("utf-8")) % len(PALETTE)]


def _children(layer):
    child = layer.GetDown() if layer is not None else None
    while child:
        yield child
        child = child.GetNext()


def find_layer(doc, name, parent=None):
    """Layer called name directly under parent (None: the top level), or None."""
    container = parent if parent is not None else doc.GetLayerObjectRoot()
    return next((layer for layer in _children(container) if layer.GetName() == name), None)


def ensure_layer(doc, name, color, parent=None):
    """(layer, created): the existing layer called name under parent, or a new one inserted there."""
    found = find_layer(doc, name, parent)
    if found is not None:
        return found, False
    layer = documents.LayerObject()
    layer.SetName(name)
    layer[c4d.ID_LAYER_COLOR] = color
    if parent is not None:
        layer.InsertUnderLast(parent)
    else:
        layer.InsertUnderLast(doc.GetLayerObjectRoot())
    return layer, True


def common_layer(doc):
    """(layer, created): the common layer, an existing one under an old name first, else the SimRCL layer."""
    old = next((found for found in (find_layer(doc, name) for name in OLD_PARENT_NAMES) if found is not None), None)
    return (old, False) if old is not None else ensure_layer(doc, PARENT_NAME, PARENT_COLOR)


def asset_layer(doc, name):
    """(layer, newly created layers): the layer of asset name under the common SimRCL layer."""
    parent, parent_new = common_layer(doc)
    layer, layer_new = ensure_layer(doc, name, color_for(name), parent)
    return layer, [created for created, new in ((parent, parent_new), (layer, layer_new)) if new]


def assign(layer, group, materials):
    """Put group, everything below it and materials on layer; returns how many items were assigned."""
    items = [group] + list(simready_cleanup.iter_objects(group)) + list(materials)
    for item in items:
        item.SetLayerObject(layer)
    return len(items)


def materials_of(group):
    """Materials used by the texture tags below group (each once, in order of first use)."""
    found = []
    for obj in [group] + list(simready_cleanup.iter_objects(group)):
        for tag in obj.GetTags():
            material = tag[c4d.TEXTURETAG_MATERIAL] if tag.GetType() == c4d.Ttexture else None
            if material is not None and material not in found:
                found.append(material)
    return found
