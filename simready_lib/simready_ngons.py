"""Map USD face indices onto Cinema 4D polygons when the importer split n-gons.

Cinema 4D polygons have at most four corners. A USD face with five or more becomes several polygons of one
n-gon, so the object has more polygons than the USD mesh has faces (the NVIDIA warehouse office chair:
13 083 faces, 13 089 polygons). Material subsets, and the face-count check that pairs a polygon object
with its USD mesh, then point at the wrong polygons, and the model came in without materials.

The pieces of one n-gon follow each other in the polygon list and share one entry of the polygon
translation map, while ordinary polygons keep the USD order. So consecutive polygons with the same
translation entry are one USD face, which turns face ranges into polygon ranges. No Cinema 4D imports:
the functions only call methods of the mesh they get.
"""


def face_runs(translation):
    """[[polygon index, ...] per USD face] from a polygon translation map (polygon -> n-gon space index)."""
    runs = []
    for polygon, entry in enumerate(translation):
        if runs and translation[polygon - 1] == entry:
            runs[-1].append(polygon)
        else:
            runs.append([polygon])
    return runs


def to_ranges(indices):
    """Sorted indices compressed into inclusive [start, end] ranges (the inspector's format)."""
    ranges = []
    for index in sorted(indices):
        if ranges and index == ranges[-1][1] + 1:
            ranges[-1][1] = index
        else:
            ranges.append([index, index])
    return ranges


def remap_ranges(ranges, runs):
    """Face ranges -> the polygon ranges that make up those faces."""
    return to_ranges(polygon for start, end in ranges for face in range(start, end + 1) for polygon in runs[face])


def adapt_spec(mesh_spec, runs):
    """Copy of mesh_spec in polygon indices, or None when runs do not describe this USD mesh."""
    if len(runs) != mesh_spec["faces"]:
        return None
    subsets = [dict(subset, ranges=remap_ranges(subset["ranges"], runs)) for subset in mesh_spec["subsets"]]
    return dict(mesh_spec, faces=sum(len(run) for run in runs), subsets=subsets)


def matched_spec(mesh, mesh_spec):
    """mesh_spec as it applies to this polygon object: unchanged, remapped for split n-gons, or None."""
    count = mesh.GetPolygonCount()
    if count == mesh_spec["faces"]:
        return mesh_spec
    if count < mesh_spec["faces"] or not mesh.GetNgonCount():
        return None
    _, translation = mesh.GetPolygonTranslationMap()
    return adapt_spec(mesh_spec, face_runs(translation))
