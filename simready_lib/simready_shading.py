"""Phong normals of imported meshes.

The USD importer gives every mesh a Phong tag with the "Uniform" style, which averages the face normals
around a point without regard to face size: long thin triangles next to large faces bend the shading.
"Area Weighted" weights each face by its area, the usual best choice for CAD-like SimReady meshes.
"""
import c4d

import simready_cleanup

AREA_WEIGHTED = 2  # PHONGTAG_STYLE: 0 Uniform, 1 Angle, 2 Area, 3 Angle and Area, 4 Square Area Weighted


def area_weighted_phong(root):
    """Set every Phong tag below root to Area Weighted, adding one to meshes without; returns the meshes changed."""
    changed = 0
    for obj in simready_cleanup.iter_objects(root):
        if not obj.IsInstanceOf(c4d.Opolygon):
            continue
        tag = obj.GetTag(c4d.Tphong) or obj.MakeTag(c4d.Tphong)
        if tag[c4d.PHONGTAG_STYLE] != AREA_WEIGHTED:
            tag[c4d.PHONGTAG_STYLE] = AREA_WEIGHTED
            changed += 1
    return changed
