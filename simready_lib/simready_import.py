"""Import a local USD asset into the active Cinema 4D document.

Imports a local USD file, rebuilds its visual materials as Redshift materials and binds them to faces.
Run from Script Manager (Extensions > Script Manager) or call import_asset() from another script.
"""
import os
import sys

import c4d
from c4d import documents, gui, storage


def _script_dir():
    """Folder with the simready_*.py files; Script Manager may run scripts without __file__."""
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        pass
    for root in (c4d.C4D_PATH_LIBRARY_USER, c4d.C4D_PATH_PREFS):
        for folder, dirs, files in os.walk(os.path.join(c4d.storage.GeGetC4DPath(root), "scripts")):
            dirs[:] = [d for d in dirs if not d.startswith("_")]  # skip _backup copies of older modules
            if "simready_client.py" in files:
                return folder
    return None


_HERE = _script_dir()
if _HERE and _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import simready_axes
import simready_cleanup
import simready_colliders
import simready_hierarchy
import simready_material_spec
import simready_materials
import simready_render_target
import simready_layers
import simready_rig
import simready_roundcorners
import simready_shading
import simready_split
import simready_uvscale
import simready_xforms
import simready_runtime
import simready_settings

# SimReady assets are authored in meters; the scene scale is derived from the document unit.
ASSET_UNIT_IN_METERS = 1.0
LOAD_FLAGS = c4d.SCENEFILTER_OBJECTS | c4d.SCENEFILTER_MATERIALS
LOAD_ATTEMPTS = 4
RUNTIME_DIR = simready_settings.RUNTIME_DIR

_UNIT_NAMES_TO_METERS = (
    ("DOCUMENT_UNIT_KM", 1000.0),
    ("DOCUMENT_UNIT_M", 1.0),
    ("DOCUMENT_UNIT_CM", 0.01),
    ("DOCUMENT_UNIT_MM", 0.001),
)


def meters_per_doc_unit(doc):
    """Return how many meters one unit of the document represents."""
    scale, unit = doc[c4d.DOCUMENT_DOCUNIT].GetUnitScale()
    table = {getattr(c4d, name): meters for name, meters in _UNIT_NAMES_TO_METERS if hasattr(c4d, name)}
    # Unsupported units fall back to meters: keeping the authored size beats failing the import.
    return scale * table.get(unit, 1.0)


def pick_usd_file():
    """Ask the user for a USD file and return its path, or None if the dialog was cancelled."""
    return storage.LoadDialog(c4d.FILESELECTTYPE_ANYTHING, "Select USD asset", c4d.FILESELECT_LOAD)


def load_detached(path, attempts=LOAD_ATTEMPTS):
    """Load a USD file into a standalone document, leaving the active scene untouched until commit.

    Cinema 4D 2026.4 sometimes answers a repeated load of the same file with an empty document (no error,
    returned in a few milliseconds), which would import as an empty group, so an empty result is retried.
    Returns None when every attempt came back empty.
    """
    for _ in range(attempts):
        loaded = documents.LoadDocument(path, LOAD_FLAGS)
        if loaded is not None and loaded.GetFirstObject() is not None:
            return loaded
    return None


def detach_objects(src_doc):
    """Remove all top-level objects from src_doc and return them in their original order."""
    objects = []
    obj = src_doc.GetFirstObject()
    while obj:
        following = obj.GetNext()  # Remove() breaks the sibling link, so read it first
        obj.Remove()
        objects.append(obj)
        obj = following
    return objects


def detach_materials(src_doc):
    """Remove all materials from src_doc and return them."""
    materials = list(src_doc.GetMaterials())
    for mat in materials:
        mat.Remove()
    return materials


def build_group(name, objects):
    """Wrap objects in a Null so the whole asset can be moved or deleted as one unit."""
    group = c4d.BaseObject(c4d.Onull)
    group.SetName(name)
    for obj in objects:
        obj.InsertUnderLast(group)
    return group


def bake_scale(group, scale):
    """Convert the asset from meters to document units inside the geometry, so the group keeps scale 1.

    Offsets and points are multiplied; rotations and local scales are left alone, which is exact for a
    uniform factor. A scaled group Null would instead show 100 in S.X/Y/Z and distort anything the user
    parents to it or snaps to it.
    """
    if scale == 1.0:
        return
    for obj in simready_cleanup.iter_objects(group):
        obj.SetRelPos(obj.GetRelPos() * scale)
        if obj.IsInstanceOf(c4d.Opolygon):
            obj.SetAllPoints([point * scale for point in obj.GetAllPoints()])
            obj.Message(c4d.MSG_UPDATE)


