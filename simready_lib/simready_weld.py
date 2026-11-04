"""Weld meshes that arrive as loose triangles, so they shade smoothly and edit as one surface.

Some SimReady assets were converted from STL (Menlo's Asimov humanoid: every mesh is named
"node_STL_BINARY_"). STL stores each triangle with its own three corners, so the USD mesh has as many points
as polygon corners and no two polygons share an edge: Phong smoothing has nothing to work across and every
cylinder renders faceted, selections stop at each triangle. Welding the coincident points (Optimize, points
only, a tolerance far below the model's detail) restores the surface. Polygons, UVs, vertex colours, polygon
selections and material tags are per polygon and survive unchanged.

Only meshes where a large share of points sits on another point are welded; an ordinary mesh with a few
deliberate seams (UV borders, hard edges kept as split points) is left as authored.
"""
import c4d
from c4d import utils

import simready_split

DUPLICATE_SHARE = 0.3  # weld when at least this share of the points are duplicates
TOLERANCE_SHARE = 1e-6  # tolerance as a share of the mesh's bounding-box diagonal
MIN_TOLERANCE = 1e-7


def tolerance(diagonal):
    """Weld distance for a mesh with this bounding-box diagonal: far below any modelled detail."""
    return max(diagonal * TOLERANCE_SHARE, MIN_TOLERANCE)


def unique_count(points, tol):
    """How many distinct positions the points have on a grid of size tol."""
    return len({(round(p.x / tol), round(p.y / tol), round(p.z / tol)) for p in points})


def needs_weld(point_count, unique, share=DUPLICATE_SHARE):
    """True when at least share of the points are duplicates of another point."""
    return point_count > 0 and (point_count - unique) >= share * point_count


def _weld(mesh, tol):
    """Optimize with points only; True when Cinema 4D reported success."""
    settings = c4d.BaseContainer()
    settings[c4d.MDATA_OPTIMIZE_TOLERANCE] = tol
    settings[c4d.MDATA_OPTIMIZE_POINTS] = True
    settings[c4d.MDATA_OPTIMIZE_POLYGONS] = False
    settings[c4d.MDATA_OPTIMIZE_UNUSEDPOINTS] = True
    return bool(utils.SendModelingCommand(c4d.MCOMMAND_OPTIMIZE, [mesh], c4d.MODELINGCOMMANDMODE_ALL, settings, mesh.GetDocument()))


def weld_loose_meshes(group):
    """Weld every visible mesh under group that is mostly loose triangles; returns (meshes, points before, after)."""
    welded, before, after = 0, 0, 0
    for mesh in simready_split.visible_meshes(group):
        tol = tolerance(2 * mesh.GetRad().GetLength())
        count = mesh.GetPointCount()
        if not needs_weld(count, unique_count(mesh.GetAllPoints(), tol)) or not _weld(mesh, tol):
            continue
        welded, before, after = welded + 1, before + count, after + mesh.GetPointCount()
        mesh.Message(c4d.MSG_UPDATE)
    return welded, before, after


def note(result):
    """Status text such as 'welded 26 loose-triangle meshes (2 877 108 -> 473 914 points)', '' when none."""
    welded, before, after = result
    if not welded:
        return ""
    return "welded %d loose-triangle mesh%s (%s -> %s points)" % (
        welded, "" if welded == 1 else "es", "{:,}".format(before).replace(",", " "), "{:,}".format(after).replace(",", " "))
