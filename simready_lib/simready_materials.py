"""Build the visual materials of an imported SimReady asset and assign them to its meshes.

The native USD importer of Cinema 4D drops UsdPreviewSurface networks and GeomSubsets, so the
materials are rebuilt here from a simready_inspect description: one material per USD material, in the
format of the chosen renderer (see simready_render_target), bound through polygon selections that mirror
the GeomSubsets. Renderer specific work lives in the simready_mat_<renderer> modules.
"""
import importlib

import c4d

import simready_material_spec as spec_slots
import simready_render_target as targets

BACKENDS = {targets.REDSHIFT: "simready_mat_redshift", targets.ARNOLD: "simready_mat_arnold",
            targets.STANDARD: "simready_mat_standard", targets.VRAY: "simready_mat_vray",
            targets.OCTANE: "simready_mat_octane"}


def backend(target):
    """The module that builds materials for target; loaded on first use so a missing renderer costs nothing."""
    return importlib.import_module(BACKENDS[target])


def attempts(choice):
    """(target, openpbr) pairs to try in order: the choice, the same renderer without OpenPBR, then Standard."""
    steps = [(choice.target, choice.openpbr)]
    if choice.openpbr:
        steps.append((choice.target, False))
    if choice.target != targets.STANDARD:
        steps.append((targets.STANDARD, False))
    return steps


def build_material(name, spec, choice):
    """Create a material named name for the renderer in choice; returns (material, [failure texts]).

    Renderer node APIs fail in their own ways (a missing node, a port of another type), so any failure falls
    through to the next attempt: an imported model with a plainer material is better than none.
    """
    slots = spec_slots.slots(spec)
    failures = []
    for target, openpbr in attempts(choice):
        try:
            return backend(target).build_material(name, slots, openpbr, choice.round_corners), failures
        except Exception as error:  # noqa: BLE001 - see docstring
            failures.append("%s%s: %s" % (targets.LABELS[target], " OpenPBR" if openpbr else "", error))
    raise RuntimeError("; ".join(failures))


def make_selection_tag(mesh, name, ranges):
    """Add a polygon selection tag named name that covers the inclusive face ranges."""
    tag = mesh.MakeTag(c4d.Tpolygonselection)
    tag.SetName(name)
    selection = tag.GetBaseSelect()
    for start, end in ranges:
        for index in range(start, end + 1):  # SelectAll() takes a count, not a range
            selection.Select(index)
    return tag


def make_texture_tag(mesh, material, selection_name=None):
    """Assign material to mesh, optionally restricted to a named polygon selection."""
    tag = mesh.MakeTag(c4d.Ttexture)
    tag[c4d.TEXTURETAG_MATERIAL] = material
    tag[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_UVW
    if selection_name:
        tag[c4d.TEXTURETAG_RESTRICTION] = selection_name
    return tag


def covered_faces(mesh_spec):
    """Number of faces claimed by the material subsets of a mesh."""
    return sum(end - start + 1 for subset in mesh_spec["subsets"] for start, end in subset["ranges"])


def assign_materials(mesh, mesh_spec, materials):
    """Bind materials (dict name -> BaseMaterial) to mesh following the GeomSubsets of mesh_spec.

    MakeTag puts new tags in front, and the rightmost tag wins on overlap, so the mesh-level
    material is created last to end up at the back where it only fills faces without a subset.
    """
    for subset in mesh_spec["subsets"]:
        material = materials.get(subset["material"])
        if material is None:
            continue
        make_selection_tag(mesh, subset["material"], subset["ranges"])
        make_texture_tag(mesh, material, subset["material"])
    default = materials.get(mesh_spec["default_material"])
    if default and covered_faces(mesh_spec) < mesh_spec["faces"]:
        make_texture_tag(mesh, default)