def commit_to_doc(doc, group, materials, clean_tags=False, layer_name=None):
    """Insert the group and materials into doc as a single undoable step.

    clean_tags removes stale texture tags once the materials are in the document: a tag link only
    resolves for a material that already belongs to a document. layer_name puts the group, its objects and
    the materials on that asset layer under the common SimRCL layer (simready_layers).
    """
    doc.StartUndo()
    doc.InsertObject(group)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, group)
    for mat in materials:
        doc.InsertMaterial(mat)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, mat)
    if clean_tags:
        strip_stale_texture_tags(group, materials)
    if layer_name:
        layer, created = simready_layers.asset_layer(doc, layer_name)
        for new_layer in created:
            doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, new_layer)
        simready_layers.assign(layer, group, materials)
    doc.EndUndo()


def polygon_objects(group):
    """Return the polygon objects under group in depth-first order, matching the USD traversal order."""
    found = []
    stack = [group]
    while stack:
        obj = stack.pop()
        if obj.IsInstanceOf(c4d.Opolygon):
            found.append(obj)
        stack.extend(reversed(obj.GetChildren()))
    return found


def create_materials(spec, choice):
    """Build every material of spec for choice; returns ({name: material}, [distinct failure notes])."""
    materials, notes = {}, []
    for name, inputs in spec["materials"].items():
        materials[name], failures = simready_materials.build_material(name, inputs, choice)
        notes += [text for text in failures if text not in notes]
    return materials, notes


def build_visual_materials(group, spec, choice):
    """Create the visual materials of spec for the renderer in choice and bind them to the meshes under group.

    Returns (materials, notes). Meshes whose face count differs from the USD mesh are skipped,
    because face indices would then point at the wrong polygons.
    """
    materials, notes = create_materials(spec, choice)
    for mesh, mesh_spec in zip(polygon_objects(group), spec["meshes"]):
        if mesh.GetPolygonCount() != mesh_spec["faces"]:
            continue
        simready_materials.assign_materials(mesh, mesh_spec, materials)
    return list(materials.values()), notes


def texture_tags(group):
    """All texture (material) tags in the hierarchy under group."""
    tags, stack = [], [group]
    while stack:
        obj = stack.pop()
        tags.extend(tag for tag in obj.GetTags() if tag.GetType() == c4d.Ttexture)
        stack.extend(obj.GetChildren())
    return tags


def strip_stale_texture_tags(group, keep):
    """Remove texture tags that point at nothing or at materials other than keep.

    The USD importer leaves tags to its own placeholder materials behind; once those materials are
    detached such a tag shows up as an empty '?' entry next to the real one.
    """
    for tag in texture_tags(group):
        material = tag[c4d.TEXTURETAG_MATERIAL]
        if material is None or not any(material == kept for kept in keep):
            tag.Remove()


def tidy_group(group, spec):
    """Remove the importer's clutter, then nest the parts the way the model's joints say.

    The mesh index is taken first because it relies on the importer's traversal order, which the cleanup changes.
    Without a spec (materials skipped) the parts stay flat.
    """
    index = simready_hierarchy.mesh_index(polygon_objects(group), spec) if spec else {}
    counts = simready_cleanup.tidy_hierarchy(group)
    simready_axes.center_unset_axes(group)  # before the joints: "no own axis" is judged by the authored placement
    joints = (spec or {}).get("joints", [])
    resolve = simready_hierarchy.resolver(group, index, joints)
    simready_hierarchy.build_from_joints(group, joints, resolve)
    # the unit bake comes later, so the group is still in stage units and joint anchors map straight onto it
    moving = simready_axes.set_joint_pivots(group, joints, resolve, up_axis(spec))
    return counts, moving


def apply_uv_tiling(group, spec, materials):
    """Put each material's USD texture repeat on its texture tags (all renderers); returns how many tags carry it."""
    specs = (spec or {}).get("materials", {})
    scales = {m: simready_material_spec.material_uv_scale(specs[m.GetName()]) for m in materials if m.GetName() in specs}
    scales = {m: scale for m, scale in scales.items() if scale is not None}
    return simready_uvscale.set_auto_tiles(group, scales)


def untidy_counts(group):
    """Without the tidy-up only the axes are fixed; returns ((objects, objects), no moving parts)."""
    simready_axes.center_unset_axes(group)
    return 2 * (simready_cleanup.count_objects(group),), []


def up_axis(spec):
    """'Y' or 'Z': the up axis of the inspected stage (USD's default is Y)."""
    return (spec or {}).get("up_axis", "Y")


