"""Split a single-mesh, multi-material model into one object per material.

Some assets arrive as one polygon object that carries several materials through polygon selections (the
NVIDIA adjustable desk: one mesh, top / frame / feet). One object per material is easier to select, hide and
re-shade. The split happens only when both hold:

- the visible model is that one mesh (an asset already made of parts is left as authored), and
- the polygons of different materials share no points, so every piece is a closed part of its own and the
  split cannot open seams in the surface (normals, subdivision).

Each piece keeps the mesh's UVs and other tags, gets the single material it uses and its axis at its centre.
"""
import c4d
from c4d import utils

import simready_axes
import simready_cleanup
import simready_colliders


def visible_meshes(group):
    """Polygon objects below group that render (collider groups are switched off and do not count)."""
    found = []
    for obj in simready_cleanup.iter_objects(group):
        if not obj.IsInstanceOf(c4d.Opolygon) or not obj.GetPolygonCount():
            continue
        if not any(simready_colliders.is_collider_name(p.GetName()) for p in _chain(obj, group)):
            found.append(obj)
    return found


def _chain(obj, group):
    while obj is not None and obj != group:
        yield obj
        obj = obj.GetUp()


def _selection(mesh, name):
    for tag in mesh.GetTags():
        if tag.GetType() == c4d.Tpolygonselection and tag.GetName() == name:
            return tag
    return None


def material_of_polygons(mesh, materials):
    """[material or None] per polygon, the way Cinema 4D layers texture tags (a later tag wins on its selection).

    Only tags of materials in materials count: the importer's placeholder tags are removed later anyway.
    """
    count = mesh.GetPolygonCount()
    owner = [None] * count
    for tag in mesh.GetTags():
        material = tag[c4d.TEXTURETAG_MATERIAL] if tag.GetType() == c4d.Ttexture else None
        if material is None or material not in materials:
            continue
        restriction = tag[c4d.TEXTURETAG_RESTRICTION] or ""
        if not restriction:
            owner = [material] * count
            continue
        selection = _selection(mesh, restriction)
        if selection is None:
            continue
        states = selection.GetBaseSelect().GetAll(count)
        owner = [material if selected else current for current, selected in zip(owner, states)]
    return owner


def regions(mesh, owner):
    """{material: [polygon index]} of the mesh."""
    found = {}
    for index, material in enumerate(owner):
        found.setdefault(material, []).append(index)
    return found


def _points_of(mesh, polygons):
    points = set()
    for index in polygons:
        poly = mesh.GetPolygon(index)
        points.update((poly.a, poly.b, poly.c, poly.d))
    return points


def separable(mesh, parts):
    """True when no point is used by polygons of two different materials."""
    seen = set()
    for polygons in parts.values():
        points = _points_of(mesh, polygons)
        if seen & points:
            return False
        seen |= points
    return True


def _piece(mesh, keep, material, texture_template):
    """Copy of mesh with only the polygons in keep, its unused points removed and one material tag."""
    piece = mesh.GetClone()
    drop = piece.GetPolygonS()
    drop.DeselectAll()
    keep_set = set(keep)
    for index in range(piece.GetPolygonCount()):
        if index not in keep_set:
            drop.Select(index)
    utils.SendModelingCommand(c4d.MCOMMAND_DELETE, [piece], c4d.MODELINGCOMMANDMODE_POLYGONSELECTION, c4d.BaseContainer())
    settings = c4d.BaseContainer()
    settings[c4d.MDATA_OPTIMIZE_POINTS] = False  # never weld: only drop the points no polygon uses any more
    settings[c4d.MDATA_OPTIMIZE_POLYGONS] = False
    settings[c4d.MDATA_OPTIMIZE_UNUSEDPOINTS] = True
    utils.SendModelingCommand(c4d.MCOMMAND_OPTIMIZE, [piece], c4d.MODELINGCOMMANDMODE_ALL, settings)
    for tag in [t for t in piece.GetTags() if t.GetType() == c4d.Ttexture]:
        tag.Remove()
    if material is not None:
        tag = texture_template.GetClone() if texture_template else c4d.BaseTag(c4d.Ttexture)
        tag[c4d.TEXTURETAG_MATERIAL] = material
        tag[c4d.TEXTURETAG_RESTRICTION] = ""
        piece.InsertTag(tag)
    piece.SetName("%s_%s" % (mesh.GetName(), material.GetName() if material else "unassigned"))
    piece.Message(c4d.MSG_UPDATE)
    return piece


def _template(mesh, material):
    """The mesh's texture tag of material (keeps its projection settings), or None."""
    return next((t for t in mesh.GetTags() if t.GetType() == c4d.Ttexture and t[c4d.TEXTURETAG_MATERIAL] == material), None)


def split_single_mesh(group, materials):
    """Split group's only mesh into one object per material when that is safe; returns the number of pieces (0: kept)."""
    meshes = visible_meshes(group)
    if len(meshes) != 1 or meshes[0].GetDown() is not None:
        return 0
    mesh = meshes[0]
    parts = regions(mesh, material_of_polygons(mesh, materials))
    if len(parts) < 2 or not separable(mesh, parts):
        return 0
    pieces = [_piece(mesh, polygons, material, _template(mesh, material)) for material, polygons in parts.items()]
    for piece in reversed(pieces):
        piece.InsertAfter(mesh)
        simready_axes.center_axis(piece)
    mesh.Remove()
    return len(pieces)