def inspect_safely(path):
    """Return (spec, warning). Free of Cinema 4D calls, so it may run in a worker thread.

    A failed external runtime degrades to a geometry-only import instead of aborting.
    """
    try:
        return simready_runtime.inspect_asset(path, RUNTIME_DIR), None
    except (simready_runtime.RuntimeSetupError, OSError, ValueError) as error:
        return None, "Materials were skipped: %s" % error


def join_warnings(*parts):
    """One status text from warnings, notes and lists of notes; None when there is nothing to say."""
    flat = [text for part in parts for text in (part if isinstance(part, list) else [part]) if text]
    return "; ".join(flat) or None


def add_model_controls(doc, group, tiled, kinds):
    """User data and tags on the group for texture repeat (when tiled) and round corners (when kinds)."""
    if tiled:
        simready_uvscale.add_controls(group)
    if kinds:
        simready_roundcorners.add_controls(group, kinds, simready_roundcorners.default_radius(meters_per_doc_unit(doc)))


def import_asset(doc, path, inspected=None, tidy=True, choice=None, rig=True, phong=True, split=True, layers=True,
                 round_corners=True):
    """Import the USD file at path into doc as one named group.

    inspected is an optional (spec, warning) pair from inspect_safely, computed earlier off the main
    thread. With tidy the importer's empty scopes, wrapper Nulls and prim tags are removed. choice
    (simready_render_target.Choice) says which renderer the materials are built for; by default the one
    of the document. With rig (needs tidy, which resolves the joints) every moving part gets a controller
    (simready_rig). phong sets every Phong tag to Area Weighted (simready_shading); split cuts a model that is
    one mesh with separate parts per material into one object per material (simready_split). Returns
    (group, warning, (objects_before, objects_after)); group is None if the file could not be loaded.
    layers puts the asset and its materials on a layer of their own. round_corners adds render-time rounded
    edges, off until switched on in the group's user data (simready_roundcorners).
    """
    src = load_detached(path)
    if src is None:
        return None, None, None
    spec, warning = inspected or inspect_safely(path)
    choice = (choice or simready_render_target.resolve(simready_render_target.AUTO, True, doc))._replace(
        round_corners=round_corners)
    # before anything is moved or renamed: paths still match the prims, and parts sit where USD puts them
    repaired = simready_xforms.repair_transforms(src, (spec or {}).get("xforms", {}), up_axis(spec))
    importer_materials = detach_materials(src)
    group = build_group(os.path.splitext(os.path.basename(path))[0], detach_objects(src))
    visual, notes = build_visual_materials(group, spec, choice) if spec else ([], [])
    # before the clean-up: split pieces clone their texture tag and so inherit the tiling
    tiled = apply_uv_tiling(group, spec, visual)
    kinds = simready_roundcorners.mark(visual) if round_corners else set()
    # Cleaning runs after the materials are bound: they are matched to meshes by the importer's traversal order.
    counts, moving = tidy_group(group, spec) if tidy else untidy_counts(group)
    colliders = simready_colliders.hidden_note(simready_colliders.hide_colliders(group))
    # a moving part is referenced by its joint; splitting it would leave the controls on a deleted mesh
    pieces = simready_split.split_single_mesh(group, visual) if split and visual and not moving else 0
    if phong:
        simready_shading.area_weighted_phong(group)
    scale = ASSET_UNIT_IN_METERS / meters_per_doc_unit(doc)
    bake_scale(group, scale)  # after the clean-up (fewer objects), before the controls (sized in scene units)
    controls = simready_rig.build_controls(group, moving, up_axis(spec), scale) if rig else 0
    add_model_controls(doc, group, tiled, kinds)
    # Importer materials are grey physics placeholders; keep them only when nothing better exists.
    commit_to_doc(doc, group, visual or importer_materials, clean_tags=bool(visual),
                  layer_name=group.GetName() if layers else None)
    fixes = "%d transforms corrected" % len(repaired) if repaired else ""
    split_note = "split into %d single-material objects" % pieces if pieces else ""
    rounding = simready_roundcorners.note(round_corners, kinds, bool(visual))
    return group, join_warnings(warning, choice.note, notes, fixes, split_note, colliders, rounding,
                                simready_rig.controls_note(controls)), counts


def main():
    """Script Manager entry point."""
    path = pick_usd_file()
    if not path:
        return
    group, warning, _ = import_asset(documents.GetActiveDocument(), path)
    if group is None:
        gui.MessageDialog("Could not load: " + path)
        return
    c4d.EventAdd()
    if warning:
        gui.MessageDialog(warning)


if __name__ == "__main__":
    main()
